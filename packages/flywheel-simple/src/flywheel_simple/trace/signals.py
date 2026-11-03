"""Command and measurement vectors of one control cycle (issue #31 decision, DA-38 AC 2).

Upper body: the first 28 dims of the Psi0 action (hands, then arms) against the
measured joint angles in the same order, which is how SIMPLE's
`psi0_decoupled_wbc` agent builds the policy state (`STATE_SLICES`).

Lower body, 7 values in this order (`LOWER_NAMES`):
waist roll, pitch, yaw (rad); base height (m); vx, vy (m/s, heading frame);
yaw (rad, world). The command is `action[28:34] + action[35]`; dim 34 (`vyaw`,
read by the WBC as a turning flag) is dropped. The measurement reads the waist
joints, the floating base height, the base linear velocity rotated by -yaw, and
the base yaw.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

ACTION_DIM = 36
UPPER_DIM = 28
LOWER_NAMES = (
    "waist_roll",
    "waist_pitch",
    "waist_yaw",
    "base_height",
    "vx",
    "vy",
    "yaw",
)
_LOWER_ACTION_DIMS = (28, 29, 30, 31, 32, 33, 35)

# Copy of `simple.baselines.psi0_decoupled_wbc.STATE_SLICES` at SIMPLE 6d10628: index
# ranges into the 43 robot joints of g1_sonic. A `sim` test checks it against SIMPLE.
STATE_SLICES = (
    ("left_hand_thumb", 29, 32),
    ("left_hand_middle", 34, 36),
    ("left_hand_index", 32, 34),
    ("right_hand", 36, 43),
    ("left_arm", 15, 22),
    ("right_arm", 22, 29),
)
# waist_roll_joint, waist_pitch_joint, waist_yaw_joint; the agent builds its state the same way
WAIST_RPY = (13, 14, 12)

NonFinite = Literal["NaN", "Infinity", "-Infinity"]


def split_command(action: ArrayLike) -> tuple[list[float], list[float]]:
    """(cmd_upper, cmd_lower) from one 36-D Psi0 action row."""
    a = np.asarray(action, dtype=np.float64).reshape(-1)
    if a.shape[0] != ACTION_DIM:
        raise ValueError(f"expected a {ACTION_DIM}-D Psi0 action, got {a.shape[0]} dims")
    return a[:UPPER_DIM].tolist(), a[list(_LOWER_ACTION_DIMS)].tolist()


def yaw_of(quat_wxyz: ArrayLike) -> float:
    w, x, y, z = (float(v) for v in np.asarray(quat_wxyz, dtype=np.float64).reshape(4))
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def measured_signals(
    joint_qpos: ArrayLike, base_qpos: ArrayLike, base_qvel: ArrayLike
) -> tuple[list[float], list[float]]:
    """(meas_upper, meas_lower) from the robot joints and the floating base.

    `base_qpos` is the freejoint's (x, y, z, qw, qx, qy, qz); `base_qvel` its 6 velocities,
    of which MuJoCo gives the first three in the world frame.
    """
    q = np.asarray(joint_qpos, dtype=np.float64).reshape(-1)
    base = np.asarray(base_qpos, dtype=np.float64).reshape(7)
    vel = np.asarray(base_qvel, dtype=np.float64).reshape(6)
    upper = np.concatenate([q[s:e] for _, s, e in STATE_SLICES])
    yaw = yaw_of(base[3:7])
    c, s = math.cos(yaw), math.sin(yaw)
    vx = c * vel[0] + s * vel[1]
    vy = -s * vel[0] + c * vel[1]
    lower = [*q[list(WAIST_RPY)].tolist(), float(base[2]), vx, vy, yaw]
    return upper.tolist(), lower


def image_time(t_render: float, *, frame_sent: bool) -> float | None:
    """`t_image` of a cycle: sim time of the frame the policy received then, else None.

    SIMPLE's agent sends a frame to the server only when its action queue is empty;
    the other cycles have no new frame for the policy (issue #31: null, no repeat).
    """
    return float(t_render) if frame_sent else None


def encode(value: float) -> float | NonFinite:
    """A float as the contracts encode it: finite stays a float, the rest become names."""
    v = float(value)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    return v


def encode_all(values: Sequence[float]) -> list[float | NonFinite]:
    return [encode(v) for v in values]
