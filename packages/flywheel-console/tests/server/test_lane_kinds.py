"""The data.* and eval.* job kinds and ``GET /api/kinds`` (console re-foundation, T3)."""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import make_lerobot
from flywheel.console.paths import ConsolePaths, set_active
from flywheel.console.server import app, kinds, runner
from test_app import Srv

REPO = Path(__file__).resolve().parents[4]

# A stand-in for `fw data …` that writes what each real command writes, plus the FW_ROOT it saw.
FAKE_FW = r"""
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
assert a[0] == "data", a
cmd = a[1]
def opt(k):
    return a[a.index(k) + 1]
if cmd == "ingest":
    w = Path(opt("--work")); w.mkdir(parents=True)
    src = {"root": a[2], "source_detail": opt("--source-detail")}
    (w / "source.json").write_text(json.dumps(src))
    ing = {"source_id": "src_fake", "episodes": 3, "frames": 30}
    (w / "ingest.json").write_text(json.dumps(ing))
    (w / "fw_root.txt").write_text(os.environ["FW_ROOT"])
elif cmd == "qa":
    w = Path(a[2]); (w / "qa").mkdir()
    rows = [{"decision": d} for d in ("pass", "pass", "flag")]
    (w / "qa" / "reports.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (w / "qa" / "summary.json").write_text("{}")
elif cmd == "release":
    r = Path(opt("--out")); r.mkdir(parents=True)
    rel = {"id": "rel_fake", "status": "frozen", "counts": {"train": 3}}
    (r / "release.json").write_text(json.dumps(rel))
elif cmd == "report":
    w = Path(a[2]); (w / "report").mkdir()
    (w / "report" / "dataset_report.json").write_text(json.dumps({"episode_count": 3}))
    (w / "report" / "index.html").write_text("<html></html>")
print(cmd, "done")
"""


@pytest.fixture
def rn(fw: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> Iterator[ConsolePaths]:
    fixtures = REPO / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/trace"
    monkeypatch.setattr(runner, "trace_fixtures", lambda: fixtures)
    set_active(fw)
    runner.init(fw)
    kinds.clear_cache()
    yield fw
    for rt in list(runner.RT.values()):
        rt["cancel"].set()


@pytest.fixture
def ds(rn: ConsolePaths) -> Path:
    return make_lerobot(rn.fw_root / "psi-data" / "simple" / "PickBetweenTables-v0")


def _wait(cond: Callable[[], bool], what: str, timeout: float = 30.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError(f"timeout waiting for {what}")


def _ingest(ds: Path, **kw: Any) -> dict[str, Any]:
    return {"dataset": str(ds), "source_detail": "psi_data"} | kw


def _work(rn: ConsolePaths, name: str = "j-w", qa: bool = False) -> Path:
    w = rn.store / "work" / name
    w.mkdir(parents=True)
    (w / "source.json").write_text(json.dumps({"root": "x"}))
    if qa:
        (w / "qa").mkdir()
        (w / "qa" / "reports.jsonl").write_text('{"decision": "pass"}\n')
        (w / "qa" / "summary.json").write_text("{}")
    return w


# ---------------------------------------------------------------- planning and validation
def test_new_kinds_are_allowlisted_with_a_stage() -> None:
    new = {"data.ingest", "data.qa", "data.release", "data.report", "data.pipeline",
           "eval.diag_system", "eval.diag_train"}  # fmt: skip
    assert new <= runner.KINDS
    assert set(runner.PROCESS_STAGE) == set(runner.KINDS) == set(kinds.SPEC)
    assert set(runner.PROCESS_STAGE.values()) <= set(kinds.STAGES)


def test_ingest_stages_into_the_console_store(rn: ConsolePaths, ds: Path) -> None:
    pl = runner.plan("data.ingest", _ingest(ds, license="CC BY 4.0"), "j-1")
    store = rn.store.resolve()
    assert pl["fw_root"] == str(rn.store)
    stage, argv = pl["steps"]
    assert stage[0] == "python:stage" and stage[1] == str(ds.resolve())
    staged = Path(stage[2])
    assert staged.is_relative_to(store / "datasets")
    assert argv[argv.index("ingest") + 1] == str(staged)
    assert argv[argv.index("--work") + 1] == str(rn.store / "work" / "j-1")
    assert argv[argv.index("--license") + 1] == "CC BY 4.0"
    assert argv[argv.index("--data-class") + 1] == "restricted"  # no card: restricted (DA-45)
    assert pl["task"] == "two_table"


def test_staging_copies_once(rn: ConsolePaths, ds: Path) -> None:
    dst = runner.staged_path(ds.resolve())
    rt = {"cancel": threading.Event()}
    job = runner.make_job("data.ingest", {}, pl={"argv": ["x"]})
    assert runner.stage_dataset(job, rt, ds.resolve(), dst) == 0
    assert (dst / "meta" / "info.json").is_file()
    assert not runner.stage_needed(ds.resolve(), dst)
    pl = runner.plan("data.ingest", _ingest(ds), "j-2")
    assert [s[0] for s in pl["steps"]][0] != "python:stage"  # already staged: ingest only


@pytest.mark.parametrize(
    "params, match",
    [
        ({"dataset": "/etc", "source_detail": "psi_data"}, "outside"),
        ({"dataset": "../outside", "source_detail": "psi_data"}, "outside"),
        ({"dataset": "vault/x", "source_detail": "psi_data"}, "protected"),
        ({"dataset": "", "source_detail": "psi_data"}, "dataset"),
        ({"source_detail": "teleop_keyboard"}, "source_detail"),
        ({"source_detail": "psi_data", "data_class": "secret"}, "data_class"),
        ({"source_detail": "psi_data", "split": "holdout"}, "split"),
        ({"source_detail": "psi_data", "license": "a;rm -rf /"}, "license"),
    ],
)
def test_ingest_refuses_bad_input(
    rn: ConsolePaths, ds: Path, params: dict[str, Any], match: str
) -> None:
    (rn.fw_root / "vault" / "x" / "meta").mkdir(parents=True)
    p = {"dataset": str(ds)} | params
    with pytest.raises(ValueError, match=match):
        runner.plan("data.ingest", p, "j")


def test_ingest_refuses_non_v21_and_console_folders(rn: ConsolePaths, ds: Path) -> None:
    info = json.loads((ds / "meta" / "info.json").read_text())
    (ds / "meta" / "info.json").write_text(json.dumps(info | {"codebase_version": "v3.0"}))
    with pytest.raises(ValueError, match="v2.1"):
        runner.plan("data.ingest", _ingest(ds), "j")
    other = make_lerobot(rn.console_dir / "uploads" / "ds")
    with pytest.raises(ValueError, match="console"):
        runner.plan("data.ingest", _ingest(other), "j")


def test_ingest_refuses_a_dataset_over_the_copy_limit(
    rn: ConsolePaths, ds: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "STAGE_MAX_BYTES", 10)
    with pytest.raises(ValueError, match="giới hạn"):
        runner.plan("data.ingest", _ingest(ds), "j")


def test_work_kinds_stay_in_the_store(rn: ConsolePaths, tmp_path: Path) -> None:
    w = _work(rn)
    assert runner.plan("data.qa", {"work": str(w)}, "j")["argv"][-3:] == ["data", "qa", str(w)]
    with pytest.raises(ValueError, match="QA"):
        runner.plan("data.release", {"work": str(w)}, "j")
    with pytest.raises(ValueError, match="QA"):
        runner.plan("data.report", {"work": str(w)}, "j")
    elsewhere = rn.fw_root / "pipeline" / "src_a"
    elsewhere.mkdir(parents=True)
    (elsewhere / "source.json").write_text("{}")
    for bad in (str(elsewhere), str(tmp_path), "", str(rn.store / "work" / ".." / "..")):
        with pytest.raises(ValueError):
            runner.plan("data.qa", {"work": bad}, "j")


def test_release_writes_under_the_store(rn: ConsolePaths) -> None:
    w = _work(rn, qa=True)
    pl = runner.plan("data.release", {"work": str(w), "name": "demo_1"}, "j-9")
    argv = pl["argv"]
    assert argv[argv.index("--out") + 1] == str(rn.store / "releases" / "j-9")
    assert argv[argv.index("--name") + 1] == "demo_1"
    assert pl["fw_root"] == str(rn.store)
    with pytest.raises(ValueError, match="name"):
        runner.plan("data.release", {"work": str(w), "name": "../x"}, "j")


def test_diag_system_accepts_fixtures_and_fw_root_only(rn: ConsolePaths) -> None:
    fx = runner.trace_fixtures() / "tr_clean"
    pl = runner.plan("eval.diag_system", {"episode": str(fx)}, "j-3")
    assert pl["outputs"]["fixture"] is True
    assert pl["argv"][-4:] == ["--episode", str(fx.resolve()), "--store",
                               str(rn.store / "eval" / "j-3")]  # fmt: skip
    assert runner.plan("eval.diag_system", {"episode": "tr_missing"}, "j")["outputs"]["fixture"]
    real = rn.fw_root / "eval" / "tr_1"
    real.mkdir(parents=True)
    (real / "steps.jsonl").write_text("")
    pl = runner.plan("eval.diag_system", {"episode": "eval/tr_1"}, "j")
    assert pl["outputs"]["fixture"] is False
    (rn.fw_root / "vault" / "t").mkdir(parents=True)
    (rn.fw_root / "vault" / "t" / "steps.jsonl").write_text("")
    for bad in ("/etc", str(rn.fw_root / "vault" / "t"), "", "eval/none"):
        with pytest.raises(ValueError):
            runner.plan("eval.diag_system", {"episode": bad}, "j")


def test_diag_train_needs_a_metrics_log(rn: ConsolePaths) -> None:
    j = rn.fw_root / "tray" / "pair60k" / "C" / "job"
    j.mkdir(parents=True)
    with pytest.raises(ValueError, match="metrics"):
        runner.plan("eval.diag_train", {"job": str(j)}, "j")
    (j / "metrics.jsonl").write_text("{}\n")
    pl = runner.plan("eval.diag_train", {"job": "tray/pair60k/C/job"}, "j-4")
    assert pl["argv"][-4:] == ["--job", str(j.resolve()), "--store",
                               str(rn.store / "eval" / "j-4")]  # fmt: skip
    assert pl["task"] == "tray"
    with pytest.raises(ValueError):
        runner.plan("eval.diag_train", {"job": "/etc"}, "j")


def test_pipeline_validates_before_starting(rn: ConsolePaths, ds: Path) -> None:
    with pytest.raises(ValueError):
        runner.submit("data.pipeline", {"dataset": "/etc", "source_detail": "psi_data"})
    with pytest.raises(ValueError, match="release"):
        runner.submit("data.pipeline", _ingest(ds, release="no"))
    assert runner.JOBREG == {}


# ---------------------------------------------------------------- end to end
def test_data_pipeline_chain_end_to_end(
    rn: ConsolePaths, ds: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "fake_fw.py"
    script.write_text(FAKE_FW)
    monkeypatch.setattr(runner, "fw_cmd", lambda: [sys.executable, str(script)])
    job = runner.submit("data.pipeline", _ingest(ds))
    _wait(lambda: runner.JOBREG[job["id"]]["state"] not in ("queued", "running"), "chain")
    j = runner.JOBREG[job["id"]]
    assert j["state"] == "ok", runner.read_log(job["id"], 0)["text"]
    kids = [runner.JOBREG[c] for c in j["outputs"]["children"]]
    assert [k["kind"] for k in kids] == runner.DATA_CHAIN
    assert all(k["state"] == "ok" and k["chain_id"] == job["id"] for k in kids)
    work = Path(j["outputs"]["work"])
    assert work.parent == rn.store / "work"
    assert (work / "fw_root.txt").read_text() == str(rn.store)
    assert kids[0]["outputs"]["source_id"] == "src_fake"
    assert kids[0]["process_stage"] == "data" and kids[1]["process_stage"] == "qa"
    assert kids[1]["outputs"]["decisions"] == {"pass": 2, "flag": 1}
    assert kids[2]["outputs"]["release_id"] == "rel_fake"
    assert Path(kids[2]["outputs"]["release"]).parent == rn.store / "releases"
    assert kids[3]["outputs"]["episode_count"] == 3
    assert j["task"] == "two_table"
    assert "chép" in runner.read_log(kids[0]["id"], 0)["text"]
    # nothing written outside the console folder
    outside = [p for p in rn.fw_root.rglob("*") if p.is_file()
               and not p.is_relative_to(rn.console_dir) and not p.is_relative_to(ds)]  # fmt: skip
    assert outside == []
    st = {s["id"]: s for s in runner.status()["stages"]}
    assert st["process"]["state"] in ("done", "idle")


def test_pipeline_can_skip_the_release(
    rn: ConsolePaths, ds: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "fake_fw.py"
    script.write_text(FAKE_FW)
    monkeypatch.setattr(runner, "fw_cmd", lambda: [sys.executable, str(script)])
    job = runner.submit("data.pipeline", _ingest(ds, release=False))
    _wait(lambda: runner.JOBREG[job["id"]]["state"] not in ("queued", "running"), "chain")
    kids = [runner.JOBREG[c]["kind"] for c in runner.JOBREG[job["id"]]["outputs"]["children"]]
    assert kids == ["data.ingest", "data.qa", "data.report"]


@pytest.mark.skipif(not (REPO / ".venv" / "bin" / "fw").exists(), reason="needs the repo's fw")
def test_diag_system_runs_the_real_cli_on_a_fixture(tmp_path: Path) -> None:
    fw = ConsolePaths(repo=REPO, fw_root=tmp_path / "fwdata")
    set_active(fw)
    runner.init(fw)
    try:
        job = runner.submit(
            "eval.diag_system", {"episode": str(runner.trace_fixtures() / "tr_sync_delay")}
        )
        _wait(lambda: runner.JOBREG[job["id"]]["state"] not in ("queued", "running"), "diag")
        j = runner.JOBREG[job["id"]]
        assert j["state"] == "ok", runner.read_log(job["id"], 0)["text"]
        assert j["outputs"]["fixture"] is True and j["outputs"]["findings"] == 1
        assert j["outputs"]["verdict"]
        assert Path(j["outputs"]["record"]).is_relative_to(fw.store / "eval")
    finally:
        for rt in list(runner.RT.values()):
            rt["cancel"].set()


# ---------------------------------------------------------------- /api/kinds
@pytest.fixture
def kserv(rn: ConsolePaths, ds: Path) -> Iterator[Srv]:
    httpd = app.make_server(rn, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield Srv(httpd, rn)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_kinds_shape(kserv: Srv, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.TUNNEL, "tags", lambda fresh=False: None)
    st, body = kserv.get("/api/kinds")
    assert st == 200
    d = json.loads(body)
    assert d["locked"] is False and d["stages"] == list(kinds.STAGES)
    by = {k["kind"]: k for k in d["kinds"]}
    assert set(by) == set(runner.KINDS)
    for k in d["kinds"]:
        assert k["stage"] in kinds.STAGES and k["runs_on"] == "laptop"
        assert set(k["title"]) == {"vi", "en"}
        for a in k["args"]:
            assert {"name", "type", "required", "help"} <= set(a)
        for s in k["samples"]:
            assert {"label", "params", "available", "fixture"} <= set(s)
    ing = by["data.ingest"]
    assert [s["params"]["source_detail"] for s in ing["samples"]] == ["psi_data"]
    assert ing["samples"][0]["available"] is True
    assert next(a for a in ing["args"] if a["name"] == "source_detail")["choices"] == list(
        runner.SOURCE_DETAILS
    )
    assert all(s["fixture"] for s in by["eval.diag_system"]["samples"])
    assert len(by["eval.diag_system"]["samples"]) == 4
    assert by["agentqa.run"]["needs"] == ["rtx3060_tunnel"]
    assert by["agentqa.run"]["needs_state"] == {"rtx3060_tunnel": "down"}
    assert by["data.pipeline"]["chain"] == runner.DATA_CHAIN
    remote = {r["id"]: r for r in d["remote"]}
    assert {"train", "eval_closed_loop", "eval.score", "loop"} <= set(remote)
    assert "eval.score" not in by  # left out: no runnable task definition


def test_api_kinds_reports_past_durations(kserv: Srv, rn: ConsolePaths) -> None:
    w = _work(rn, qa=True)
    job = runner.make_job("data.qa", {"work": str(w)}, pl={"argv": ["x"]})
    job.update(state="ok", started="2026-11-15T10:00:00+07:00", ended="2026-11-15T10:00:04+07:00")
    d = json.loads(kserv.get("/api/kinds")[1])
    qa = next(k for k in d["kinds"] if k["kind"] == "data.qa")
    assert qa["typical_seconds"] == 4.0 and qa["n_ok_runs"] == 1
    assert qa["samples"][0]["last_seconds"] == 4.0


@pytest.fixture
def klocked(rn: ConsolePaths, ds: Path) -> Iterator[Srv]:
    httpd = app.make_server(rn, 0, lock=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield Srv(httpd, rn)
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize(
    "kind", ["data.ingest", "data.qa", "data.release", "data.report", "data.pipeline",
             "eval.diag_system", "eval.diag_train"],
)  # fmt: skip
def test_locked_server_refuses_new_kinds(klocked: Srv, ds: Path, kind: str) -> None:
    st, body = klocked.post("/api/jobs", {"kind": kind, "params": _ingest(ds)})
    assert st == 403 and body == {"error": "locked"}
    assert runner.JOBREG == {}


def test_locked_server_lists_kinds_read_only(klocked: Srv) -> None:
    st, body = klocked.get("/api/kinds")
    d = json.loads(body)
    assert st == 200 and d["locked"] is True
    assert all(k["available"] is False for k in d["kinds"])
    assert "/home/" not in body.decode()


def test_staging_skips_symlinks_and_jobs_never_share_a_copy(
    rn: ConsolePaths, ds: Path, tmp_path: Path
) -> None:
    secret = tmp_path / "vault" / "holdout.json"
    secret.parent.mkdir()
    secret.write_text("{}")
    (ds / "meta" / "leak.json").symlink_to(secret)
    (ds / "linked_dir").symlink_to(secret.parent)
    dst = runner.staged_path(ds.resolve())
    rt = {"cancel": threading.Event()}
    a = runner.make_job("data.ingest", {}, pl={"argv": ["x"]})
    b = runner.make_job("data.ingest", {}, pl={"argv": ["x"]})
    # a's copy is under way when b starts: b must not clear or write into it
    part_a = dst.with_name(f"{dst.name}.part-{a['id']}")
    part_a.mkdir(parents=True)
    (part_a / "marker").write_text("a")
    assert runner.stage_dataset(b, rt, ds.resolve(), dst) == 0
    assert (part_a / "marker").is_file()
    assert (dst / "meta" / "info.json").is_file()
    assert not (dst / "meta" / "leak.json").exists() and not (dst / "linked_dir").exists()
    assert "symlink" in (runner.jobs_dir() / b["id"] / "log.txt").read_text()


# ---------------------------------------------------------------- dataset cards (DA-45 AC 5)
STORE_CARD = """\
schema: dataset-card/1
id: tray_s1_aaaaaaaaaaaa
alias: tray.s1.jig2.l1.p8.20261122
status: current
task: tray
kind: synthetic_s1
source_detail: planner_wbc
data_class: internal
license: "CC BY 4.0 on HF (manifest: unknown)"
counts: {episodes: 3, frames: 30, hours: 0.001}
files: {release: releases/tray_s1_aaaaaaaaaaaa}
store: tray-s1-test
locations:
  - {host: laptop, root: "fwdata/datasets/tray-s1-test", role: mirror}
"""


@pytest.fixture
def carded(rn: ConsolePaths) -> Path:
    cards_dir = rn.fw_root / "datasets" / "tray-s1-test" / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "tray_s1_aaaaaaaaaaaa.yaml").write_text(STORE_CARD)
    return make_lerobot(rn.fw_root / "datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa")


def test_store_release_is_a_sample_with_card_values(rn: ConsolePaths, carded: Path) -> None:
    by = {s["params"]["dataset"]: s for s in kinds.dataset_samples()}
    s = by["datasets/tray-s1-test/releases/tray_s1_aaaaaaaaaaaa"]
    assert s["params"]["data_class"] == "internal"
    assert s["params"]["license"] == "CC BY 4.0 on HF manifest unknown"
    assert runner.LICENSE_RE.match(s["params"]["license"])
    assert s["params"]["source_detail"] == "planner_wbc" and s["task"] == "tray"
    assert s["available"] is True


def test_sample_without_card_is_restricted(rn: ConsolePaths, ds: Path) -> None:
    (s,) = kinds.dataset_samples()
    assert s["params"]["data_class"] == "restricted" and s["params"]["license"] == "unknown"
    assert s["params"]["source_detail"] == "psi_data"  # path fallback


def test_ingest_defaults_follow_the_card(rn: ConsolePaths, carded: Path) -> None:
    p = {"dataset": str(carded), "source_detail": "planner_wbc"}
    argv = runner.plan("data.ingest", p, "j-c")["steps"][-1]
    assert argv[argv.index("--data-class") + 1] == "internal"
    assert argv[argv.index("--license") + 1] == "CC BY 4.0 on HF manifest unknown"
    p |= {"data_class": "public", "license": "CC0"}  # explicit params still win
    argv = runner.plan("data.ingest", p, "j-d")["steps"][-1]
    assert argv[argv.index("--data-class") + 1] == "public"
    assert argv[argv.index("--license") + 1] == "CC0"


def test_bad_card_falls_back_to_restricted(rn: ConsolePaths, carded: Path) -> None:
    f = rn.fw_root / "datasets/tray-s1-test/cards/tray_s1_aaaaaaaaaaaa.yaml"
    f.write_text(STORE_CARD.replace("status: current", "status: live"))
    argv = runner.plan("data.ingest", {"dataset": str(carded), "source_detail": "planner_wbc"},
                       "j-e")["steps"][-1]  # fmt: skip
    assert argv[argv.index("--data-class") + 1] == "restricted"


def test_safe_license() -> None:
    assert runner.safe_license("CC BY 4.0 on HF (manifest: unknown)") == (
        "CC BY 4.0 on HF manifest unknown"
    )
    assert runner.safe_license(None) == "unknown" and runner.safe_license("();") == "unknown"
    assert len(runner.safe_license("x" * 99)) == 64
