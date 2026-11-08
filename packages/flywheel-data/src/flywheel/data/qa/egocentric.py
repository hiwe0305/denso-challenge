"""QA of egocentric episodes (DA-04 AC 5): one contract `QAReport` per episode.

Robot QA (`qa/checks.py`) checks actions and replays; an egocentric episode has
neither, so its checks are its own (design 6.6), thresholds in
`configs/data/egocentric.yaml` `qa`:

    min_frames           frames of the pose; fails below the threshold
    video_frames         |frames of the mp4 - frames of the pose|; DA-18 cuts both
    pose_finite          share of frames whose camera pose is not finite
    hand_pose_nan        frames where a hand's wrist or tips are NaN (E-A loses hands);
                         the reason gives the count per hand. Fails `when_missing` when no
                         frame has a finite hand. The pose is not cut or mended: DA-18
                         drops the segments with NaN frames
    pose_low_confidence  share of frames where neither hand reaches `below`;
                         a source that recorded no confidence fails `when_missing`
    hand_out_of_frame    share of frames where no wrist projects inside the image
    camera_jitter_deg_s  RMS of the camera's angular speed minus its 9-frame mean
    instruction          1 when the episode has no sentence
    segments             1 without segments, or with empty, overlapping or out-of-order
                         ones, or ones past the last frame
    segment_count        number of segments; fails below the threshold (a pick and a place)
    segment_ambiguous    share of events the rules left open, no model or person
    deid_gate            1 when the de-identification gate stops the episode

A check fails when its value is above the threshold (min_frames, segment_count:
below). The
decision is the worst `on_fail` of the failed checks, as in robot QA.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from flywheel.contracts.artifacts import Episode, QACheck, QAReport
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose
from flywheel.data.ingest.egocentric.segments import EgoSegment, smooth
from numpy.typing import NDArray

SEVERITY = {"pass": 0, "flag": 1, "quarantine": 2, "reject": 3}
JITTER_WINDOW = 9


@dataclass(frozen=True)
class EgoQAInput:
    episode: Episode
    pose: EgoPose
    segments: Sequence[EgoSegment]
    unresolved_share: float
    video_frames: int
    instruction: str
    intrinsic: NDArray[np.float64]  # (3, 3)
    image_size: tuple[int, int]  # width, height
    fps: float
    gate_passed: bool


def finite_hands(pose: EgoPose) -> dict[str, NDArray[np.bool_]]:
    """Per side, (T,) True where the wrist and the five tips are all finite."""
    t = pose.frames
    out: dict[str, NDArray[np.bool_]] = {}
    for side in SIDES:
        joints = np.concatenate([pose.wrist(side).reshape(t, -1), pose.tips(side).reshape(t, -1)],
                                axis=1)
        out[side] = np.asarray(np.isfinite(joints).all(axis=1))
    return out


def judge_hands(pose: EgoPose, cfg: EgoConfig,
                results: list[tuple[QACheck, str, str | None]]) -> None:
    """`hand_pose_nan`: flag NaN hand frames, reject when no frame has a finite hand."""
    rule = cfg.qa["hand_pose_nan"]
    finite = finite_hands(pose)
    nan = {side: int((~ok).sum()) for side, ok in finite.items()}
    count = sum(1 for ok in zip(*finite.values()) if not all(ok))
    check = QACheck(name="hand_pose_nan", value=float(count), threshold=rule.threshold,
                    passed=count <= rule.threshold)
    if check.passed:
        results.append((check, "pass", None))
        return
    per_hand = ", ".join(f"{side} {nan[side]}/{pose.frames}" for side in SIDES)
    if not np.logical_or(*finite.values()).any():
        results.append((check, rule.when_missing or rule.on_fail,
                        f"hand_pose_nan ({rule.code}): no frame has a finite hand pose"
                        f" (NaN frames: {per_hand})"))
    else:
        results.append((check, rule.on_fail,
                        f"hand_pose_nan ({rule.code}): NaN hand pose in {count} frames"
                        f" ({per_hand})"))


def wrist_pixels(pose: EgoPose, side: str, intrinsic: NDArray[np.float64]) -> NDArray[np.float64]:
    """(T, 3): u, v of the wrist and its depth z in the camera frame (NaN if unknown)."""
    world = pose.wrist(side)[:, :, 3].astype(np.float64)
    camera = np.linalg.inv(pose.camera.astype(np.float64))
    local = np.einsum("tij,tj->ti", camera, world)[:, :3]
    z = local[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = intrinsic[0, 0] * local[:, 0] / z + intrinsic[0, 2]
        v = intrinsic[1, 1] * local[:, 1] / z + intrinsic[1, 2]
    return np.stack([u, v, z], axis=1)


def in_frame(pose: EgoPose, intrinsic: NDArray[np.float64], size: tuple[int, int]) -> NDArray[
        np.bool_]:
    """(T,) whether at least one wrist projects inside the image, in front of the camera."""
    seen = np.zeros(pose.frames, dtype=bool)
    for side in SIDES:
        u, v, z = wrist_pixels(pose, side, intrinsic).T
        with np.errstate(invalid="ignore"):
            seen |= (z > 0) & (u >= 0) & (u < size[0]) & (v >= 0) & (v < size[1])
    return seen


def angular_speed_deg_s(camera: NDArray[np.float32], fps: float) -> NDArray[np.float64]:
    """Rotation angle between consecutive camera poses, degrees per second, (T-1,)."""
    r = camera[:, :3, :3].astype(np.float64)
    relative = np.einsum("tji,tjk->tik", r[:-1], r[1:])
    cos = np.clip((np.trace(relative, axis1=1, axis2=2) - 1) / 2, -1.0, 1.0)
    out: NDArray[np.float64] = np.degrees(np.arccos(cos)) * fps
    return out


def jitter_deg_s(camera: NDArray[np.float32], fps: float) -> float:
    if len(camera) < 3:
        return 0.0
    speed = angular_speed_deg_s(camera, fps)
    finite = speed[np.isfinite(speed)]
    if len(finite) < 2:
        return 0.0
    high = finite - smooth(finite, JITTER_WINDOW)
    return float(np.sqrt(np.mean(high**2)))


def valid_segments(segments: Sequence[EgoSegment], frames: int) -> bool:
    """At least one segment, each non-empty, in order, not overlapping, inside
    [0, frames). Rules tile the episode; a segment a reviewer rejected leaves a gap."""
    if not segments:
        return False
    end = 0
    for segment in segments:
        if segment.frame_start < end or segment.frame_end <= segment.frame_start:
            return False
        end = segment.frame_end
    return end <= frames


def run_ego_qa(item: EgoQAInput, cfg: EgoConfig) -> QAReport:
    pose = item.pose
    results: list[tuple[QACheck, str, str | None]] = []

    def judge(name: str, value: float, detail: str = "", below: bool = False) -> None:
        rule = cfg.qa[name]
        passed = value >= rule.threshold if below else value <= rule.threshold
        check = QACheck(name=name, value=float(value), threshold=rule.threshold, passed=passed)
        if passed:
            results.append((check, "pass", None))
        else:
            sign = "<" if below else ">"
            reason = f"{name}: {value:g} {sign} {rule.threshold:g}" + (f" ({detail})" if detail
                                                                         else "")
            results.append((check, rule.on_fail, reason))

    judge("deid_gate", 0.0 if item.gate_passed else 1.0,
          "raw and not waived, or a blurred copy missing or changed")
    judge("min_frames", pose.frames, "frames of the pose", below=True)
    judge("video_frames", abs(item.video_frames - pose.frames),
          f"mp4 {item.video_frames}, pose {pose.frames}")
    finite = np.isfinite(pose.camera.reshape(pose.frames, -1)).all(axis=1)
    judge("pose_finite", float(1 - finite.mean()) if pose.frames else 1.0)
    judge_hands(pose, cfg, results)
    confidence = np.stack([pose.confidence_left, pose.confidence_right], axis=1)
    if not np.isfinite(confidence).any():
        rule = cfg.qa["pose_low_confidence"]
        check = QACheck(name="pose_low_confidence", value=1.0, threshold=rule.threshold,
                        passed=False)
        results.append((check, rule.when_missing or rule.on_fail,
                        "pose_low_confidence: the source recorded no pose confidence"))
    else:
        below = cfg.qa["pose_low_confidence"].below or 0.0
        best = np.nanmax(np.nan_to_num(confidence, nan=-1.0), axis=1)
        judge("pose_low_confidence", float((best < below).mean()), f"below {below:g}")
    seen = in_frame(pose, item.intrinsic, item.image_size)
    judge("hand_out_of_frame", float(1 - seen.mean()) if pose.frames else 1.0)
    judge("camera_jitter_deg_s", jitter_deg_s(pose.camera, item.fps))
    judge("instruction", 0.0 if item.instruction.strip() else 1.0)
    judge("segments", 0.0 if valid_segments(item.segments, pose.frames) else 1.0,
          f"{len(item.segments)} segments")
    # a pick-and-place episode has a pick and a place at least; one segment means an
    # event was lost (review of PR 152: a model frame 0 left ep_603d1475 one pick)
    judge("segment_count", len(item.segments), "a pick and a place at least", below=True)
    judge("segment_ambiguous", item.unresolved_share)
    decision = max((r[1] for r in results), key=SEVERITY.__getitem__, default="pass")
    key = hashlib.sha256(f"{item.episode.episode_id}|{cfg.threshold_version}".encode())
    return QAReport(
        report_id=f"qa_{key.hexdigest()[:16]}",
        episode_id=item.episode.episode_id,
        threshold_version=cfg.threshold_version,
        decision=decision,  # type: ignore[arg-type]
        reasons=[r[2] for r in results if r[2] is not None],
        checks=[r[0] for r in results],
    )
