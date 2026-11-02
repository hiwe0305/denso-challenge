"""Both wrists through TeleopRetargetingIK and Dex3 hand closure (DA-33 AC 1).

`hand_q` tests are pure; the rest runs only in the SIMPLE venv from S1-02:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/wbc -m sim -v
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from flywheel_simple.wbc.upper_body import HAND_JOINTS, hand_q


def proprio(driver: Any) -> dict[str, Any]:
    return dict(driver.env.unwrapped.task.robot.prepare_obs())


def arm_q(driver: Any) -> np.ndarray:
    """Simulated arm joints in the IK's arm order."""
    data = driver.env.unwrapped.mjData
    names = [
        driver.ctrl.model.joint_names[i] for i in driver.ctrl.model.get_joint_group_indices("arms")
    ]
    return np.array([data.joint(n).qpos[0] for n in names])


def ik_arm_q(driver: Any, upper: np.ndarray) -> np.ndarray:
    model = driver.ctrl.model
    upper_idx = model.get_joint_group_indices("upper_body")
    return upper[[upper_idx.index(i) for i in model.get_joint_group_indices("arms")]]


def palm(driver: Any, side: str) -> np.ndarray:
    # As tray_state: g1_sonic has no palm link.
    data = driver.env.unwrapped.mjData
    wrist = data.body(f"{side}_wrist_yaw_link").xpos
    finger = data.body(f"{side}_hand_middle_0_link").xpos
    return np.asarray((wrist + finger) / 2)


def forward_component(driver: Any, d: np.ndarray) -> float:
    heading = driver.env.unwrapped.mjData.body("pelvis").xmat.reshape(3, 3)[:, 0]
    return float(d @ heading)


def shift(pose: np.ndarray, dx: float) -> np.ndarray:
    out = pose.copy()
    out[0, 3] += dx  # pelvis frame: x forward
    return out


def hand_qpos(driver: Any, side: str) -> np.ndarray:
    data = driver.env.unwrapped.mjData
    return np.array([data.joint(f"{side}_hand_{j}_joint").qpos[0] for j in HAND_JOINTS])


def run(
    driver: Any,
    seconds: float,
    wrist_pose: tuple[np.ndarray, np.ndarray] | None = None,
    hand_closure: tuple[float, float] = (0.0, 0.0),
) -> None:
    for _ in range(round(seconds / 0.02)):
        driver.env.step(
            driver.ctrl.action(proprio(driver), wrist_pose=wrist_pose, hand_closure=hand_closure)
        )


def test_hand_q_is_open_at_zero_and_mirrored_when_closed() -> None:
    assert np.all(hand_q("left", 0.0) == 0.0)
    closed = hand_q("left", 1.0)
    assert np.allclose(hand_q("right", 1.0)[1:], -closed[1:])
    assert np.allclose(hand_q("left", 0.5), closed / 2)
    assert np.allclose(hand_q("left", 2.0), closed)  # closure clipped to [0, 1]


@pytest.mark.sim
def test_closed_hand_is_80_percent_of_the_mjcf_flexion_range(tray_env_standing: Any) -> None:
    model = tray_env_standing.env.unwrapped.mjModel
    for side in ("left", "right"):
        ranges = np.array([model.joint(f"{side}_hand_{j}_joint").range for j in HAND_JOINTS])
        closed = hand_q(side, 1.0)
        flexion = np.where(closed >= 0, ranges[:, 1], ranges[:, 0])
        bends = closed != 0
        assert np.allclose(closed[bends], 0.8 * flexion[bends], atol=1e-3)
        assert np.all((ranges[:, 0] <= closed) & (closed <= ranges[:, 1]))


@pytest.mark.sim
def test_ik_round_trip_keeps_the_current_pose(tray_env_standing: Any) -> None:
    ik = tray_env_standing.ctrl.ik
    ik.reset(proprio(tray_env_standing))
    left, right = ik.current_wrists(proprio(tray_env_standing))
    upper = ik.solve(left, right)
    assert np.max(np.abs(ik_arm_q(tray_env_standing, upper) - arm_q(tray_env_standing))) < 0.05


@pytest.mark.sim
def test_wrist_target_moves_the_wrist(tray_env_standing: Any) -> None:
    # The pelvis slides ~9 cm back in the first 0.6 s after band release, with or
    # without arm commands; let it settle first.
    run(tray_env_standing, seconds=3.0)
    ik = tray_env_standing.ctrl.ik
    left, right = ik.current_wrists(proprio(tray_env_standing))
    p0 = palm(tray_env_standing, "left")
    run(tray_env_standing, seconds=1.5, wrist_pose=(shift(left, dx=0.10), right))
    left1, right1 = ik.current_wrists(proprio(tray_env_standing))
    # IK frame: SIMPLE's arm PD has no gravity feed-forward, so the wrist sags ~2 cm.
    assert 0.07 <= left1[0, 3] - left[0, 3] <= 0.13
    assert np.linalg.norm(right1[:3, 3] - right[:3, 3]) < 0.03
    assert forward_component(tray_env_standing, palm(tray_env_standing, "left") - p0) >= 0.05


@pytest.mark.sim
def test_hand_closure_closes_the_fingers(tray_env_standing: Any) -> None:
    # Index and middle reach 87 % of the target after 1 s and 95 % after 2 s.
    run(tray_env_standing, seconds=2.0, hand_closure=(1.0, 1.0))
    for side in ("left", "right"):
        assert np.max(np.abs(hand_qpos(tray_env_standing, side) - hand_q(side, 1.0))) < 0.15


@pytest.mark.sim
def test_last_record_has_teleop_recorder_fields(tray_env_standing: Any) -> None:
    tray_env_standing.ctrl.action(proprio(tray_env_standing))
    shapes = {k: np.shape(v) for k, v in tray_env_standing.ctrl.last_record.items()}
    assert (
        shapes.items()
        >= {
            "action_eef": (14,),
            "navigate_cmd": (4,),
            "base_height_command": (1,),
            "target_waist": (3,),
            "target_q": (29,),
            "left_hand_q": (7,),
            "right_hand_q": (7,),
            "goal_navigate_cmd": (4,),
            "goal_base_height_command": (1,),
        }.items()
    )
    model = tray_env_standing.ctrl.model
    assert shapes["goal_upper_body"] == (len(model.get_joint_group_indices("upper_body")),)


@pytest.mark.sim
def test_controller_ignores_wall_clock(make_standing: Any) -> None:
    """Same commands, same arm motion, however long each step takes (Review Focus 3)."""
    import time

    def reach(delay: float) -> np.ndarray:
        driver = make_standing()
        left, right = driver.ctrl.ik.current_wrists(proprio(driver))
        for k in range(40):  # a moving target, as the planner's ramps and walks give
            if delay:
                time.sleep(delay)
            target = (shift(left, dx=0.003 * k), right)
            driver.env.step(driver.ctrl.action(proprio(driver), wrist_pose=target))
        return arm_q(driver)

    assert np.max(np.abs(reach(0.0) - reach(0.01))) < 1e-3
