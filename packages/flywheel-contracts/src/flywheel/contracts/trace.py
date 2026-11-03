"""Contracts for per-step execution traces and camera parameters (Issue #31).

TraceStep records one control cycle: commands and measurements for the upper and
lower body (R3 tracking), the simulation-clock stamps of state and image (R4
sync), and frames lost in the cycle (missing-signal check). CameraParams records
the intrinsics, render resolution, mount and pose of one camera of a trace (R5
calibration).
"""

from __future__ import annotations

import math
import re
from typing import Literal

from flywheel.contracts.artifacts import Artifact
from pydantic import Field, model_validator
from typing_extensions import Self

NonFinite = Literal["NaN", "Infinity", "-Infinity"]
FloatOrNonFinite = float | NonFinite

# G1 36-D action (Psi0 ACTION_SLICES_36D, names as in docs/g0/psi-data.md and D-26):
# the left hand goes thumb, middle, index; the right hand thumb, index, middle.
UPPER_BODY: tuple[str, ...] = (
    # left hand, action[0:7]
    "left_hand_thumb_0_joint",
    "left_hand_thumb_1_joint",
    "left_hand_thumb_2_joint",
    "left_hand_middle_0_joint",
    "left_hand_middle_1_joint",
    "left_hand_index_0_joint",
    "left_hand_index_1_joint",
    # right hand, action[7:14]
    "right_hand_thumb_0_joint",
    "right_hand_thumb_1_joint",
    "right_hand_thumb_2_joint",
    "right_hand_index_0_joint",
    "right_hand_index_1_joint",
    "right_hand_middle_0_joint",
    "right_hand_middle_1_joint",
    # left arm, action[14:21]
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    # right arm, action[21:28]
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
)
"""`cmd_upper` = action[0:28] and `meas_upper`, in this order; joint angles in rad."""

LOWER_BODY: tuple[str, ...] = (
    "waist_roll",  # rad, joint angle; action[28]
    "waist_pitch",  # rad, joint angle; action[29]
    "waist_yaw",  # rad, joint angle; action[30]
    "base_height",  # m, height of the floating base; action[31]
    "vx",  # m/s, base velocity in the heading (yaw-only) frame of the base; action[32]
    "vy",  # m/s, same frame; action[33]
    "yaw",  # rad, heading of the base in the world frame; cmd is target_yaw, action[35]
)
"""`cmd_lower` and `meas_lower`, in this order (issue #31). action[34] (navigate.vyaw,
read by the WBC as the turning flag) is left out: it is discrete."""

# run_plan_id of a run that has no RunPlan, such as a G0 or scripted eval (PO decision G2).
G0_RUN_PLAN_ID = re.compile(r"^g0-[A-Z][A-Z0-9]*-[0-9]+-[0-9]{8}$")


class TraceStep(Artifact):
    """A single control cycle in a rollout trace.

    One clock: MuJoCo simulation time `data.time`, in seconds. Non-finite values are
    written as the strings "NaN", "Infinity", "-Infinity" so the line stays JSON; a
    check that needs such a value says CHƯA RÕ instead of scoring it.
    """

    trace_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    run_plan_id: str = Field(
        min_length=1,
        description=(
            "RunPlan of the run; a run without one (G0, scripted eval) uses "
            "g0-<story>-<yyyymmdd>, for example g0-DA-38-20261103."
        ),
    )
    step: int = Field(ge=0)
    t_state: FloatOrNonFinite = Field(description="Simulation time the state was read, s.")
    t_image: FloatOrNonFinite | None = Field(
        default=None,
        description=(
            "Simulation time of the frame fed to the policy in this cycle, s; null when the "
            "cycle has no new frame (not a repeat of the last one)."
        ),
    )
    cmd_upper: list[FloatOrNonFinite] = Field(
        min_length=len(UPPER_BODY),
        max_length=len(UPPER_BODY),
        description="Commanded joint angles, rad: action[0:28], in the order of UPPER_BODY.",
    )
    meas_upper: list[FloatOrNonFinite] = Field(
        min_length=len(UPPER_BODY),
        max_length=len(UPPER_BODY),
        description="Measured joint angles, rad, in the order of UPPER_BODY.",
    )
    cmd_lower: list[FloatOrNonFinite] = Field(
        min_length=len(LOWER_BODY),
        max_length=len(LOWER_BODY),
        description=(
            "action[28:34] + action[35]: waist roll, pitch, yaw (rad), base_height (m), "
            "vx, vy (m/s, heading frame of the base), target_yaw (rad, world)."
        ),
    )
    meas_lower: list[FloatOrNonFinite] = Field(
        min_length=len(LOWER_BODY),
        max_length=len(LOWER_BODY),
        description=(
            "Measured, same order: waist joint angles, base height, base velocity in the "
            "heading frame, base yaw in the world frame."
        ),
    )
    dropped_frames: int = Field(
        default=0,
        ge=0,
        description=(
            "Camera frames due in this cycle that never reached the policy; a count for "
            "this cycle, not a running total. Renders are synchronous in sim, so 0 there "
            "is measured."
        ),
    )

    @model_validator(mode="after")
    def g0_run_plan_id(self) -> Self:
        if self.run_plan_id.startswith("g0-") and not G0_RUN_PLAN_ID.match(self.run_plan_id):
            raise ValueError(
                f"run_plan_id {self.run_plan_id!r} must read g0-<story>-<yyyymmdd>, "
                "for example g0-DA-38-20261103"
            )
        return self


class CameraParams(Artifact):
    """One camera of an episode run.

    `fx`, `fy`, `cx`, `cy` are pixels at the render resolution `width` x `height`;
    `pose` is position (m) + MuJoCo quaternion (w, x, y, z) relative to the mount body.
    """

    episode_id: str = Field(min_length=1)
    uid: str = Field(min_length=1)
    mount: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fx: float = Field(gt=0.0)
    fy: float = Field(gt=0.0)
    cx: float = Field(gt=0.0)
    cy: float = Field(gt=0.0)
    pose: list[float]
    reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_pose(self) -> Self:
        if len(self.pose) != 7:
            raise ValueError(
                f"pose must contain 7 elements [x, y, z, qw, qx, qy, qz], got {len(self.pose)}"
            )
        qw, qx, qy, qz = self.pose[3:7]
        norm_sq = qw * qw + qx * qx + qy * qy + qz * qz
        if abs(norm_sq - 1.0) > 1e-2:
            raise ValueError(
                f"quaternion [qw, qx, qy, qz] must be normalized (norm^2 = {norm_sq:.4f})"
            )
        if any(math.isnan(val) or math.isinf(val) for val in self.pose):
            raise ValueError("pose elements must be finite numbers")
        return self
