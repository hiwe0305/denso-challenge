"""Human-1M's episode requirements and 3D-tracking checks, measured on one episode.

Requirements (QUALITY_STANDARDS of the Human-1M release): at least 30 fps and 480p,
one or more hands in frame for at least 95 % of the episode, subtasks of 1-10 s.
Tracking checks: bone-length consistency (coefficient of variation of each bone over
the frames a hand is seen, median over bones) and smoothness (median joint
acceleration, m/s^2). They are reported; the export keeps an episode that misses them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from flywheel.data.export.human1m.frames import SIDES, EpisodeFrames, known_frames
from flywheel.data.export.human1m.layout import BONES
from flywheel.data.export.human1m.subtasks import Subtask
from numpy.typing import NDArray


@dataclass(frozen=True)
class Requirements:
    min_fps: float = 30.0
    min_height: int = 480
    min_hands_visible: float = 0.95
    subtask_seconds: tuple[float, float] = (1.0, 10.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Requirements:
        out = dict(data)
        if "subtask_seconds" in out:
            out["subtask_seconds"] = tuple(out["subtask_seconds"])
        return cls(**out)


def bone_cv(points: NDArray[Any], seen: NDArray[np.bool_]) -> float | None:
    """Median over the 20 bones of std / mean of the bone's length; None under 10 frames."""
    p = points[seen].astype(np.float64)
    if len(p) < 10:
        return None
    lengths = np.stack([np.linalg.norm(p[:, b] - p[:, a], axis=1) for a, b in BONES], axis=1)
    mean = lengths.mean(axis=0)
    return float(np.median(lengths.std(axis=0) / np.maximum(mean, 1e-9)))


def acceleration(points: NDArray[Any], seen: NDArray[np.bool_], fps: float) -> float | None:
    """Median joint acceleration over triples of consecutive seen frames, m/s^2."""
    ok = seen[2:] & seen[1:-1] & seen[:-2]
    if not ok.any():
        return None
    p = points.astype(np.float64)
    second = (p[2:] - 2 * p[1:-1] + p[:-2])[ok]
    return float(np.median(np.linalg.norm(second, axis=2)) * fps * fps)


def measure(frames: EpisodeFrames, fps: float, height: int, subtasks: Sequence[Subtask],
            req: Requirements) -> dict[str, Any]:
    """The numbers and pass/fail of each requirement, for the episode metadata."""
    masks = {side: frames.mask(side) for side in SIDES}
    either = masks["left"] | masks["right"]
    visible = float(either.mean()) if frames.frames else 0.0
    lo, hi = req.subtask_seconds
    within = [lo <= s.seconds(fps) <= hi for s in subtasks]
    out: dict[str, Any] = {
        "hands_visible": visible,
        "left_visible": float(masks["left"].mean()),
        "right_visible": float(masks["right"].mean()),
        "subtasks_in_range": float(np.mean(within)) if within else 0.0,
    }
    for side in SIDES:
        known = known_frames(frames.hands[side])
        out[f"{side}_bone_cv"] = bone_cv(frames.hands[side], known)
        out[f"{side}_accel_m_s2"] = acceleration(frames.hands[side], known, fps)
    out["checks"] = {
        "fps": fps >= req.min_fps,
        "resolution": height >= req.min_height,
        "hands_visible": visible >= req.min_hands_visible,
        "subtask_seconds": all(within),
    }
    return out
