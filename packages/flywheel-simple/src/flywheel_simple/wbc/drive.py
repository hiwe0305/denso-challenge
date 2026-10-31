"""Walk and turn G1 on decoupled WBC through `navigate_cmd`, with a per-step log.

Used by the locomotion tests and `scripts/g0/tray/measure_locomotion.py` (DA-33
Task 1). The env and controller are passed in, so this module imports nothing
from the SIMPLE venv.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.wbc.navigate import NavIntegrator, wrap


@dataclass
class Driver:
    """An env standing under `ctrl`, the integrator feeding it, and one log row per step."""

    env: Any
    ctrl: Any
    nav: NavIntegrator = field(default_factory=NavIntegrator)
    log: list[dict[str, float]] = field(default_factory=list)

    def step(self, cmd: NDArray[np.float64]) -> float:
        """One env step with `cmd`; returns the torso's uprightness after it."""
        sim = self.env.unwrapped
        self.env.step(self.ctrl.action(sim.task.robot.prepare_obs(), navigate_cmd=cmd))
        xy, yaw = pelvis_pose(self.env)
        self.log.append(
            {
                "t": float(sim.mjData.time),
                "walk_policy": float(walk_policy_runs(cmd)),
                "x": float(xy[0]),
                "y": float(xy[1]),
                "yaw": yaw,
                "target_yaw": float(cmd[3]),
                # Yaw rate the Walk policy was given (G1GearWbcPolicy.cmd[2]).
                "policy_vyaw": float(self.ctrl.lower_body.cmd[2]),
            }
        )
        return upright(self.env)


def pelvis_pose(env: Any) -> tuple[NDArray[np.float64], float]:
    """Pelvis xy and yaw in the world frame."""
    data = env.unwrapped.mjData
    w, x, y, z = np.asarray(data.body("pelvis").xquat, dtype=float)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return np.asarray(data.body("pelvis").xpos[:2], dtype=float).copy(), yaw


def upright(env: Any) -> float:
    """World z of the torso's up axis (DA-32 D-04)."""
    return float(env.unwrapped.mjData.body("torso_link").xmat.reshape(3, 3)[2, 2])


def yaw_error(yaw: float, target: float) -> float:
    return abs(wrap(target - yaw))


def walk_policy_runs(cmd: NDArray[np.float64]) -> bool:
    """G1GearWbcPolicy.get_action runs Balance.onnx when |(vx, vy, turn flag)| < 0.1."""
    return bool(np.linalg.norm(cmd[:3]) >= 0.1)


def walk(
    driver: Driver, vx: float, seconds: float, vy: float = 0.0, hold_heading: float = 0.0
) -> tuple[float, float, float]:
    """Walk at (vx, vy) for `seconds`; returns (along, lateral, min upright).

    `along` and `lateral` are the signed pelvis displacement along and across the
    start heading. `hold_heading` is the turn flag sent while walking: 0 leaves the
    heading free, >= 0.1 makes the lower body hold the start heading.
    """
    xy0, yaw0 = pelvis_pose(driver.env)
    driver.nav.reset(yaw=yaw0)
    up = 1.0
    for _ in range(round(seconds / driver.nav.dt)):
        up = min(up, driver.step(driver.nav.command(vx, vy, hold_heading, limit_yaw=yaw0)))
    d = pelvis_pose(driver.env)[0] - xy0
    heading = np.array([math.cos(yaw0), math.sin(yaw0)])
    left = np.array([-heading[1], heading[0]])
    return float(d @ heading), float(d @ left), up


def turn(
    driver: Driver,
    vyaw: float,
    target: float,
    max_seconds: float,
    tol: float = math.radians(5),
    settle_s: float = 1.0,
) -> tuple[float, float, float]:
    """Turn in place by `target` rad at `vyaw`, hold until within `tol` for 0.5 s, then stand.

    Returns (heading change, pelvis displacement, min upright); the heading change
    is wrapped to [-pi, pi].
    """
    xy0, yaw0 = pelvis_pose(driver.env)
    goal = wrap(yaw0 + target)
    driver.nav.reset(yaw=yaw0)
    up, settled = 1.0, 0.0
    for _ in range(round(max_seconds / driver.nav.dt)):
        up = min(up, driver.step(driver.nav.command(0.0, 0.0, vyaw, limit_yaw=goal)))
        within = yaw_error(pelvis_pose(driver.env)[1], goal) <= tol
        settled = settled + driver.nav.dt if within else 0.0
        if settled >= 0.5:
            break
    for _ in range(round(settle_s / driver.nav.dt)):
        up = min(up, driver.step(driver.nav.command(0.0, 0.0, 0.0)))
    xy, yaw = pelvis_pose(driver.env)
    return wrap(yaw - yaw0), float(np.linalg.norm(xy - xy0)), up
