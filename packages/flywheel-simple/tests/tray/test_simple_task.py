"""The tray task registered in SIMPLE and reset in sim_mode=mujoco (DA-32 AC 4, M0 part 2).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray -m sim -v
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim


def head_image(obs: dict[str, Any]) -> np.ndarray:
    return np.asarray(obs["head_stereo_left"])


def tray_position(env: Any) -> np.ndarray:
    return np.asarray(env.unwrapped.mjData.body("tray").xpos).copy()


def part_positions(env: Any) -> np.ndarray:
    data = env.unwrapped.mjData
    return np.array([data.body(f"part_{i}").xpos for i in range(6)])


def flat_keys(tree: Any, prefix: str = "") -> list[str]:
    if isinstance(tree, dict):
        out = []
        for key, value in tree.items():
            out += [str(key)] + flat_keys(value, f"{prefix}{key}.")
        return out
    return []


def handle_height(env: Any) -> float:
    return float(env.unwrapped.mjData.body("tray").xpos[2]) + 0.06


def arm_reach_band(env: Any, side: str = "left") -> tuple[float, float]:
    """Heights a hand can reach: shoulder height +- the summed link offsets down to the palm."""
    data = env.unwrapped.mjData
    chain = [
        "shoulder_pitch",
        "shoulder_roll",
        "shoulder_yaw",
        "elbow",
        "wrist_roll",
        "wrist_pitch",
        "wrist_yaw",
        "hand_middle_0",
    ]  # g1_sonic has no palm link
    points = [np.asarray(data.body(f"{side}_{link}_link").xpos) for link in chain]
    length = float(sum(np.linalg.norm(b - a) for a, b in zip(points, points[1:])))
    shoulder = float(points[0][2])
    return shoulder - length, shoulder + length


@pytest.fixture(scope="module")
def env() -> Iterator[Any]:
    from flywheel_simple.tray.simple_task import make_env

    e = make_env(seed=0)
    yield e
    e.close()


def test_env_id_and_task_registered_from_our_package(env: Any) -> None:
    from flywheel_simple.tray.simple_task import ENV_ID, TASK_UID

    assert env.spec.id == ENV_ID
    assert env.unwrapped.task.uid == TASK_UID
    assert env.unwrapped.task.robot.uid == "g1_sonic"


def test_env_resets_in_mujoco_and_renders_head_camera(env: Any) -> None:
    obs, _ = env.reset(seed=0)
    img = head_image(obs)
    assert img.ndim == 3 and img.shape[2] == 3 and img.std() > 1.0


def facing_table_a(env: Any) -> float:
    """Cosine between the pelvis forward axis and the direction to table A's centre."""
    from flywheel_simple.tray import TrayConfig, scene_geometry

    pelvis = env.unwrapped.mjData.body("pelvis")
    to_a = scene_geometry(TrayConfig.load()).table_a_center - np.asarray(pelvis.xpos[:2])
    forward = pelvis.xmat.reshape(3, 3)[:2, 0]
    return float(forward @ to_a / np.linalg.norm(forward) / np.linalg.norm(to_a))


def test_robot_spawns_between_tables_closer_to_a_facing_a(env: Any) -> None:
    from flywheel_simple.tray import TrayConfig, scene_geometry

    env.reset(seed=0)
    geo = scene_geometry(TrayConfig.load())
    x = float(env.unwrapped.mjData.body("pelvis").xpos[0])
    assert abs(x - geo.table_a_center[0]) < abs(x - geo.table_b_center[0])
    assert (
        min(geo.table_a_center[0], geo.table_b_center[0])
        < x
        < max(geo.table_a_center[0], geo.table_b_center[0])
    )
    assert facing_table_a(env) > 0.99


def test_robot_stands_facing_table_a_after_band_release(env: Any) -> None:
    from flywheel_simple.wbc import StandWalkController, release_band

    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    assert release_band(env, ctrl) < 200
    for _ in range(100):
        env.step(ctrl.action(env.unwrapped.task.robot.prepare_obs()))
    assert 0.70 <= float(env.unwrapped.mjData.body("pelvis").xpos[2]) <= 0.78
    assert facing_table_a(env) > 0.99


def test_tray_and_parts_still_after_idle(env: Any) -> None:
    from flywheel_simple.wbc import StandWalkController

    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    tray0, parts0 = tray_position(env), part_positions(env)
    for _ in range(200):  # 4 s at render_hz 50, band still holding the robot
        env.step(ctrl.action(env.unwrapped.task.robot.prepare_obs()))
    assert np.linalg.norm(tray_position(env) - tray0) < 0.005
    assert np.max(np.linalg.norm((part_positions(env) - parts0)[:, :2], axis=1)) < 0.02


def test_privileged_state_not_in_policy_observation(env: Any) -> None:
    obs, info = env.reset(seed=0)
    assert not {"tray_pos", "tray_quat", "part_pos", "target_pose"} & set(flat_keys(obs))
    assert "privileged" in info
    assert {"tray_pos", "tray_quat", "part_pos", "target_pose"} <= set(info["privileged"])


def test_handles_within_g1_reach(env: Any) -> None:
    env.reset(seed=0)
    low, high = arm_reach_band(env)
    assert low <= handle_height(env) <= high


def test_runner_registers_env_then_hands_over_to_simple_cli() -> None:
    import gymnasium as gym
    from flywheel_simple.tray import run
    from flywheel_simple.tray.simple_task import ENV_ID

    with pytest.raises(SystemExit) as exit_info:
        run.main(["eval-decoupled-wbc", "--help"])  # teleop needs PyAV (PICO), not in the venv
    assert exit_info.value.code == 0
    assert ENV_ID in gym.registry


def test_runner_rejects_unknown_command() -> None:
    from flywheel_simple.tray import run

    assert run.main(["datagen"]) == 2
