"""What each layer reported on one benchmark copy, as (target, code) pairs (DA-31 AC 1).

Two layers look at every copy of the injected-defect benchmark of DA-27 (design
27/10/2026 section 9.2):

    code   the checks written as code: QA tier 4 of the data lane on a dataset copy
           (`fw data qa` writes `qa/reports.jsonl` under its work dir), the F-TRAIN
           and F-SYS detectors of this lane (DA-08, DA-13) on a log copy
    agent  Agent QA/QC (DA-20): one `AgentReport` or more per copy

Both are read as artifacts; nothing here imports the data lane. A result names
what it found by the design 10 code and by a target. The target is brought to the
id the `DefectManifest` uses for the same thing, so the scorer can compare them:

    dataset copy  `episode_000012`, the parquet stem (DA-27 `episode_ref`); an
                  `ep_<hex>` episode id of ingest maps to it through the work dir's
                  `episode_index.json`, a parquet path through its stem
    log copy      `train/<job>` or `rtc/<job>`, the job dir under the copy root

A target that names nothing in the copy keeps its own spelling; it can then match
no defect, and the scorer counts it as a false alarm, never drops it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal

from flywheel.contracts.agentqa import FINDING_CODE, AgentReport
from flywheel.contracts.artifacts import Episode, QAReport

Layer = Literal["code", "agent"]
LAYERS: tuple[Layer, ...] = ("code", "agent")

COPY_MARKER = Path("meta") / "benchmark_copy.json"
QA_REPORTS = Path("qa") / "reports.jsonl"
EPISODE_INDEX = "episode_index.json"
EPISODES = "episodes.jsonl"
LOG_PARTS = ("train", "rtc")

# A QA reason starts "<check> (<code>): ..." (flywheel.data.qa.checks._judge and
# _missing_replay); `min_frames` is the one reason without a code.
_REASON_CODE = re.compile(r"^\S+ \(([A-Z][0-9]+)\):")
_CODE = re.compile(FINDING_CODE)


class BenchInputError(ValueError):
    """A result that cannot be read as the result of the copy it is said to be for."""


@dataclass(frozen=True)
class Detection:
    """One thing a layer said is wrong: the target it named and the design 10 code.

    `report_id`, `finding_id` and `rank` are set for an agent finding, so the
    scorer can judge the ranking and look up the engineer's `AgentReview`.
    """

    target: str
    code: str
    report_id: str | None = None
    finding_id: str | None = None
    rank: int | None = None


@dataclass(frozen=True)
class LayerRun:
    """Everything one layer reported on one copy.

    `units` are the episodes or jobs the copy holds, the denominator of the false
    alarm rate. `aliases` maps other spellings of a unit (an ingest episode id) to
    it. `inputs` are the refs the layer says it read; the session checks them
    against the answer key. `uncoded` lists failures that carried no code.
    """

    layer: Layer
    dataset_id: str
    units: tuple[str, ...]
    detections: tuple[Detection, ...]
    reported_at: datetime | None
    aliases: Mapping[str, str] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()
    uncoded: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.layer not in LAYERS:
            raise BenchInputError(f"unknown layer {self.layer!r}")
        if not self.units:
            raise BenchInputError(f"{self.layer} run of {self.dataset_id} names no unit")
        if self.reported_at is not None and self.reported_at.tzinfo is None:
            raise BenchInputError("reported_at must carry a time zone")


def resolve_target(ref: str, units: Iterable[str], aliases: Mapping[str, str]) -> str:
    """The unit `ref` names, or `ref` itself (slashes made forward) when it names none.

    Tries the whole ref, then walks its path from the end: at each part, the part
    with the one before it (`train/<job>`), the part, and its stem
    (`episode_000012.parquet`), each against the units and then the aliases. So a
    file inside a job dir (`.../train/<job>/metrics.jsonl`) names the job.
    """
    known = set(units)
    text = ref.replace("\\", "/").strip().strip("/")
    parts = PurePosixPath(text).parts
    candidates = [text]
    for i in range(len(parts) - 1, -1, -1):
        if i >= 1:
            candidates.append(f"{parts[i - 1]}/{parts[i]}")
        candidates += [parts[i], PurePosixPath(parts[i]).stem]
    for candidate in candidates:
        if candidate in known:
            return candidate
        if candidate in aliases:
            return aliases[candidate]
    return text


def read_copy_id(root: Path) -> str:
    """The `benchmark_copy_id` a copy carries in `meta/benchmark_copy.json` (DA-27)."""
    marker = root / COPY_MARKER
    if not marker.is_file():
        raise BenchInputError(f"{root}: no {COPY_MARKER.as_posix()}; not a benchmark copy")
    value = json.loads(marker.read_text(encoding="utf-8")).get("benchmark_copy_id")
    if not isinstance(value, str) or not value:
        raise BenchInputError(f"{marker}: no benchmark_copy_id")
    return value


def read_qa_work(work: Path, dataset_id: str) -> LayerRun:
    """The code layer on a dataset copy, from the work dir of `fw data qa`.

    Every episode of the work dir must carry `benchmark_copy_id` == `dataset_id`
    (ingest marks a copy's episodes, DA-27), so a work dir of the wrong copy, or
    of a dataset that is no copy at all, is refused rather than scored.
    `reported_at` is when `qa/reports.jsonl` was written.
    """
    index_path, episodes_path, reports_path = (
        work / EPISODE_INDEX,
        work / EPISODES,
        work / QA_REPORTS,
    )
    for path in (index_path, episodes_path, reports_path):
        if not path.is_file():
            raise BenchInputError(f"{work}: no {path.relative_to(work).as_posix()}")
    index = {k: int(v) for k, v in json.loads(index_path.read_text(encoding="utf-8")).items()}
    episodes = [Episode.model_validate_json(line) for line in _lines(episodes_path)]
    wrong = [e.episode_id for e in episodes if e.meta.benchmark_copy_id != dataset_id]
    if wrong:
        raise BenchInputError(
            f"{work}: {len(wrong)} episode(s) are not of copy {dataset_id}, e.g. {wrong[0]}"
        )
    aliases = {episode_id: _episode_ref(i) for episode_id, i in index.items()}
    units = tuple(sorted(aliases[e.episode_id] for e in episodes))
    reports = [QAReport.model_validate_json(line) for line in _lines(reports_path)]
    detections: list[Detection] = []
    uncoded: list[str] = []
    for report in reports:
        if report.episode_id not in aliases:
            raise BenchInputError(f"{reports_path}: report of unknown episode {report.episode_id}")
        target = aliases[report.episode_id]
        for reason in report.reasons:
            match = _REASON_CODE.match(reason)
            if match and _CODE.fullmatch(match.group(1)):
                detections.append(Detection(target, match.group(1)))
            else:
                uncoded.append(f"{target}: {reason}")
    stamp = datetime.fromtimestamp(reports_path.stat().st_mtime, tz=timezone.utc)
    return LayerRun(
        layer="code",
        dataset_id=dataset_id,
        units=units,
        detections=_unique(detections),
        reported_at=stamp,
        aliases=aliases,
        inputs=(work.as_posix(),),
        uncoded=tuple(uncoded),
    )


def log_units(root: Path) -> tuple[str, ...]:
    """The jobs of a log copy: `train/<job>` and `rtc/<job>` dirs under its root."""
    units = [
        f"{part}/{job.name}"
        for part in LOG_PARTS
        if (root / part).is_dir()
        for job in sorted((root / part).iterdir())
        if job.is_dir()
    ]
    if not units:
        raise BenchInputError(f"{root}: no train/ or rtc/ job")
    return tuple(units)


def agent_run(
    reports: Sequence[AgentReport],
    dataset_id: str,
    units: Sequence[str],
    aliases: Mapping[str, str] | None = None,
) -> LayerRun:
    """The agent layer on one copy, from its `AgentReport`s.

    `units` and `aliases` come from the code layer's run of the same copy, so both
    layers are scored over the same episodes or jobs. `reported_at` is the latest
    `created_at`; `inputs` gathers every ref the reports say they read or cite.
    """
    if not reports:
        raise BenchInputError(f"agent run of {dataset_id} has no AgentReport")
    names = aliases or {}
    detections = [
        Detection(
            target=resolve_target(finding.target_ref, units, names),
            code=finding.code,
            report_id=report.report_id,
            finding_id=finding.finding_id,
            rank=finding.rank,
        )
        for report in reports
        for finding in report.findings
    ]
    inputs = [
        ref
        for report in reports
        for ref in (
            report.subject_ref,
            *(i.ref for i in report.inputs),
            *(f.source_ref for f in report.facts),
            *(f.target_ref for f in report.findings),
            *(path for f in report.findings for path in f.figures),
        )
    ]
    return LayerRun(
        layer="agent",
        dataset_id=dataset_id,
        units=tuple(units),
        detections=tuple(detections),
        reported_at=max(report.created_at for report in reports),
        aliases=dict(names),
        inputs=tuple(inputs),
    )


def _episode_ref(index: int) -> str:
    return f"episode_{index:06d}"


def _lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _unique(detections: Iterable[Detection]) -> tuple[Detection, ...]:
    return tuple(dict.fromkeys(detections))
