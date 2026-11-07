"""A person reviews a sample of the segments (AC 3; D6: rules, then models, then a person).

`sample` draws `sample_share` of all segments with a fixed seed and writes a review
sheet, one JSON object per line, with `decision` empty. Each line names its segment by
`match` (step_id, frame_start, frame_end as sampled), which the reviewer leaves alone,
and fills:

    decision     accept | fix | reject
    description  the corrected sentence (fix)
    frame_start, frame_end  corrected bounds (fix, optional)
    reviewer     who reviewed

`apply` writes the reviewed segments back: accept and fix set `label_source = human`
(a fix also changes what the reviewer changed); reject drops the segment, and the
sheet, which is kept, holds why. A row is matched to the segment by its episode and
`match`, not by position (review of PR 152), so a segment rejected, fixed or re-cut
since the sheet was written is refused, never another one edited. An episode not in
episodes.jsonl, a segment reviewed twice, or a fix that breaks the tiling refuses the
whole sheet before anything is written. The sheet is the record of the review; nothing
else is deleted.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

from flywheel.data.ingest.egocentric.episodes import SEGMENTS, bundle_dir, read_bundle
from flywheel.data.ingest.egocentric.files import write_text
from flywheel.data.ingest.egocentric.segments import (
    EgoSegment,
    read_segment_rows,
    write_segment_table,
)

DECISIONS = ("accept", "fix", "reject")


def sample(work: Path, episode_ids: list[str], share: float, seed: int) -> list[dict[str, Any]]:
    """Review rows for `share` of the segments of these episodes (at least one)."""
    every = []
    for eid in sorted(episode_ids):
        for i, s in enumerate(read_segment_rows(bundle_dir(work, eid) / SEGMENTS)):
            every.append({"episode_id": eid, "match": _key(s), "frame_start": s.frame_start,
                          "frame_end": s.frame_end, "step_id": s.step_id,
                          "description": s.description, "label_source": s.label_source,
                          "decision": None, "reviewer": None, "order": i})
    if not every:
        return []
    count = max(1, round(share * len(every)))
    rows = random.Random(seed).sample(every, min(count, len(every)))
    rows.sort(key=lambda r: (r["episode_id"], r.pop("order")))
    return rows


def write_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def read_sheet(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def apply(work: Path, rows: list[dict[str, Any]], episode_ids: list[str]) -> dict[str, int]:
    """Write the reviewed rows into each episode's segments; counts by decision.
    Every row is checked before any file is written."""
    counts = dict.fromkeys(DECISIONS, 0)
    by_episode: dict[str, list[dict[str, Any]]] = {}
    known = set(episode_ids)
    for row in rows:
        if row.get("decision") is None:
            continue
        if row["decision"] not in DECISIONS:
            raise ValueError(f"review decision {row['decision']!r} is not one of {DECISIONS}")
        if row.get("episode_id") not in known:
            raise ValueError(f"review row for {row.get('episode_id')!r}: not an episode of"
                             " episodes.jsonl")
        if not isinstance(row.get("match"), dict):
            raise ValueError(f"{row['episode_id']}: review row without `match`; sample again")
        if not row.get("reviewer"):
            raise ValueError(f"{row['episode_id']} {_name(row['match'])}: no reviewer named")
        by_episode.setdefault(row["episode_id"], []).append(row)
    written: list[tuple[Path, list[EgoSegment], float]] = []
    for eid, reviewed in by_episode.items():
        path = bundle_dir(work, eid) / SEGMENTS
        current = read_segment_rows(path)
        segments: list[EgoSegment | None] = list(current)
        for row in reviewed:
            matches = [i for i, s in enumerate(current) if _key(s) == row["match"]]
            if not matches:
                raise ValueError(f"{eid} has no segment {_name(row['match'])}: rejected, fixed"
                                 " or re-cut since the sheet was written")
            index = matches[0]
            if segments[index] is None or segments[index] is not current[index]:
                raise ValueError(f"{eid} segment {_name(row['match'])} reviewed twice")
            counts[row["decision"]] += 1
            if row["decision"] == "reject":
                segments[index] = None
                continue
            segments[index] = replace(
                current[index], label_source="human",
                description=str(row.get("description") or current[index].description),
                frame_start=int(row.get("frame_start", current[index].frame_start)),
                frame_end=int(row.get("frame_end", current[index].frame_end)),
            )
        kept = [s for s in segments if s is not None]
        _check_order(eid, kept)
        written.append((path, kept, read_bundle(work, eid).fps))
    for path, kept, fps in written:
        write_segment_table(path, kept, fps)
    return counts


def _key(segment: EgoSegment) -> dict[str, Any]:
    return {"step_id": segment.step_id, "frame_start": segment.frame_start,
            "frame_end": segment.frame_end}


def _name(match: dict[str, Any]) -> str:
    return f"{match.get('step_id')}@{match.get('frame_start')}-{match.get('frame_end')}"


def _check_order(eid: str, segments: list[EgoSegment]) -> None:
    for a, b in zip(segments, segments[1:]):
        if b.frame_start < a.frame_end:
            raise ValueError(f"{eid}: reviewed segments overlap at frame {b.frame_start}")
    for s in segments:
        if s.frame_end <= s.frame_start:
            raise ValueError(f"{eid}: segment {s.step_id} is empty after review")
