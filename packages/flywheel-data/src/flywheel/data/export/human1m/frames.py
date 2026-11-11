"""Per-frame hand and camera arrays of one episode, in the conventions of the shard.

Camera frame: x right, y down, z forward (OpenCV), metres. Quaternions (qx, qy, qz, qw).

- E-A (the team's recordings): the 21 MediaPipe landmarks the E-A job lifted into the
  camera frame (`left_cam`, `right_cam` of its .npz), cleaned here like task 10 cleans
  the wrist and tips (jump interpolation, Savitzky-Golay per run of seen frames).
  The intrinsic is an assumption of the device (90 deg HFOV), so the metric depth is
  approximate. Joint rotations and the head trajectory are not measured: NaN.
- E-B (EgoDex): ARKit tracking. Joints are moved into the camera frame with
  `inv(camera) @ joint`; the camera pose is ARKit's world pose of the camera.

A hand's mask is 1 when its joints are known and at least one projects inside the
image; its confidence is MediaPipe's handedness score (E-A) or the mean ARKit joint
confidence (E-B; NaN when the file recorded none).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.data.export.human1m.layout import arkit_joints
from flywheel.data.ingest.egocentric.clean import fitted_window, savgol, seen_runs, to_quaternion
from flywheel.data.ingest.egocentric.egodex import read_confidences, read_transforms
from numpy.typing import NDArray

F32 = NDArray[np.float32]
F64 = NDArray[np.float64]
SIDES = ("left", "right")


@dataclass(frozen=True)
class JointClean:
    """Cleaning of E-A joints; the same numbers as `pose_ea.clean` of egocentric.yaml."""

    jump_mad: float = 5.0
    jump_burst: int = 4
    savgol_window: int = 21
    savgol_order: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JointClean:
        return cls(**{k: data[k] for k in ("jump_mad", "jump_burst", "savgol_window",
                                           "savgol_order") if k in data})


@dataclass(frozen=True)
class EpisodeFrames:
    """`hands[side]` (T, 21, 3); `rotations[side]` (T, 21, 4) or None when not measured;
    `camera_position` (T, 3) and `camera_rotation` (T, 4) in the world, or None;
    `confidence[side]` (T,); `intrinsic` (3, 3) and `image_size` (w, h) of the source
    video; `provenance` says where each array came from."""

    hands: dict[str, F32]
    rotations: dict[str, F32 | None]
    camera_position: F32 | None
    camera_rotation: F32 | None
    confidence: dict[str, F32]
    intrinsic: F64
    image_size: tuple[int, int]
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def frames(self) -> int:
        return int(self.hands["left"].shape[0])

    def mask(self, side: str) -> NDArray[np.bool_]:
        """Known and in the image (at least one joint in front of the camera inside it)."""
        points = self.hands[side].astype(np.float64)
        known = known_frames(points)
        pixels, front = project(points, self.intrinsic)
        w, h = self.image_size
        inside = (front & (pixels[..., 0] >= 0) & (pixels[..., 0] < w)
                  & (pixels[..., 1] >= 0) & (pixels[..., 1] < h)).any(axis=1)
        result: NDArray[np.bool_] = known & inside
        return result


def known_frames(points: NDArray[Any]) -> NDArray[np.bool_]:
    """(T,) True where every joint of a (T, J, 3) array is finite."""
    return np.asarray(np.isfinite(points).all(axis=(1, 2)), dtype=np.bool_)


def project(points: F64, intrinsic: F64) -> tuple[F64, NDArray[np.bool_]]:
    """(..., 3) camera-frame points to (..., 2) pixels, and whether each is in front."""
    z = points[..., 2]
    front = np.isfinite(z) & (z > 1e-6)
    safe = np.where(front, z, np.nan)
    u = intrinsic[0, 0] * points[..., 0] / safe + intrinsic[0, 2]
    v = intrinsic[1, 1] * points[..., 1] / safe + intrinsic[1, 2]
    return np.stack([u, v], axis=-1), front


def clean_joints(points: F64, params: JointClean) -> tuple[F64, dict[str, int]]:
    """(T, 21, 3) with NaN rows for unseen frames. In each run of seen frames, steps
    above median + k x 1.4826 x MAD of the mean joint step cut the run into pieces; a
    piece of at most `jump_burst` frames that is not the run's longest is rebuilt by
    linear interpolation from the rest of the run; then Savitzky-Golay per run."""
    out = np.array(points, dtype=np.float64)
    t = len(out)
    seen = known_frames(out)
    bad = np.zeros(t, dtype=bool)
    runs = seen_runs(seen)
    for start, stop in runs:
        if stop - start < 3:
            continue
        step = np.linalg.norm(out[start + 1:stop] - out[start:stop - 1], axis=2).mean(axis=1)
        median = np.median(step)
        mad = 1.4826 * np.median(np.abs(step - median)) + 1e-9
        edges = [start, *(start + 1 + int(i) for i in np.flatnonzero(
            step > median + params.jump_mad * mad)), stop]
        pieces = list(zip(edges, edges[1:]))
        longest = max(pieces, key=lambda piece: piece[1] - piece[0])
        for a, b in pieces:
            if (a, b) != longest and b - a <= params.jump_burst:
                bad[a:b] = True
    flat = out.reshape(t, -1)
    interpolated = 0
    for start, stop in runs:
        frames = np.arange(start, stop)
        good, fix = frames[~bad[start:stop]], frames[bad[start:stop]]
        if len(good) < 2 or not len(fix):
            continue
        for column in range(flat.shape[1]):
            flat[fix, column] = np.interp(fix, good, flat[good, column])
        interpolated += len(fix)
    smoothed = 0
    for start, stop in runs:
        if fitted_window(params.savgol_window, stop - start) <= params.savgol_order + 1:
            continue
        out[start:stop] = savgol(out[start:stop], params.savgol_window, params.savgol_order)
        smoothed += 1
    return out, {"seen_frames": int(seen.sum()), "interpolated_frames": interpolated,
                 "smoothed_runs": smoothed}


def _fit(values: F64, frames: int) -> F64:
    """Cut or NaN-pad axis 0 to `frames`."""
    if len(values) >= frames:
        return values[:frames]
    pad = np.full((frames - len(values), *values.shape[1:]), np.nan)
    return np.concatenate([values, pad])


def from_estimates(path: Path, frames: int, intrinsic: F64, image_size: tuple[int, int],
                   params: JointClean) -> EpisodeFrames:
    """E-A: the job's .npz for one episode, `frames` long (the video's)."""
    with np.load(path) as data:
        arrays = {k: np.asarray(data[k], dtype=np.float64) for k in data.files if k != "meta"}
        meta = str(data["meta"]) if "meta" in data.files else ""
    hands: dict[str, F32] = {}
    confidence: dict[str, F32] = {}
    cleaning: dict[str, Any] = {}
    for side in SIDES:
        points = _fit(arrays[f"{side}_cam"], frames)
        cleaned, cleaning[side] = clean_joints(points, params)
        hands[side] = cleaned.astype(np.float32)
        score = _fit(arrays[f"{side}_score"], frames)
        seen = known_frames(cleaned)
        confidence[side] = np.where(seen, np.nan_to_num(score), 0.0).astype(np.float32)
    return EpisodeFrames(
        hands=hands, rotations={"left": None, "right": None},
        camera_position=None, camera_rotation=None, confidence=confidence,
        intrinsic=np.asarray(intrinsic, dtype=np.float64), image_size=image_size,
        provenance={"pose_source": "E-A", "estimates": path.name, "job_meta": meta,
                    "estimated_frames": int(len(arrays["left_cam"])),
                    "cleaning": {"params": params.__dict__, **cleaning}},
    )


def _xyzw(rotations: F64) -> F64:
    """(N, 3, 3) to (N, 4) quaternions in (qx, qy, qz, qw) order."""
    wxyz = to_quaternion(rotations)
    return np.concatenate([wxyz[:, 1:], wxyz[:, :1]], axis=1)


def from_egodex(path: Path, intrinsic: F64, image_size: tuple[int, int]) -> EpisodeFrames:
    """E-B: an EgoDex HDF5."""
    names = {side: arkit_joints(side) for side in SIDES}
    transforms = read_transforms(path, ["camera", *names["left"], *names["right"]])
    confidences = read_confidences(path, [*names["left"], *names["right"]])
    camera = transforms["camera"].astype(np.float64)
    t = len(camera)
    to_camera = np.linalg.inv(camera)
    hands: dict[str, F32] = {}
    rotations: dict[str, F32 | None] = {}
    confidence: dict[str, F32] = {}
    for side in SIDES:
        world = np.stack([transforms[j].astype(np.float64) for j in names[side]], axis=1)
        local = to_camera[:, None] @ world  # (T, 21, 4, 4)
        hands[side] = local[..., :3, 3].astype(np.float32)
        rotations[side] = _xyzw(local[..., :3, :3].reshape(-1, 3, 3)).reshape(
            t, 21, 4).astype(np.float32)
        recorded = [confidences[j] for j in names[side] if j in confidences]
        confidence[side] = (np.mean(recorded, axis=0) if recorded
                            else np.full(t, np.nan)).astype(np.float32)
    return EpisodeFrames(
        hands=hands, rotations=rotations,
        camera_position=camera[:, :3, 3].astype(np.float32),
        camera_rotation=_xyzw(camera[:, :3, :3]).astype(np.float32),
        confidence=confidence, intrinsic=np.asarray(intrinsic, dtype=np.float64),
        image_size=image_size,
        provenance={"pose_source": "E-B", "hdf5": path.name,
                    "confidence": "recorded" if confidences else "not recorded"},
    )


def scaled_intrinsic(intrinsic: F64, source: tuple[int, int],
                     target: tuple[int, int]) -> F64:
    """The intrinsic of the video after scaling from `source` to `target` (w, h)."""
    sx, sy = target[0] / source[0], target[1] / source[1]
    out = np.array(intrinsic, dtype=np.float64)
    out[0] *= sx
    out[1] *= sy
    return out
