"""Cut an egocentric episode into task steps, each with its sentence (AC 3; D6).

Rules first. The active hand is the one whose wrist travels at least `min_path_m`
(the longer one when both do). A *dwell* is a run of at least `min_dwell_frames`
frames where its smoothed wrist speed is under `still_speed_m_s`; dwells touching
the first or last frame are rest, not events. Across a dwell the thumb-index
aperture closes at a grasp and opens at a release (`close_delta_m`). Same-kind dwells
in a row collapse to the one with the largest aperture change, a release before any
grasp is dropped, so events alternate grasp, release, grasp... An event sits at the
middle of its dwell.

An event is *ambiguous* when its dwell's mean pose confidence is under
`min_confidence`, it is closer than `min_gap_frames` to the previous event, both hands
are active, or no aperture change says what it is (the longest dwell, or the slowest
frame, stands in for a missing grasp). Ambiguous events go to the `SegmentSuggester`
(RoboBrain) with `model_frames` frames around them, when one is given; its frame then
replaces the rule's (`label_source = model`). Unresolved ones stay as the rule put
them and QA counts them (`segment_ambiguous`).

Layouts (configs/data/egocentric.yaml `segment.steps`):

    pick_place  EgoDex: pick [prev, grasp), place [grasp, next grasp or the end): the
                hand going back after a release belongs to its place
    two_table   the team's recordings of the two-table task, 6 steps (design 3):
                approach, grasp, walk, arrive, place, release; walk is where the
                camera moves faster than `walk_speed_rel` of its peak

Each segment's sentence comes from the `Labeler` (RoboBrain) when given, else from the
step's template filled with the episode's object. `segments.parquet` has the columns
of the contract `Segment` plus `frame_start`, `frame_end` (half-open, at `fps`), as DA-18
reads it (plan 6/11/2026 4.2a); `read_segment_rows` checks every row against `Segment`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.segments import SEGMENT_SCHEMA, Segment
from flywheel.data.ingest.egocentric.config import SegmentConfig
from flywheel.data.ingest.egocentric.pose import SIDES, EgoPose, aperture, wrist_speed
from numpy.typing import NDArray

EventKind = Literal["grasp", "release"]
LabelSource = Literal["rule", "model", "human"]
TABLE_SCHEMA = SEGMENT_SCHEMA.append(pa.field("frame_start", pa.int64(), nullable=False)) \
    .append(pa.field("frame_end", pa.int64(), nullable=False))


class SegmentSuggester(Protocol):
    def suggest(self, images: Sequence[bytes], frames: Sequence[int], event: str,
                instruction: str) -> int | None: ...


class Labeler(Protocol):
    def describe(self, images: Sequence[bytes], step: str, instruction: str) -> str | None: ...


FramesOf = Callable[[Sequence[int]], list[bytes]]  # JPEG frames of the episode's video


@dataclass(frozen=True)
class Dwell:
    start: int
    end: int  # exclusive
    delta_m: float  # aperture at the end minus at the start
    confidence: float  # mean over the dwell; NaN when not recorded

    @property
    def middle(self) -> int:
        return (self.start + self.end) // 2


@dataclass
class Event:
    kind: EventKind
    frame: int
    dwell: Dwell | None
    reasons: list[str] = field(default_factory=list)  # why the rule is unsure
    source: LabelSource = "rule"
    model_frame: int | None = None

    @property
    def unresolved(self) -> bool:
        return bool(self.reasons) and self.source == "rule"


@dataclass(frozen=True)
class EgoSegment:
    frame_start: int
    frame_end: int  # exclusive
    step_id: str
    description: str
    label_source: LabelSource

    def to_segment(self, fps: float) -> Segment:
        return Segment(t_start=self.frame_start / fps, t_end=self.frame_end / fps,
                       step_id=self.step_id, description=self.description,
                       label_source=self.label_source)


@dataclass
class Cut:
    """The segments of one episode and how they were made (`labels.json`)."""

    side: str | None
    segments: list[EgoSegment]
    events: list[Event]
    notes: list[str]
    models: dict[str, str]  # role -> model name, for the roles that answered

    @property
    def unresolved_share(self) -> float:
        """Share of events left open; 1 when the rules found no event at all."""
        return sum(e.unresolved for e in self.events) / len(self.events) if self.events else 1.0

    def labels(self) -> dict[str, Any]:
        return {"side": self.side, "events": [asdict(e) for e in self.events],
                "notes": self.notes, "models": self.models,
                "unresolved_share": self.unresolved_share}


def smooth(values: NDArray[Any], frames: int) -> NDArray[np.float64]:
    if frames <= 1 or len(values) == 0:
        return np.asarray(values, dtype=np.float64)
    pad = frames // 2
    padded = np.pad(np.asarray(values, dtype=np.float64), (pad, frames - 1 - pad), mode="edge")
    return np.asarray(np.convolve(padded, np.ones(frames) / frames, mode="valid"),
                      dtype=np.float64)


def active_sides(pose: EgoPose, cfg: SegmentConfig) -> list[str]:
    """Hands whose wrist travels at least `min_path_m`, longest path first."""
    paths = {}
    for side in SIDES:
        position = pose.wrist(side)[:, :3, 3]
        steps = np.linalg.norm(np.diff(position, axis=0), axis=1)
        paths[side] = float(np.nansum(steps))
    return sorted((s for s in SIDES if paths[s] >= cfg.min_path_m), key=lambda s: -paths[s])


def find_dwells(pose: EgoPose, side: str, fps: float, cfg: SegmentConfig) -> list[Dwell]:
    speed = smooth(wrist_speed(pose, side, fps), cfg.smooth_frames)
    opening = smooth(aperture(pose, side), cfg.smooth_frames)
    confidence = pose.confidence(side)
    still = np.nan_to_num(speed, nan=np.inf) < cfg.still_speed_m_s
    dwells = []
    start: int | None = None
    for i, flag in enumerate([*still, False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            end = i
            if end - start >= cfg.min_dwell_frames and start > 0 and end < len(still):
                window = confidence[start:end]
                dwells.append(Dwell(
                    start, end, float(opening[end - 1] - opening[start]),
                    float(np.nanmean(window)) if np.isfinite(window).any() else float("nan"),
                ))
            start = None
    return dwells


def find_events(
    pose: EgoPose, fps: float, cfg: SegmentConfig
) -> tuple[str | None, list[Event], list[str]]:
    """The active hand, its alternating grasp/release events, and notes."""
    sides = active_sides(pose, cfg)
    if not sides:
        return None, [], ["no hand travels min_path_m: no event"]
    side = sides[0]
    notes = [f"active hand {side}"]
    dwells = find_dwells(pose, side, fps, cfg)
    signed: list[tuple[EventKind, Dwell]] = []
    for dwell in dwells:
        if abs(dwell.delta_m) < cfg.close_delta_m:
            continue
        kind: EventKind = "grasp" if dwell.delta_m < 0 else "release"
        if signed and signed[-1][0] == kind:
            if abs(dwell.delta_m) > abs(signed[-1][1].delta_m):
                signed[-1] = (kind, dwell)
            continue
        signed.append((kind, dwell))
    if signed and signed[0][0] == "release":
        notes.append(f"release at {signed[0][1].middle} before any grasp: dropped")
        signed = signed[1:]
    events = [Event(kind, d.middle, d) for kind, d in signed]
    if not events:
        events = [_stand_in_grasp(pose, side, fps, cfg, dwells)]
    previous: int | None = None
    for event in events:
        held = event.dwell
        if held is not None and np.isfinite(held.confidence) \
                and held.confidence < cfg.min_confidence:
            event.reasons.append("low_confidence")
        if previous is not None and event.frame - previous < cfg.min_gap_frames:
            event.reasons.append("close_to_previous")
        if len(sides) > 1:
            event.reasons.append("two_hands")
        previous = event.frame
    return side, events, notes


def _stand_in_grasp(
    pose: EgoPose, side: str, fps: float, cfg: SegmentConfig, dwells: list[Dwell]
) -> Event:
    if dwells:
        longest = max(dwells, key=lambda d: d.end - d.start)
        return Event("grasp", longest.middle, longest, ["aperture_flat"])
    speed = smooth(wrist_speed(pose, side, fps), cfg.smooth_frames)
    lo, hi = int(len(speed) * 0.2), max(int(len(speed) * 0.8), int(len(speed) * 0.2) + 1)
    frame = lo + int(np.nanargmin(speed[lo:hi]))
    return Event("grasp", frame, None, ["no_dwell"])


def pick_place_steps(events: list[Event], frames: int) -> list[tuple[str, int, int]]:
    """pick up to each grasp, place up to the release after it; what follows the last
    release (the hand going back) stays in that place."""
    cuts = [e.frame for e in events if 0 < e.frame < frames]
    if len(cuts) >= 2 and len(cuts) % 2 == 0:
        cuts = cuts[:-1]
    bounds = [0, *cuts, frames]
    steps = []
    for i in range(len(bounds) - 1):
        if bounds[i + 1] > bounds[i]:
            steps.append(("pick" if i % 2 == 0 else "place", bounds[i], bounds[i + 1]))
    return steps


def camera_speed(pose: EgoPose, fps: float, frames: int) -> NDArray[np.float64]:
    position = pose.camera[:, :3, 3].astype(np.float64)
    if len(position) < 2:
        return np.zeros(len(position))
    step = np.linalg.norm(np.diff(position, axis=0), axis=1) * fps
    return smooth(np.concatenate([step[:1], step]), frames)


def two_table_steps(
    events: list[Event], speed: NDArray[np.float64], frames: int, cfg: SegmentConfig
) -> tuple[list[tuple[str, int, int]], list[str]]:
    """Approach, grasp, walk, arrive, place, release from the first grasp, the release
    after it and the camera's walk between them."""
    notes: list[str] = []
    grasp = next((e for e in events if e.kind == "grasp"), None)
    release = next((e for e in events if e.kind == "release" and grasp and e.frame > grasp.frame),
                   None)
    if grasp is None or release is None:
        notes.append("two_table: no grasp followed by a release; one segment per event")
        return pick_place_steps(events, frames), notes
    g0 = grasp.dwell.start if grasp.dwell else grasp.frame
    r1 = release.dwell.end if release.dwell else release.frame
    between = speed[grasp.frame:release.frame]
    peak = float(np.nanmax(between)) if len(between) else 0.0
    moving = np.flatnonzero(between > cfg.walk_speed_rel * peak) if peak > 0 else np.array([])
    if len(moving) == 0:
        notes.append("two_table: the camera does not move between grasp and release")
        walk0 = walk1 = (grasp.frame + release.frame) // 2
    else:
        walk0, walk1 = grasp.frame + int(moving[0]), grasp.frame + int(moving[-1]) + 1
    r0 = release.dwell.start if release.dwell else release.frame
    bounds = [0, g0, max(walk0, g0), max(walk1, walk0, g0), max(r0, walk1),
              max(r1, r0, walk1), frames]
    names = ("approach", "grasp", "walk", "arrive", "place", "release")
    steps = [(n, bounds[i], bounds[i + 1]) for i, n in enumerate(names)
             if bounds[i + 1] > bounds[i]]
    return steps, notes


def cut_episode(
    pose: EgoPose,
    fps: float,
    layout: str,
    cfg: SegmentConfig,
    *,
    instruction: str,
    obj: str,
    suggester: SegmentSuggester | None = None,
    labeler: Labeler | None = None,
    frames_of: FramesOf | None = None,
    model_names: dict[str, str] | None = None,
) -> Cut:
    """Rules, then the models for what the rules leave open."""
    names = model_names or {}
    frames = pose.frames
    side, events, notes = find_events(pose, fps, cfg)
    used: dict[str, str] = {}
    if suggester is not None and frames_of is not None:
        for event in events:
            if not event.reasons:
                continue
            lo = max(event.frame - cfg.model_window_frames, 0)
            hi = min(event.frame + cfg.model_window_frames, frames - 1)
            shown = sorted({int(round(x)) for x in np.linspace(lo, hi, cfg.model_frames)})
            answer = suggester.suggest(frames_of(shown), shown, event.kind, instruction)
            if answer is not None:
                event.model_frame, event.frame, event.source = answer, answer, "model"
                used["segment_suggester"] = names.get("segment_suggester", "model")
    events.sort(key=lambda e: e.frame)
    if layout == "two_table":
        steps, more = two_table_steps(events, camera_speed(pose, fps, cfg.smooth_frames),
                                      frames, cfg)
        notes += more
    else:
        steps = pick_place_steps(events, frames)
    by_frame = {e.frame: e for e in events}
    templates = cfg.steps[layout]
    segments = []
    for step, start, end in steps:
        modelled = any(by_frame.get(b) is not None and by_frame[b].source == "model"
                       for b in (start, end))
        description = templates.get(step, step).format(object=obj, instruction=instruction)
        source: LabelSource = "model" if modelled else "rule"
        if labeler is not None and frames_of is not None:
            shown = sorted({int(round(x)) for x in np.linspace(start, end - 1, cfg.model_frames)})
            sentence = labeler.describe(frames_of(shown), step, instruction)
            if sentence is not None:
                description, source = sentence, "model"
                used["labeler"] = names.get("labeler", "model")
        segments.append(EgoSegment(start, end, step, description, source))
    return Cut(side, segments, events, notes, used)


def write_segment_table(path: Path, segments: Sequence[EgoSegment], fps: float) -> None:
    rows = [{**s.to_segment(fps).model_dump(), "frame_start": s.frame_start,
             "frame_end": s.frame_end} for s in segments]
    pq.write_table(pa.Table.from_pylist(rows, schema=TABLE_SCHEMA), path)


def read_segment_rows(path: Path) -> list[EgoSegment]:
    """Rows of segments.parquet; each one must be a valid contract `Segment`."""
    table = pq.read_table(path)
    if not table.schema.equals(TABLE_SCHEMA, check_metadata=False):
        raise ValueError(f"{path}: not the egocentric segments schema")
    segments = []
    for row in table.to_pylist():
        frame_start, frame_end = row.pop("frame_start"), row.pop("frame_end")
        segment = Segment.model_validate(row)
        segments.append(EgoSegment(frame_start, frame_end, segment.step_id,
                                   segment.description, segment.label_source))
    return segments
