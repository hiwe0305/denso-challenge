"""Clean G1 episodes written in the test, and thresholds to judge them (DA-17).

A clean episode moves every joint of the G1 layout (dims 0-30) on a slow sine
inside its limits; the action leads the recorded state by LEAD frames, as a
commanded target leads the joint that follows it. Timestamps are frame_index /
fps exactly, as in psi-data e78fb93.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import ActionLayout
from flywheel.data.config import load_layout
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode
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
        timestamp=(frame_index / FPS).astype(np.float32).astype(np.float64),
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
        unit_ratio={g: 3.0 for g in groups},
        min_std=1e-3,
        mapping_correlation={n: 0.5 for n in names},
        dynamic_quantile=0.99,
        state_error={g: 0.5 for g in groups},
        hand_event_offset_steps=10,
    )


def outcome_line(index: int, success: bool = True, **changes: object) -> str:
    """A replay_outcomes.jsonl line of a replay that tracked the recording closely."""
    line: dict[str, object] = {
        "episode_index": index,
        "success": success,
        "state_error_by_group": {"hand": 0.05 + 0.001 * index, "arm": 0.03, "torso_rpy": 0.02},
        "hand_event_offset_steps": index % 3 - 1,
    }
    return json.dumps({**line, **changes})


INFO = {
    "codebase_version": "v2.1",
    "robot_type": "g1",
    "total_episodes": 0,
    "total_frames": 0,
    "total_tasks": 0,
    "total_videos": 0,
    "total_chunks": 1,
    "chunks_size": 1000,
    "fps": FPS,
    "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
    "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
    "features": {
        CAMERA: {"dtype": "video", "shape": [360, 640, 3], "video_info": {}},
        "states": {"dtype": "float32", "shape": [-1]},
        "action": {"dtype": "float32", "shape": [-1]},
        **{k: {"dtype": t, "shape": [1]} for k, t in [
            ("timestamp", "float32"), ("frame_index", "int64"), ("episode_index", "int64"),
            ("index", "int64"), ("next.done", "bool"), ("task_index", "int64")]},
    },
}


def write_dataset(root: Path, episodes: Sequence[EpisodeFrames]) -> Path:
    """A LeRobot v2.1 dataset in Psi0's layout, with an mp4 per episode that holds only
    its frame count (the reader counts samples, never decodes)."""
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps(INFO, indent=4))
    for frames in episodes:
        write_episode(root, frames)
        mp4 = root / "videos" / "chunk-000" / CAMERA / f"episode_{frames.episode_index:06d}.mp4"
        _fake_mp4(mp4, len(frames.timestamp))
    return root


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _fake_mp4(path: Path, frames: int) -> None:
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    stsz = _box(b"stsz", bytes(4) + struct.pack(">II", 0, frames) + bytes(4 * frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak) + _box(b"mdat"))
