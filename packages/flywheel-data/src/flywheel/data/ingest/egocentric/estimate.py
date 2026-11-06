"""E-A in the lane: the Protocols of the estimators and the reader of the job's output.

The estimators run in `estimate_job.py` outside the workspace venv (D5): MediaPipe
Hands for the hand, OpenCV visual odometry for the camera. The lane never imports
MediaPipe; it reads the `.npz` the job wrote and turns it into an `EgoPose` in the
same layout as E-B, in the VO's world frame (the first frame's camera), so every
later tier and DA-18's export read E-A and E-B the same way. CI runs the same math
with fakes of the two Protocols.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from flywheel.data.ingest.egocentric.estimate_job import (
    TIPS,
    HandDetection,
    wrist_frame,
)
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose
from numpy.typing import NDArray

F64 = NDArray[np.float64]


class HandPoseModel(Protocol):
    def detect(self, rgb: NDArray[np.uint8], timestamp_ms: int) -> list[HandDetection]: ...


class CameraTracker(Protocol):
    def step(self, gray: NDArray[np.uint8], mask: NDArray[np.uint8] | None) -> tuple[
        F64, F64, bool]: ...


@dataclass(frozen=True)
class Estimate:
    """What the job wrote for one episode."""

    camera: F64  # (T, 4, 4)
    pixels: dict[str, F64]  # side -> (T, 21, 2), full-size frame
    points: dict[str, F64]  # side -> (T, 21, 3), camera frame
    score: dict[str, F64]  # side -> (T,)
    moving: F64  # (T,)
    meta: dict[str, Any]

    @property
    def frames(self) -> int:
        return int(self.camera.shape[0])


def read_estimate(path: Path) -> Estimate:
    with np.load(path) as data:
        return Estimate(
            camera=np.asarray(data["camera"], np.float64),
            pixels={s: np.asarray(data[f"{s}_px"], np.float64) for s in SIDES},
            points={s: np.asarray(data[f"{s}_cam"], np.float64) for s in SIDES},
            score={s: np.asarray(data[f"{s}_score"], np.float64) for s in SIDES},
            moving=np.asarray(data["moving"], np.float64),
            meta=json.loads(str(data["meta"])),
        )


def to_pose(estimate: Estimate) -> EgoPose:
    """The E-A `EgoPose`: hands moved from the camera frame to the VO world frame.

    A hand not found in a frame has NaN wrist and tips and confidence 0; the
    confidence of a found hand is MediaPipe's handedness score.
    """
    t = estimate.frames
    values: dict[str, NDArray[np.float32]] = {"camera": estimate.camera.astype(np.float32)}
    for side in SIDES:
        wrist = np.full((t, 4, 4), np.nan)
        tips = np.full((t, 5, 3), np.nan)
        for i in range(t):
            local = estimate.points[side][i]
            if not np.isfinite(local).all():
                continue
            world = estimate.camera[i] @ np.vstack([local.T, np.ones(len(local))])
            world_points = world[:3].T
            wrist[i] = estimate.camera[i] @ wrist_frame(local)
            tips[i] = world_points[list(TIPS)]
        values[f"{side}_wrist"] = wrist.astype(np.float32)
        values[f"{side}_tips"] = tips.astype(np.float32)
        values[f"confidence_{side}"] = estimate.score[side].astype(np.float32)
    return EgoPose(**values)
