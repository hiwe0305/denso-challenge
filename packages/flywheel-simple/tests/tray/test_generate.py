"""Seeds, shards, the append-only attempt log and QA rules of the generator; no simulator."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from flywheel_simple.tray.generate import (
    AttemptRow,
    append_attempt,
    batch_planner_versions,
    check_planner_version,
    episode_qa,
    logged_seeds,
    next_seeds,
    read_log,
    shard_dir,
    split_attempts,
)

ROW = AttemptRow(
    seed=0,
    level=1,
    shard=0,
    success=True,
    failure=None,
    abort_reason=None,
    phase_reached="DONE",
    steps=1500,
    sim_s=30.0,
    wall_s=45.0,
    gpu_name="test",
    planner_version="p",
    visuals_revision="none",
    recorded=True,
    episode_index=0,
    qa="pass",
)


def test_next_seeds_skips_logged_and_stays_in_train() -> None:
    assert next_seeds({0, 1}, start=0, n=3) == [2, 3, 4]
    with pytest.raises(ValueError, match="train"):
        next_seeds(set(), start=999_999, n=2)


def test_shards_take_disjoint_seeds() -> None:
    shards = [next_seeds(set(), start=10, n=3, shard=k, workers=4) for k in range(4)]
    assert shards[1] == [11, 15, 19]
    flat = [s for seeds in shards for s in seeds]
    assert len(set(flat)) == len(flat) == 12


def test_split_attempts_shares_n_over_workers() -> None:
    shares = split_attempts(130, 22)
    assert sum(shares) == 130 and max(shares) - min(shares) <= 1


def test_log_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "gen_log.jsonl"
    append_attempt(log, ROW)
    before = log.read_bytes()
    append_attempt(log, replace(ROW, seed=1))
    assert log.read_bytes().startswith(before)
    assert [r["seed"] for r in read_log(log)] == [0, 1]


def test_logged_seeds_cover_every_shard(tmp_path: Path) -> None:
    append_attempt(shard_dir(tmp_path, 0) / "gen_log.jsonl", ROW)
    append_attempt(shard_dir(tmp_path, 3) / "gen_log.jsonl", replace(ROW, seed=7, shard=3))
    assert logged_seeds(tmp_path) == {0, 7}


def test_a_batch_of_another_planner_version_is_refused(tmp_path: Path) -> None:
    check_planner_version(tmp_path, "p")  # a new batch
    append_attempt(shard_dir(tmp_path, 0) / "gen_log.jsonl", ROW)
    check_planner_version(tmp_path, "p")  # resuming the same planner
    append_attempt(shard_dir(tmp_path, 3) / "gen_log.jsonl",
                   replace(ROW, seed=7, shard=3, planner_version="old", recorded=False))
    assert batch_planner_versions(tmp_path) == {"p", "old"}
    with pytest.raises(RuntimeError, match=r"\['old'\].*new --out"):
        check_planner_version(tmp_path, "p")


def test_generate_refuses_a_batch_of_another_planner_before_any_attempt(tmp_path: Path) -> None:
    # Resume goes by seed only: without this check a planner-5 run would top up a
    # planner-4 batch and the release would mix them (D-28). The check runs before the
    # simulator imports, so this needs no SIMPLE venv.
    from flywheel_simple.tray import generate as gen

    append_attempt(shard_dir(tmp_path, 0) / "gen_log.jsonl", replace(ROW, planner_version="old"))
    before = (shard_dir(tmp_path, 0) / "gen_log.jsonl").read_bytes()
    with pytest.raises(RuntimeError, match="generated with planner"):
        gen.generate(tmp_path, 1, level=1, seed_start=100, allow_plain=True)
    assert (shard_dir(tmp_path, 0) / "gen_log.jsonl").read_bytes() == before


@pytest.mark.parametrize(
    ("kwargs", "verdict"),
    [
        ({}, "pass"),
        ({"success": False}, "not_success"),
        ({"rows": 200}, "too_short"),
        ({"rows": 50 * 91}, "too_long"),
        ({"has_nan": True}, "nan"),
        ({"video_frames": 1499}, "video_rows_mismatch"),
        ({"phases": ["APPROACH_A", "REACH", "GRASP", "LIFT"]}, "phases_incomplete"),
    ],
)
def test_episode_qa_names_the_first_failing_check(kwargs: dict, verdict: str) -> None:  # type: ignore[type-arg]
    args = {
        "success": True,
        "rows": 1500,
        "video_frames": 1500,
        "has_nan": False,
        "phases": ["APPROACH_A", "REACH", "GRASP", "LIFT", "CARRY", "LOWER", "RELEASE", "RETREAT"],
    }
    args.update(kwargs)
    if "rows" in kwargs and "video_frames" not in kwargs:
        args["video_frames"] = args["rows"]
    assert episode_qa(**args) == verdict
