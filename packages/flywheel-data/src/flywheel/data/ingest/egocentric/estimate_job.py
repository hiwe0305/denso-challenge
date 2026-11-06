"""E-A job: hand pose and camera motion from RGB only (D5; DA-04 AC 4).

Runs outside the workspace, in its own venv on the rtx3060 host, because MediaPipe
pins a numpy that conflicts with `uv.lock`. The file imports only numpy at the top
(OpenCV and MediaPipe inside the functions that need them), so the lane imports its
math and tests it on CPU; the job is copied and run as a script:

    python estimate_job.py --manifest jobs.json --root <source root> --out <dir> \\
        --model hand_landmarker.task

`jobs.json` (written by `fw egocentric pose --job`) lists `episode_id`, `mp4` relative
to `--root`, `intrinsic` (3x3) and `fps`. For each episode the job writes
`<out>/<episode_id>.npz`:

    camera        (T, 4, 4)   camera to world, world = the first frame's camera
    left_px       (T, 21, 2)  MediaPipe landmarks in pixels of the full-size frame
    left_cam      (T, 21, 3)  the same landmarks in the camera frame, metres
    left_score    (T,)        handedness score; 0 where the hand was not found
    right_*                   the same for the right hand
    moving        (T,)        1 where VO estimated a translation for the step
    meta          JSON: model, versions, parameters, seconds

Hands: MediaPipe Hands (Tasks API, `hand_landmarker.task`). Its handedness label is
not used: on EgoDex it is right on some episodes and swapped on others; sides come
from image position (`SideTracker`). Its world
landmarks are metric, centred on the hand, axes along the camera's; the job puts them
in the camera frame with the translation that best reprojects them onto the image
landmarks (linear least squares, `lift_hand`).

Camera: monocular visual odometry with OpenCV between consecutive frames (ORB,
hands masked out). A homography that explains the matches about as well as the
essential matrix means rotation only (`H/E` inlier ratio >= 0.8, or median flow under
`--min-flow`); else `recoverPose` gives rotation and the direction of translation.
Monocular VO has no scale: a moving step is `--step-m` metres long, an assumption.
Everything is tagged `pseudo`.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

LANDMARKS = 21
WRIST, THUMB_TIP, INDEX_MCP, INDEX_TIP, MIDDLE_MCP, MIDDLE_TIP = 0, 4, 5, 8, 9, 12
RING_TIP, PINKY_MCP, PINKY_TIP = 16, 17, 20
TIPS = (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)
H_OVER_E = 0.8
F64 = NDArray[np.float64]


@dataclass(frozen=True)
class HandDetection:
    side: str  # "left" or "right", the person's own hand
    pixels: F64  # (21, 2) in the frame the detector saw
    world: F64  # (21, 3) metres, hand-centred, camera-aligned
    score: float


def lift_hand(pixels: F64, world: F64, intrinsic: F64) -> F64:
    """Camera-frame landmarks: `world + t` with the t that best reprojects onto `pixels`.

    For each landmark, u = fx (X + tx) / (Z + tz) + cx gives tx - a tz = a Z - X with
    a = (u - cx) / fx, and the same in y: two linear equations in t per landmark.
    """
    fx, fy, cx, cy = intrinsic[0, 0], intrinsic[1, 1], intrinsic[0, 2], intrinsic[1, 2]
    a = (pixels[:, 0] - cx) / fx
    b = (pixels[:, 1] - cy) / fy
    n = len(pixels)
    rows = np.zeros((2 * n, 3))
    rows[:n, 0], rows[:n, 2] = 1.0, -a
    rows[n:, 1], rows[n:, 2] = 1.0, -b
    rhs = np.concatenate([a * world[:, 2] - world[:, 0], b * world[:, 2] - world[:, 1]])
    t, *_ = np.linalg.lstsq(rows, rhs, rcond=None)
    return np.asarray(world + t, dtype=np.float64)


def wrist_frame(points: F64) -> F64:
    """(4, 4) wrist pose in the frame of `points` (21, 3): x across the knuckles from
    little to index, y towards the middle knuckle, z normal to the palm, origin at the
    wrist. EgoDex's wrist joint has its own axes, so E-A and E-B are compared by
    position only."""
    x = points[INDEX_MCP] - points[PINKY_MCP]
    y = points[MIDDLE_MCP] - points[WRIST]
    x = x / np.linalg.norm(x)
    z = np.cross(x, y)
    z = z / np.linalg.norm(z)
    y = np.cross(z, x)
    pose = np.eye(4)
    pose[:3, :3] = np.stack([x, y, z], axis=1)
    pose[:3, 3] = points[WRIST]
    return pose


def scaled_intrinsic(intrinsic: F64, scale: float) -> F64:
    k = np.array(intrinsic, dtype=np.float64)
    k[:2] *= scale
    return k


def rotation_from_homography(h: F64, intrinsic: F64) -> F64:
    """The rotation closest to K^-1 H K, which is R for a camera that only rotates."""
    m = np.linalg.inv(intrinsic) @ h @ intrinsic
    u, _, vt = np.linalg.svd(m)
    r = u @ vt
    return np.asarray(r if np.linalg.det(r) > 0 else -r, dtype=np.float64)


def chain(camera: F64, rotation: F64, translation: F64) -> F64:
    """Pose of the next camera, given x_next = R x_prev + t between the two."""
    step = np.eye(4)
    step[:3, :3], step[:3, 3] = rotation, translation
    return np.asarray(camera @ np.linalg.inv(step), dtype=np.float64)


class VOTracker:
    """Frame-to-frame monocular VO with OpenCV; `step` returns (R, t, moving)."""

    def __init__(self, intrinsic: F64, features: int, min_flow: float, step_m: float) -> None:
        self.cv2 = importlib.import_module("cv2")
        self.k = intrinsic
        self.orb = self.cv2.ORB_create(nfeatures=features)
        self.matcher = self.cv2.BFMatcher(self.cv2.NORM_HAMMING, crossCheck=True)
        self.min_flow = min_flow
        self.step_m = step_m
        self.previous: tuple[Any, Any] | None = None

    def step(self, gray: NDArray[np.uint8], mask: NDArray[np.uint8] | None) -> tuple[
            F64, F64, bool]:
        cv2 = self.cv2
        keys, desc = self.orb.detectAndCompute(gray, mask)
        previous, self.previous = self.previous, (keys, desc)
        still = (np.eye(3), np.zeros(3), False)
        if previous is None or desc is None or previous[1] is None:
            return still
        matches = self.matcher.match(previous[1], desc)
        if len(matches) < 12:
            return still
        p0 = np.array([previous[0][m.queryIdx].pt for m in matches], dtype=np.float64)
        p1 = np.array([keys[m.trainIdx].pt for m in matches], dtype=np.float64)
        flow = float(np.median(np.linalg.norm(p1 - p0, axis=1)))
        h, h_inliers = cv2.findHomography(p0, p1, cv2.RANSAC, 2.0)
        e, e_inliers = cv2.findEssentialMat(p0, p1, self.k, cv2.RANSAC, 0.999, 1.0)
        if h is None:
            return still
        rotation_only = (
            flow < self.min_flow or e is None or e.shape != (3, 3)
            or int(h_inliers.sum()) >= H_OVER_E * max(int(e_inliers.sum()), 1)
        )
        if rotation_only:
            return rotation_from_homography(h, self.k), np.zeros(3), False
        _, r, t, _ = cv2.recoverPose(e, p0, p1, self.k, mask=e_inliers)
        return np.asarray(r, np.float64), np.asarray(t, np.float64).ravel() * self.step_m, True


class MediaPipeHands:
    """MediaPipe Hands in video mode; `side` is MediaPipe's label, which `SideTracker`
    replaces."""

    def __init__(self, model: Path) -> None:
        mp = importlib.import_module("mediapipe")
        vision = importlib.import_module("mediapipe.tasks.python.vision")
        base = importlib.import_module("mediapipe.tasks.python")
        options = vision.HandLandmarkerOptions(
            base_options=base.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO, num_hands=2,
        )
        self.mp = mp
        self.landmarker = vision.HandLandmarker.create_from_options(options)

    def detect(self, rgb: NDArray[np.uint8], timestamp_ms: int) -> list[HandDetection]:
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, timestamp_ms)
        height, width = rgb.shape[:2]
        found = []
        for marks, world, handed in zip(result.hand_landmarks, result.hand_world_landmarks,
                                        result.handedness):
            found.append(HandDetection(
                side=handed[0].category_name.lower(),
                pixels=np.array([[m.x * width, m.y * height] for m in marks]),
                world=np.array([[m.x, m.y, m.z] for m in world]),
                score=float(handed[0].score),
            ))
        return found


class SideTracker:
    """Which detection is which hand, from where it is in the image.

    MediaPipe's handedness is not usable on EgoDex's back-of-hand view: unswapped it is
    wrong on one episode, swapped on another (6/11/2026). So the label is ignored. Two
    hands: the one further left is the person's left (a forward view). One hand: the
    side whose last seen wrist is nearer, when it was seen within `reach` of the image
    width; else the image half it is in.
    """

    def __init__(self, width: float, reach: float = 0.25) -> None:
        self.width = width
        self.reach = reach
        self.last: dict[str, float] = {}

    def assign(self, found: list[HandDetection]) -> dict[str, HandDetection]:
        ranked = sorted(found, key=lambda h: -h.score)[:2]
        if len(ranked) == 2:
            ordered = sorted(ranked, key=lambda h: h.pixels[WRIST, 0])
            sides = {"left": ordered[0], "right": ordered[1]}
        elif len(ranked) == 1:
            x = float(ranked[0].pixels[WRIST, 0])
            near = {s: abs(x - p) for s, p in self.last.items() if abs(x - p) <= self.reach
                    * self.width}
            side = min(near, key=near.__getitem__) if near else (
                "left" if x < self.width / 2 else "right")
            sides = {side: ranked[0]}
        else:
            sides = {}
        for side, hand in sides.items():
            self.last[side] = float(hand.pixels[WRIST, 0])
        return {side: replace(hand, side=side) for side, hand in sides.items()}


def hand_mask(shape: tuple[int, int], hands: list[HandDetection], margin: float = 0.25) -> (
        NDArray[np.uint8]):
    """255 everywhere but the hands' boxes (grown by `margin`): VO features off the hands."""
    mask = np.full(shape, 255, dtype=np.uint8)
    for hand in hands:
        lo, hi = hand.pixels.min(axis=0), hand.pixels.max(axis=0)
        grow = (hi - lo) * margin
        x0, y0 = np.maximum((lo - grow).astype(int), 0)
        x1, y1 = (hi + grow).astype(int)
        mask[y0:y1 + 1, x0:x1 + 1] = 0
    return mask


def estimate_video(
    frames: Iterator[NDArray[np.uint8]],
    hands: Any,
    tracker: Any,
    intrinsic: F64,
    fps: float,
    scale: float,
) -> dict[str, F64]:
    """Run the detector and the tracker over BGR `frames` already downscaled by `scale`;
    pixels come back at full size, the camera chain starts at identity."""
    k = scaled_intrinsic(intrinsic, scale)
    sides: SideTracker | None = None
    out: dict[str, list[Any]] = {name: [] for name in
                                 ("camera", "moving", "left_px", "left_cam", "left_score",
                                  "right_px", "right_cam", "right_score")}
    camera = np.eye(4)
    for i, bgr in enumerate(frames):
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        sides = sides or SideTracker(width=float(rgb.shape[1]))
        found = sides.assign(hands.detect(rgb, int(round(i * 1000 / fps))))
        gray = rgb.mean(axis=2).astype(np.uint8)
        r, t, moving = tracker.step(gray, hand_mask(gray.shape, list(found.values())))
        camera = chain(camera, r, t) if i else camera
        out["camera"].append(camera.copy())
        out["moving"].append(float(moving))
        for side in ("left", "right"):
            hand = found.get(side)
            if hand is None:
                out[f"{side}_px"].append(np.full((LANDMARKS, 2), np.nan))
                out[f"{side}_cam"].append(np.full((LANDMARKS, 3), np.nan))
                out[f"{side}_score"].append(0.0)
                continue
            out[f"{side}_px"].append(hand.pixels / scale)
            out[f"{side}_cam"].append(lift_hand(hand.pixels, hand.world, k))
            out[f"{side}_score"].append(hand.score)
    return {name: np.asarray(values, dtype=np.float64) for name, values in out.items()}


def read_video(mp4: Path, max_side: int) -> tuple[Iterator[NDArray[np.uint8]], float, int]:
    cv2 = importlib.import_module("cv2")
    capture = cv2.VideoCapture(str(mp4))
    width, height = capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    scale = min(1.0, max_side / max(width, height))
    size = (round(width * scale), round(height * scale))

    def frames() -> Iterator[NDArray[np.uint8]]:
        try:
            while True:
                ok, image = capture.read()
                if not ok:
                    return
                yield image if scale == 1.0 else cv2.resize(image, size,
                                                            interpolation=cv2.INTER_AREA)
        finally:
            capture.release()

    return frames(), scale, int(capture.get(cv2.CAP_PROP_FRAME_COUNT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E-A: MediaPipe Hands + OpenCV VO")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--max-side", type=int, default=960)
    parser.add_argument("--features", type=int, default=1500)
    parser.add_argument("--min-flow", type=float, default=1.0)
    parser.add_argument("--step-m", type=float, default=0.005)
    args = parser.parse_args(argv)
    mp = importlib.import_module("mediapipe")
    cv2 = importlib.import_module("cv2")
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = json.loads(args.manifest.read_text())
    for job in jobs:
        target = args.out / f"{job['episode_id']}.npz"
        if target.exists():
            continue
        start = time.monotonic()
        frames, scale, count = read_video(args.root / job["mp4"], args.max_side)
        intrinsic = np.array(job["intrinsic"], dtype=np.float64)
        tracker = VOTracker(scaled_intrinsic(intrinsic, scale), args.features, args.min_flow,
                            args.step_m)
        result = estimate_video(frames, MediaPipeHands(args.model), tracker, intrinsic,
                                float(job["fps"]), scale)
        meta = {"model": args.model.name, "mediapipe": mp.__version__, "opencv": cv2.__version__,
                "numpy": np.__version__, "scale": scale, "frames_declared": count,
                "max_side": args.max_side, "features": args.features,
                "min_flow": args.min_flow, "step_m": args.step_m, "action_quality": "pseudo",
                "seconds": round(time.monotonic() - start, 2)}
        partial = target.with_suffix(".part.npz")
        arrays: dict[str, Any] = {"meta": np.array(json.dumps(meta)), **result}
        np.savez(partial, **arrays)
        partial.replace(target)
        print(f"{job['episode_id']}: {len(result['camera'])} frames, {meta['seconds']} s",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
