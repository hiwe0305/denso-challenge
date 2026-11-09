"""Cleaning of the E-A pose before it is written (DA-04 task 10, 9/11/2026).

The E-A job (`estimate_job.py`) gives one hand pose per frame and a camera track from
monocular VO. On the team's tray clips the stage 1 export made from it had 41.6 % of
its normalized actions clipped at +-1 (EgoDex 2.2 %; docs/he/stage1.md 2.7). Offline,
only these steps together brought it under 5 % (2.8):

    frame     the hands in each frame's camera frame, `camera` the identity: the VO
              track is not a measurement (translation a fixed step, rotation drifting)
    flip      MediaPipe sometimes gives a mirrored hand for a frame; the wrist axes
              (`estimate_job.wrist_frame`, signs fixed by the landmarks) then turn by
              pi, mostly about y (81 % of 1052 flips on the 153 tray clips). Each frame
              is turned pi about a wrist axis when that brings it more than `flip_deg`
              closer to the previous seen frame. Then the whole track gets one sign:
              turned pi about y when most frames have the other hand's chirality
              (fingertips on the palm side: +z for a right hand, -z for a left one).
              Forcing that chirality frame by frame was tried and gave more flips
              (6.4 % of steps instead of 4.9 %): it is a vote over the track, not a rule
              per frame. A pi turn of the whole track leaves every delta unchanged.

Parameters are `pose_ea.clean` of `configs/data/egocentric.yaml`. E-B (EgoDex tracking)
is never cleaned. Frames are never dropped or added: DA-18 reads the video and the pose
by the same frame index. A frame where a hand was not seen stays NaN.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np
from flywheel.data.ingest.egocentric.estimate import POSE_FRAMES
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose
from numpy.typing import NDArray

F64 = NDArray[np.float64]
# pi about the wrist's x, y, z: R @ FLIP keeps that axis and negates the other two
FLIPS = (np.diag([1.0, -1.0, -1.0]), np.diag([-1.0, 1.0, -1.0]), np.diag([-1.0, -1.0, 1.0]))
FLIP_Y = FLIPS[1]
CHIRALITY = {"left": -1.0, "right": 1.0}  # side of the palm plane the fingertips are on


@dataclass(frozen=True)
class CleanParams:
    frame: str = "world"
    flip_deg: float | None = None  # None: no continuity guard, no track sign

    def __post_init__(self) -> None:
        if self.frame not in POSE_FRAMES:
            raise ValueError(f"pose_ea.clean.frame {self.frame!r} is not one of {POSE_FRAMES}")

    @classmethod
    def from_config(cls, pose_ea: Mapping[str, Any]) -> CleanParams:
        raw = dict(pose_ea.get("clean") or {})
        unknown = set(raw) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise ValueError(f"pose_ea.clean has unknown keys {sorted(unknown)}")
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def angle(a: F64, b: F64) -> F64:
    """Rotation angle between rotation matrices, radians; broadcasts over leading axes."""
    cos = (np.trace(a @ np.swapaxes(b, -1, -2), axis1=-2, axis2=-1) - 1) / 2
    out: F64 = np.arccos(np.clip(cos, -1.0, 1.0))
    return out


def finite_frames(wrist: F64) -> NDArray[np.bool_]:
    return np.asarray(np.isfinite(wrist.reshape(len(wrist), -1)).all(axis=1))


def keep_continuous(rotations: F64, flip_deg: float) -> tuple[F64, int]:
    """(T, 3, 3) with NaN rows where the hand was not seen: each seen frame turned pi
    about a wrist axis when that is more than `flip_deg` closer to the previous seen
    (already turned) frame. Returns the rotations and how many frames were turned."""
    out = rotations.copy()
    seen = np.flatnonzero(np.isfinite(rotations.reshape(len(rotations), -1)).all(axis=1))
    turned = 0
    for previous, t in zip(seen, seen[1:]):
        candidates = np.stack([out[t], *(out[t] @ flip for flip in FLIPS)])
        gaps = angle(candidates, out[previous][None])
        best = int(np.argmin(gaps))
        if best and gaps[0] - gaps[best] > np.radians(flip_deg):
            out[t] = candidates[best]
            turned += 1
    return out, turned


def chirality(wrist: F64, tips: F64) -> F64:
    """(T,) +1 where the four fingertips (not the thumb) are on the +z side of the wrist
    frame, -1 on the -z side; NaN where the hand was not seen."""
    offset = tips[:, 1:] - wrist[:, None, :3, 3]
    out: F64 = np.sign(np.einsum("tfi,ti->t", offset, wrist[:, :3, 2]) / 4)
    return out


def one_sign(wrist: F64, tips: F64, side: str) -> tuple[F64, bool]:
    """The track turned pi about y when most seen frames have the other hand's chirality."""
    votes = chirality(wrist, tips)
    votes = votes[np.isfinite(votes)]
    if not len(votes) or np.sum(votes == CHIRALITY[side]) >= np.sum(votes == -CHIRALITY[side]):
        return wrist, False
    out = wrist.copy()
    out[:, :3, :3] = wrist[:, :3, :3] @ FLIP_Y
    return out, True


def clean_pose(pose: EgoPose, params: CleanParams) -> tuple[EgoPose, dict[str, Any]]:
    """The cleaned pose and what was done, for `bundle.json` `pose_cleaning`."""
    values = {name: np.asarray(getattr(pose, name), np.float64) for name in (
        "left_wrist", "right_wrist", "left_tips", "right_tips")}
    report: dict[str, Any] = {"params": params.to_dict()}
    for side in SIDES:
        wrist, tips = values[f"{side}_wrist"], values[f"{side}_tips"]
        done: dict[str, Any] = {"seen_frames": int(finite_frames(wrist).sum())}
        if params.flip_deg is not None:
            wrist = wrist.copy()
            wrist[:, :3, :3], done["flipped_frames"] = keep_continuous(wrist[:, :3, :3],
                                                                       params.flip_deg)
            wrist, done["track_turned"] = one_sign(wrist, tips, side)
        values[f"{side}_wrist"], values[f"{side}_tips"] = wrist, tips
        report[side] = done
    cleaned = replace(pose, **{k: v.astype(np.float32) for k, v in values.items()})
    return cleaned, report
