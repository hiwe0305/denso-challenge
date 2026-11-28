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
        "ego.human1m agentqa.run agentqa.review export.zip data.ingest data.qa data.release "
        "data.report data.pipeline eval.diag_system eval.diag_train".split()
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


def test_export_zip_relative_path_resolves_under_fw_root(rn: ConsolePaths) -> None:
    d = rn.fw_root / "cut" / "S70"
    d.mkdir(parents=True)
    (d / "a.json").write_text("{}")
    planned = runner.plan("export.zip", {"path": "cut/S70"}, "x")
    assert planned["outputs"]["dir"] == str(d.resolve())
    with pytest.raises(ValueError):
        runner.plan("export.zip", {"path": "../escape"}, "x")


def _review_params(rn: ConsolePaths) -> dict[str, Any]:
    rep = rn.fw_root / "aqa" / "reports.jsonl"
    rep.parent.mkdir(parents=True)
    rep.write_text("{}\n")
    return {
        "reports": str(rep), "report_id": "r1",
        "decisions": [{"finding_id": "f1", "decide": "agree"}],
    }  # fmt: skip


def test_agentqa_review_reviewer_from_env(
    rn: ConsolePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FW_REVIEWER", "Ada")
    argv = runner.plan("agentqa.review", _review_params(rn), "x")["argv"]
    assert argv[argv.index("--reviewer") + 1] == "Ada"
    assert "Hiếu" not in argv


def test_agentqa_review_refuses_without_reviewer(
    rn: ConsolePaths, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FW_REVIEWER", raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    with pytest.raises(ValueError, match="FW_REVIEWER"):
        runner.plan("agentqa.review", _review_params(rn), "x")


def test_status_eval_and_loop_wait_without_index(rn: ConsolePaths) -> None:
    st = {s["id"]: s for s in runner.status()["stages"]}
    assert st["eval"]["state"] == "waiting" and st["loop"]["state"] == "waiting"


def _pair_index(rn: ConsolePaths, retest: str) -> dict[str, Any]:
    pair = {
        "best": "C_70",
        "runs": [
            {"run": "C_70", "successes": 10, "n": 60},
            {"run": retest, "successes": 4, "n": 60},
        ],
        "comparisons": [
            {"variant": retest, "baseline": "C_70", "outcome": "F"},
            {"variant": retest, "baseline": "C_ALL", "outcome": "F"},
            {"variant": "C_70", "baseline": "C_ALL", "outcome": "continue"},
        ],
    }  # fmt: skip
    rn.index.mkdir(parents=True, exist_ok=True)
    (rn.index / "story.json").write_text(
        json.dumps({"pair": pair, "round": {"chain": {"selected": 181}}}), encoding="utf-8"
    )
    return {s["id"]: s for s in runner.status()["stages"]}


def test_status_reads_pair_round_from_index(rn: ConsolePaths) -> None:
    st = _pair_index(rn, "X_R2")  # a retest run no round holds
    # the home page reads the first fraction of eval.now as the success rate: the best run's
    assert st["eval"]["state"] == "done"
    assert st["eval"]["now"] == "Tốt nhất C_70 10/60 · vòng X_R2 4/60"
    assert st["loop"]["state"] == "done"
    assert st["loop"]["now"] == "Vòng X_R2: chọn 181 tập → 4/60 → dừng (F)"


def test_status_does_not_present_the_held_retest(rn: ConsolePaths) -> None:
    st = _pair_index(rn, "C70_R1")  # withhold_eval of the seed; the index lists nothing
    assert st["eval"]["now"] == "Tốt nhất C_70 10/60"
    assert st["loop"]["now"] == "Đã chọn 181 tập nhắm lỗi · kết quả thi lại không trình bày"


def _jig_index(rn: ConsolePaths, status: str) -> None:
    """story.json with a pair round and a jig block of the DA-53 shape (index/jig.py)."""
    pair = {"best": "C_70", "runs": [{"run": "C_70", "successes": 10, "n": 60}]}
    ev: dict[str, Any] = {"run": "M", "role": "baseline", "status": status}
    if status == "ready":
        ev["headline"] = {"n": 180, "successes": 136, "p": 0.7556, "ci": [0.7, 0.8111]}
    jig = {
        "evals": [ev], "featured": "M" if status == "ready" else None,
        "runs": [{"branch": "M", "ckpt_step": 100000, "max_steps": 100000}],
        "next_cut": None, "paired": None,
    }  # fmt: skip
    rn.index.mkdir(parents=True, exist_ok=True)
    (rn.index / "story.json").write_text(json.dumps({"pair": pair, "jig": jig}), encoding="utf-8")


def test_status_reads_the_featured_jig_eval(rn: ConsolePaths) -> None:
    """DA-53 2.4: the jig line is the featured run's results.json headline; no cut name."""
    _jig_index(rn, "ready")
    st = {s["id"]: s for s in runner.status()["stages"]}
    assert st["eval"]["now"] == "Tốt nhất C_70 10/60 · Cảnh jig2: M 136/180"
    assert ".tar" not in st["loop"]["now"]


def test_status_has_no_jig_figure_while_results_json_is_missing(rn: ConsolePaths) -> None:
    _jig_index(rn, "missing")
    st = {s["id"]: s for s in runner.status()["stages"]}
    assert st["eval"]["now"] == "Tốt nhất C_70 10/60"


def test_train_runs_skip_abandoned_attempts(rn: ConsolePaths) -> None:
    for branch in ("C70_R1", "C70_R1.attempt1"):
        d = rn.fw_root / "tray/pair60k" / branch / "job"
        d.mkdir(parents=True)
        (d / "metrics.jsonl").write_text(json.dumps({"step": 60000, "loss": 0.1}) + "\n")
    assert [r["branch"] for r in runner.train_runs()] == ["C70_R1"]


def test_train_runs_and_colab_leave_out_a_hidden_run(rn: ConsolePaths) -> None:
    """``withhold_runs`` (run N, Hiếu 28/11/2026): not in the train listing nor the Colab VMs."""
    for folder in ("tray/jig-m/da48-ft-m-s0", "tray/jig-n/da50-ft-n-s0"):
        d = rn.fw_root / folder
        d.mkdir(parents=True)
        (d / "metrics.jsonl").write_text(json.dumps({"step": 9, "loss": 0.1}) + "\n")
    assert [r["branch"] for r in runner.train_runs()] == ["M"]
    batch = rn.fw_root / "colab/batch-1"
    batch.mkdir(parents=True)
    (batch / "da50-n.json").write_text(json.dumps({"name": "da50-n", "endpoint": "gpu-l4-n"}))
    (batch / "da48-m.json").write_text(json.dumps({"name": "da48-m", "endpoint": "gpu-a100-m"}))
    poll = {"event": "poll", "balance": 5.0, "listed": ["gpu-l4-n", "gpu-a100-m"], "time": "t"}
    (batch / "guard.jsonl").write_text(json.dumps(poll) + "\n")
    assert runner.colab_state()["sessions"] == ["gpu-a100-m"]


def test_cancel_stops_a_job_left_by_an_earlier_server(rn: ConsolePaths) -> None:
    """A running job reloaded from disk has no thread here: Cancel kills its process group."""
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        jid = "j-left"
        d = runner.jobs_dir() / jid
        d.mkdir(parents=True)
        rec = {"id": jid, "kind": "ego.qa", "state": "running", "created": runner.now(),
               "pid": proc.pid}  # fmt: skip
        (d / "job.json").write_text(json.dumps(rec))
        runner.load_registry()
        assert runner.JOBREG[jid]["state"] == "running"
        runner.cancel(jid)
        proc.wait(timeout=10)
        _wait(lambda: runner.JOBREG[jid]["state"] == "cancelled", "cancelled")
    finally:
        if proc.poll() is None:
            proc.kill()
