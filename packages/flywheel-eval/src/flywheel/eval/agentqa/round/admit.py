"""Step B1, admit: the one place that decides which data goes on, and to which models.

For a pack (step B0) it checks every file is still the file that was packed, loads
each with the contract of its declared kind, and works out the data class of the whole
pack (architecture 20/11 section 6, B1; design 19/11 section 8, hard blocks 2 and 3):

- a changed or missing file refuses the pack: it is no longer that pack;
- a forbidden path, an unknown kind or a file that does not parse is rejected alone,
  with the reason, and the rest goes on;
- the pack's class is the highest of every entry's declared class and of every record
  that carries one (`Episode`, `Source`), rejected entries included;
- a declared `public` is not enough for a hosted model: every accepted entry must hold
  records that say `public` themselves, or be linked to an entry that does. Otherwise
  the class is unknown for it and only local models may be called.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flywheel.contracts.artifacts import (
    DatasetReport,
    Episode,
    QAReport,
    ReplayReport,
    RTCInferenceRecord,
)
from flywheel.contracts.entities import Cluster, Condition, Score, Source
from flywheel.contracts.trace import TraceStep
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.round.pack import PACK_FILE, PackRefused, refused_path, sha256_of
from flywheel.eval.agentqa.round.records import (
    CLASS_ORDER,
    Admission,
    DataClass,
    Pack,
    Rejected,
    highest,
)
from pydantic import BaseModel, ValidationError

ADMISSION_FILE = "admission.json"
Parse = Callable[[str], tuple[Any, ...]]


def _lines(model: type[BaseModel]) -> Parse:
    def parse(text: str) -> tuple[Any, ...]:
        return tuple(model.model_validate_json(line) for line in text.splitlines()
                     if line.strip())
    return parse


def _one(model: type[BaseModel]) -> Parse:
    def parse(text: str) -> tuple[Any, ...]:
        return (model.model_validate_json(text),)
    return parse


# kind -> how a file of that kind is read. A kind that is not here is rejected: the
# agent only reads artifacts that have a contract (03 section 7.3).
KINDS: dict[str, Parse] = {
    "scores": _lines(Score),
    "clusters": _lines(Cluster),
    "conditions": _lines(Condition),
    "trace": _lines(TraceStep),
    "metrics": _lines(TrainingMetric),
    "rtc_log": _lines(RTCInferenceRecord),
    "episodes": _lines(Episode),
    "sources": _lines(Source),
    "qa_reports": _lines(QAReport),
    "replay_reports": _lines(ReplayReport),
    "dataset_report": _one(DatasetReport),
}


@dataclass(frozen=True)
class Admitted:
    admission: Admission
    records: dict[str, tuple[Any, ...]]  # ref -> the parsed records of an accepted entry


def _first_line(error: Exception) -> str:
    return str(error).strip().splitlines()[0][:200]


def _vouched(confirming: set[str], accepted: Sequence[str], pack: Pack) -> set[str]:
    """Accepted entries a confirming entry reaches over the declared links, either way."""
    alive = set(accepted)
    near: dict[str, set[str]] = {ref: set() for ref in alive}
    for link in pack.links:
        if link.source in alive and link.target in alive:
            near[link.source].add(link.target)
            near[link.target].add(link.source)
    seen, todo = set(confirming), list(confirming)
    while todo:
        for other in near[todo.pop()]:
            if other not in seen:
                seen.add(other)
                todo.append(other)
    return seen


def admit(pack_path: Path, expected_kinds: Sequence[str] = ()) -> Admitted:
    """Check and load the pack whose manifest is `pack_path`; its directory is the root."""
    root = pack_path.parent
    try:
        pack = Pack.model_validate_json(pack_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise PackRefused(f"{pack_path}: {_first_line(error)}") from error
    records: dict[str, tuple[Any, ...]] = {}
    rejected: list[Rejected] = []
    classes: list[DataClass] = []
    confirming: set[str] = set()
    for entry in pack.entries:
        classes.append(entry.data_class)
        reason = refused_path(root, entry.ref)
        if reason is not None:
            rejected.append(Rejected(ref=entry.ref, reason=reason))
            continue
        path = root / entry.ref
        if not path.is_file():
            raise PackRefused(f"{entry.ref}: the file of the pack is gone")
        if sha256_of(path) != entry.sha256:
            raise PackRefused(f"{entry.ref}: the file changed after it was packed")
        parse = KINDS.get(entry.kind)
        if parse is None:
            rejected.append(Rejected(ref=entry.ref, reason=f"kind {entry.kind} has no contract "
                                     f"here (known: {', '.join(sorted(KINDS))})"))
            continue
        try:
            parsed = parse(path.read_text(encoding="utf-8"))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as error:
            rejected.append(Rejected(ref=entry.ref, reason="does not parse as "
                                     f"{entry.kind}: {_first_line(error)}"))
            continue
        records[entry.ref] = parsed
        own = [r.data_class for r in parsed if hasattr(r, "data_class")]
        classes.extend(own)
        if own and entry.data_class == "public" and all(c == "public" for c in own):
            confirming.add(entry.ref)
    if not records:
        raise PackRefused(f"{pack.pack_id}: no entry was accepted "
                          f"({'; '.join(f'{r.ref}: {r.reason}' for r in rejected)})")
    accepted = [e.ref for e in pack.entries if e.ref in records]
    data_class = highest(classes)
    unconfirmed = sorted(set(accepted) - _vouched(confirming, accepted, pack))
    kinds = {e.kind for e in pack.entries if e.ref in records}
    admission = Admission(
        pack_id=pack.pack_id, pack_sha256=sha256_of(pack_path), accepted=accepted,
        rejected=rejected, missing_kinds=[k for k in expected_kinds if k not in kinds],
        data_class=data_class, data_class_basis=sorted(confirming), unconfirmed=unconfirmed,
        hosted_allowed=CLASS_ORDER[data_class] == 0 and not unconfirmed,
    )
    return Admitted(admission, records)


def write_admission(admission: Admission, out: Path) -> Path:
    path = out / ADMISSION_FILE
    path.write_text(admission.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["ADMISSION_FILE", "KINDS", "PACK_FILE", "Admitted", "admit", "write_admission"]
