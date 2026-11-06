"""A person reviews a sample of the segments (AC 3; D6: rules, then models, then a person).

`sample` draws `sample_share` of all segments with a fixed seed and writes a review
sheet, one JSON object per line, with `decision` empty. The reviewer fills each line:

    decision     accept | fix | reject
    description  the corrected sentence (fix)
    frame_start, frame_end  corrected bounds (fix, optional)
    reviewer     who reviewed

`apply` writes the reviewed segments back: accept and fix set `label_source = human`
(a fix also changes what the reviewer changed); reject drops the segment, and the
sheet, which is kept, holds why. A fix that breaks the tiling of the episode is
refused, not written. The sheet is the record of the review; nothing else is deleted.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

from flywheel.data.ingest.egocentric.episodes import SEGMENTS, bundle_dir, read_bundle
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
            every.append({"episode_id": eid, "segment": i, "frame_start": s.frame_start,
                          "frame_end": s.frame_end, "step_id": s.step_id,
                          "description": s.description, "label_source": s.label_source,
                          "decision": None, "reviewer": None})
    if not every:
        return []
    count = max(1, round(share * len(every)))
    rows = random.Random(seed).sample(every, min(count, len(every)))
    return sorted(rows, key=lambda r: (r["episode_id"], r["segment"]))


def write_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def read_sheet(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def apply(work: Path, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Write the reviewed rows into each episode's segments; counts by decision."""
    counts = dict.fromkeys(DECISIONS, 0)
    by_episode: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("decision") is None:
            continue
        if row["decision"] not in DECISIONS:
            raise ValueError(f"review decision {row['decision']!r} is not one of {DECISIONS}")
        if not row.get("reviewer"):
            raise ValueError(f"{row['episode_id']} segment {row['segment']}: no reviewer named")
        by_episode.setdefault(row["episode_id"], []).append(row)
    for eid, reviewed in by_episode.items():
        path = bundle_dir(work, eid) / SEGMENTS
        segments: list[EgoSegment | None] = list(read_segment_rows(path))
        for row in reviewed:
            index = int(row["segment"])
            current = segments[index]
            if current is None:
                raise ValueError(f"{eid} segment {index} reviewed twice")
            counts[row["decision"]] += 1
            if row["decision"] == "reject":
                segments[index] = None
                continue
            segments[index] = replace(
                current, label_source="human",
                description=str(row.get("description") or current.description),
                frame_start=int(row.get("frame_start", current.frame_start)),
                frame_end=int(row.get("frame_end", current.frame_end)),
            )
        kept = [s for s in segments if s is not None]
        _check_order(eid, kept)
        write_segment_table(path, kept, read_bundle(work, eid).fps)
    return counts


def _check_order(eid: str, segments: list[EgoSegment]) -> None:
    for a, b in zip(segments, segments[1:]):
        if b.frame_start < a.frame_end:
            raise ValueError(f"{eid}: reviewed segments overlap at frame {b.frame_start}")
    for s in segments:
        if s.frame_end <= s.frame_start:
            raise ValueError(f"{eid}: segment {s.step_id} is empty after review")
