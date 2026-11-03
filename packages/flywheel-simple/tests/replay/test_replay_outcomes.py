"""The replay adapter's comparison and sharding, without SIMPLE (DA-17 task 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.replay.compare import GROUPS, hand_event_offset, joint_order, outcome
from flywheel_simple.replay.outcomes import (
    OUTCOMES,
    SUMMARY,
    Shard,
    env_id_of,
    episode_indices,
    replay_lerobot,
    shards,
    stage,
)

ENV = "simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0"


def states(length: int = 100, close_at: int = 40) -> np.ndarray:
    """32-D recorded states: arms on a slow sine, right hand closing at close_at."""
    t = np.arange(length)[:, None]
    s = np.zeros((length, 32))
    s[:, 14:31] = 0.3 * np.sin(t / 15 + np.arange(17))
    s[close_at:, 7:14] = 0.8
    return s


def replay_of(recorded: np.ndarray, shift: int = 0) -> np.ndarray:
    """What a perfect replay returns: the state after each action, delayed by shift."""
    after = recorded[1:, :31]
    return np.concatenate([np.repeat(after[:1], shift, axis=0), after])[: len(after)]


def test_perfect_replay_has_zero_error_and_no_offset() -> None:
    rec = states()
    line = outcome(5, rec, replay_of(rec), True)
    assert line["state_error_by_group"] == {g: 0.0 for g in GROUPS}
    assert line["hand_event_offset_steps"] == 0
    assert (line["episode_index"], line["success"]) == (5, True)
    assert (line["replayed_frames"], line["recorded_frames"]) == (99, 100)


def test_late_replay_shows_the_lag_and_the_peak() -> None:
    rec = states()
    line = outcome(5, rec, replay_of(rec, shift=4), False)
    assert line["hand_event_offset_steps"] == 4
    assert line["state_error_by_group"]["hand"] == pytest.approx(0.8)
    assert line["state_error_peak_frame_by_group"]["hand"] == 40
    assert line["success"] is False


def test_replay_that_never_closes_the_hand_is_a_lower_bound() -> None:
    rec = states()
    rep = replay_of(rec)
    rep[:, 7:14] = 0.0
    assert hand_event_offset(rec[:, :31], rep) == 99 + 1 - 40


def test_hand_that_does_not_move_has_no_event() -> None:
    rec = states()
    rec[:, 7:14] = 0.05
    assert outcome(0, rec, replay_of(rec), True)["hand_event_offset_steps"] is None


def test_replay_longer_than_the_recording_is_cut() -> None:
    rec = states()
    rep = np.concatenate([replay_of(rec), np.ones((10, 31))])
    line = outcome(0, rec, rep, True)
    assert line["state_error_by_group"]["arm"] == 0.0 and line["replayed_frames"] == 109


def test_joint_order_by_name() -> None:
    assert joint_order(["b", "a", "c"] + [f"x{i}" for i in range(29)],
                       ["a", "b", "c"] + [f"x{i}" for i in range(29)])[:3] == [1, 0, 2]
    with pytest.raises(KeyError, match="lack"):
        joint_order(["a"], ["a", "b"])


def test_shards_are_contiguous_and_cover_all() -> None:
    plan = shards(list(range(10)), 4)
    assert [s.episodes for s in plan] == [[0, 1, 2], [3, 4, 5], [6, 7], [8, 9]]
    assert [s.episodes for s in shards([0, 1], 8)] == [[0], [1]]


def dataset(root: Path, count: int = 3) -> Path:
    (root / "meta").mkdir(parents=True)
    info = {"chunks_size": 1000,
            "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"}
    (root / "meta" / "info.json").write_text(json.dumps(info))
    rows = [json.dumps({"episode_index": i, "length": 5}) for i in range(count)]
    (root / "meta" / "episodes.jsonl").write_text("\n".join(rows) + "\n")
    (root / "meta" / "replay.txt").write_text("0: True\n")
    for i in range(count):
        path = root / "data" / "chunk-000" / f"episode_{i:06d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"parquet")
    return root


def test_stage_links_only_the_shard_and_drops_replay_txt(tmp_path: Path) -> None:
    root = dataset(tmp_path / "G1WholebodyLocomotionPickBetweenTablesTeleop-v0")
    staged = stage(root, Shard("s", [1, 2]), tmp_path / "stage")
    files = sorted(p.name for p in (staged / "data" / "chunk-000").iterdir())
    assert files == ["episode_000001.parquet", "episode_000002.parquet"]
    assert (staged / "data" / "chunk-000" / files[0]).is_symlink()
    assert not (staged / "meta" / "replay.txt").exists()
    assert (root / "meta" / "replay.txt").exists()
    assert env_id_of(root) == ENV and episode_indices(root) == [0, 1, 2]


def test_gaps_in_the_episode_indices_are_refused(tmp_path: Path) -> None:
    root = dataset(tmp_path / "d")
    (root / "meta" / "episodes.jsonl").write_text('{"episode_index": 0}\n{"episode_index": 2}\n')
    with pytest.raises(ValueError, match="not contiguous"):
        episode_indices(root)


FAKE_RUN = """
import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
start, n = int(args["--episode-start"]), int(args["--num-episodes"])
with open(args["--outcomes"], "a") as f:
    for i in range(start, start + n):
        if i != {skip}:
            f.write(json.dumps({{"episode_index": i, "success": True}}) + "\\n")
"""


def fake_python(tmp_path: Path, skip: int = -1) -> str:
    """A python that runs a fake `flywheel_simple.replay.run` instead of SIMPLE."""
    pkg = tmp_path / "fake" / "flywheel_simple" / "replay"
    pkg.mkdir(parents=True)
    (pkg.parent / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "run.py").write_text(FAKE_RUN.format(skip=skip))
    script = tmp_path / "python"
    script.write_text(f"#!/bin/sh\nPYTHONPATH={tmp_path / 'fake'} exec {sys.executable} \"$@\"\n")
    script.chmod(0o755)
    return str(script)


def test_replay_lerobot_merges_the_shards_in_order(tmp_path: Path) -> None:
    root = dataset(tmp_path / "G1WholebodyLocomotionPickBetweenTablesTeleop-v0", count=5)
    path = replay_lerobot(root, tmp_path / "work", 2, python=fake_python(tmp_path), stagger_s=0)
    indices = [json.loads(line)["episode_index"] for line in path.read_text().splitlines()]
    assert path.name == OUTCOMES and indices == [0, 1, 2, 3, 4]
    summary = json.loads((tmp_path / "work" / SUMMARY).read_text())
    assert summary["replayed"] == 5 and summary["workers"] == 2 and summary["env_id"] == ENV


def test_an_episode_without_outcome_raises_after_writing(tmp_path: Path) -> None:
    root = dataset(tmp_path / "G1WholebodyLocomotionPickBetweenTablesTeleop-v0", count=3)
    with pytest.raises(RuntimeError, match="1 episodes without"):
        replay_lerobot(root, tmp_path / "work", 1, python=fake_python(tmp_path, skip=1),
                       stagger_s=0)
    summary = json.loads((tmp_path / "work" / SUMMARY).read_text())
    assert summary["missing"] == [1] and summary["replayed"] == 2
