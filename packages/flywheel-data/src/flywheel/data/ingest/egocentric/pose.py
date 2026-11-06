"""Hand and camera pose of an egocentric episode, in the `pose.npz` layout DA-18 reads.

`EgoPose` is what every later tier uses, whatever the source (plan 6/11/2026 4.2a):

    camera                      (T, 4, 4)  camera to world
    left_wrist, right_wrist     (T, 4, 4)  wrist to world
    left_tips, right_tips       (T, 5, 3)  Thumb, Index, Middle, Ring, Little tip, world
    confidence_left, _right     (T,)       in [0, 1]

all float32. E-B reads it from EgoDex tracking (ARKit world frame, y up; camera frame as in
OpenCV, see `egodex.py`); E-A estimates it from RGB (`estimate.py`, world frame of the visual
odometry). A hand that was not seen has NaN poses and confidence 0.

The confidence of a hand is the mean of the confidences of its wrist and five tips,
the six joints exported. A file that recorded no confidence gives NaN: not recorded,
which QA tells apart from 0, not seen.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

SIDES = ("left", "right")
Array = NDArray[np.float32]


@dataclass(frozen=True)
class EgoPose:
    camera: Array
    left_wrist: Array
    right_wrist: Array
    left_tips: Array
    right_tips: Array
    confidence_left: Array
    confidence_right: Array

    def __post_init__(self) -> None:
        t = self.camera.shape[0]
        shapes = {"camera": (t, 4, 4), "left_wrist": (t, 4, 4), "right_wrist": (t, 4, 4),
                  "left_tips": (t, 5, 3), "right_tips": (t, 5, 3),
                  "confidence_left": (t,), "confidence_right": (t,)}
        for name, shape in shapes.items():
            value = getattr(self, name)
            if value.shape != shape:
                raise ValueError(f"pose {name} has shape {value.shape}, expected {shape}")
            if value.dtype != np.float32:
                raise ValueError(f"pose {name} is {value.dtype}, expected float32")

    @property
    def frames(self) -> int:
        return int(self.camera.shape[0])

    def wrist(self, side: str) -> Array:
        return self.left_wrist if side == "left" else self.right_wrist

    def tips(self, side: str) -> Array:
        return self.left_tips if side == "left" else self.right_tips

    def confidence(self, side: str) -> Array:
        return self.confidence_left if side == "left" else self.confidence_right


def save_pose(pose: EgoPose, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **{f.name: getattr(pose, f.name) for f in fields(EgoPose)})


def load_pose(path: Path) -> EgoPose:
    with np.load(path) as data:
        return EgoPose(**{f.name: np.asarray(data[f.name]) for f in fields(EgoPose)})


def aperture(pose: EgoPose, side: str) -> Array:
    """Distance between thumb tip and index tip, metres; how open the hand is."""
    tips = pose.tips(side)
    out: Array = np.linalg.norm(tips[:, 0] - tips[:, 1], axis=1).astype(np.float32)
    return out


def wrist_speed(pose: EgoPose, side: str, fps: float) -> Array:
    """Speed of the wrist, metres per second, the first frame repeating the second."""
    position = pose.wrist(side)[:, :3, 3]
    if len(position) < 2:
        return np.zeros(len(position), dtype=np.float32)
    step = np.linalg.norm(np.diff(position, axis=0), axis=1) * fps
    out: Array = np.concatenate([step[:1], step]).astype(np.float32)
    return out
