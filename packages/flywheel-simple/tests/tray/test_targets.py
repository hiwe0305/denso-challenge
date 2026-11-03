"""Failure-targeted seed planning and its shards (DA-33 Task 10); no simulator."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from flywheel_simple.tray import TrayConfig
from flywheel_simple.tray.generate import AttemptRow, append_attempt, shard_dir, targeted_jobs
from flywheel_simple.tray.randomize import sample_episode, split_of
from flywheel_simple.tray.targets import (
    PURPOSE,
    Condition,
    distance,
    load_conditions,
    plan_targets,
    read_targets,
    write_targets,
)

SEARCH = range(100_000, 101_500)
DEV_SEED = 1_000_007
C1 = {"cluster_id": "c1", "level": 1, "n": 5, "seed": DEV_SEED}
ROW = AttemptRow(
    seed=0, level=1, shard=0, success=False, failure="L-ONE-HAND", abort_reason=None,
    phase_reached="ABORT", steps=900, sim_s=18.0, wall_s=40.0, gpu_name="test",
    planner_version="p", visuals_revision="none", recorded=False, episode_index=None,
    qa="not_recorded",
)


def _cfg() -> TrayConfig:
    return TrayConfig.load()


def _write(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_targets_are_unused_train_seeds_never_the_dev_seed() -> None:
    conds = [Condition("c1", level=1, n=6, seed=DEV_SEED), Condition("c2", level=1, n=4, seed=5)]
    targets = plan_targets(_cfg(), conds, exclude={100_001}, search=SEARCH)
    seeds = [t.seed for t in targets]
    assert [t.cluster_id for t in targets] == ["c1"] * 6 + ["c2"] * 4
    assert len(set(seeds)) == 10 and all(s in SEARCH and split_of(s) == "train" for s in seeds)
    assert 100_001 not in seeds and DEV_SEED not in seeds
    assert all(t.purpose == PURPOSE and t.level == 1 for t in targets)


def test_targets_are_the_nearest_scenes_in_the_window() -> None:
    cond = Condition("c1", level=1, n=5, seed=DEV_SEED)
    dists = [t.distance for t in plan_targets(_cfg(), [cond], search=SEARCH)]
    assert dists == sorted(dists)
    ref = sample_episode(_cfg(), 1, DEV_SEED)
    others = [distance(cond, ref, sample_episode(_cfg(), 1, s)) for s in SEARCH]
    assert dists == [round(d, 4) for d in sorted(others)[:5]]


def test_an_explicit_tray_pose_finds_the_seed_that_produced_it() -> None:
    sample = sample_episode(_cfg(), 1, 100_777)
    pose = (sample.tray_pose.x, sample.tray_pose.y, sample.tray_pose.yaw)
    cond = Condition("far", level=1, n=1, tray_pose=pose)
    assert cond.match == ("tray",)
    [target] = plan_targets(_cfg(), [cond], search=SEARCH)
    assert (target.seed, target.distance) == (100_777, 0.0)


def test_the_search_window_must_stay_in_train() -> None:
    with pytest.raises(ValueError, match="train"):
        plan_targets(_cfg(), [Condition("a", 1, 1, seed=1)], search=range(999_990, 1_000_010))


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"cluster_id": "a", "level": 0, "n": 1, "seed": 1}, "level"),
        ({"cluster_id": "a", "level": 1, "n": 0, "seed": 1}, "positive"),
        ({"cluster_id": "a", "level": 1, "n": 1}, "seed"),
        ({"cluster_id": "a", "level": 1, "n": 1, "seed": 1, "match": ["colour"]}, "unknown"),
        ({"cluster_id": "a", "level": 2, "n": 1, "tray_pose": [0, 0, 0], "match": ["gap"]}, "left"),
    ],
)
def test_bad_conditions_are_refused(row: dict[str, object], message: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=message):
        load_conditions(_write(tmp_path / "c.jsonl", [row]))


def test_cluster_ids_must_be_unique(tmp_path: Path) -> None:
    rows = [{"cluster_id": "a", "level": 1, "n": 1, "seed": s} for s in (1, 2)]
    with pytest.raises(ValueError, match="unique"):
        load_conditions(_write(tmp_path / "c.jsonl", rows))


def test_the_plan_is_written_once_and_refuses_other_conditions(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    conds = _write(tmp_path / "c.jsonl", [C1])
    plan = write_targets(out, conds, search=SEARCH)
    assert write_targets(out, conds, search=range(150_000, 150_010)) == plan == read_targets(out)
    other = _write(tmp_path / "d.jsonl", [{**C1, "n": 4}])
    with pytest.raises(ValueError, match="other conditions"):
        write_targets(out, other, search=SEARCH)


def test_targeted_jobs_split_the_plan_by_shard_and_skip_logged_seeds(tmp_path: Path) -> None:
    out = tmp_path / "batch"
    conds = _write(tmp_path / "c.jsonl", [C1])
    plan = write_targets(out, conds, search=SEARCH)
    assert [j[0] for j in targeted_jobs(out, shard=1, workers=2)] == [plan[1].seed, plan[3].seed]
    append_attempt(shard_dir(out, 0) / "gen_log.jsonl", replace(ROW, seed=plan[2].seed))
    jobs = targeted_jobs(out, shard=0, workers=2)
    assert jobs == [(t.seed, 1, PURPOSE, "c1") for t in (plan[0], plan[4])]
