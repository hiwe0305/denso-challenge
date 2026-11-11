"""Chunk order, finished episodes, reruns and resume of the eval batch, on CPU (DA-34 task 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray.eval_batch import (
    Chunk,
    chunk_plan,
    finished,
    missing,
    phases_for,
    run_batch,
)


def rows(counts: dict[int, int]) -> list[dict[str, Any]]:
    """Condition rows in plan order: level 0 first, seeds from 1000100."""
    return [
        {"level": level, "seed": 1000100 + i}
        for level in sorted(counts)
        for i in range(counts[level])
    ]


def test_levels_1_and_2_interleave_before_level_0() -> None:
    plan = chunk_plan(rows({0: 30, 1: 120, 2: 120}), 10)
    assert len(plan) == 27 and sum(len(c.seeds) for c in plan) == 270
    assert [c.id for c in plan[:4]] == ["l1-000", "l2-000", "l1-010", "l2-010"]
    assert [c.id for c in plan[-3:]] == ["l0-000", "l0-010", "l0-020"]
    assert plan[2].seeds == tuple(range(1000110, 1000120)) and plan[2].start == 10


def test_a_short_last_chunk_and_unequal_levels() -> None:
    plan = chunk_plan(rows({0: 3, 1: 25, 2: 10}), 10)
    assert [(c.id, len(c.seeds)) for c in plan] == [
        ("l1-000", 10),
        ("l2-000", 10),
        ("l1-010", 10),
        ("l1-020", 5),
        ("l0-000", 3),
    ]


def test_a_level_outside_the_phases_is_refused() -> None:
    with pytest.raises(ValueError, match="levels"):
        chunk_plan(rows({0: 3, 1: 3, 3: 3}), 10)


def write_episode(attempt: Path, chunk: Chunk, episode: int, stats: bool = True) -> None:
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "eval").mkdir(exist_ok=True)
    row = {"seed": chunk.seed_of(episode), "level": chunk.level, "success": False}
    with (attempt / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    if stats:
        with (attempt / "eval/eval_stats.txt").open("a") as f:
            f.write(f"episode_{episode}: False \n")


CHUNK = Chunk("l1-010", 1, 10, tuple(range(1000110, 1000114)))


def test_an_episode_is_finished_with_both_its_stats_line_and_its_outcome(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt-0"
    write_episode(attempt, CHUNK, 10)
    write_episode(attempt, CHUNK, 11, stats=False)  # cut short: logged on close, no stats line
    assert sorted(finished(CHUNK, attempt)) == [10]


def test_an_outcome_of_another_condition_is_an_error(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt-0"
    write_episode(attempt, Chunk("l2-010", 2, 10, CHUNK.seeds), 10)
    with pytest.raises(ValueError, match="level 2"):
        finished(CHUNK, attempt)


def test_a_crash_reruns_from_the_first_missing_episode(tmp_path: Path) -> None:
    calls: list[tuple[str, int, int, str]] = []

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        calls.append((chunk.id, start, n, attempt.name))
        last = start + n if attempt.name != "attempt-0" else start + 2  # first attempt crashes
        for episode in range(start, last):
            write_episode(attempt, chunk, episode)
        return 0 if last == start + n else 139

    assert run_batch(tmp_path, [CHUNK], launch, log=lambda _: None) == 0
    assert calls == [("l1-010", 10, 4, "attempt-0"), ("l1-010", 12, 2, "attempt-1")]
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert [(r["exit"], r["finished"], r["missing"]) for r in runs] == [
        (139, [10, 11], [12, 13]),
        (0, [12, 13], []),
    ]
    assert runs[1]["seeds"] == [1000112, 1000113]
    assert missing(tmp_path, CHUNK) == []
    assert run_batch(tmp_path, [CHUNK], launch, log=lambda _: None) == 0  # resume: nothing left
    assert len(calls) == 2


def test_the_batch_stops_when_a_chunk_keeps_failing(tmp_path: Path) -> None:
    later = Chunk("l2-010", 2, 10, CHUNK.seeds)
    seen = []

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        seen.append(chunk.id)
        attempt.mkdir(parents=True)
        return 1

    assert run_batch(tmp_path, [CHUNK, later], launch, max_attempts=2, log=lambda _: None) == 1
    assert seen == ["l1-010", "l1-010"]


def test_phases_are_cut_to_the_levels_of_a_smaller_set() -> None:
    assert phases_for([{"level": 1}, {"level": 1}]) == ((1,),)
    assert phases_for([{"level": 0}, {"level": 2}]) == ((2,), (0,))
    with pytest.raises(ValueError):
        phases_for([{"level": 3}])


def test_max_chunks_runs_the_first_chunks_of_the_order_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # branch B's stage 1 (tray.md 18.2): the first 6 chunks, 30 level 1 and 30 level 2
    from flywheel_psi0.tray import eval_batch
    from flywheel_psi0.tray.eval_set import conditions_sha256

    conditions = [
        row | {"environment_config": {"flywheel": {"run_plan_id": "rp_a04c14e79dfd"}}}
        for row in rows({0: 30, 1: 120, 2: 120})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    common = [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run",
    ]  # fmt: skip
    assert eval_batch.main([*common, "--max-chunks", "6"]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in printed] == [
        "l1-000", "l2-000", "l1-010", "l2-010", "l1-020", "l2-020",
    ]  # fmt: skip
    assert {line.split()[1] for line in printed} == {"1000100", "1000110", "1000120"}
    assert eval_batch.main(common) == 0
    assert len(capsys.readouterr().out.splitlines()) == 27  # without it: the whole order
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--max-chunks", "0"])


def test_chunks_splits_stage_1_into_lanes_that_share_one_out_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # tray.md 20.15: stage 1 of C70_R1 on three serve lanes, two chunks each
    from flywheel_psi0.tray import eval_batch
    from flywheel_psi0.tray.eval_set import conditions_sha256

    conditions = [
        row | {"environment_config": {"flywheel": {"run_plan_id": "rp_a04c14e79dfd"}}}
        for row in rows({0: 30, 1: 120, 2: 120})
    ]
    (tmp_path / "conditions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in conditions)
    )
    common = [
        "--set", str(tmp_path), "--conditions-sha256", conditions_sha256(conditions),
        "--out", str(tmp_path / "out"), "--simple-python", "python", "--pythonpath", "x",
        "--dry-run", "--max-chunks", "6",
    ]  # fmt: skip
    lanes = []
    for lane in ("l2-000,l1-000", "l1-010,l2-010", "l1-020,l2-020"):
        assert eval_batch.main([*common, "--chunks", lane]) == 0
        lanes.append([line.split()[0] for line in capsys.readouterr().out.splitlines()])
    assert lanes[0] == ["l1-000", "l2-000"]  # the plan's order, not the flag's
    assert sorted(c for lane in lanes for c in lane) == sorted(
        ["l1-000", "l2-000", "l1-010", "l2-010", "l1-020", "l2-020"]
    )
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--chunks", "l1-030"])  # past --max-chunks: not stage 1
    with pytest.raises(SystemExit):
        eval_batch.main([*common, "--chunks", "l1-000,l1-000"])
