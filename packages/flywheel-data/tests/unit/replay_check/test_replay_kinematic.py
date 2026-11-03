"""Kinematic replay of one episode lists the frames of each fault (DA-17 task 1, AC 1)."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.config import ConfigError
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.replay_check.kinematic import DEG_PER_RAD, check_kinematic, joint_dims
from flywheel.data.replay_check.thresholds import load_thresholds
from replay_data import FPS, clean_frames, g1_layout, loose_thresholds

LAYOUT = g1_layout()
NAMES = [d.name for d in LAYOUT.dimensions]
ARM = NAMES.index("right_elbow_joint")


def check(frames: EpisodeFrames) -> dict[str, list[int]]:
    report = check_kinematic(frames, LAYOUT, loose_thresholds(), episode_id="ep_1", fps=FPS)
    assert report.mode == "kinematic" and report.episode_id == "ep_1"
    return {issue.code: issue.frames for issue in report.issues}


def with_action(frames: EpisodeFrames, dim: int, values: np.ndarray) -> EpisodeFrames:
    action = frames.action.copy()
    action[:, dim] = values
    return dataclasses.replace(frames, action=action)


def test_joints_are_the_limited_dims_the_states_hold() -> None:
    assert joint_dims(LAYOUT, 32) == list(range(31))
    assert joint_dims(LAYOUT, 14) == list(range(14))


@pytest.mark.parametrize("index", range(5))
def test_clean_episode_has_no_issue(index: int) -> None:
    assert check(clean_frames(index)) == {}


def test_timestamp_moved_two_frames_lists_every_frame() -> None:
    frames = clean_frames(0)
    moved = dataclasses.replace(frames, timestamp=frames.timestamp + 2 / FPS)
    assert check(moved) == {"timestamp_offset": list(range(200))}


def test_timestamp_nan_is_an_offset_not_an_error() -> None:
    frames = clean_frames(0)
    stamps = frames.timestamp.copy()
    stamps[5] = math.nan
    assert check(dataclasses.replace(frames, timestamp=stamps)) == {"timestamp_offset": [5]}


def test_action_past_a_limit_lists_its_frames() -> None:
    frames = clean_frames(0)
    high = LAYOUT.dimensions[ARM].limit_high
    assert high is not None
    values = frames.action[:, ARM].copy()
    values[[10, 11, 50]] = high + 0.1
    assert check(with_action(frames, ARM, values)) == {"joint_limit": [10, 11, 50]}


def test_action_in_degrees_is_a_unit_and_a_limit_issue() -> None:
    frames = clean_frames(0)
    issues = check(with_action(frames, ARM, frames.action[:, ARM] * DEG_PER_RAD))
    assert set(issues) == {"unit_deg_rad", "joint_limit"}
    assert issues["joint_limit"] == list(range(200))


def test_small_joint_in_degrees_is_caught_by_its_spread() -> None:
    # A joint that stays under 2 pi in degrees: only std(action)/std(state) shows it.
    frames = clean_frames(0)
    small = 0.02 * np.sin(np.arange(200) / 20)
    states = frames.states.copy()
    states[:, ARM] = 1.0 + small
    frames = dataclasses.replace(frames, states=states)
    frames = with_action(frames, ARM, 1.0 + small * DEG_PER_RAD)
    report = check_kinematic(frames, LAYOUT, loose_thresholds(), episode_id="ep_1", fps=FPS)
    units = [i for i in report.issues if i.code == "unit_deg_rad"]
    assert len(units) == 1 and "right_elbow_joint" in units[0].detail


def test_action_sign_flip_breaks_the_joint_mapping() -> None:
    frames = clean_frames(0)
    dim = LAYOUT.dimensions[ARM]
    assert dim.limit_low is not None and dim.limit_high is not None
    mid = (dim.limit_low + dim.limit_high) / 2
    flipped = 2 * mid - frames.action[:, ARM]  # mirrored around mid, still inside the limits
    report = check_kinematic(
        with_action(frames, ARM, flipped), LAYOUT, loose_thresholds(), episode_id="e", fps=FPS
    )
    assert [i.code for i in report.issues] == ["joint_mapping"]
    assert "right_elbow_joint" in report.issues[0].detail and report.issues[0].frames == []


def test_a_joint_jump_is_left_to_qa() -> None:
    frames = clean_frames(0)
    states = frames.states.copy()
    states[120:, ARM] += 0.3
    assert check(dataclasses.replace(frames, states=states)) == {}


@pytest.mark.parametrize("length", [0, 1])
def test_episode_under_two_frames_has_no_issue(length: int) -> None:
    frames = clean_frames(0)
    short = dataclasses.replace(
        frames,
        timestamp=frames.timestamp[:length],
        frame_index=frames.frame_index[:length],
        states=frames.states[:length],
        action=frames.action[:length],
    )
    assert check(short) == {}


def test_thresholds_file_needs_every_key(tmp_path: Path) -> None:
    path = tmp_path / "replay.yaml"
    path.write_text("version: replay-1\ncalibration: test\nkinematic: {}\ndynamic: {}\n")
    with pytest.raises(ConfigError, match="kinematic: missing"):
        load_thresholds(path)
