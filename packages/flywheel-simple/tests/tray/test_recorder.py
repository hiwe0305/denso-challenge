"""Planner episodes recorded in SIMPLE's teleop LeRobot format (DA-33 AC 4, Task 5).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_recorder.py -m sim -v
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim

LEROBOT_INDEX_FEATURES = {"timestamp", "frame_index", "episode_index", "index", "task_index"}
EGO_VIEW = "observation.images.ego_view"
SECONDS = 2.0


@pytest.fixture(scope="module")
def recorded(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Any]]:
    """One 2 s planner episode (level 1, seed 1) recorded and saved; (dataset root, env)."""
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig
    from flywheel_simple.tray.recorder import (
        EpisodeRecorder,
        FlywheelMeta,
        planner_version,
        visuals_revision,
    )
    from flywheel_simple.tray.simple_task import make_env
    from flywheel_simple.tray.visuals import default_manifest_path

    root = tmp_path_factory.mktemp("rec") / "dataset"
    env = make_env(seed=1, level=1)
    cfg = PlannerConfig.load()
    agent = TrayAgent(env, cfg)
    recorder = EpisodeRecorder.for_env(env, agent, root)
    run_episode(env, agent, seed=1, level=1, on_frame=recorder.add, limit_s=SECONDS)
    task = env.unwrapped.task
    task.set_flywheel_meta(
        FlywheelMeta(
            seed=1,
            level=1,
            planner_version=planner_version(cfg),
            visuals_revision=visuals_revision(default_manifest_path()),
        )
    )
    assert recorder.save(task.state_dict()) == 0
    recorder.close()
    yield root, env
    env.close()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _table(root: Path) -> Any:
    import pyarrow.parquet as pq

    return pq.read_table(root / "data/chunk-000/episode_000000.parquet")


def test_recorded_features_match_simple_teleop(recorded: tuple[Path, Any]) -> None:
    from decoupled_wbc.data.utils import get_dataset_features
    from flywheel_simple.tray.recorder import TRAY_FEATURES
    from flywheel_simple.wbc import StandWalkController

    root, env = recorded
    model = StandWalkController(env.unwrapped.task.robot).model
    info = json.loads((root / "meta/info.json").read_text())
    expected = set(get_dataset_features(model)) | set(TRAY_FEATURES)
    assert set(info["features"]) - LEROBOT_INDEX_FEATURES == expected
    assert info["fps"] == 50 and list(info["features"]["action"]["shape"]) == [43]
    assert list(info["features"][EGO_VIEW]["shape"]) == [360, 640, 3]


def test_environment_config_carries_flywheel_meta(recorded: tuple[Path, Any]) -> None:
    root, _ = recorded
    episode = _read_jsonl(root / "meta/episodes.jsonl")[0]
    env_cfg = json.loads(episode["environment_config"])
    meta = env_cfg["flywheel"]
    assert meta["synthetic_tier"] == "S1" and meta["split"] == "train"
    assert (meta["seed"], meta["level"]) == (1, 1)
    assert env_cfg["tray"]["sample"]["seed"] == 1


def test_recording_starts_once_the_robot_is_stable(recorded: tuple[Path, Any]) -> None:
    root, _ = recorded
    table = _table(root)
    base_pose = np.asarray(table.column("observation.base_pose")[0].as_py())
    base_vel = np.asarray(table.column("observation.base_vel")[0].as_py())
    assert base_pose[2] >= 0.70, base_pose
    assert np.linalg.norm(base_vel[:2]) < 0.05, base_vel
    assert table.num_rows == pytest.approx(SECONDS * 50, abs=2)


def test_video_frames_match_rows(recorded: tuple[Path, Any]) -> None:
    import av

    root, _ = recorded
    video = root / f"videos/chunk-000/{EGO_VIEW}/episode_000000.mp4"
    with av.open(str(video)) as container:
        frames = sum(1 for _ in container.decode(video=0))
    assert frames == _table(root).num_rows


def test_save_refuses_an_episode_without_flywheel_meta(tmp_path: Path) -> None:
    from flywheel_simple.tray.recorder import EpisodeRecorder

    recorder = EpisodeRecorder(tmp_path / "ds", robot_model=None, joint_names=[], task_prompt="x")
    with pytest.raises(ValueError, match="flywheel"):
        recorder.save({"uid": "tray", "flywheel": None})
