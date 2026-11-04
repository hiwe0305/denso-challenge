"""The retargeting IK's joint step limit and waist lock (DA-35 task 10, 12), on CPU.

pink, the solver and TeleopRetargetingIK are faked.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray.pico.ik_limit import arms_only, limit_joint_step
from flywheel_simple.tray.pico.operator import LOCK_WAIST, OPERATOR_VERSION, OperatorConfig


class _VelocityLimit:
    def __init__(self, model: Any, velocity_limit: np.ndarray) -> None:
        self.model = model
        self.velocity_limit = np.asarray(velocity_limit)


@pytest.fixture
def fake_pink(monkeypatch: pytest.MonkeyPatch) -> None:
    limits = types.ModuleType("pink.limits")
    limits.VelocityLimit = _VelocityLimit  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pink", types.ModuleType("pink"))
    monkeypatch.setitem(sys.modules, "pink.limits", limits)


def solver(urdf: np.ndarray) -> Any:
    # Any values other than 1 make a wrong product of steps, dt and amplification show.
    model = types.SimpleNamespace(velocityLimit=urdf)
    return types.SimpleNamespace(
        configuration=types.SimpleNamespace(model=model),
        num_step_per_frame=3,
        dt=0.05,
        amplify_factor=1.5,
    )


@pytest.mark.parametrize("max_step", [0.08, 0.02])
def test_no_joint_moves_more_than_max_step_per_control_step(
    fake_pink: None, max_step: float
) -> None:
    urdf = np.array([37.0, 22.0, 22.0, 0.05])
    s = solver(urdf)

    limit_joint_step(s, max_step)

    model = s.configuration.model
    speed = model.velocity_limit.velocity_limit
    assert model.velocity_limit.model is model
    per_control_step = speed * s.dt * s.amplify_factor * s.num_step_per_frame
    assert per_control_step.max() <= max_step + 1e-12
    np.testing.assert_allclose(per_control_step[:3], max_step)
    assert speed[3] == 0.05  # the URDF limit stays where it is lower (0.011 rad per step)


def test_the_operator_config_caps_arm_steps_below_the_qa_threshold() -> None:
    # DA-03's action_jump.arm flags a step over 0.0869 rad (psi-data's p99.9).
    assert OperatorConfig.load().arm_step_max == 0.08


class _RetargetingIK:
    """TeleopRetargetingIK's constructor as SIMPLE's PICO agent calls it."""

    def __init__(self, robot_model: Any, *, body_active_joint_groups: Any = None) -> None:
        self.robot_model = robot_model
        self.body_active_joint_groups = body_active_joint_groups


def test_a_locked_waist_builds_the_ik_on_the_arms_alone() -> None:
    # SIMPLE asks for the upper_body groups (waist included); the lock replaces them.
    model = object()
    ik = arms_only(_RetargetingIK)(model, body_active_joint_groups=["upper_body"])
    assert ik.robot_model is model
    assert ik.body_active_joint_groups == ["arms"]
    again = arms_only(_RetargetingIK)(model, body_active_joint_groups=["upper_body"])
    assert again.body_active_joint_groups is not ik.body_active_joint_groups  # not shared


def test_the_virtual_operator_locks_the_waist() -> None:
    # PO 4/11/2026: DA-17 rejected every parent on the waist; batches before are virtual-2.
    assert LOCK_WAIST is True
    assert OPERATOR_VERSION == "da35-virtual-3"
