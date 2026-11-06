"""How far E-A is from E-B on the same EgoDex frames (DA-04 AC 5; design 6.6).

E-A sees only the video; E-B is Vision Pro's tracking of the same episode. On every
frame where both have a hand:

    pixel error   E-B's wrist and five tips projected with the intrinsic, against
                  MediaPipe's landmarks of the same joints, in pixels of the 1920x1080
                  frame
    3D error      the same joints in the camera frame, metres (E-A lifted with
                  MediaPipe's metric landmarks; depth is its weak axis)
    detection     share of the frames where E-B's wrist is in the image that E-A found
                  the hand in

Camera, over steps of `stride` frames: the angle between E-A's and E-B's relative
rotation, and, on steps where VO estimated a translation and E-B moved at least
`min_move_m`, the angle between the two translation directions. Monocular VO has
no scale, so translation length is not compared. Both camera frames are OpenCV-like
(x right, y down, z forward; `egodex.py`), so relative rotations compare directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from flywheel.data.ingest.egocentric.estimate import Estimate
from flywheel.data.ingest.egocentric.estimate_job import TIPS, WRIST
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose
from numpy.typing import NDArray

F64 = NDArray[np.float64]
JOINTS = (WRIST, *TIPS)  # MediaPipe indices of wrist, thumb, index, middle, ring, little


@dataclass(frozen=True)
class HandDeviation:
    frames: int  # frames where both found the hand
    detection: float
    pixel_median: float
    pixel_p90: float
    wrist_pixel_median: float
    point_median_m: float
    depth_median_m: float


@dataclass(frozen=True)
class PoseDeviation:
    hands: dict[str, HandDeviation | None]
    rotation_median_deg: float | None
    rotation_p90_deg: float | None
    eb_rotation_median_deg: float | None  # how much E-B itself rotates per step
    translation_direction_median_deg: float | None
    translation_steps: int
    stride: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def eb_camera_points(pose: EgoPose, side: str) -> F64:
    """(T, 6, 3) E-B wrist and tips in the camera frame."""
    world = np.concatenate([pose.wrist(side)[:, None, :3, 3], pose.tips(side)], axis=1)
    camera = np.linalg.inv(pose.camera.astype(np.float64))
    homogeneous = np.concatenate([world, np.ones((*world.shape[:2], 1))], axis=2)
    out: F64 = np.einsum("tij,tkj->tki", camera, homogeneous)[..., :3]
    return out


def project(points: F64, intrinsic: F64) -> F64:
    with np.errstate(divide="ignore", invalid="ignore"):
        u = intrinsic[0, 0] * points[..., 0] / points[..., 2] + intrinsic[0, 2]
        v = intrinsic[1, 1] * points[..., 1] / points[..., 2] + intrinsic[1, 2]
    return np.stack([u, v], axis=-1)


def hand_deviation(
    eb: EgoPose, ea: Estimate, side: str, intrinsic: F64, size: tuple[int, int]
) -> HandDeviation | None:
    points = eb_camera_points(eb, side)
    pixels = project(points, intrinsic)
    wrist = pixels[:, 0]
    with np.errstate(invalid="ignore"):
        visible = (points[:, 0, 2] > 0) & (wrist[:, 0] >= 0) & (wrist[:, 0] < size[0]) \
            & (wrist[:, 1] >= 0) & (wrist[:, 1] < size[1])
    found = np.isfinite(ea.pixels[side][:, WRIST]).all(axis=1) & (ea.score[side] > 0)
    both = visible & found & np.isfinite(points).all(axis=(1, 2))
    if not both.any():
        return None
    ea_pixels = ea.pixels[side][both][:, list(JOINTS)]
    ea_points = ea.points[side][both][:, list(JOINTS)]
    pixel = np.linalg.norm(ea_pixels - pixels[both], axis=2)
    point = np.linalg.norm(ea_points - points[both], axis=2)
    depth = np.abs(ea_points[..., 2] - points[both][..., 2])
    return HandDeviation(
        frames=int(both.sum()),
        detection=float(found[visible].mean()) if visible.any() else 0.0,
        pixel_median=float(np.median(pixel)),
        pixel_p90=float(np.percentile(pixel, 90)),
        wrist_pixel_median=float(np.median(pixel[:, 0])),
        point_median_m=float(np.median(point)),
        depth_median_m=float(np.median(depth)),
    )


def rotation_angle_deg(r: F64) -> F64:
    cos = np.clip((np.trace(r, axis1=-2, axis2=-1) - 1) / 2, -1.0, 1.0)
    out: F64 = np.degrees(np.arccos(cos))
    return out


def relative(camera: F64, stride: int) -> tuple[F64, F64]:
    """Rotation and translation of camera i+stride in camera i's frame, (T-s, ...)."""
    r = camera[:, :3, :3]
    p = camera[:, :3, 3]
    r_rel = np.einsum("tji,tjk->tik", r[:-stride], r[stride:])
    t_rel = np.einsum("tji,tj->ti", r[:-stride], p[stride:] - p[:-stride])
    return r_rel, t_rel


def compare(
    eb: EgoPose, ea: Estimate, intrinsic: F64, size: tuple[int, int], *,
    stride: int = 1, min_move_m: float = 0.002,
) -> PoseDeviation:
    if eb.frames != ea.frames:
        raise ValueError(f"E-B has {eb.frames} frames, E-A {ea.frames}: not the same video")
    hands = {s: hand_deviation(eb, ea, s, intrinsic, size) for s in SIDES}
    if eb.frames <= stride:
        return PoseDeviation(hands, None, None, None, None, 0, stride)
    eb_r, eb_t = relative(eb.camera.astype(np.float64), stride)
    ea_r, ea_t = relative(ea.camera, stride)
    error = rotation_angle_deg(np.einsum("tji,tjk->tik", ea_r, eb_r))
    finite = np.isfinite(error)
    moving = ea.moving[stride:] > 0
    moved = np.linalg.norm(eb_t, axis=1) >= min_move_m
    steps = moving & moved & np.isfinite(eb_t).all(axis=1)
    directions = None
    if steps.any():
        a = ea_t[steps] / np.linalg.norm(ea_t[steps], axis=1, keepdims=True)
        b = eb_t[steps] / np.linalg.norm(eb_t[steps], axis=1, keepdims=True)
        directions = float(np.median(np.degrees(np.arccos(np.clip((a * b).sum(1), -1, 1)))))
    return PoseDeviation(
        hands=hands,
        rotation_median_deg=float(np.median(error[finite])) if finite.any() else None,
        rotation_p90_deg=float(np.percentile(error[finite], 90)) if finite.any() else None,
        eb_rotation_median_deg=float(np.median(rotation_angle_deg(eb_r))),
        translation_direction_median_deg=directions,
        translation_steps=int(steps.sum()),
        stride=stride,
    )
