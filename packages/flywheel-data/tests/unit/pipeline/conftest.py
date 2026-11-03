"""A small LeRobot v2.1 dataset in Psi0's layout, written in the test (DA-03 task 1)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.config import QAConfig, load_layout, load_qa_config
from flywheel.data.ingest.lerobot import EpisodeFrames, write_episode
from qa_data import CAMERA, FPS, G1_YAML, QA_YAML, SPLITS, TASK, fake_mp4, psi0_info, video_path


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
        fake_mp4(video_path(root, frames.episode_index), len(frames.timestamp))
    return episodes


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[Path, list[EpisodeFrames]]:
    root = tmp_path / "psi"
    return root, make_dataset(root, [5, 7, 3])


@pytest.fixture
def dataset_factory() -> Callable[[Path, list[int]], list[EpisodeFrames]]:
    return make_dataset


TRAY_UID = "g1_wholebody_tray_transfer_teleop"
S1_BLOCK = {
    "seed": 1000,
    "level": 1,
    "planner_version": "da33-planner-4+cfg.815b822a",
    "source_kind": "synthetic",
    "source_detail": "planner_wbc",
    "synthetic_tier": "S1",
    "action_quality": "planned",
    "embodiment_id": "g1_sonic_dwbc@1",
    "renderer": "mujoco",
    "data_class": "public",
    "split": "train",
}


def set_flywheel(root: Path, index: int, block: dict[str, object], uid: str = TRAY_UID) -> None:
    """Put a recorder's flywheel block in an episode's environment_config, as SIMPLE does."""
    meta = root / "meta" / "episodes.jsonl"
    rows = [json.loads(line) for line in meta.read_text().splitlines()]
    for row in rows:
        if row["episode_index"] == index:
            row["environment_config"] = json.dumps({"uid": uid, "flywheel": block})
    meta.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def flywheel() -> Callable[..., None]:
    return set_flywheel


@pytest.fixture
def s1_block() -> dict[str, object]:
    return dict(S1_BLOCK)


@pytest.fixture
def mp4() -> Callable[..., None]:
    return fake_mp4


@pytest.fixture(autouse=True)
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test's datasets sit under tmp_path, which is the store root ($FW_ROOT)."""
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    return tmp_path



@pytest.fixture
def qa_config() -> QAConfig:
    """configs/data/qa.yaml as the lane loads it, with G1's layout and the shared SplitPlan."""
    return load_qa_config(QA_YAML, load_layout(G1_YAML), SPLITS)
