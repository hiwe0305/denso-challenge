"""Stand-and-walk controller on GR00T decoupled WBC (DA-32 AC 1).

Runs only in the SIMPLE venv from S1-02:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/wbc -m sim -v
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

TWO_TABLE = "simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0"


@dataclass
class Trace:
    pelvis_z: list[float] = field(default_factory=list)
    upright: list[float] = field(default_factory=list)


def pelvis_xy(env: Any) -> np.ndarray:
    return np.asarray(env.unwrapped.mjData.body("pelvis").xpos[:2], dtype=float).copy()


def run(
    env: Any, ctrl: Any, steps: int, navigate_cmd: Sequence[float] = (0.0, 0.0, 0.0, 0.0)
) -> Trace:
    sim = env.unwrapped
    trace = Trace()
    for _ in range(steps):
        env.step(ctrl.action(sim.task.robot.prepare_obs(), navigate_cmd=navigate_cmd))
        trace.pelvis_z.append(float(sim.mjData.body("pelvis").xpos[2]))
        # Trunk axis as S1-02 measured it: world z of the torso's up axis. The
        # pelvis sways ~10 degrees per gait cycle and dips under 0.99 when walking.
        trace.upright.append(float(sim.mjData.body("torso_link").xmat.reshape(3, 3)[2, 2]))
    return trace


@pytest.fixture(scope="module")
def env() -> Any:
    from flywheel_simple.wbc import make_sonic_env

    e = make_sonic_env(TWO_TABLE, seed=0)
    yield e
    e.close()


@pytest.mark.sim
def test_stands_after_band_release(env: Any) -> None:
    from flywheel_simple.wbc import StandWalkController, release_band

    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    released = release_band(env, ctrl)
    trace = run(env, ctrl, steps=400)
    assert released < 200
    assert 0.70 <= min(trace.pelvis_z) and max(trace.pelvis_z) <= 0.78
    assert min(trace.upright) >= 0.99


@pytest.mark.sim
def test_walks_backward_on_navigate_cmd(env: Any) -> None:
    from flywheel_simple.wbc import StandWalkController, release_band

    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    release_band(env, ctrl)
    x0 = pelvis_xy(env)[0]
    trace = run(env, ctrl, steps=150, navigate_cmd=(-0.25, 0.0, 0.0, 0.0))
    assert 0.5 <= abs(pelvis_xy(env)[0] - x0) <= 0.9
    assert min(trace.upright) >= 0.99
