"""The retargeting IK's joint step limit (DA-35 task 10), with pink and the solver faked."""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np
import pytest
from flywheel_simple.tray.pico.ik_limit import limit_joint_step
from flywheel_simple.tray.pico.operator import OperatorConfig


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
