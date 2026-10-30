"""check_success in sim against an oracle that moves the tray (DA-32 AC 7, M1 part 2).

The oracle writes the tray's and parts' free-joint qpos directly, as one rigid
block, while G1 stands. It tests the checker only and never produces data.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray -m sim -v
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim
DEV_SEED = 1_000_000
BODIES = ["tray"] + [f"part_{i}" for i in range(6)]


def quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def quat_rot(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    return quat_mul(quat_mul(q, np.r_[0.0, v]), q * [1, -1, -1, -1])[1:]


def move_rigidly(env: Any, delta_pos: np.ndarray, delta_quat: np.ndarray) -> None:
    """Apply one rigid motion about the tray origin to the tray and every part."""
    import mujoco

    model, data = env.unwrapped.mjModel, env.unwrapped.mjData
    pivot = np.array(data.body("tray").xpos)
    for name in BODIES:
        joint = model.joint("tray_joint" if name == "tray" else f"{name}_joint")
        qa, va = joint.qposadr[0], joint.dofadr[0]
        pos, quat = data.qpos[qa : qa + 3].copy(), data.qpos[qa + 3 : qa + 7].copy()
        data.qpos[qa : qa + 3] = pivot + delta_pos + quat_rot(delta_quat, pos - pivot)
        data.qpos[qa + 3 : qa + 7] = quat_mul(delta_quat, quat)
        data.qvel[va : va + 6] = 0.0
    mujoco.mj_forward(model, data)


def stand(env: Any, ctrl: Any, seconds: float) -> dict[str, Any]:
    info: dict[str, Any] = {}
    for _ in range(int(seconds * 50)):
        _, _, _, _, info = env.step(ctrl.action(env.unwrapped.task.robot.prepare_obs()))
    return info


def oracle_place(env: Any, ctrl: Any, dx: float = 0.0, then_wait: float = 1.5) -> dict[str, Any]:
    """Put the tray, parts inside, on table B at the target pose (+dx), then wait."""
    task, data = env.unwrapped.task, env.unwrapped.mjData
    target = task.sample.target_pose
    tray = np.array(data.body("tray").xpos)
    yaw_now = 2 * math.atan2(data.body("tray").xquat[3], data.body("tray").xquat[0])
    turn = target.yaw - yaw_now
    goal = np.array([target.x + dx, target.y, task.cfg.table_height + 0.002])
    move_rigidly(env, goal - tray, np.array([math.cos(turn / 2), 0, 0, math.sin(turn / 2)]))
    return stand(env, ctrl, then_wait)


@pytest.fixture(scope="module")
def env() -> Iterator[Any]:
    from flywheel_simple.tray.simple_task import make_env

    e = make_env(seed=DEV_SEED)
    yield e
    e.close()


@pytest.fixture
def ctrl(env: Any) -> Any:
    from flywheel_simple.wbc import StandWalkController

    env.reset(seed=DEV_SEED, options={"level": 2})
    c = StandWalkController(env.unwrapped.task.robot)
    c.reset()
    return c


def test_untouched_tray_is_not_a_success(env: Any, ctrl: Any) -> None:
    info = stand(env, ctrl, 1.5)
    report = info["tray_report"]
    assert not report.success and report.failure is None
    assert not env.unwrapped.task.check_success(info, mujoco_env=env.unwrapped.mujoco)


def test_oracle_placement_in_target_succeeds(env: Any, ctrl: Any) -> None:
    info = oracle_place(env, ctrl)
    assert info["tray_report"].success
    assert env.unwrapped.task.check_success(info, mujoco_env=env.unwrapped.mujoco)


def test_oracle_placement_off_target_fails_with_place_pose(env: Any, ctrl: Any) -> None:
    info = oracle_place(env, ctrl, dx=0.10)
    assert info["tray_report"].failure == "L-PLACE-POSE"
    assert not env.unwrapped.task.check_success(info, mujoco_env=env.unwrapped.mujoco)


def test_oracle_tilt_spills_part_and_fails(env: Any, ctrl: Any) -> None:
    # 60 deg (the plan's value) only slides the parts against the 6 cm wall and the
    # tray falls back flat; flipping it past 90 deg tips it over its parts.
    tilt = math.radians(150)
    move_rigidly(
        env, np.array([0, 0, 0.15]), np.array([math.cos(tilt / 2), 0, math.sin(tilt / 2), 0])
    )
    info = stand(env, ctrl, 2.0)
    assert info["tray_report"].failure in {"L-PART-DROP", "L-TRAY-TILT"}


def test_state_dict_records_sample_and_report(env: Any, ctrl: Any) -> None:
    stand(env, ctrl, 0.2)
    state = env.unwrapped.task.state_dict()
    assert state["tray"]["sample"]["seed"] == DEV_SEED and state["tray"]["sample"]["level"] == 2
    assert len(state["tray"]["report"]["steps"]) == 7
