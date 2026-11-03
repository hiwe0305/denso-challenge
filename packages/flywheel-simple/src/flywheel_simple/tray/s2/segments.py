"""Cut a parent demo into the three S2 segments by its StepTracker flags (DA-35 task 8, AC 4).

| Segment | Frames | Scorer steps |
|---|---|---|
| K, near the tray | start until lift is reached, plus `hold_s` | 1 approach, 2 grasp, 3 lift |
| W, walk carrying | until reach_b is reached | 4 carry, 5 reach_b |
| P, place | until the end (success, step 7) | 6 place, 7 release_stand |

Each frame also gets an anchor: the frame its wrist targets follow when S2
moves the scene (task 10). The hands follow the robot while it walks (the
approach to table A, the carry, the arrival at table B) and the tray or the
target zone while they handle the tray there:

| Anchor | Frames |
|---|---|
| robot | [0, walk_a_end), [k_end, place_start) |
| tray | [walk_a_end, k_end) |
| target | [place_start, end) |

`walk_a_end` is the end of the approach walk: the last walking run of at least
`walk_min_s` that starts before step 1 (shorter runs are the corrective steps
DA-33's planner takes while reaching). `place_start` is the end of the last
walking run that starts before step 6, i.e. once the robot stands at table B.
The lower body walks while |(vx, vy, vyaw)| >= 0.1 (G1GearWbcPolicy's switch
between its walk and balance policies).

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.predicates import STEP_NAMES
from flywheel_simple.tray.s2.parents import ParentDemo

FPS = 50
WALK_FLAG = 0.1  # |(vx, vy, vyaw)| from which the lower body runs its walking policy
APPROACH, GRASP, LIFT, CARRY, REACH_B, PLACE, RELEASE = range(len(STEP_NAMES))

Segment = Literal["K", "W", "P"]
Anchor = Literal["robot", "tray", "target"]


class SegmentError(ValueError):
    """The demo's flags do not allow the cut (a step missing or out of order)."""


@dataclass(frozen=True)
class Segmentation:
    frames: int
    step_frames: tuple[int | None, ...]  # first frame showing each flag, STEP_NAMES order
    k_end: int  # K = [0, k_end)
    w_end: int  # W = [k_end, w_end), P = [w_end, frames)
    walk_a_end: int
    place_start: int
    walking: tuple[tuple[int, int], ...]  # [start, end) runs of the walking policy

    def segment_of(self, frame: int) -> Segment:
        if not 0 <= frame < self.frames:
            raise IndexError(f"frame {frame} outside [0, {self.frames})")
        if frame < self.k_end:
            return "K"
        return "W" if frame < self.w_end else "P"

    def anchor_of(self, frame: int) -> Anchor:
        segment = self.segment_of(frame)
        if segment == "K":
            return "tray" if frame >= self.walk_a_end else "robot"
        return "target" if frame >= self.place_start else "robot"

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["walking"] = [list(run) for run in self.walking]
        out["step_frames"] = list(self.step_frames)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segmentation:
        return cls(
            frames=int(data["frames"]),
            step_frames=tuple(data["step_frames"]),
            k_end=int(data["k_end"]),
            w_end=int(data["w_end"]),
            walk_a_end=int(data["walk_a_end"]),
            place_start=int(data["place_start"]),
            walking=tuple((int(a), int(b)) for a, b in data["walking"]),
        )


def walking_runs(navigate: NDArray[np.float64]) -> tuple[tuple[int, int], ...]:
    """[start, end) frame runs in which the sticks keep the lower body walking."""
    moving = np.linalg.norm(navigate[:, :3], axis=1) >= WALK_FLAG
    edges = np.diff(np.r_[0, moving.astype(np.int8), 0])
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return tuple((int(a), int(b)) for a, b in zip(starts, ends))


def first_frames(steps: NDArray[np.bool_]) -> tuple[int | None, ...]:
    out: list[int | None] = []
    for k in range(steps.shape[1]):
        hits = np.flatnonzero(steps[:, k])
        out.append(int(hits[0]) if len(hits) else None)
    return tuple(out)


def segment(demo: ParentDemo, hold_s: float = 0.5, walk_min_s: float = 0.5) -> Segmentation:
    """The K, W, P cut and the anchors of `demo`; SegmentError if its flags do not allow it."""
    first = first_frames(demo.steps)
    needed = first[: PLACE + 1]
    if any(f is None for f in needed):
        missing = [STEP_NAMES[k] for k, f in enumerate(needed) if f is None]
        raise SegmentError(f"{demo.parent_id}: no frame shows {missing}")
    reached = [int(f) for f in needed if f is not None]
    if reached != sorted(reached):
        raise SegmentError(f"{demo.parent_id}: steps reached out of order {reached}")
    w_end = reached[REACH_B]
    k_end = min(reached[LIFT] + round(hold_s * FPS), w_end)
    if k_end <= reached[LIFT]:
        raise SegmentError(f"{demo.parent_id}: reach_b on the frame lift is reached")

    runs = walking_runs(demo.navigate)
    before_a = [run for run in runs if run[0] < reached[APPROACH]]
    long_runs = [run for run in before_a if run[1] - run[0] >= round(walk_min_s * FPS)]
    approach = long_runs or before_a
    walk_a_end = min(approach[-1][1], k_end) if approach else 0
    to_b = [run for run in runs if k_end <= run[0] < reached[PLACE]]
    place_start = max(w_end, to_b[-1][1]) if to_b else w_end
    return Segmentation(
        frames=demo.frames,
        step_frames=first,
        k_end=k_end,
        w_end=w_end,
        walk_a_end=walk_a_end,
        place_start=min(place_start, demo.frames),
        walking=runs,
    )
