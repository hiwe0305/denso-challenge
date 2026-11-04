"""The parents launcher fails the batch on a dead worker, an unlogged condition or a
mismatched shard (DA-35 task 12, the -9 of parents-1104)."""

from __future__ import annotations

import contextlib
import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "pico" / "generate_parents.py"  # noqa: E501


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_parents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log_attempt(shard: Path, level: int, seed: int) -> None:
    shard.mkdir(parents=True, exist_ok=True)
    row = {"level": level, "seed": seed, "outcome": "failure", "failure": "L-TRAY-TILT",
           "steps_reached": 3, "sim_s": 20.0, "wall_s": 60.0, "episode_index": None}  # fmt: skip
    with (shard / "attempts.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


@pytest.fixture
def no_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    from flywheel.data import ledger

    @contextlib.contextmanager
    def fake(*_: Any, **__: Any) -> Iterator[Any]:
        yield SimpleNamespace(notes=[], run_plan_id="rp", job_id="job")

    monkeypatch.setattr(ledger, "job_ledger", fake)


@pytest.mark.parametrize(
    ("codes", "logs", "status"),
    [([0, 0], [0, 1], 0), ([0, -9], [0], 1), ([0, 0], [0], 1)],
    ids=["clean", "killed worker", "exit 0 with a condition left"],
)
@pytest.mark.usefixtures("no_ledger")
def test_a_batch_passes_only_when_every_condition_is_logged_by_a_clean_worker(
    gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, codes: list[int],
    logs: list[int], status: int,
) -> None:  # fmt: skip
    def launch(args: Any) -> list[Any]:
        for k in logs:  # worker k logs seed 100 + k
            log_attempt(args.out / f"shard-{k:02d}", 0, 100 + k)
        return [SimpleNamespace(wait=lambda c=c: c) for c in codes]

    monkeypatch.setattr(gen, "launch", launch)
    argv = ["--out", str(tmp_path), "--levels", "0", "--seeds", "100-101", "--workers", "2"]
    assert gen.main(argv) == status


@pytest.mark.usefixtures("no_ledger")
def test_a_mismatched_shard_is_not_resumed(
    gen: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = tmp_path / "shard-00" / "simple" / "Tray-v0" / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text("{}")
    (meta / "episodes.jsonl").write_text('{"episode_index": 0}\n')  # saved, never logged
    monkeypatch.setattr(gen, "launch", lambda _: pytest.fail("a worker started"))
    assert gen.main(["--out", str(tmp_path), "--levels", "0", "--seeds", "100"]) == 1
    assert gen.summarize(tmp_path, None)["shard_mismatches"] == {
        "shard-00": [
            "episodes [0] saved but no attempt logs them",
            "episodes [0] have no flywheel block",
        ]
    }
