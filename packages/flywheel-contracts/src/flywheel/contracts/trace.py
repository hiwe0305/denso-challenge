"""Contracts for per-step execution traces and camera parameters (Issue #31).

TraceStep records per-cycle control signals (commands and measurements for both
upper and lower body, control clock timestamps, and dropped frames) for system
fault detection (R3 tracking, R4 camera sync offset, R6 infra).

CameraParams records calibrated camera intrinsics, render resolution, mount,
and 7D pose (position [x, y, z] + MuJoCo quaternion [w, x, y, z]) relative to
its mount body, paired with a reference configuration hash for R5 calibration checks.
"""

from __future__ import annotations

import math
from typing import Literal

from flywheel.contracts.artifacts import Artifact
from pydantic import Field, model_validator
from typing_extensions import Self

NonFinite = Literal["NaN", "Infinity", "-Infinity"]
FloatOrNonFinite = float | NonFinite


class TraceStep(Artifact):
    """A single control cycle in a rollout trace."""

    trace_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    run_plan_id: str = Field(min_length=1)
    step: int = Field(ge=0)
    t_state: FloatOrNonFinite
    t_image: FloatOrNonFinite | None = None
    cmd_upper: list[FloatOrNonFinite]
    meas_upper: list[FloatOrNonFinite]
    cmd_lower: list[FloatOrNonFinite]
    meas_lower: list[FloatOrNonFinite]
    dropped_frames: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def matching_dimensions(self) -> Self:
        if len(self.cmd_upper) != len(self.meas_upper):
            raise ValueError(
                f"cmd_upper length ({len(self.cmd_upper)}) does not match "
                f"meas_upper length ({len(self.meas_upper)})"
            )
        if len(self.cmd_lower) != len(self.meas_lower):
            raise ValueError(
                f"cmd_lower length ({len(self.cmd_lower)}) does not match "
                f"meas_lower length ({len(self.meas_lower)})"
            )
        return self


class CameraParams(Artifact):
    """Camera intrinsic and extrinsic parameters for an episode run."""

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
