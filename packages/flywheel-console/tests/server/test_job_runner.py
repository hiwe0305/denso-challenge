from __future__ import annotations

import json
import subprocess
import sys
import time
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flywheel.console.paths import ConsolePaths, set_active
from flywheel.console.server import runner

GATE_SCRIPT = (
    "import os, time\nwhile not os.path.exists(os.environ['GATE']):\n    time.sleep(0.05)\n"
)


@pytest.fixture
def rn(fw: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> Iterator[ConsolePaths]:
    set_active(fw)
    runner.init(fw)
    yield fw
    for rt in list(runner.RT.values()):
        rt["cancel"].set()


def _wait(cond: Callable[[], bool], what: str, timeout: float = 20.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError(f"timeout waiting for {what}")


def _states(ids: list[str]) -> list[str]:
    return [runner.JOBREG[i]["state"] for i in ids]


def _gated(monkeypatch: pytest.MonkeyPatch, gate: Path) -> None:
    monkeypatch.setenv("GATE", str(gate))
    monkeypatch.setattr(runner, "fw_cmd", lambda: [sys.executable, "-c", GATE_SCRIPT])


def test_kinds_are_the_allowlist() -> None:
    assert runner.KINDS == frozenset(
        "ego.ingest ego.deid ego.ea ego.pose ego.annotate ego.qa ego.report ego.pipeline "
        "ego.human1m agentqa.run agentqa.review export.zip".split()
    )


@pytest.mark.parametrize(
    "kind", ["train.run", "eval.run", "holdout.run", "shell", "ego.ingest ", "", "agentqa"]
)
def test_runner_rejects_unknown_kind(rn: ConsolePaths, kind: str) -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        runner.submit(kind, {})
    assert runner.JOBREG == {}


def test_runner_two_concurrent_max(
    rn: ConsolePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "gate"
    _gated(monkeypatch, gate)
    ids = [runner.submit("ego.ingest", {"source": "egodex"})["id"] for _ in range(3)]
    _wait(lambda: _states(ids).count("running") == 2, "two running")
    time.sleep(0.6)
    st = _states(ids)
    assert st.count("running") == 2 and st.count("queued") == 1
    gate.write_text("go")
    _wait(lambda: _states(ids) == ["ok"] * 3, "all ok")
    assert all(runner.JOBREG[i]["rc"] == 0 for i in ids)
    on_disk = json.loads((rn.jobs / ids[0] / "job.json").read_text())
    assert on_disk["state"] == "ok" and on_disk["host"] == "laptop"


def test_model_jobs_run_one_at_a_time(
    rn: ConsolePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for n in ("src_a", "src_b"):
        w = rn.fw_root / "pipeline" / n
        w.mkdir(parents=True)
        (w / "source.json").write_text(json.dumps({"deid_waiver": "x", "episodes": ["e"]}))
    gate = tmp_path / "gate"
    _gated(monkeypatch, gate)
    monkeypatch.setattr(runner.TUNNEL, "ensure", lambda timeout=15: True)
    monkeypatch.setattr(runner.TUNNEL, "tags", lambda fresh=False: ["m"])
    ids = [runner.submit("ego.annotate", {"work": str(rn.fw_root / "pipeline" / n)})["id"]
           for n in ("src_a", "src_b")]  # fmt: skip
    _wait(lambda: "running" in _states(ids), "one running")
    time.sleep(0.6)
    assert sorted(_states(ids)) == ["queued", "running"]
    gate.write_text("go")
    _wait(lambda: _states(ids) == ["ok", "ok"], "both ok")


def test_cancel_queued_job(
    rn: ConsolePaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "gate"
    _gated(monkeypatch, gate)
    ids = [runner.submit("ego.ingest", {"source": "egodex"})["id"] for _ in range(3)]
    _wait(lambda: _states(ids).count("running") == 2, "two running")
    queued = [i for i in ids if runner.JOBREG[i]["state"] == "queued"][0]
    assert runner.cancel(queued)["state"] == "cancelled"
    gate.write_text("go")
    _wait(lambda: sorted(_states(ids)) == ["cancelled", "ok", "ok"], "settled")


def test_plan_starts_nothing(rn: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("plan must not start anything")

    monkeypatch.setattr(runner.TUNNEL, "ensure", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    inp = rn.fw_root / "pipeline" / "src_a" / "report"
    inp.mkdir(parents=True)
    pl = runner.plan("agentqa.run", {"input": str(inp)}, "j-1")
    assert pl["argv"][-4:-2] == ["--out", str(rn.console_dir / "agentqa" / "j-1")]
    assert pl["model"] and pl["tunnel"]
    assert runner.plan("ego.ingest", {"source": "egodex"}, "x")["argv"][-4:] == [
        "ingest", "egodex", "--split", "train",
    ]  # fmt: skip
    assert runner.AQA == rn.console_dir / "agentqa"


def test_plan_gates_and_paths(rn: ConsolePaths, tmp_path: Path) -> None:
    w = rn.fw_root / "pipeline" / "src_a"
    w.mkdir(parents=True)
    (w / "source.json").write_text(json.dumps({"episodes": ["e"], "deid_copies": {}}))
    with pytest.raises(ValueError, match="che mặt"):
        runner.plan("ego.pose", {"work": str(w)}, "x")
    assert runner.plan("ego.deid", {"work": str(w)}, "x")["outputs"]["work"] == str(w)
    with pytest.raises(ValueError):
        runner.plan("ego.deid", {"work": str(tmp_path)}, "x")
    with pytest.raises(ValueError):
        runner.plan("export.zip", {"path": str(tmp_path)}, "x")
    with pytest.raises(ValueError):
        runner.plan("agentqa.run", {"input": str(rn.fw_root / ".." / "x")}, "x")
    with pytest.raises(ValueError):
        runner.plan("ego.ingest", {"source": "video", "root": "/etc"}, "x")


def test_under_denies_vault_and_holdout(tmp_path: Path) -> None:
    (tmp_path / "vault").mkdir()
    (tmp_path / "holdout-a").mkdir()
    (tmp_path / "ok").mkdir()
    assert runner.under(tmp_path / "ok", tmp_path) == (tmp_path / "ok").resolve()
    for bad in (tmp_path / "vault", tmp_path / "holdout-a", tmp_path / ".." / "x"):
        with pytest.raises(ValueError):
            runner.under(bad, tmp_path)


def test_export_zip_skips_data_and_holdout(rn: ConsolePaths) -> None:
    d = rn.fw_root / "tray" / "x"
    (d / "holdout-b").mkdir(parents=True)
    (d / "videos").mkdir()
    (d / "a.json").write_text("{}")
    (d / "holdout-b" / "h.json").write_text("{}")
    (d / "videos" / "v.json").write_text("{}")
    (d / "big.mp4").write_bytes(b"0")
    (rn.fw_root / "vault").mkdir()
    (rn.fw_root / "vault" / "conditions.json").write_text("{}")
    (rn.fw_root / "console" / "jobs").mkdir(parents=True, exist_ok=True)
    (rn.fw_root / "console" / "jobs" / "x.log").write_text("x")
    (d / "a" / "holdout_x").mkdir(parents=True)
    (d / "a" / "holdout_x" / "f.json").write_text("{}")
    (d / "a" / "vault").mkdir()
    (d / "a" / "vault" / "v.json").write_text("{}")
    (d / "a" / ".hid").mkdir()
    (d / "a" / ".hid" / "h.json").write_text("{}")
    (d / "a" / "console").mkdir()
    (d / "a" / "console" / "c.json").write_text("{}")
    jid = runner.submit("export.zip", {"path": str(d)})["id"]
    _wait(lambda: runner.JOBREG[jid]["state"] == "ok", "zip done")
    z = runner.JOBREG[jid]["outputs"]["zip"]
    assert Path(z).parent == rn.exports
    assert zipfile.ZipFile(z).namelist() == ["x/a.json"]
    assert [e["name"] for e in runner.list_exports() if e["kind"] == "zip"] == [Path(z).name]


def test_export_zip_of_fw_root_skips_vault_and_console(rn: ConsolePaths) -> None:
    (rn.fw_root / "vault").mkdir()
    (rn.fw_root / "vault" / "conditions.json").write_text("{}")
    (rn.fw_root / "console" / "jobs").mkdir(parents=True, exist_ok=True)
    (rn.fw_root / "console" / "jobs" / "x.log").write_text("x")
    (rn.fw_root / "keep.json").write_text("{}")
    jid = runner.submit("export.zip", {"path": str(rn.fw_root)})["id"]
    _wait(lambda: runner.JOBREG[jid]["state"] == "ok", "zip done")
    names = zipfile.ZipFile(runner.JOBREG[jid]["outputs"]["zip"]).namelist()
    assert names == [f"{rn.fw_root.name}/keep.json"]


def test_export_zip_walks_the_planned_path(rn: ConsolePaths) -> None:
    d = rn.fw_root / "tray" / "x"
    d.mkdir(parents=True)
    (d / "a.json").write_text("{}")
    link = rn.fw_root / "link"
    link.symlink_to(d)
    jid = runner.submit("export.zip", {"path": str(link)})["id"]
    _wait(lambda: runner.JOBREG[jid]["state"] == "ok", "zip done")
    job = runner.JOBREG[jid]
    assert job["outputs"]["dir"] == str(d)
    assert zipfile.ZipFile(job["outputs"]["zip"]).namelist() == ["x/a.json"]


def test_running_jobs_counts_leaf_jobs_once(rn: ConsolePaths) -> None:
    parent = runner.make_job("ego.pipeline", {}, pl={"argv": ["chain"]})
    child = runner.make_job("ego.deid", {}, chain_id=parent["id"], pl={"argv": ["x"]})
    parent["state"] = child["state"] = "running"
    assert runner.status()["machines"]["laptop"]["running_jobs"] == 1


def test_init_registers_atexit_once(rn: ConsolePaths, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(runner.atexit, "register", lambda f: calls.append(f))
    monkeypatch.setattr(runner, "_atexit_done", False)
    runner.init(rn)
    runner.init(rn)
    assert len(calls) == 1


def test_registry_reload_marks_dead_running_job(rn: ConsolePaths) -> None:
    d = rn.jobs / "j-old"
    d.mkdir(parents=True)
    (d / "job.json").write_text(
        json.dumps({"id": "j-old", "kind": "ego.qa", "state": "running", "pid": 2**22 + 12,
                    "created": "2026-11-11T00:00:00+00:00", "stage": "process", "outputs": {}})
    )  # fmt: skip
    runner.init(rn)
    j = runner.JOBREG["j-old"]
    assert j["state"] == "failed" and "restarted" in j["note"]


def test_status_shape(rn: ConsolePaths) -> None:
    st = runner.status()
    assert [s["id"] for s in st["stages"]] == [
        "collect", "process", "release", "train", "eval", "loop"
    ]  # fmt: skip
    assert st["machines"]["laptop"]["slots"] == 2
