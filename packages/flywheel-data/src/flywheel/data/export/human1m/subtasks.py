"""Timed, hand-specific subtask annotations that cover the whole episode.

Human-1M's subtasks are contiguous, 1-10 s, hand-specific segments (QUALITY_STANDARDS).

- Team tray clips (two_table): three phases from frame marks read off keyframes
  (`lift`, `place`): reach and grasp [0, lift), lift and carry [lift, place), lower and
  release [place, end). A phase shorter than `min_seconds` merges into a neighbour and
  the sentence of the merged phases is used. The clips last 2-4 s, so the 1 s floor of
  Human-1M is not used; how many subtasks fall in 1-10 s is reported instead.
- EgoDex: the rule segments of `fw egocentric annotate` (pick, place), the hand that
  the rules found active added to the sentence, gaps closed at their midpoints so the
  segments tile the episode.

Each subtask names its annotation source; `info.json` describes the sources.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

PHASES = ("grasp", "carry", "place")


@dataclass(frozen=True)
class Subtask:
    start: int  # first frame
    end: int  # one past the last frame
    text: str
    source: str  # key of the annotation source

    def seconds(self, fps: float) -> float:
        return (self.end - self.start) / fps


@dataclass(frozen=True)
class Marks:
    """Phase marks of one tray clip, frames: box off the first table, starts going down
    onto the second."""

    lift: int
    place: int


def merge_short(pieces: list[tuple[tuple[str, ...], int, int]],
                min_frames: int) -> list[tuple[tuple[str, ...], int, int]]:
    """Merge the shortest piece below `min_frames` into its neighbour (the shorter one
    when it has two) until none is below or one piece is left."""
    pieces = [p for p in pieces if p[2] > p[1]]
    while len(pieces) > 1:
        short = [i for i, p in enumerate(pieces) if p[2] - p[1] < min_frames]
        if not short:
            break
        i = min(short, key=lambda k: pieces[k][2] - pieces[k][1])
        if i == 0:
            j = 1
        elif i == len(pieces) - 1:
            j = i - 1
        else:
            before, after = pieces[i - 1], pieces[i + 1]
            j = i - 1 if before[2] - before[1] <= after[2] - after[1] else i + 1
        a, b = sorted((i, j))
        merged = (pieces[a][0] + pieces[b][0], pieces[a][1], pieces[b][2])
        pieces = [*pieces[:a], merged, *pieces[b + 1:]]
    return pieces


def tray_subtasks(frames: int, fps: float, marks: Marks | None,
                  templates: Mapping[str, str], min_seconds: float, source: str,
                  fallback: str, fallback_source: str) -> list[Subtask]:
    """Subtasks of one tray clip; without marks, one subtask with the task sentence."""
    if marks is None:
        return [Subtask(0, frames, fallback, fallback_source)]
    if not 0 <= marks.lift <= marks.place <= frames:
        raise ValueError(f"marks {marks} do not fit a clip of {frames} frames")
    pieces = merge_short([(("grasp",), 0, marks.lift), (("carry",), marks.lift, marks.place),
                          (("place",), marks.place, frames)],
                         max(1, round(min_seconds * fps)))
    out = []
    for names, start, end in pieces:
        key = "+".join(names)
        if key not in templates:
            raise ValueError(f"no subtask sentence for {key!r} in the config")
        out.append(Subtask(start, end, templates[key], source))
    return out


def with_hand(text: str, side: str | None) -> str:
    """'pick up the bowl' and 'right' -> 'Pick up the bowl with the right hand.'"""
    sentence = text.strip().rstrip(".")
    if side in ("left", "right"):
        sentence += f" with the {side} hand"
    return sentence[:1].upper() + sentence[1:] + "."


def tile(segments: Sequence[tuple[int, int, str]], frames: int) -> list[tuple[int, int, str]]:
    """Segments sorted by start, made to cover [0, frames): the first starts at 0, the
    last ends at `frames`, a gap or overlap between two closes at its midpoint."""
    ordered = sorted((max(0, a), min(frames, b), t) for a, b, t in segments if b > a)
    ordered = [s for s in ordered if s[1] > s[0]]
    if not ordered:
        return []
    cuts = [0]
    for (_, end, _), (start, _, _) in zip(ordered, ordered[1:]):
        cuts.append(max(cuts[-1], (end + start) // 2))
    cuts.append(frames)
    tiled = [(cuts[i], cuts[i + 1], t) for i, (_, _, t) in enumerate(ordered)]
    return [s for s in tiled if s[1] > s[0]]


def rule_subtasks(segments: Sequence[tuple[int, int, str]], frames: int, side: str | None,
                  source: str, fallback: str, fallback_source: str) -> list[Subtask]:
    """EgoDex: rule segments (frame_start, frame_end, description) tiled over the episode."""
    tiled = tile(segments, frames)
    if not tiled:
        return [Subtask(0, frames, fallback, fallback_source)]
    return [Subtask(a, b, with_hand(t, side), source) for a, b, t in tiled]
