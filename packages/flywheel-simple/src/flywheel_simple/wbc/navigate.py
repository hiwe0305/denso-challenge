"""`navigate_cmd` for decoupled WBC from planned base velocities, as PicoStreamer builds it.

`navigate_cmd = [vx, vy, vyaw, target_yaw]`. The lower body reads `vyaw` only as a
turn flag: with |vyaw| >= 0.1 it turns at `(target_yaw - yaw) / 0.5` rad/s
(clamped to 1 rad/s) towards the absolute `target_yaw`, below 0.1 it does not
turn at all (G1GearWbcPolicy.get_action). So a turn ends where `target_yaw`
stops, not where `vyaw` drops to zero.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

MAX_LINEAR_VEL = 0.5  # m/s, PicoStreamer
MAX_ANGULAR_VEL = 1.0  # rad/s, PicoStreamer and G1GearWbcPolicy


def wrap(angle: float) -> float:
    """Angle in [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class NavIntegrator:
    """Clip base velocities and integrate `target_yaw` from `vyaw` at the control rate."""

    def __init__(self, dt: float = 0.02) -> None:
        self.dt = dt
        self.target_yaw = 0.0

    def reset(self, yaw: float = 0.0) -> None:
        """Start integrating from `yaw`, normally the base's current heading."""
        self.target_yaw = wrap(yaw)

    def command(
        self, vx: float, vy: float, vyaw: float, limit_yaw: float | None = None
    ) -> NDArray[np.float64]:
        """One `navigate_cmd`; `target_yaw` advances by `vyaw * dt` before it is returned.

        With `limit_yaw`, `target_yaw` moves towards it by the short way and stops
        there while `vyaw` stays in the command, so the lower body keeps correcting
        the heading onto `limit_yaw`.
        """
        vx = float(np.clip(vx, -MAX_LINEAR_VEL, MAX_LINEAR_VEL))
        vy = float(np.clip(vy, -MAX_LINEAR_VEL, MAX_LINEAR_VEL))
        vyaw = float(np.clip(vyaw, -MAX_ANGULAR_VEL, MAX_ANGULAR_VEL))
        delta = vyaw * self.dt
        if limit_yaw is not None:
            remaining = wrap(limit_yaw - self.target_yaw)
            delta = math.copysign(min(abs(delta), abs(remaining)), remaining)
        self.target_yaw = wrap(self.target_yaw + delta)
        return np.array([vx, vy, vyaw, self.target_yaw])
