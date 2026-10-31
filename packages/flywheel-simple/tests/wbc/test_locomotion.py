"""G1 walking and turning in the tray scene on decoupled WBC (DA-33 AC 1).

Runs only in the SIMPLE venv from S1-02:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/wbc -m sim -v
"""

from __future__ import annotations

import math
import os
from typing import Any

import pytest

pytestmark = pytest.mark.sim


@pytest.mark.parametrize("vx", [0.2, 0.3, 0.4])
def test_forward_walk_covers_most_of_the_command(open_floor_standing: Any, vx: float) -> None:
    from flywheel_simple.wbc.drive import walk

    # Walk.onnx reaches 0.80-0.85 of a forward command after ~0.6 s, so 4 s cover
    # 0.60-0.72 of vx * 4 (D-10); heading held with the turn flag, as the planner does.
    dx, drift, up = walk(open_floor_standing, vx=vx, seconds=4.0, hold_heading=0.1)
    assert dx >= 0.5 * vx * 4.0 and abs(drift) <= 0.15 and up >= 0.99


def test_turns_in_place_by_pi(tray_env_standing: Any) -> None:
    from flywheel_simple.wbc.drive import turn, yaw_error

    yaw, moved, up = turn(tray_env_standing, vyaw=0.5, target=math.pi, max_seconds=10.0)
    assert yaw_error(yaw, math.pi) <= math.radians(10) and moved <= 0.2 and up >= 0.99


def test_env_close_removes_its_scene_file(scene_envs: Any) -> None:
    from flywheel_simple.tray.simple_task import make_env, scene_dir

    scene_envs.close()  # one live env per process
    env = make_env(seed=0)
    path = scene_dir() / f"scene_{os.getpid()}.xml"
    assert path.exists()
    env.close()
    assert not path.exists()
