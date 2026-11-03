"""A small LeRobot v2.1 dataset in Psi0's layout, written in the test (DA-03 task 1)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode

FPS = 50
CAMERA = "observation.images.egocentric"
TASK = "pick up the cracker box from table1, locomotion to table2, and place on table2."


def psi0_info(fps: int = FPS) -> dict[str, object]:
    """info.json as Psi0's postprocess writes it, minus the observation.* columns."""
    scalar = {"shape": [1]}
    return {
        "codebase_version": "v2.1",
        "robot_type": "g1",
        "total_episodes": 0,
        "total_frames": 0,
        "total_tasks": 0,
        "total_videos": 0,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": fps,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4",
        "features": {
            CAMERA: {"dtype": "video", "shape": [360, 640, 3], "video_info": {}},
            "states": {"dtype": "float32", "shape": [-1]},
            "action": {"dtype": "float32", "shape": [-1]},
            "timestamp": {"dtype": "float32", **scalar},
            "frame_index": {"dtype": "int64", **scalar},
            "episode_index": {"dtype": "int64", **scalar},
            "index": {"dtype": "int64", **scalar},
            "next.done": {"dtype": "bool", **scalar},
            "task_index": {"dtype": "int64", **scalar},
        },
    }


def make_frames(index: int, length: int, task: str = TASK) -> EpisodeFrames:
    rng = np.random.default_rng(index)
    return EpisodeFrames(
        episode_index=index,
        task=task,
        timestamp=(np.arange(length) / FPS).astype(np.float32).astype(np.float64),
        frame_index=np.arange(length, dtype=np.int64),
        states=rng.standard_normal((length, 32)).astype(np.float32),
        action=rng.standard_normal((length, 36)).astype(np.float32),
        video_frames={CAMERA: length},
    )


def make_dataset(root: Path, lengths: list[int]) -> list[EpisodeFrames]:
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps(psi0_info(), indent=4))
    episodes = [make_frames(i, n) for i, n in enumerate(lengths)]
    for frames in episodes:
        write_episode(root, frames)
        name = f"episode_{frames.episode_index:06d}.mp4"
        video = root / "videos" / "chunk-000" / "egocentric" / name
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"\x00not a real mp4")
    return episodes


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[Path, list[EpisodeFrames]]:
    root = tmp_path / "psi"
    return root, make_dataset(root, [5, 7, 3])


@pytest.fixture
def dataset_factory() -> Callable[[Path, list[int]], list[EpisodeFrames]]:
    return make_dataset
