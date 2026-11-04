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


def log_attempt(shard: Path, j: dict[str, Any]) -> None:
    shard.mkdir(parents=True, exist_ok=True)
    row = {"parent_episode": j["parent_id"], "level": j["level"], "seed": j["seed"],
           "gen_seed": j["gen_seed"], "outcome": "success", "failure": None,
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
    argv = ["--parents", str(parents(tmp_path, 4)), "--out", str(tmp_path / "out"), "--replay"]
    assert gen.main([*argv, "--poll-s", "0", "--max-restarts", "0"]) == status
    assert started == list(range(len(codes)))
    assert gen.main([*argv[:4], "--summarize"]) == 0


@pytest.mark.parametrize(("last", "status"), [([0, 0], 0), (["stalled"], 1), ([0, -9], 1)])
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


class FakeWorker:
    """Logs its jobs one per poll; `crash_after` ends it with -11, `hang_after` stops logging."""

    def __init__(self, shard: Path, jobs: list[dict[str, Any]], crash_after: int | None = None,
                 hang_after: int | None = None) -> None:  # fmt: skip
        self.shard, self.jobs, self.done = shard, jobs, 0
        self.crash_after, self.hang_after, self.killed = crash_after, hang_after, False

    def poll(self) -> int | None:
        if self.killed:
            return -9
        if self.crash_after is not None and self.done == self.crash_after:
            return -11
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
    gen: ModuleType, tmp_path: Path, faults: list[dict[str, int]], max_restarts: int = 3
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
