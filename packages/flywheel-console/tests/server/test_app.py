from __future__ import annotations

import http.client
import json
import sys
import threading
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from conftest import H, W, write_mp4
from flywheel.console.paths import ConsolePaths
from flywheel.console.server import app, media

ROWS = [
    {"id": "S70", "lerobot": "cut/S70"},
    {"id": "vwr", "ego_viewer": "viewer"},
]


class Srv:
    def __init__(self, httpd: app.ConsoleServer, paths: ConsolePaths) -> None:
        self.httpd = httpd
        self.paths = paths
        self.port = httpd.port

    def req(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            c.request(method, path, body=body, headers=headers or {})
            r = c.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            c.close()

    def get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
        st, _, b = self.req("GET", path, headers=headers)
        return st, b

    def post(
        self, path: str, obj: Any, origin: str | None = "self", host: str | None = None
    ) -> tuple[int, Any]:
        h = {"Content-Type": "application/json"}
        if origin == "self":
            origin = f"http://127.0.0.1:{self.port}"
        if origin:
            h["Origin"] = origin
        if host:
            h["Host"] = host
        st, _, b = self.req("POST", path, json.dumps(obj).encode(), h)
        return st, json.loads(b or b"null")


@pytest.fixture
def srv(
    fw: ConsolePaths, lerobot: Path, work: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Srv]:
    monkeypatch.setattr(media, "seed_rows", lambda: ROWS)
    write_mp4(fw.fw_root / "viewer" / "media" / "ep_v1.mp4")
    httpd = app.make_server(fw, 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield Srv(httpd, fw)
    finally:
        httpd.shutdown()
        httpd.server_close()


def _size(jpg: bytes) -> tuple[int, int]:
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    return img.shape[1], img.shape[0]


def test_binds_loopback(srv: Srv) -> None:
    assert srv.httpd.server_address[0] == "127.0.0.1"
    st, body = srv.get("/")
    assert st == 200
    assert b"<html" in body.lower()


def test_range_returns_206(srv: Srv) -> None:
    srv.paths.index.mkdir(parents=True, exist_ok=True)
    (srv.paths.index / "r.bin").write_bytes(bytes(range(100)))
    st, h, b = srv.req("GET", "/data/r.bin", headers={"Range": "bytes=10-19"})
    assert st == 206
    assert b == bytes(range(10, 20))
    assert h["content-range"] == "bytes 10-19/100"
    st, _, b = srv.req("GET", "/data/r.bin", headers={"Range": "bytes=-5"})
    assert st == 206 and b == bytes(range(95, 100))
    st, _, _ = srv.req("GET", "/data/r.bin", headers={"Range": "bytes=500-600"})
    assert st == 416
    st, _, b = srv.req("GET", "/data/r.bin")
    assert st == 200 and len(b) == 100


def test_media_mount_serves_lerobot_video(srv: Srv) -> None:
    st, _, b = srv.req("GET", "/media/S70/episode_000001.mp4", headers={"Range": "bytes=0-3"})
    assert st == 206 and len(b) == 4
    st, _ = srv.get("/media/nope/episode_000001.mp4")
    assert st == 404


@pytest.mark.parametrize(
    "path",
    [
        "/data/../pyproject.toml",
        "/data/%2e%2e/pyproject.toml",
        "/data/..%2fpyproject.toml",
        "/data//etc/passwd",
        "/../pyproject.toml",
        "/ego/../../pyproject.toml",
        "/media/S70/../../../../pyproject.toml",
    ],
)
def test_static_traversal(srv: Srv, path: str) -> None:
    (srv.paths.console_dir / "pyproject.toml").write_text("SECRET")
    (srv.paths.fw_root / "pyproject.toml").write_text("SECRET")
    st, body = srv.get(path)
    assert st in (403, 404)
    assert b"SECRET" not in body


def test_static_denies_vault_and_holdout(srv: Srv) -> None:
    for name in ("vault", "holdout-x"):
        d = srv.paths.index / name
        d.mkdir(parents=True)
        (d / "a.json").write_text('{"x":1}')
        st, body = srv.get(f"/data/{name}/a.json")
        assert st in (403, 404)
        assert b'"x"' not in body


def test_post_rejects_foreign_origin(srv: Srv) -> None:
    body = {"kind": "nope", "params": {}}
    assert srv.post("/api/jobs", body, origin="http://evil.example")[0] == 403
    assert srv.post("/api/jobs", body, origin=f"http://127.0.0.1:{srv.port + 1}")[0] == 403
    assert srv.post("/api/jobs", body, origin=None)[0] == 403
    assert srv.post("/api/jobs", body, host="evil.example")[0] == 403
    st, obj = srv.post("/api/jobs", body)
    assert st == 400 and obj["error"] == "unknown kind"


def test_get_rejects_foreign_host(srv: Srv) -> None:
    st, _ = srv.get("/api/status", headers={"Host": "evil.example"})
    assert st == 403
    st, _ = srv.get("/", headers={"Host": "evil.example"})
    assert st == 403


def test_poster_404_without_deid(srv: Srv) -> None:
    st, _ = srv.get("/api/poster?work=src_test&ep=ep_raw")
    assert st == 404
    st, _ = srv.get("/api/poster?work=src_missing&ep=ep_deid")
    assert st == 404
    st, b = srv.get("/api/poster?work=src_test&ep=ep_deid&w=128")
    assert st == 200 and _size(b) == (128, 96)
    st, _ = srv.get("/api/poster?work=..&ep=ep_deid")
    assert st == 400


def test_ego_strip_from_deid(srv: Srv) -> None:
    st, b = srv.get("/api/ego_strip?work=src_test&ep=ep_deid&n=4")
    assert st == 200
    assert _size(b) == (4 * int(72 * W / H), 72)
    assert srv.get("/api/ego_strip?work=src_test&ep=ep_raw&n=4")[0] == 404
    assert srv.get("/api/ego_strip?work=src_test&ep=ep_nope")[0] == 404


def test_ego_strip_from_viewer_row(srv: Srv) -> None:
    st, b = srv.get("/api/ego_strip?work=vwr&ep=ep_v1")
    assert st == 200 and _size(b)[1] == 72
    assert srv.get("/api/ego_strip?work=vwr&ep=ep_zz")[0] == 404
    assert srv.get("/api/poster?work=vwr&ep=ep_v1")[0] == 200


def test_work_episodes_flags_deid(srv: Srv) -> None:
    st, b = srv.get("/api/work_episodes?work=src_test")
    rows = {r["episode_id"]: r for r in json.loads(b)}
    assert rows["ep_deid"]["deid"] is True and rows["ep_deid"]["qa"] == "pass"
    assert rows["ep_raw"]["deid"] is False


def test_robot_strip_and_unknown_ds(srv: Srv) -> None:
    st, b = srv.get("/api/strip?ds=S70&ep=1")
    assert st == 200 and b[:2] == b"\xff\xd8"
    assert srv.get("/api/strip?ds=ZZ&ep=1")[0] == 404
    assert srv.get("/api/strip?ds=S70&ep=77")[0] == 404
    assert srv.get("/api/strip?ds=S70&ep=-1")[0] == 400


def test_fs_denies_vault(srv: Srv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / "vault").mkdir(parents=True)
    (home / "clips").mkdir()
    (home / "holdout-set").mkdir()
    monkeypatch.setenv("HOME", str(home))
    st, b = srv.get(f"/api/fs?path={home}/vault")
    assert st == 400
    assert srv.get(f"/api/fs?path={home}/holdout-set")[0] == 400
    assert srv.get("/api/fs?path=/etc")[0] == 400
    assert srv.get(f"/api/dir_check?path={home}/vault")[0] == 400
    st, b = srv.get(f"/api/fs?path={home}")
    names = [d["name"] for d in json.loads(b)["dirs"]]
    assert names == ["clips"]


def test_exports_download_is_zip_only(srv: Srv) -> None:
    srv.paths.exports.mkdir(parents=True, exist_ok=True)
    (srv.paths.exports / "a.zip").write_bytes(b"PK")
    (srv.paths.exports / "b.txt").write_text("x")
    assert srv.get("/api/exports/a.zip") == (200, b"PK")
    assert srv.get("/api/exports/b.txt")[0] == 404
    (srv.paths.console_dir / "out.zip").write_bytes(b"PK")
    assert srv.get("/api/exports/..%2fout.zip")[0] == 404


def test_upload_goes_under_console_uploads(srv: Srv) -> None:
    vid = (srv.paths.fw_root / "viewer" / "media" / "ep_v1.mp4").read_bytes()
    h = {"Origin": f"http://127.0.0.1:{srv.port}", "X-Filename": "clip%201.mp4"}
    h["Content-Length"] = str(len(vid))
    q = "/api/upload?dir=upload-20261111-1200&task=two_table"
    st, _, b = srv.req("POST", q, vid, h)
    assert st == 201
    saved = Path(json.loads(b)["saved"])
    assert saved.is_relative_to(srv.paths.uploads)
    assert (srv.paths.uploads / "upload-20261111-1200" / "device.json").is_file()
    st, _, _ = srv.req("POST", "/api/upload?dir=../x", vid, h)
    assert st == 400
    st, _, _ = srv.req("POST", q, vid, {**h, "Origin": "http://evil.example"})
    assert st == 403


def _stub(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: Any) -> None:
    m = types.ModuleType(f"flywheel.console.chat.{name}")
    for k, v in attrs.items():
        setattr(m, k, v)
    monkeypatch.setitem(sys.modules, m.__name__, m)


def _no_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every ``flywheel.console.chat.*`` import fail as if the module were absent."""

    def missing(name: str) -> Any:
        raise ModuleNotFoundError(f"No module named 'flywheel.console.chat.{name}'",
                                  name=f"flywheel.console.chat.{name}")  # fmt: skip

    monkeypatch.setattr(app, "_chat", missing)


def test_chat_routes_use_lazy_modules(srv: Srv, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        _no_chat(m)
        assert json.loads(srv.get("/api/models")[1])["nemotron"] == "down"
        assert srv.get("/api/tools")[0] == 503
    st, b = srv.get("/api/models")
    seen: dict[str, Any] = {}

    def stream(body: dict[str, Any]) -> Iterator[bytes]:
        seen["body"] = body
        yield b"event: token\ndata: {}\n\n"
        yield b"event: done\ndata: {}\n\n"

    _stub(
        monkeypatch, "llm", stream=stream, nemotron_status=lambda: "warm",
        prewarm=lambda: {"ok": True}, latest_bench=lambda: None,
        list_traces=lambda limit: [{"limit": limit}], get_trace=lambda t: None,
    )  # fmt: skip

    def call(name: str, args: dict[str, Any], ctx: dict[str, Any] | None) -> dict[str, Any]:
        return {"ok": True, "name": name, "args": args, "ctx": ctx}

    _stub(monkeypatch, "registry", call=call, describe=lambda route: [{"route": route}])
    assert json.loads(srv.get("/api/models")[1])["nemotron"] == "warm"
    q = "/api/tool?name=x&args=%7B%22a%22%3A1%7D&route=data"
    assert json.loads(srv.get(q)[1]) == {"ok": True, "name": "x", "args": {"a": 1},
                                         "ctx": {"route": "data"}}  # fmt: skip
    assert srv.get("/api/tool?name=x&args=notjson")[0] == 400
    assert json.loads(srv.get("/api/tools?route=qa")[1]) == [{"route": "qa"}]
    assert srv.get("/api/chat/bench")[0] == 404
    assert json.loads(srv.get("/api/chat/traces?limit=3")[1]) == [{"limit": 3}]
    assert srv.get("/api/chat/traces/t1")[0] == 404
    assert srv.post("/api/models/prewarm", {}) == (200, {"ok": True})
    h = {"Origin": f"http://127.0.0.1:{srv.port}"}
    st, hd, b = srv.req("POST", "/api/chat", b'{"messages":[]}', h)
    assert st == 200 and hd["content-type"].startswith("text/event-stream")
    assert b == b"event: token\ndata: {}\n\nevent: done\ndata: {}\n\n"
    assert seen["body"] == {"messages": []}


def test_missing_chat_module_is_503_other_import_errors_are_500(
    srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as m:
        _no_chat(m)
        assert srv.get("/api/tools")[0] == 503
        assert srv.post("/api/models/prewarm", {})[0] == 503

    def broken(name: str) -> Any:
        raise ModuleNotFoundError("No module named 'numpyy'", name="numpyy")

    monkeypatch.setattr(app, "_chat", broken)
    assert srv.get("/api/tools")[0] == 500
    assert srv.get("/api/models")[0] == 500
    assert srv.post("/api/models/prewarm", {})[0] == 500


def test_unexpected_key_error_is_500_not_404(srv: Srv, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise KeyError("runner bug")

    monkeypatch.setattr(app.runner, "list_works", boom)
    assert srv.get("/api/works")[0] == 500
    with monkeypatch.context() as m:
        m.setattr(app.runner, "cancel", lambda jid: boom())
        assert srv.post("/api/jobs/j-1/cancel", {})[0] == 500
    assert srv.get("/api/jobs/nope/log")[0] == 404
    assert srv.post("/api/jobs/nope/cancel", {})[0] == 404


def test_chat_stream_failing_before_first_chunk_sends_error_event(
    srv: Srv, monkeypatch: pytest.MonkeyPatch
) -> None:
    def stream(body: dict[str, Any]) -> Iterator[bytes]:
        raise RuntimeError("no model")

    _stub(monkeypatch, "llm", stream=stream)
    h = {"Origin": f"http://127.0.0.1:{srv.port}"}
    st, hd, b = srv.req("POST", "/api/chat", b'{"messages":[]}', h)
    assert st == 200 and hd["content-type"].startswith("text/event-stream")
    assert b.startswith(b"event: error\n") and b"no model" in b
    assert b.count(b"HTTP/") == 0
