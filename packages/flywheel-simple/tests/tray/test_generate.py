"""Seeds, shards, the append-only attempt log and QA rules of the generator; no simulator."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from flywheel_simple.tray.generate import (
    AttemptRow,
    append_attempt,
    batch_planner_versions,
    check_planner_version,
    check_visuals_revision,
    episode_qa,
    logged_seeds,
    next_seeds,
    read_log,
    shard_dir,
    split_attempts,
    summarize,
)
from flywheel_simple.tray.planner import PlannerConfig

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


def test_a_row_keeps_phase_times_and_carry_offset(tmp_path: Path) -> None:
    log = tmp_path / "gen_log.jsonl"
    phases = [("APPROACH_A", 0.0), ("CARRY", 12.5), ("LOWER", 21.04)]
    append_attempt(log, replace(ROW, phases=phases, carry_offset=(0.03, -0.02)))
    [row] = read_log(log)
    assert row["phases"] == [["APPROACH_A", 0.0], ["CARRY", 12.5], ["LOWER", 21.04]]
    assert row["carry_offset"] == [0.03, -0.02]


def test_a_row_without_them_logs_the_defaults(tmp_path: Path) -> None:
    log = tmp_path / "gen_log.jsonl"
    append_attempt(log, ROW)
    [row] = read_log(log)
    assert row["phases"] == [] and row["carry_offset"] == [0.0, 0.0]


def test_rows_before_da46_are_still_read_and_counted(tmp_path: Path) -> None:
    old = {k: v for k, v in asdict(ROW).items() if k not in ("phases", "carry_offset")}
    log = shard_dir(tmp_path, 0) / "gen_log.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(old) + "\n")
    append_attempt(log, replace(ROW, seed=1, phases=[("APPROACH_A", 0.0)]))
    assert logged_seeds(tmp_path) == {0, 1}
    counts = summarize(tmp_path)
    assert (counts["attempts"], counts["successes"], counts["qa_pass"]) == (2, 2, 2)


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


def test_a_jittered_run_refuses_a_plain_batch(tmp_path: Path) -> None:
    # DA-46: the jitter's tag is part of the version, so a plain batch is not topped up
    # with jittered episodes (or the other way round).
    from flywheel_simple.tray.planner import CarryJitter
    from flywheel_simple.tray.recorder import planner_version

    cfg = PlannerConfig.load()
    append_attempt(
        shard_dir(tmp_path, 0) / "gen_log.jsonl", replace(ROW, planner_version=planner_version(cfg))
    )
    check_planner_version(tmp_path, planner_version(cfg, CarryJitter()))
    with pytest.raises(RuntimeError, match="new --out"):
        check_planner_version(tmp_path, planner_version(cfg, CarryJitter(0.05, 0.05)))


def test_a_batch_of_other_visuals_is_refused(tmp_path: Path) -> None:
    # A batch started before the target zone was drawn must not be topped up with it.
    check_visuals_revision(tmp_path, "rev+zone1")  # a new batch
    append_attempt(shard_dir(tmp_path, 0) / "gen_log.jsonl", replace(ROW, visuals_revision="rev"))
    with pytest.raises(RuntimeError, match=r"\['rev'\].*renders rev\+zone1.*new --out"):
        check_visuals_revision(tmp_path, "rev+zone1")


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


def test_generate_refuses_a_batch_of_other_visuals_before_any_attempt(tmp_path: Path) -> None:
    from flywheel_simple.tray import generate as gen
    from flywheel_simple.tray.recorder import planner_version

    version = planner_version(PlannerConfig.load())
    row = replace(ROW, planner_version=version, visuals_revision="old")
    append_attempt(shard_dir(tmp_path, 0) / "gen_log.jsonl", row)
    before = (shard_dir(tmp_path, 0) / "gen_log.jsonl").read_bytes()
    with pytest.raises(RuntimeError, match="rendered with visuals"):
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
