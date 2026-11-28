"""Server safety (audit 28/11/2026): held results, hidden runs, broken input, lifecycle."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from flywheel.console.chat import providers
from flywheel.console.paths import ConsolePaths
from flywheel.console.server import app, runner, withhold
from test_app import Srv

SEED = ConsolePaths(repo=Path(), fw_root=Path()).seed / "tasks.yaml"
SECRET = "SENTINEL-HELD"  # stands for a held result figure


def _serve(paths: ConsolePaths, **kw: Any) -> Iterator[Srv]:
    httpd = app.make_server(paths, 0, **kw)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield Srv(httpd, paths)
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def srv(fw: ConsolePaths) -> Iterator[Srv]:
    yield from _serve(fw, lock=True)


@pytest.fixture
def open_srv(fw: ConsolePaths) -> Iterator[Srv]:
    yield from _serve(fw)


def _index(ix: Path) -> None:
    """An index that still carries the held run's figures, as ``fw console index`` writes it."""
    (ix / "ds").mkdir(parents=True, exist_ok=True)
    story = {
        "pair": {
            "best": "C_70",
            "runs": [
                {"run": "C_70", "successes": 10, "n": 60},
                {"run": "C70_R1", "successes": 4, "n": 60, "note": SECRET},
            ],
            "comparisons": [{"variant": "C70_R1", "baseline": "C_70", "outcome": SECRET}],
        },
        "follow": {"runs": {"C70_R1": SECRET, "C_70": 2}, "r3": {"x": SECRET}},
        "round": {"chain": {"selected": 181}},
    }
    (ix / "story.json").write_text(json.dumps(story))
    tasks = {"rounds": [{"id": "tray-r1", "withhold_eval": ["C70_R1"], "runs": [{"id": "C_70"}]}]}
    (ix / "tasks.json").write_text(json.dumps(tasks))


# ---------------------------------------------------------------- P0: path variants
@pytest.mark.parametrize(
    "path",
    [
        "/data/story.json",
        "/data/story.json/",
        "/data/./story.json",
        "/data/ds/../story.json",
        "/data/%2e/story.json",
        "/data/ds/%2e%2e/story.json",
        "/data/%2E/story.json",
        "/data/story%2ejson",
        "/data/story.json%2f",
        "/data//story.json",
        "//data/story.json",
        "/data/ds//../story.json",
        "/data/story.json/.",
    ],
)
def test_path_variants_never_serve_the_raw_story(srv: Srv, path: str) -> None:
    _index(srv.paths.index)
    st, body = srv.get(path)
    assert SECRET.encode() not in body, (path, st)
    assert st in (200, 404)


@pytest.mark.parametrize("path", ["/data/tasks.json/", "/data/./tasks.json"])
def test_path_variants_never_serve_the_raw_tasks(srv: Srv, path: str) -> None:
    ix = srv.paths.index
    ix.mkdir(parents=True, exist_ok=True)
    doc = {"rounds": [{"id": "r", "runs": [{"id": "N"}], "withhold_runs": [{"id": "N"}]}]}
    (ix / "tasks.json").write_text(json.dumps(doc))
    st, body = srv.get(path)
    assert st == 200 and b"withhold_runs" not in body and b'"N"' not in body


# ---------------------------------------------------------------- P0: filter fails closed
@pytest.mark.parametrize("state", ["missing", "empty", "truncated", "list"])
def test_held_list_does_not_depend_on_the_index(srv: Srv, state: str) -> None:
    _index(srv.paths.index)
    f = srv.paths.index / "tasks.json"
    if state == "missing":
        f.unlink()
    elif state == "empty":
        f.write_text("")
    elif state == "truncated":
        f.write_text(f.read_text()[:20])
    else:
        f.write_text("[]")
    st, body = srv.get("/data/story.json")
    assert st == 200 and SECRET.encode() not in body
    st, body = srv.get("/api/status")
    assert st == 200 and b"C70_R1" not in body


@pytest.fixture(params=["missing", "empty", "truncated", "list"])
def broken_seed(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    d = tmp_path / "seed"
    d.mkdir()
    text = SEED.read_text(encoding="utf-8")
    state = str(request.param)
    if state != "missing":
        body = {"empty": "", "truncated": text[: len(text) // 2], "list": "[]"}[state]
        (d / "tasks.yaml").write_text(body, encoding="utf-8")
    monkeypatch.setattr(ConsolePaths, "seed", property(lambda self: d))
    return state


def test_unreadable_seed_refuses_instead_of_serving(
    broken_seed: str, fw: ConsolePaths, open_srv: Srv
) -> None:
    _index(fw.index)
    job = fw.fw_root / "tray/jig-n/da50-ft-n-s0"
    job.mkdir(parents=True)
    (job / "metrics.jsonl").write_text(json.dumps({"step": 9, "loss": 0.1}) + "\n")
    for path in ("/data/story.json", "/data/story.json/", "/data/tasks.json"):
        st, body = open_srv.get(path)
        assert st == 500 and SECRET.encode() not in body, path
    for path in ("/api/chat/traces", "/api/chat/traces/t1"):
        assert open_srv.get(path)[0] == 500, path
    st, body = open_srv.get("/api/status")
    stages = {s["id"]: s for s in json.loads(body)["stages"]}
    assert st == 200 and b"C70_R1" not in body and b"da50" not in body
    assert stages["eval"]["state"] == stages["loop"]["state"] == "blocked"
    assert stages["train"]["runs"] == []
    assert open_srv.get("/api/fs")[0] == 500


def test_withhold_matches_the_jig_filter_of_the_pages() -> None:
    """Same blocks as ``filterWithheldStory`` (web/core.js) for the jig round."""
    jig = {
        "runs": [{"branch": "M", "episodes": 5}],
        "evals": [
            {"run": "HELD", "role": "after_round", "status": "ready", "headline": {"s": 4}},
            {"run": "M", "role": "baseline", "status": "ready", "headline": {"s": 9}},
        ],
        "outcomes": [{"run": "HELD"}, {"run": "M"}],
        "rollouts": [{"run": "HELD"}],
        "conditions": [{"run": "HELD"}],
        "featured": "HELD",
        "paired": {"variant": "HELD", "baseline": "M", "delta": 3},
        "compare60": {"run": "HELD", "successes": 4},
    }
    out = withhold.story({"jig": jig}, {"HELD"})["jig"]
    assert out["evals"][0] == {"run": "HELD", "role": "after_round", "status": "withheld"}
    assert out["evals"][1] == jig["evals"][1]
    assert out["outcomes"] == [{"run": "M"}] and out["rollouts"] == out["conditions"] == []
    assert out["featured"] is None and out["paired"] is None and out["compare60"] is None
    assert out["runs"] == jig["runs"]  # the train entry stays, as for pair
    assert "rollouts" not in withhold.story({"jig": {"runs": []}}, {"HELD"})["jig"]


# ---------------------------------------------------------------- P0: hidden run folder names
HIDDEN_DIRS = [
    "tray/jig-n/da50-ft-n-s0",
    "tray/outcomes/jig-n-100000-r3",
    "tray/eval/jig-n-100000-r3/l1-000",
    "colab/da50-eval-n-20261128-033608",
    "analysis/da50-clean",
]
# folders a later job of the same run would write: not in the manifest, found by their prefix
LATER_HIDDEN_DIRS = [
    "tray/jig-n-60000-r3",
    "tray/eval/jig-n-60000-r3",
    "tray/outcomes/jig-n_old",
    "colab/jig-n.bak",
    "tray/da50-ft-n-s0-retry",
]


def test_fs_and_dir_check_skip_hidden_runs(
    open_srv: Srv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    shown = ["tray/jig-m", "tray/jig-new", "tray/outcomes/jig-m-100000-r3", "tray/eval"]
    shown += [".ssh/keys"]
    for rel in HIDDEN_DIRS + LATER_HIDDEN_DIRS + shown:
        (home / rel).mkdir(parents=True, exist_ok=True)
    (home / "tray" / "da50-demo.mp4").write_bytes(b"x")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    def listing(rel: str) -> tuple[int, str]:
        st, body = open_srv.get(f"/api/fs?path={home / rel}")
        return st, body.decode()

    for rel in ("", "tray", "tray/outcomes", "tray/eval", "colab", "analysis"):
        st, text = listing(rel)
        assert st == 200, rel
        for needle in ('jig-n"', "jig-n-", "jig-n_", "jig-n.", "da50", ".ssh"):
            assert needle not in text, (rel, needle)
    assert "jig-m" in listing("tray")[1] and "jig-new" in listing("tray")[1]  # not a prefix
    later = [*HIDDEN_DIRS, *LATER_HIDDEN_DIRS]
    for rel in [*later, "tray/jig-n", "tray/eval/jig-n-100000-r3", ".ssh"]:
        for api in ("fs", "dir_check"):
            st, body = open_srv.get(f"/api/{api}?path={home / rel}")
            assert st == 400 and b"l1-000" not in body, (api, rel)


def test_fs_allows_a_data_root_below_a_dot_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worktree lives under ``.claude/``: its own fwdata must stay browsable."""
    home = tmp_path / "home"
    root = home / ".claude" / "wt" / "fwdata"
    (root / "console" / "uploads" / "upload-1").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for s in _serve(ConsolePaths(repo=tmp_path, fw_root=root)):
        st, body = s.get(f"/api/fs?path={root / 'console' / 'uploads'}")
        assert st == 200 and b"upload-1" in body


# ---------------------------------------------------------------- load and lifecycle
def test_listen_backlog_holds_a_burst() -> None:
    assert app.ConsoleServer.request_queue_size == 128


def test_tunnel_gives_up_on_a_silent_connection() -> None:
    assert "ServerAliveInterval=15" in runner.Tunnel.CMD
    assert "ServerAliveCountMax=3" in runner.Tunnel.CMD
    assert runner.Tunnel.CMD[-1] == "rtx3060"


def test_status_and_kinds_are_cached_until_a_post(
    open_srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"status": 0, "kinds": 0}

    def status() -> dict[str, Any]:
        calls["status"] += 1
        return {"stages": []}

    def catalog(locked: bool) -> dict[str, Any]:
        calls["kinds"] += 1
        return {"kinds": []}

    monkeypatch.setattr(app.runner, "status", status)
    monkeypatch.setattr(app.kinds, "catalog", catalog)
    for _ in range(3):
        assert open_srv.get("/api/status")[0] == 200
        assert open_srv.get("/api/kinds")[0] == 200
    assert calls == {"status": 1, "kinds": 1}
    open_srv.post("/api/jobs/none/cancel", {})
    open_srv.get("/api/status")
    assert calls["status"] == 2


def test_sigterm_closes_the_tunnel(tmp_path: Path) -> None:
    code = (
        "import subprocess, sys\n"
        "from flywheel.console.paths import ConsolePaths\n"
        "from flywheel.console.server import app, runner\n"
        "runner.TUNNEL.proc = subprocess.Popen(['sleep', '60'], start_new_session=True)\n"
        "print(runner.TUNNEL.proc.pid, flush=True)\n"
        "app.serve(ConsolePaths.from_env(), port=0, lock=True)\n"
    )
    env = os.environ | {"FW_ROOT": str(tmp_path)}
    p = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, text=True)
    child = 0
    try:
        assert p.stdout is not None
        child = int(p.stdout.readline())
        assert p.stdout.readline().startswith("console on ")
        p.send_signal(signal.SIGTERM)
        assert p.wait(20) == 0
        try:
            state = Path(f"/proc/{child}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except OSError:
            state = "gone"
        assert state in ("gone", "Z", "X"), state
    finally:
        p.kill()
        if child:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass


# ---------------------------------------------------------------- broken input
def test_over_long_path_is_404(open_srv: Srv) -> None:
    for path in ("/" + "a" * 300, "/data/" + "a" * 300 + "/x", "/media/" + "a" * 300 + "/x"):
        assert open_srv.get(path)[0] == 404, path


def _raw_post(s: Srv, headers: str, body: bytes = b"") -> bytes:
    head = (
        f"POST /api/jobs HTTP/1.1\r\nHost: 127.0.0.1:{s.port}\r\n"
        f"Origin: http://127.0.0.1:{s.port}\r\n{headers}\r\n\r\n"
    )
    with socket.create_connection(("127.0.0.1", s.port), timeout=10) as c:
        c.sendall(head.encode() + body)
        out = b""
        while chunk := c.recv(4096):
            out += chunk
    return out


@pytest.mark.parametrize("length", ["-1", "abc", "1e3"])
def test_bad_content_length_is_400(open_srv: Srv, length: str) -> None:
    assert _raw_post(open_srv, f"Content-Length: {length}").startswith(b"HTTP/1.0 400")


def test_short_body_does_not_hold_the_thread(
    open_srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app, "BODY_TIMEOUT_S", 0.5)
    assert _raw_post(open_srv, "Content-Length: 50", b"{}").startswith(b"HTTP/1.0 400")


@pytest.mark.parametrize("body", [[1], "x", 3, None])
def test_body_that_is_not_an_object_is_400(open_srv: Srv, body: Any) -> None:
    st, out = open_srv.post("/api/jobs", body)
    assert st == 400 and "object" in out["error"]


def test_params_that_are_not_an_object_are_400(open_srv: Srv) -> None:
    st, out = open_srv.post("/api/jobs", {"kind": "data.qa", "params": [1]})
    assert st == 400 and "object" in out["error"]


@pytest.mark.parametrize(
    "story", ['{"pair": 5}', '{"pair": {"runs": [1, 2]}}', "[1]", '{"jig": {"evals": 5}}']
)
def test_story_of_the_wrong_shape(open_srv: Srv, story: str) -> None:
    ix = open_srv.paths.index
    ix.mkdir(parents=True, exist_ok=True)
    (ix / "story.json").write_text(story)
    st, body = open_srv.get("/api/status")
    assert st == 200 and len(json.loads(body)["stages"]) == 6
    assert open_srv.get("/data/story.json")[0] in (200, 500)


@pytest.mark.parametrize("exc", [BrokenPipeError, ConnectionResetError, TimeoutError])
def test_a_client_that_left_prints_nothing(
    open_srv: Srv, capsys: pytest.CaptureFixture[str], exc: type[OSError]
) -> None:
    try:
        raise exc()
    except exc:
        open_srv.httpd.handle_error(None, ("127.0.0.1", 1))
    assert capsys.readouterr().err == ""
    try:
        raise KeyError("a real bug")
    except KeyError:
        open_srv.httpd.handle_error(None, ("127.0.0.1", 1))
    assert "a real bug" in capsys.readouterr().err


def test_missing_qa_json_is_not_a_404(open_srv: Srv) -> None:
    ds = open_srv.paths.index / "ds" / "S70"
    ds.mkdir(parents=True)
    assert open_srv.get("/data/ds/S70/qa.json")[0] == 404  # no data at all
    (ds / "quality.json").write_text("{}")
    assert open_srv.get("/data/ds/S70/qa.json") == (204, b"")
    assert open_srv.get("/data/ds/NOPE/qa.json")[0] == 404
    (ds / "qa.json").write_text('{"a": 1}')
    assert open_srv.get("/data/ds/S70/qa.json")[0] == 200


# ---------------------------------------------------------------- readiness asks the model
class FakeModel(BaseHTTPRequestHandler):
    """An OpenAI-compatible server that knows one model id."""

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def reply(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        ids = ["text-embedding-3-small", "nano-banana-pro", "good", "vendor/other-chat"]
        self.reply(200, json.dumps({"data": [{"id": i} for i in ids]}).encode())

    def do_POST(self) -> None:
        got = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if got["model"] == "good":
            self.reply(200, b'data: {"choices": [{"delta": {"content": "ok"}}]}\n\n')
        elif got["model"] == "stream-error":
            self.reply(200, b'data: {"error": {"message": "no"}}\n\n')
        else:
            self.reply(404, b'{"error": {"message": "The model is not available."}}')


@pytest.fixture
def model_url() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _use_model(monkeypatch: pytest.MonkeyPatch, url: str, model: str) -> None:
    providers.reset_runtime_config()
    monkeypatch.setenv("FW_CHAT_BASE_URL", url)
    monkeypatch.setenv("FW_CHAT_MODEL", model)
    monkeypatch.setenv("FW_CHAT_SELF_HOSTED", "1")
    monkeypatch.delenv("FW_CHAT_KIND", raising=False)


@pytest.mark.parametrize(
    ("model", "ready"), [("good", True), ("no-such-model", False), ("stream-error", False)]
)
def test_ready_means_the_model_answered(
    open_srv: Srv, model_url: str, monkeypatch: pytest.MonkeyPatch, model: str, ready: bool
) -> None:
    _use_model(monkeypatch, model_url, model)
    st, out = open_srv.post("/api/models/prewarm", {})
    assert st == 200 and out["ok"] is ready
    info = json.loads(open_srv.get("/api/models")[1])
    assert info["chat"]["ready"] is ready
    assert info["nemotron"] == ("warm" if ready else "down")
    if not ready:
        assert out["error"] and info["chat"]["problem"] == out["error"]


def test_ready_is_false_when_nothing_listens(
    open_srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_model(monkeypatch, "http://127.0.0.1:9/v1", "good")
    assert open_srv.post("/api/models/prewarm", {})[1]["ok"] is False
    assert json.loads(open_srv.get("/api/models")[1])["chat"]["ready"] is False


def test_model_list_keeps_chat_models_only(
    open_srv: Srv, model_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_model(monkeypatch, model_url, "vendor/good")
    monkeypatch.setenv("FW_CHAT_API_KEY", "k")
    models = json.loads(open_srv.get("/api/chat/remote_models")[1])["models"]
    assert models == ["vendor/other-chat", "good"]  # the active model's namespace first
    found = json.loads(open_srv.get("/api/chat/remote_models?q=GOO")[1])["models"]
    assert found == ["good"]


def test_nothing_is_asked_while_the_chat_is_off(
    srv: Srv, model_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--lock`` without ``--chat``: no request leaves the console for the model server."""
    from flywheel.console.server import probe

    _use_model(monkeypatch, model_url, "good")
    monkeypatch.setenv("FW_CHAT_API_KEY", "k")

    def asked(*a: Any, **kw: Any) -> Any:
        raise AssertionError("the model server was asked")

    monkeypatch.setattr(probe, "_open", asked)
    info = json.loads(srv.get("/api/models")[1])
    assert info["chat"]["ready"] is False and info["chat"]["problem"] == "chat is off"
    assert json.loads(srv.get("/api/chat/remote_models")[1]) == {"models": []}


def test_a_nemotron_that_failed_to_load_stays_not_ready(
    open_srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel.console.chat import llm
    from flywheel.console.server import probe

    providers.reset_runtime_config()
    monkeypatch.delenv("FW_CHAT_BASE_URL", raising=False)
    monkeypatch.setattr(runner.TUNNEL, "tags", lambda fresh=False: [llm.MODEL])
    monkeypatch.setattr(llm, "nemotron_status", lambda: "cold")
    result: dict[str, Any] = {"ok": False, "nemotron": "cold", "error": "load failed"}
    monkeypatch.setattr(llm, "prewarm", lambda: dict(result))

    def ready() -> Any:
        return json.loads(open_srv.get("/api/models")[1])["chat"]["ready"]

    assert ready() is True  # tunnel up, model listed: not "needs an API key"
    assert open_srv.post("/api/models/prewarm", {})[1]["ok"] is False
    monkeypatch.setattr(probe, "TTL_FAIL_S", 0.0)
    assert ready() is False  # until a prewarm succeeds, however long that takes
    result.update(ok=True, error=None)
    assert open_srv.post("/api/models/prewarm", {})[1]["ok"] is True and ready() is True
