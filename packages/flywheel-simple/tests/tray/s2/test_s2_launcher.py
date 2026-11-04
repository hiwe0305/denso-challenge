"""The S2 launcher: job filter, exit status, worker supervisor and empty-dataset set-aside
(DA-35 tasks 9-12)."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "s2" / "generate_s2.py"


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_s2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(i: int) -> dict[str, Any]:
    return {"parent_id": f"p/shard-00/{i}", "level": 1, "seed": 100 + i, "gen_seed": i}


def log_attempt(shard: Path, j: dict[str, Any], outcome: str = "success") -> None:
    shard.mkdir(parents=True, exist_ok=True)
    row = {"parent_episode": j["parent_id"], "level": j["level"], "seed": j["seed"],
           "gen_seed": j["gen_seed"], "outcome": outcome, "failure": None,
           "wall_s": 90.0, "sim_s": 30.0}  # fmt: skip
    with (shard / "attempts.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def parents(tmp_path: Path, count: int) -> Path:
    path = tmp_path / "parents"
    path.mkdir()
    rows = [{"parent_id": j["parent_id"], "level": j["level"], "seed": j["seed"]}
            for j in map(job, range(count))]  # fmt: skip
    (path / "s2_segments.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_an_interrupted_job_is_still_pending(gen: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "out"
    log_attempt(out / "shard-00", job(0))
    log_attempt(out / "shard-00", job(1), outcome="interrupted")
    log_attempt(out / "shard-00", job(2), outcome="failure")  # ran to an outcome: done
    args = SimpleNamespace(out=out)
    assert [j["gen_seed"] for j in gen.pending(args, [job(i) for i in range(3)])] == [1]


def test_pending_ignores_logged_jobs_outside_the_list(gen: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "out"
    log_attempt(out / "shard-00", job(1))
    log_attempt(out / "shard-01", job(9))  # an earlier, longer list
    args = SimpleNamespace(out=out)
    assert [j["gen_seed"] for j in gen.pending(args, [job(i) for i in range(3)])] == [0, 2]


@pytest.mark.parametrize(("codes", "status"), [([0, 0], 0), ([0, -11], 1), ([1], 1), ([], 0)])
def test_any_failed_worker_fails_the_batch(
    gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, codes: list[int], status: int
) -> None:
    from flywheel.data import ledger

    @contextlib.contextmanager
    def no_ledger(*_: Any, **__: Any) -> Iterator[Any]:
        yield SimpleNamespace(notes=[], run_plan_id="rp", job_id="job")

    started: list[int] = []

    def launch(args: Any, jobs: list[dict[str, Any]]) -> dict[int, Any]:
        for k, code in enumerate(codes):  # worker k logs its job, then ends with its code
            if code == 0:
                log_attempt(args.out / f"shard-{k:02d}", jobs[k])
            started.append(k)
        return {k: SimpleNamespace(poll=lambda c=code: c) for k, code in enumerate(codes)}

    monkeypatch.setattr(ledger, "job_ledger", no_ledger)
    monkeypatch.setattr(gen, "launch", launch)
    argv = ["--parents", str(parents(tmp_path, len(codes))), "--out", str(tmp_path / "out"),
            "--replay"]  # fmt: skip
    assert gen.main([*argv, "--poll-s", "0", "--max-restarts", "0"]) == status
    assert started == list(range(len(codes)))
    assert gen.main([*argv[:4], "--summarize"]) == 0


def test_a_worker_that_exits_0_with_jobs_left_fails_the_batch(
    gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    """An interrupted session exits 0 before its jobs are done: the batch must not pass."""
    from flywheel.data import ledger

    @contextlib.contextmanager
    def no_ledger(*_: Any, **__: Any) -> Iterator[Any]:
        yield SimpleNamespace(notes=[], run_plan_id="rp", job_id="job")

    def launch(args: Any, jobs: list[dict[str, Any]]) -> dict[int, Any]:
        log_attempt(args.out / "shard-00", jobs[0])  # one of three, then a clean exit
        return {0: SimpleNamespace(poll=lambda: 0)}

    monkeypatch.setattr(ledger, "job_ledger", no_ledger)
    monkeypatch.setattr(gen, "launch", launch)
    argv = ["--parents", str(parents(tmp_path, 3)), "--out", str(tmp_path / "out"), "--replay"]
    assert gen.main([*argv, "--poll-s", "0", "--max-restarts", "0"]) == 1
    assert "2 jobs not logged: rerun" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("last", "status"),
    [([0, 0], 0), (["stalled"], 1), ([0, -9], 1), (["stalled-done"], 0), ([0, "mismatch"], 1)],
)
def test_a_shard_counts_by_its_last_worker(
    gen: ModuleType, last: list[int | str], status: int
) -> None:
    assert gen.exit_status(last) == status


def dataset(shard: Path, name: str, episodes: bool) -> Path:
    meta = shard / "simple" / name / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text("{}")
    if episodes:
        (meta / "episodes.jsonl").write_text('{"episode_index": 0}\n')
    return meta.parent


def test_only_a_dataset_with_no_saved_episode_is_set_aside(gen: ModuleType, tmp_path: Path) -> None:
    empty = dataset(tmp_path / "shard-00", "Tray-v0", episodes=False)
    kept = dataset(tmp_path / "shard-01", "Tray-v0", episodes=True)
    old = dataset(tmp_path / "shard-00", "Tray-v0.empty-1104T1740", episodes=False)
    assert gen.set_aside_empty_datasets(tmp_path / "shard-00", "s") == [
        empty.with_name("Tray-v0.empty-s")
    ]
    assert gen.set_aside_empty_datasets(tmp_path / "shard-01", "s") == []
    assert (empty.with_name("Tray-v0.empty-s") / "meta" / "info.json").exists()
    assert kept.exists() and old.exists() and not empty.exists()


def saved_unlogged_episode(shard: Path) -> None:
    """What a worker leaves when it dies between saving an episode and logging it."""
    meta = shard / "simple" / "Tray-v0" / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text("{}")
    config = json.dumps({"flywheel": {"source_detail": "s2"}})
    (meta / "episodes.jsonl").write_text(
        json.dumps({"episode_index": 0, "environment_config": config}) + "\n"
    )


class FakeWorker:
    """Logs its jobs one per poll; `crash_after` ends it with -11 (`orphan`: leaving a saved,
    unlogged episode), `quit_after` with 0, `interrupt_after` with 0 after logging the next
    job as interrupted (a SIGINT'd session), `hang_after` stops logging."""

    def __init__(self, shard: Path, jobs: list[dict[str, Any]], crash_after: int | None = None,
                 quit_after: int | None = None, hang_after: int | None = None,
                 orphan: bool = False, interrupt_after: int | None = None) -> None:  # fmt: skip
        self.shard, self.jobs, self.done = shard, jobs, 0
        self.crash_after, self.quit_after, self.hang_after = crash_after, quit_after, hang_after
        self.orphan, self.interrupt_after, self.killed = orphan, interrupt_after, False

    def poll(self) -> int | None:
        if self.killed:
            return -9
        if self.interrupt_after is not None and self.done == self.interrupt_after:
            log_attempt(self.shard, self.jobs[self.done], outcome="interrupted")
            self.interrupt_after = None
            return 0
        if self.crash_after is not None and self.done == self.crash_after:
            if self.orphan and not (self.shard / "simple").exists():
                saved_unlogged_episode(self.shard)
            return -11
        if self.quit_after is not None and self.done == self.quit_after:
            return 0
        if self.hang_after is not None and self.done == self.hang_after:
            return None
        if self.done == len(self.jobs):
            return 0
        log_attempt(self.shard, self.jobs[self.done])
        self.done += 1
        return None

    def kill(self) -> None:
        self.killed = True

    def wait(self) -> int:
        return -9


Started = list[list[dict[str, Any]]]


def run(
    gen: ModuleType, tmp_path: Path, faults: list[dict[str, Any]], max_restarts: int = 3
) -> tuple[dict[int, list[Any]], Started]:
    """One shard; the n-th worker started gets faults[n] (later ones run clean)."""
    args = argparse.Namespace(out=tmp_path, workers=1, poll_s=1.0, stall_s=100.0,
                              max_restarts=max_restarts)  # fmt: skip
    clock = {"t": 0.0}
    started: Started = []

    def start(a: argparse.Namespace, k: int, mine: list[dict[str, Any]]) -> FakeWorker:
        shard = a.out / f"shard-{k:02d}"
        shard.mkdir(parents=True, exist_ok=True)
        (shard / "jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in mine))
        fault = faults[len(started)] if len(started) < len(faults) else {}
        started.append(mine)
        return FakeWorker(shard, mine, **fault)

    def sleep(s: float) -> None:
        clock["t"] += s

    procs = gen.launch(args, [job(i) for i in range(6)], start=start)
    # file mtimes are real time: the fake clock starts there and only moves forward
    clock["t"] = max(p.stat().st_mtime for p in tmp_path.rglob("*")) + 1
    ends = gen.supervise(args, procs, start=start, now=lambda: clock["t"], sleep=sleep)
    return ends, started


def logged(tmp_path: Path) -> list[str]:
    rows = (tmp_path / "shard-00" / "attempts.jsonl").read_text().splitlines()
    return [json.loads(r)["parent_episode"] for r in rows]


def test_a_crashed_worker_restarts_on_its_unlogged_jobs(gen: ModuleType, tmp_path: Path) -> None:
    ends, started = run(gen, tmp_path, [{"crash_after": 2}])
    assert ends == {0: [-11, 0]}
    assert [j["gen_seed"] for j in started[1]] == [2, 3, 4, 5]
    assert logged(tmp_path) == [f"p/shard-00/{i}" for i in range(6)]
    event = json.loads((tmp_path / "supervisor.jsonl").read_text())
    assert (event["end"], event["restart"], event["pending"]) == (-11, 1, 4)


def test_a_stalled_worker_is_killed_and_restarted(gen: ModuleType, tmp_path: Path) -> None:
    ends, started = run(gen, tmp_path, [{"hang_after": 3}])
    assert ends == {0: ["stalled", 0]}
    assert [j["gen_seed"] for j in started[1]] == [3, 4, 5]
    assert len(logged(tmp_path)) == 6


def test_restarts_stop_at_the_cap(gen: ModuleType, tmp_path: Path) -> None:
    ends, started = run(gen, tmp_path, [{"crash_after": 0}] * 5, max_restarts=2)
    assert ends == {0: [-11, -11, -11]}
    assert len(started) == 3
    assert len((tmp_path / "supervisor.jsonl").read_text().splitlines()) == 2


def test_a_clean_batch_starts_nothing_again(gen: ModuleType, tmp_path: Path) -> None:
    ends, started = run(gen, tmp_path, [])
    assert ends == {0: [0]} and len(started) == 1
    assert not (tmp_path / "supervisor.jsonl").exists()
    summary = gen.summarize(tmp_path, None)
    assert summary["worker_restarts"] == 0 and summary["attempts"] == 6


def test_a_worker_that_exits_0_early_restarts_on_its_unlogged_jobs(
    gen: ModuleType, tmp_path: Path
) -> None:
    ends, started = run(gen, tmp_path, [{"quit_after": 2}])
    assert ends == {0: [0, 0]}
    assert [j["gen_seed"] for j in started[1]] == [2, 3, 4, 5]
    assert len(logged(tmp_path)) == 6


def test_a_stall_after_every_job_is_logged_is_done(gen: ModuleType, tmp_path: Path) -> None:
    ends, started = run(gen, tmp_path, [{"hang_after": 6}])
    assert ends == {0: ["stalled-done"]} and len(started) == 1
    assert gen.exit_status([e[-1] for e in ends.values()]) == 0
    assert not (tmp_path / "supervisor.jsonl").exists()


def test_a_stall_is_timed_by_the_attempts_log_not_the_worker_log(
    gen: ModuleType, tmp_path: Path
) -> None:
    shard = tmp_path / "shard-00"
    log_attempt(shard, job(0))
    (shard / "worker.log").write_text("still warning\n")
    t = (shard / "attempts.jsonl").stat().st_mtime
    assert gen.last_progress(shard, t - 50) == t
    assert gen.last_progress(shard, t + 50) == t + 50


def test_a_shard_whose_dataset_and_log_disagree_is_not_resumed(
    gen: ModuleType, tmp_path: Path
) -> None:
    ends, started = run(gen, tmp_path, [{"crash_after": 2, "orphan": True}])
    assert ends == {0: [-11, "mismatch"]} and len(started) == 1
    assert gen.exit_status([e[-1] for e in ends.values()]) == 1
    assert gen.summarize(tmp_path, None)["shard_mismatches"] == {
        "shard-00": ["episodes [0] saved but no attempt logs them"]
    }


def test_the_launcher_refuses_to_resume_a_mismatched_shard(
    gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved_unlogged_episode(tmp_path / "out" / "shard-00")
    monkeypatch.setattr(gen, "launch", lambda *_: pytest.fail("a worker started"))
    argv = ["--parents", str(parents(tmp_path, 2)), "--out", str(tmp_path / "out"), "--replay"]
    assert gen.main(argv) == 1


def test_a_kill_reaches_the_workers_process_group(gen: ModuleType) -> None:
    import subprocess
    import sys
    import time

    child = "import subprocess, sys, time; g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); print(g.pid, flush=True); time.sleep(60)"  # noqa: E501
    proc = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE,
                            start_new_session=True)  # fmt: skip
    assert proc.stdout is not None
    grandchild = Path(f"/proc/{int(proc.stdout.readline())}/stat")
    worker = gen.GroupWorker(proc)
    worker.kill()
    assert worker.wait() == -9

    def dead() -> bool:  # gone, or a zombie waiting for its new parent to reap it
        try:
            return grandchild.read_text().rsplit(")", 1)[1].split()[0] in "ZX"
        except (FileNotFoundError, ProcessLookupError):  # reaped, during or before the read
            return True

    deadline = time.monotonic() + 5
    while not dead() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert dead()


def test_a_sigint_worker_restarts_on_the_job_it_was_interrupted_in(
    gen: ModuleType, tmp_path: Path
) -> None:
    ends, started = run(gen, tmp_path, [{"interrupt_after": 2}])
    assert ends == {0: [0, 0]}
    assert [j["gen_seed"] for j in started[1]] == [2, 3, 4, 5]
    outcomes = [json.loads(r)["outcome"] for r in
                (tmp_path / "shard-00" / "attempts.jsonl").read_text().splitlines()]  # fmt: skip
    assert outcomes.count("interrupted") == 1 and outcomes.count("success") == 6
