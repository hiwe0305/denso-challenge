"""Cleaning of the E-A pose before it is written (DA-04 task 10, 9/11/2026).

The E-A job (`estimate_job.py`) gives one hand pose per frame and a camera track from
monocular VO. On the team's tray clips the stage 1 export made from it had 41.6 % of
its normalized actions clipped at +-1 (EgoDex 2.2 %; docs/he/stage1.md 2.7). Offline,
only these steps together brought it under 5 % (2.8):

    frame     the hands in each frame's camera frame, `camera` the identity: the VO
              track is not a measurement (translation a fixed step, rotation drifting)

Parameters are `pose_ea.clean` of `configs/data/egocentric.yaml`. E-B (EgoDex tracking)
is never cleaned. Frames are never dropped or added: DA-18 reads the video and the pose
by the same frame index. A frame where a hand was not seen stays NaN.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from flywheel.data.ingest.egocentric.estimate import POSE_FRAMES
from flywheel.data.ingest.egocentric.pose import EgoPose


@dataclass(frozen=True)
class CleanParams:
    frame: str = "world"

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


def clean_pose(pose: EgoPose, params: CleanParams) -> tuple[EgoPose, dict[str, Any]]:
    """The cleaned pose and what was done, for `bundle.json` `pose_cleaning`."""
    return pose, {"params": params.to_dict()}
