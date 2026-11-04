"""The S2 launcher's job filter and exit status (DA-35 tasks 9-11)."""

from __future__ import annotations

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

    def launch(args: Any, jobs: list[dict[str, Any]]) -> list[Any]:
        for k, code in enumerate(codes):  # worker k logs its job, then ends with its code
            if code == 0:
                log_attempt(args.out / f"shard-{k:02d}", jobs[k])
            started.append(k)
        return [SimpleNamespace(wait=lambda c=code: c) for code in codes]

    monkeypatch.setattr(ledger, "job_ledger", no_ledger)
    monkeypatch.setattr(gen, "launch", launch)
    argv = ["--parents", str(parents(tmp_path, 4)), "--out", str(tmp_path / "out"), "--replay"]
    assert gen.main(argv) == status
    assert started == list(range(len(codes)))
    assert gen.main([*argv[:4], "--summarize"]) == 0
