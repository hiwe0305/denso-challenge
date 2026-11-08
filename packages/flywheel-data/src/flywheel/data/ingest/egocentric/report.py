"""The egocentric part of the dataset report (DA-04 AC 7; design 6.5).

The `DatasetReport` contract and the page come from the lane's API
(`dataset_report`, `render_html`), as for the robot sources. This module adds what
is egocentric, as JSON (`report/egocentric.json`) and as a section put into that
page: segments and their label sources, pass, flag and reject by check, the hours
of video, the source's licence and de-identification waiver, and how far E-A is from
E-B where both exist. Nothing is added to the contract.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import DatasetReport, Episode, QAReport
from flywheel.data.ingest.egocentric.segments import EgoSegment
from flywheel.data.ingest.egocentric.source import EgoSourceRecord

DECISIONS = ("pass", "flag", "quarantine", "reject")
DEVIATION_KEYS = ("pixel_median", "wrist_pixel_median", "point_median_m", "depth_median_m",
                  "detection")


@dataclass
class EgoSummary:
    dataset_id: str
    threshold_version: str
    source: dict[str, Any]  # source_id, detail, licence, data_class, waiver, files, bytes
    episodes: int
    frames: int
    seconds: float
    segments: int
    steps: dict[str, int]
    label_sources: dict[str, int]
    decisions: dict[str, int]
    checks: dict[str, dict[str, Any]]  # name -> outcome counts, threshold, median value
    deviation: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def summarize_ego(
    dataset_id: str,
    source: EgoSourceRecord,
    episodes: Sequence[Episode],
    reports: Sequence[QAReport],
    segments: Mapping[str, Sequence[EgoSegment]],
    frames: Mapping[str, tuple[int, float]],  # episode_id -> (frames, fps)
    deviations: Mapping[str, Mapping[str, Any]],
    on_fail: Mapping[str, str],  # check -> what failing it does (egocentric.yaml qa)
) -> EgoSummary:
    by_episode = {r.episode_id: r for r in reports}
    missing = [e.episode_id for e in episodes if e.episode_id not in by_episode]
    if missing:
        raise ValueError(f"{len(missing)} episodes have no egocentric QAReport, e.g. {missing[0]}")
    decisions: Counter[str] = Counter(by_episode[e.episode_id].decision for e in episodes)
    checks: dict[str, dict[str, Any]] = {}
    values: dict[str, list[float]] = {}
    for e in episodes:
        report = by_episode[e.episode_id]
        for check in report.checks:
            entry = checks.setdefault(check.name, {"threshold": check.threshold,
                                                   **dict.fromkeys(DECISIONS, 0)})
            entry["pass" if check.passed else on_fail[check.name]] += 1
            values.setdefault(check.name, []).append(check.value)
    for name, entry in checks.items():
        entry["median"] = float(np.median(values[name]))
    every = [s for e in episodes for s in segments.get(e.episode_id, ())]
    total = sum(frames[e.episode_id][0] for e in episodes)
    seconds = sum(f / fps for f, fps in (frames[e.episode_id] for e in episodes))
    return EgoSummary(
        dataset_id=dataset_id,
        threshold_version=reports[0].threshold_version if reports else "",
        source={"source_id": source.source_id, "source_detail": source.source_detail,
                "license": source.license, "data_class": source.data_class,
                "deid_waiver": source.deid_waiver, "files": len(source.files),
                "bytes": source.total_bytes, "deid_copies": len(source.deid_copies),
                "deid_model": source.deid_method.get("model", {}).get("name")},
        episodes=len(episodes),
        frames=total,
        seconds=round(seconds, 2),
        segments=len(every),
        steps=dict(sorted(Counter(s.step_id for s in every).items())),
        label_sources=dict(sorted(Counter(s.label_source for s in every).items())),
        decisions={d: decisions.get(d, 0) for d in DECISIONS},
        checks=dict(sorted(checks.items())),
        deviation=aggregate_deviation(deviations),
    )


def aggregate_deviation(deviations: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Medians over episodes of each episode's E-A against E-B numbers."""
    if not deviations:
        return {}
    out: dict[str, Any] = {"episodes": len(deviations)}
    for side in ("left", "right"):
        hands = [d["hands"][side] for d in deviations.values() if d["hands"].get(side)]
        out[side] = {k: float(np.median([h[k] for h in hands])) for k in DEVIATION_KEYS} \
            if hands else None
        if hands:
            out[side]["frames"] = int(sum(h["frames"] for h in hands))
    for key in ("rotation_median_deg", "rotation_p90_deg", "eb_rotation_median_deg",
                "translation_direction_median_deg"):
        found = [d[key] for d in deviations.values() if d.get(key) is not None]
        out[key] = float(np.median(found)) if found else None
    return out


def section_html(summary: EgoSummary) -> str:
    s = summary.source
    parts = [
        "<h2>Egocentric</h2>",
        f"<p>Source <code>{_e(s['source_id'])}</code> ({_e(s['source_detail'])}),"
        f" licence {_e(s['license'])}, data class {_e(s['data_class'])}; {s['files']} files,"
        f" {s['bytes'] / 1e6:.1f} MB. {summary.episodes} episodes, {summary.frames} frames,"
        f" {summary.seconds / 60:.1f} min of video. QA <code>{_e(summary.threshold_version)}"
        "</code>.</p>",
    ]
    if s["deid_waiver"]:
        parts.append(f"<p class='note'>De-identification waived: {_e(s['deid_waiver'])}</p>")
    if s.get("deid_copies"):
        parts.append(f"<p class='note'>De-identified: {s['deid_copies']} videos copied with"
                     f" their faces covered by {_e(str(s['deid_model']))} on this machine;"
                     " every later step read the copies.</p>")
    parts.append(_table("Decisions", ["decision", "episodes"],
                        [[d, n] for d, n in summary.decisions.items()]))
    parts.append(_table(
        "Egocentric checks", ["check", "threshold", "median value", *DECISIONS],
        [[name, f"{c['threshold']:g}", f"{c['median']:.3g}", *(c[d] for d in DECISIONS)]
         for name, c in summary.checks.items()],
    ))
    parts.append(_table(
        f"Segments ({summary.segments})", ["step", "segments"],
        [[k, v] for k, v in summary.steps.items()],
    ))
    parts.append(_table("Label source", ["label_source", "segments"],
                        [[k, v] for k, v in summary.label_sources.items()]))
    d = summary.deviation
    if d:
        rows = []
        for side in ("left", "right"):
            h = d.get(side)
            if h:
                rows.append([side, h["frames"], f"{h['detection']:.2f}",
                             f"{h['pixel_median']:.1f}", f"{h['wrist_pixel_median']:.1f}",
                             f"{h['point_median_m'] * 100:.1f}",
                             f"{h['depth_median_m'] * 100:.1f}"])
        parts.append(_table(
            f"E-A against E-B, median over {d['episodes']} episodes",
            ["hand", "frames", "detection", "px (6 joints)", "px wrist", "3D cm", "depth cm"],
            rows,
        ))
        parts.append(
            "<p>Camera, per frame: rotation error"
            f" {_num(d.get('rotation_median_deg'))}° (p90 {_num(d.get('rotation_p90_deg'))}°)"
            f" against E-B's own {_num(d.get('eb_rotation_median_deg'))}° per frame;"
            " translation direction"
            f" {_num(d.get('translation_direction_median_deg'))}°. E-A is <code>pseudo</code>.</p>"
        )
    return "".join(parts)


def write_page(page: Path, summary: EgoSummary) -> None:
    """Put the egocentric section into the page `render_html` wrote."""
    text = page.read_text(encoding="utf-8")
    marker = "</body>"
    if marker not in text:
        raise ValueError(f"{page}: not a page render_html wrote")
    page.write_text(text.replace(marker, section_html(summary) + marker, 1), encoding="utf-8")


def check_report(report: DatasetReport, summary: EgoSummary) -> None:
    if report.episode_count != summary.episodes:
        raise ValueError("DatasetReport and egocentric summary count different episodes")


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _e(value: object) -> str:
    return html.escape(str(value))


def _table(title: str, head: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    header = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<h3>{_e(title)}</h3><table><tr>{header}</tr>{body}</table>"
