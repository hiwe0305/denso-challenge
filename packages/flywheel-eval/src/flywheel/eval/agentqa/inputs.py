"""Read the artifacts a run is given, and nothing else (DA-20 AC 2).

The agent reads files the lanes wrote, by path; it never runs a job. Each file is
recognised by name and must parse as its contract, or the run stops:

    dataset_report.json    DatasetReport           (fw data report, DA-03)
    qa/reports.jsonl       QAReport per line       (fw data qa)
    episodes.jsonl         Episode per line        (fw data ingest)
    episode_index.json     episode_id -> index     (fw data ingest)
    replay*.jsonl          ReplayReport per line   (DA-17)
    metrics.jsonl          TrainingMetric per line (DA-19)
    probe*.json            ProbeP1..P4             (DA-09; fixtures until then)
    rtc.jsonl              RTCInferenceRecord      (DA-19 RTCClient)
    scores.jsonl           Score per line          (DA-36)
    clusters.jsonl         Cluster per line        (DA-13)
    meta/benchmark_copy.json  which copy this is   (DA-27)

Anything else under a given directory is skipped and listed, never parsed. A path
with a `vault` part (holdout, spec 7.3) or an `answers` part (where DA-27 seals
the key of a benchmark copy) is refused before it is opened.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from flywheel.contracts.agentqa import AgentInput
from flywheel.contracts.artifacts import (
    DatasetReport,
    Episode,
    ProbeP1,
    ProbeP2,
    ProbeP3,
    ProbeP4,
    QAReport,
    ReplayReport,
    RTCInferenceRecord,
)
from flywheel.contracts.entities import Cluster, Score
from flywheel.contracts.training import TrainingMetric
from pydantic import BaseModel, ValidationError

FORBIDDEN_PARTS = ("vault", "answers")


class InputRefused(ValueError):
    """A path the agent may not read, or a file that is not what its name says."""


@dataclass(frozen=True)
class Loaded:
    path: Path
    ref: str  # posix path as recorded in the report
    kind: str
    sha256: str
    records: tuple[Any, ...]  # parsed contract objects (one for a .json file)

    def to_input(self) -> AgentInput:
        return AgentInput(ref=self.ref, kind=self.kind, sha256=self.sha256)


@dataclass
class InputSet:
    loaded: list[Loaded] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def of(self, kind: str) -> list[Loaded]:
        return [item for item in self.loaded if item.kind == kind]

    def one(self, kind: str) -> Loaded | None:
        found = self.of(kind)
        return found[0] if found else None


def _lines(model: type[BaseModel]) -> Callable[[str], tuple[Any, ...]]:
    def parse(text: str) -> tuple[Any, ...]:
        return tuple(model.model_validate_json(line) for line in text.splitlines() if line.strip())

    return parse


def _one(model: type[BaseModel]) -> Callable[[str], tuple[Any, ...]]:
    def parse(text: str) -> tuple[Any, ...]:
        return (model.model_validate_json(text),)

    return parse


def _probe(text: str) -> tuple[Any, ...]:
    raw = json.loads(text)
    models: dict[str, type[BaseModel]] = {
        "P1": ProbeP1, "P2": ProbeP2, "P3": ProbeP3, "P4": ProbeP4
    }
    probe = raw.get("probe") if isinstance(raw, dict) else None
    if probe not in models:
        raise ValueError(f"unknown probe {probe!r}")
    return (models[probe].model_validate(raw),)


def _json(text: str) -> tuple[Any, ...]:
    return (json.loads(text),)


def _index(text: str) -> tuple[Any, ...]:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("episode_index.json is not an object")
    return ({str(k): int(v) for k, v in raw.items()},)


def kind_of(path: Path) -> tuple[str, Callable[[str], tuple[Any, ...]]] | None:
    name = path.name
    parts = path.parts
    if name == "dataset_report.json":
        return "dataset_report", _one(DatasetReport)
    if name == "reports.jsonl" and len(parts) > 1 and parts[-2] == "qa":
        return "qa_reports", _lines(QAReport)
    if name == "episodes.jsonl":
        return "episodes", _lines(Episode)
    if name == "episode_index.json":
        return "episode_index", _index
    if name.startswith("replay") and name.endswith(".jsonl"):
        return "replay_reports", _lines(ReplayReport)
    if name == "metrics.jsonl":
        return "metrics", _lines(TrainingMetric)
    if name.startswith("probe") and name.endswith(".json"):
        return "probe", _probe
    if name == "rtc.jsonl":
        return "rtc_log", _lines(RTCInferenceRecord)
    if name == "scores.jsonl":
        return "scores", _lines(Score)
    if name == "clusters.jsonl":
        return "clusters", _lines(Cluster)
    if name == "benchmark_copy.json" and len(parts) > 1 and parts[-2] == "meta":
        return "benchmark_copy", _json
    return None


def forbidden_part(path: Path) -> str | None:
    """The forbidden directory `path` is in, as written or once links are resolved."""
    for candidate in (path, path.resolve()):
        lowered = [p.lower() for p in PurePosixPath(candidate.as_posix()).parts]
        for part in FORBIDDEN_PARTS:
            if part in lowered:
                return part
    return None


def refuse_forbidden(path: Path) -> None:
    # Resolved too: a link (file or directory) into vault/ is vault/.
    part = forbidden_part(path)
    if part is not None:
        raise InputRefused(f"{path}: the agent does not read {part}/")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_file(path: Path, ref: str | None = None) -> Loaded:
    refuse_forbidden(path)
    known = kind_of(path)
    if known is None:
        raise InputRefused(f"{path}: not an input kind the agent reads")
    kind, parse = known
    data = path.read_bytes()
    try:
        records = parse(data.decode("utf-8"))
    except (ValidationError, ValueError, UnicodeDecodeError) as exc:
        raise InputRefused(f"{path}: does not parse as {kind}: {str(exc)[:300]}") from exc
    return Loaded(path, ref or path.as_posix(), kind, _sha256(data), records)


def collect(paths: Iterable[Path], base: Path | None = None) -> InputSet:
    """Load every known file under `paths` (files or directories), in path order.

    `base`, if given, makes the recorded refs relative to it.
    """
    found = InputSet()
    for root in paths:
        refuse_forbidden(root)
        files: Sequence[Path] = [root] if root.is_file() else sorted(p for p in root.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            rel = path.relative_to(root) if root.is_dir() else Path(path.name)
            if any(part.lower() in FORBIDDEN_PARTS for part in rel.parts) or forbidden_part(path):
                found.skipped.append(f"{path.as_posix()} (forbidden part)")
                continue
            if kind_of(path) is None:
                found.skipped.append(path.as_posix())
                continue
            ref = path.relative_to(base).as_posix() if base and path.is_relative_to(base) else None
            found.loaded.append(load_file(path, ref))
    return found
