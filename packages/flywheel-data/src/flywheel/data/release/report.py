"""The dataset report: the `DatasetReport` artifact and a static HTML page (DA-03 AC 5).

Design 6.5 asks the page for episodes by source, pass, flag and reject by check, the
conditions against the train range, episode lengths and stats by action group: part 3
of the 17/11 demo ("pipeline performance"). The `DatasetReport` contract carries the
first two (counts by source, failed checks by source). The rest is lane-internal
(`DatasetSummary`, built from the frames while QA runs) and goes only into the page;
no field was added to the contract for it.

Sources are keyed by `source_detail` (psi_data, planner_wbc, teleop_pico), else
`source_kind`. A check is counted once per episode it failed in; the action-jump
groups count under their own names (`action_jump.arm`).
"""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import DatasetReport, Episode, QAReport
from flywheel.data.config import COMMON_CHECKS, QAConfig
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.qa.checks import DatasetFinding
from numpy.typing import NDArray

DECISIONS = ("pass", "flag", "quarantine", "reject")


def source_of(episode: Episode) -> str:
    return episode.meta.source_detail or episode.source_kind


def dataset_report(
    dataset_id: str, episodes: Sequence[Episode], reports: Sequence[QAReport]
) -> DatasetReport:
    """Counts by source and failed checks by source, from one QAReport per episode."""
    source = {e.episode_id: source_of(e) for e in episodes}
    failed: dict[str, Counter[str]] = defaultdict(Counter)
    for report in reports:
        if report.episode_id not in source:
            raise ValueError(f"QAReport {report.report_id} is for {report.episode_id}, not given")
        failed[source[report.episode_id]].update(c.name for c in report.checks if not c.passed)
    return DatasetReport(
        dataset_id=dataset_id,
        episode_count=len(episodes),
        counts_by_source=dict(Counter(source.values())),
        failed_checks_by_source={s: dict(sorted(c.items())) for s, c in sorted(failed.items())},
    )


@dataclass
class SourceSummary:
    """What the page shows of one source beyond the DatasetReport."""

    episodes: int = 0
    decisions: dict[str, int] = field(default_factory=dict)
    frames: list[int] = field(default_factory=list)  # rows per episode
    seeds: dict[str, int] = field(default_factory=dict)  # in_train, outside, unknown
    action: dict[str, dict[str, float]] = field(default_factory=dict)  # group -> stats
    not_run: list[str] = field(default_factory=list)  # configured checks no episode ran


@dataclass
class DatasetSummary:
    dataset_id: str
    fps: float
    threshold_version: str
    train_seeds: tuple[int, int]
    codes: dict[str, str]  # check -> D-code, from qa.yaml
    sources: dict[str, SourceSummary]
    dataset_checks: list[dict[str, Any]]  # D4 findings
    notes: list[str] = field(default_factory=list)  # e.g. ingest index findings

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> DatasetSummary:
        data = json.loads(text)
        data["sources"] = {k: SourceSummary(**v) for k, v in data["sources"].items()}
        data["train_seeds"] = tuple(data["train_seeds"])
        return cls(**data)


def summarize(
    dataset_id: str,
    episodes: Sequence[Episode],
    reports: Sequence[QAReport],
    frames: Mapping[str, EpisodeFrames],
    cfg: QAConfig,
    *,
    fps: float,
    seeds: Mapping[str, int | None],
    findings: Sequence[DatasetFinding] = (),
    notes: Sequence[str] = (),
) -> DatasetSummary:
    """The page's data: `frames` and `seeds` are keyed by episode_id."""
    by_id = {r.episode_id: r for r in reports}
    start, stop = cfg.train_seeds
    sources: dict[str, SourceSummary] = {}
    values: dict[str, list[NDArray[Any]]] = defaultdict(list)
    ran: dict[str, set[str]] = defaultdict(set)
    for episode in episodes:
        name = source_of(episode)
        summary = sources.setdefault(name, SourceSummary())
        summary.episodes += 1
        report = by_id[episode.episode_id]
        summary.decisions[report.decision] = summary.decisions.get(report.decision, 0) + 1
        ran[name].update(c.name.split(".")[0] for c in report.checks)
        seed = seeds.get(episode.episode_id)
        where = "unknown" if seed is None else "in_train" if start <= seed < stop else "outside"
        summary.seeds[where] = summary.seeds.get(where, 0) + 1
        if episode.episode_id in frames:
            episode_frames = frames[episode.episode_id]
            summary.frames.append(len(episode_frames.timestamp))
            values[name].append(episode_frames.action)
    for name, summary in sources.items():
        expected = [*COMMON_CHECKS, *cfg.source_checks.get(name, ())]
        summary.not_run = [c for c in expected if c not in ran[name]]
        if values[name]:
            summary.action = _group_stats(np.concatenate(values[name]), cfg.groups)
    return DatasetSummary(
        dataset_id=dataset_id,
        fps=fps,
        threshold_version=cfg.threshold_version,
        train_seeds=cfg.train_seeds,
        codes={name: rule.code for name, rule in cfg.checks.items()},
        sources=dict(sorted(sources.items())),
        dataset_checks=[
            {"name": f.check.name, "code": f.code, "value": f.check.value,
             "threshold": f.check.threshold, "passed": f.check.passed, "detail": f.detail}
            for f in findings
        ],
        notes=list(notes),
    )


def render_html(
    report: DatasetReport, out: Path, *, summary: DatasetSummary | None = None
) -> Path:
    """Write the static page to `out` (a file path) and return it."""
    parts = [f"<h1>Dataset report · {_e(report.dataset_id)}</h1>"]
    if summary is not None:
        parts.append(
            f"<p>QA thresholds <code>{_e(summary.threshold_version)}</code> ·"
            f" train seeds [{summary.train_seeds[0]}, {summary.train_seeds[1]})"
            f" · {summary.fps:g} fps</p>"
        )
    parts.append(_sources_table(report, summary))
    parts.append(_checks_table(report, summary))
    if summary is not None:
        parts += [_lengths_table(summary), _seeds_table(summary), _actions_table(summary)]
        parts.append(_dataset_checks_table(summary))
        parts += [f"<p class='note'>{_e(n)}</p>" for n in summary.notes]
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>Dataset report {_e(report.dataset_id)}</title><style>{CSS}</style>"
        f"</head><body>{''.join(parts)}</body></html>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


CSS = (
    "body{font:14px/1.45 system-ui,sans-serif;margin:24px;max-width:1100px;color:#1d2433}"
    "table{border-collapse:collapse;margin:8px 0 20px}th,td{border:1px solid #c8cdd6;"
    "padding:3px 8px;text-align:right}th:first-child,td:first-child{text-align:left}"
    "th{background:#eef1f5}.bad{background:#fde2e1}.ok{background:#e3f4e6}"
    ".note{color:#55606f}code{font-size:13px}"
)


def _e(value: object) -> str:
    return html.escape(str(value))


def _table(title: str, head: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    cells = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join(
        "<tr>" + "".join(c if isinstance(c, _Cell) else f"<td>{_e(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<h2>{_e(title)}</h2><table><tr>{cells}</tr>{body}</table>"


class _Cell(str):
    """A cell already rendered as HTML."""


def _mark(value: object, bad: bool) -> _Cell:
    return _Cell(f"<td class='{'bad' if bad else 'ok'}'>{_e(value)}</td>")


def _sources_table(report: DatasetReport, summary: DatasetSummary | None) -> str:
    rows: list[list[object]] = []
    for source, count in sorted(report.counts_by_source.items()):
        decisions = summary.sources[source].decisions if summary else {}
        rows.append([source, count, *[decisions.get(d, "") for d in DECISIONS]])
    rows.append(["total", report.episode_count, *[
        sum(s.decisions.get(d, 0) for s in summary.sources.values()) if summary else ""
        for d in DECISIONS]])
    return _table("Episodes by source", ["source", "episodes", *DECISIONS], rows)


def _checks_table(report: DatasetReport, summary: DatasetSummary | None) -> str:
    sources = sorted(report.counts_by_source)
    names = sorted({n for counts in report.failed_checks_by_source.values() for n in counts})
    rows: list[list[object]] = []
    for name in names:
        code = summary.codes.get(name.split(".")[0], "") if summary else ""
        counts = [report.failed_checks_by_source.get(s, {}).get(name, 0) for s in sources]
        rows.append([name, code, *[_mark(c, c > 0) for c in counts]])
    if not rows:
        rows.append(["no check failed", "", *["" for _ in sources]])
    table = _table("Failed checks (episodes) by source", ["check", "code", *sources], rows)
    if summary is not None:
        not_run = [f"{s}: {', '.join(v.not_run)}" for s, v in summary.sources.items() if v.not_run]
        if not_run:
            table += "<p class='note'>Not run (no input, e.g. no ReplayReport yet): "
            table += "; ".join(_e(n) for n in not_run) + "</p>"
    return table


def _lengths_table(summary: DatasetSummary) -> str:
    rows: list[list[object]] = []
    for source, s in summary.sources.items():
        if not s.frames:
            continue
        frames = np.asarray(s.frames)
        rows.append([source, len(frames), int(frames.min()), int(np.median(frames)),
                     int(frames.max()), f"{frames.min() / summary.fps:.1f}",
                     f"{frames.max() / summary.fps:.1f}", int(frames.sum())])
    head = ["source", "episodes", "min", "median", "max", "min s", "max s", "frames"]
    return _table("Episode length (frames)", head, rows)


def _seeds_table(summary: DatasetSummary) -> str:
    rows = [[s, v.seeds.get("in_train", 0), _mark(v.seeds.get("outside", 0),
             v.seeds.get("outside", 0) > 0), v.seeds.get("unknown", 0)]
            for s, v in summary.sources.items()]
    return _table("Condition seeds against the train range", ["source", "in train", "outside",
                                                              "not recorded"], rows)


def _actions_table(summary: DatasetSummary) -> str:
    rows: list[list[object]] = []
    for source, s in summary.sources.items():
        for group, stats in s.action.items():
            rows.append([f"{source} · {group}", *[f"{stats[k]:.4g}" for k in
                                                  ("mean", "std", "min", "max")]])
    return _table("Action stats by group", ["source · group", "mean", "std", "min", "max"], rows)


def _dataset_checks_table(summary: DatasetSummary) -> str:
    rows = [[c["name"], c["code"], _mark(f"{c['value']:.3g}", not c["passed"]),
             f"{c['threshold']:g}", c["detail"]] for c in summary.dataset_checks]
    if not rows:
        rows.append(["no stats file shipped", "", "", "", ""])
    return _table("Dataset checks (D4: shipped stats against the frames)",
                  ["check", "code", "value", "threshold", "where"], rows)


def _group_stats(action: NDArray[Any], groups: Sequence[str]) -> dict[str, dict[str, float]]:
    stats = {}
    for group in dict.fromkeys(groups):
        values = action[:, [d for d, g in enumerate(groups) if g == group]].astype(np.float64)
        stats[group] = {"mean": float(values.mean()), "std": float(values.std()),
                        "min": float(values.min()), "max": float(values.max())}
    return stats
