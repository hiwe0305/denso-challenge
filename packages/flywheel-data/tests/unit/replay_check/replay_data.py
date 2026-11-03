"""Clean G1 episodes written in the test, and thresholds to judge them (DA-17).

A clean episode moves every joint of the G1 layout (dims 0-30) on a slow sine
inside its limits; the action leads the recorded state by LEAD frames, as a
commanded target leads the joint that follows it. Timestamps are frame_index /
fps exactly, as in psi-data e78fb93.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from flywheel.data.config import load_layout
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.replay_check.kinematic import joint_dims
from flywheel.data.replay_check.thresholds import ReplayThresholds

REPO = Path(__file__).resolve().parents[5]
G1_YAML = REPO / "configs" / "embodiments" / "g1.yaml"
REPLAY_YAML = REPO / "configs" / "data" / "replay.yaml"
FPS = 50
LEAD = 2
CAMERA = "observation.images.egocentric"


def g1_layout() -> ActionLayout:
    return load_layout(G1_YAML)


def clean_frames(
    index: int, length: int = 200, layout: ActionLayout | None = None
) -> EpisodeFrames:
    layout = layout or g1_layout()
    rng = np.random.default_rng(index)
    t = (np.arange(length + LEAD) / FPS)[:, None]
    dims = joint_dims(layout, 32)
    low = np.array([layout.dimensions[i].limit_low for i in dims])
    high = np.array([layout.dimensions[i].limit_high for i in dims])
    freq = rng.uniform(0.2, 0.5, len(dims))
    phase = rng.uniform(0, 2 * math.pi, len(dims))
    path = (low + high) / 2 + 0.3 * (high - low) / 2 * np.sin(2 * math.pi * freq * t + phase)
    states = np.zeros((length, 32), dtype=np.float32)
    action = np.zeros((length, 36), dtype=np.float32)
    states[:, dims] = path[:length]
    action[:, dims] = path[LEAD:] + rng.normal(0, 1e-4, (length, len(dims)))
    action[:, dims] = np.clip(action[:, dims], low, high)
    states[:, 31] = action[:, 31] = 0.74
    action[:, 32:35] = rng.uniform(-0.2, 0.2, (length, 3))
    frame_index = np.arange(length, dtype=np.int64)
    return EpisodeFrames(
        episode_index=index,
        task="pick up the cracker box from table1, locomotion to table2, and place on table2.",
        timestamp=frame_index / FPS,
        frame_index=frame_index,
        states=states,
        action=action,
        video_frames={CAMERA: length},
    )


def loose_thresholds(layout: ActionLayout | None = None) -> ReplayThresholds:
    """Thresholds that pass every clean_frames episode, picked by hand."""
    layout = layout or g1_layout()
    names = [layout.dimensions[i].name for i in joint_dims(layout, 32)]
    groups = ("hand", "arm", "torso_rpy")
    return ReplayThresholds(
        version="test@000000000000",
        kinematic_quantile=1.0,
        timestamp_tolerance_frames=0.5,
        limit_tolerance={"action": 1e-5, "states": 1e-5},
        joint_jump={g: 0.2 for g in groups},
        unit_ratio={g: 3.0 for g in groups},
        min_std=1e-3,
        mapping_correlation={n: 0.5 for n in names},
        dynamic_quantile=0.99,
        state_error={g: 0.5 for g in groups},
        hand_event_offset_steps=10,
    )
