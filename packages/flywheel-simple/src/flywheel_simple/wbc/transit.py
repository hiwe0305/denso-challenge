"""Joint-space arm transits: a quintic from the commanded joints to one IK goal (DA-33, D-29).

Near the palm-up hold (D-25) the per-step IK reconfigures in null space: with
`wrist_roll` on its limit and `wrist_pitch` near 90 degrees, roll and yaw nearly
line up and the solver swaps one for the other between control steps
(docs/g0/tray/wrist-jump.md). A velocity limit in its QP bounds the swap but
crawls through that region (planner-5: two `timeout:REACH`). A posture change
whose end is known needs no per-step IK: `UpperBodyIK.goal` solves the end once,
from several seeds, and `choose_branch` keeps the solution furthest from the
`wrist_roll` limit; the arm then follows `JointPath`, a minimum-jerk (quintic)
path in joint space with zero speed and acceleration at both ends, long enough
that no joint moves more than `max_step` in a control step.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

PEAK_SPEED = 1.875  # max of d/dtau of the quintic below: 30 tau^2 (1 - tau)^2 at tau = 1/2


def quintic(tau: float) -> float:
    """10 tau^3 - 15 tau^4 + 6 tau^5 on [0, 1]: 0 to 1, zero speed and acceleration at both ends."""
    tau = min(1.0, max(0.0, tau))
    return tau**3 * (10.0 + tau * (6.0 * tau - 15.0))


def transit_steps(
    start: NDArray[np.float64], goal: NDArray[np.float64], max_step: float, min_steps: int = 1
) -> int:
    """Control steps for the quintic from `start` to `goal` that move no joint > `max_step`.

    A step from k-1 to k moves joint j by |goal - start|_j times the quintic's rise over
    [(k-1)/N, k/N], at most PEAK_SPEED / N of it.
    """
    if max_step <= 0:
        raise ValueError(f"max_step must be positive, got {max_step}")
    span = float(np.max(np.abs(np.asarray(goal) - np.asarray(start)), initial=0.0))
    return max(min_steps, math.ceil(PEAK_SPEED * span / max_step - 1e-12))


@dataclass(frozen=True)
class JointPath:
    """The quintic from `start` to `goal` over `steps` control steps; `at(k)` for k = 1..steps."""

    start: NDArray[np.float64]
    goal: NDArray[np.float64]
    steps: int

    @classmethod
    def plan(
        cls,
        start: NDArray[np.float64],
        goal: NDArray[np.float64],
        max_step: float,
        min_steps: int = 1,
    ) -> JointPath:
        start, goal = np.asarray(start, float).copy(), np.asarray(goal, float).copy()
        return cls(start, goal, transit_steps(start, goal, max_step, min_steps))

    def at(self, k: int) -> NDArray[np.float64]:
        """Joints after step k (0 is `start`, `steps` and later are `goal`)."""
        s = quintic(k / self.steps)
        out: NDArray[np.float64] = self.start + s * (self.goal - self.start)
        return out


def roll_margin(q: float, low: float, high: float) -> float:
    """Distance of a joint value to the nearer of its limits (rad)."""
    return min(q - low, high - q)


def choose_branch(
    errors: Sequence[float],
    margins: Sequence[float],
    distances: Sequence[float],
    error_tol: float,
) -> int:
    """Index of the IK solution to go to: among those within `error_tol` of the best pose
    error, the one with the largest `wrist_roll` margin, then the shortest joint distance.
    Margins within 1 mrad count as equal: the hold pose may put every solution on the limit.
    """
    if not errors or not (len(errors) == len(margins) == len(distances)):
        raise ValueError("need one error, margin and distance per candidate")
    best = min(errors)
    ok = [i for i, e in enumerate(errors) if e <= best + error_tol]
    widest = max(margins[i] for i in ok)
    wide = [i for i in ok if margins[i] >= widest - 1e-3]
    return min(wide, key=lambda i: distances[i])
