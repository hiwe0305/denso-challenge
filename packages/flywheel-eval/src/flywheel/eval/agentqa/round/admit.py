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

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from flywheel.contracts.artifacts import (
    DatasetReport,
    Episode,
    QAReport,
    ReplayReport,
    RTCInferenceRecord,
)
from flywheel.contracts.entities import (
    Cluster,
    Condition,
    FixRateEvent,
    LedgerEntry,
    Score,
    Source,
)
from flywheel.contracts.trace import TraceStep
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.round.pack import PACK_FILE, PackRefused, refused_path, sha256_of
from flywheel.eval.agentqa.round.records import (
    CLASS_ORDER,
    Admission,
    DataClass,
    Pack,
    PackEntry,
    Rejected,
    highest,
)
from pydantic import BaseModel, ValidationError

ADMISSION_FILE = "admission.json"


@dataclass(frozen=True)
class Kind:
    """The contract of a file kind: JSON lines of `model`, or one JSON document (`one`)."""

    model: type[BaseModel]
    one: bool = False


# kind -> how a file of that kind is read. A kind that is not here is rejected: the
# agent only reads artifacts that have a contract (03 section 7.3).
KINDS: dict[str, Kind] = {
    "scores": Kind(Score),
    "clusters": Kind(Cluster),
    "conditions": Kind(Condition),
    "trace": Kind(TraceStep),
    "metrics": Kind(TrainingMetric),
    "rtc_log": Kind(RTCInferenceRecord),
    "episodes": Kind(Episode),
    "sources": Kind(Source),
    "qa_reports": Kind(QAReport),
    "replay_reports": Kind(ReplayReport),
    "dataset_report": Kind(DatasetReport, one=True),
    "ledger": Kind(LedgerEntry),  # a store snapshot (task 4.7); rows carry no data class
    "fix_rate": Kind(FixRateEvent),
}
# Kinds whose files can be large (real data: 1.5 GB of trace, 280 MB of metrics). Their
# records are never kept: every read parses the file again, one record at a time.
UNCACHED = frozenset({"trace", "metrics", "rtc_log"})


class Undecodable(ValueError):
    """A line is not UTF-8; the message is the one decoding the whole file would give."""


# What a file that does not hold its kind raises. Never `PackRefused`, which is a refusal.
PARSE_ERRORS = (ValidationError, json.JSONDecodeError, UnicodeDecodeError, Undecodable)


def _undecodable(error: UnicodeDecodeError, offset: int) -> Undecodable:
    start, end = error.start + offset, error.end + offset
    if error.end - error.start == 1:
        where = f"byte 0x{error.object[error.start]:02x} in position {start}"
    else:
        where = f"bytes in position {start}-{end - 1}"
    return Undecodable(f"'{error.encoding}' codec can't decode {where}: {error.reason}")


class Reader:
    """The records of one file, parsed one at a time while the file is hashed.

    Iterate it once. When the file is not what the pack recorded (`expected`), the end of
    the iteration raises `PackRefused`, also when a line does not parse: a file that changed
    is refused, never read. Without `expected`, the caller compares `sha256` itself.
    """

    def __init__(self, path: Path, ref: str, kind: Kind, expected: str | None = None) -> None:
        self.path, self.ref, self.kind, self.expected = path, ref, kind, expected
        self.sha256 = ""

    def _changed(self) -> PackRefused:
        return PackRefused(f"{self.ref}: the file changed after it was packed")

    def __iter__(self) -> Iterator[Any]:
        digest = hashlib.sha256()
        try:
            f = self.path.open("rb")
        except FileNotFoundError as error:
            raise PackRefused(f"{self.ref}: the file of the pack is gone") from error
        with f:
            try:
                yield from self._records(f, digest)
            except PARSE_ERRORS:
                for block in iter(lambda: f.read(1 << 20), b""):
                    digest.update(block)
                self.sha256 = digest.hexdigest()
                if self.expected is not None and self.sha256 != self.expected:
                    raise self._changed() from None
                raise
        self.sha256 = digest.hexdigest()
        if self.expected is not None and self.sha256 != self.expected:
            raise self._changed()

    def _records(self, f: BinaryIO, digest: Any) -> Iterator[Any]:
        model = self.kind.model
        if self.kind.one:
            raw = f.read()
            digest.update(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise _undecodable(error, 0) from None
            yield model.model_validate_json(text)
            return
        offset = 0
        for raw in f:  # split on b"\n" only; UTF-8 never holds that byte inside a character
            digest.update(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise _undecodable(error, offset) from None
            offset += len(raw)
            # As `str.splitlines` of the whole text: the lines end where they did before.
            for line in text.splitlines():
                if line.strip():
                    yield model.model_validate_json(line)


class Records(Mapping[str, tuple[Any, ...]]):
    """ref -> the records of an accepted entry, read from the file when asked for.

    Small kinds are parsed once and kept; an `UNCACHED` kind is parsed again on every
    access and never kept, so use `stream` for those. Every read checks the sha256 the
    pack records and refuses a file that changed since step B1.
    """

    def __init__(self, root: Path, entries: Sequence[PackEntry]) -> None:
        self._root = root
        self._entries = {e.ref: e for e in entries}
        self._kept: dict[str, tuple[Any, ...]] = {}

    def stream(self, ref: str) -> Iterator[Any]:
        entry = self._entries[ref]
        if ref in self._kept:
            return iter(self._kept[ref])
        return iter(Reader(self._root / ref, ref, KINDS[entry.kind], entry.sha256))

    def __getitem__(self, ref: str) -> tuple[Any, ...]:
        if ref in self._kept:
            return self._kept[ref]
        records = tuple(self.stream(ref))
        if self._entries[ref].kind not in UNCACHED:
            self._kept[ref] = records
        return records

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, ref: object) -> bool:
        return ref in self._entries


@dataclass(frozen=True)
class Admitted:
    admission: Admission
    # ref -> the parsed records of an accepted entry (`Records` reads them when asked for)
    records: Mapping[str, Sequence[Any]]

    def stream(self, ref: str) -> Iterator[Any]:
        """The records of `ref` one at a time, without keeping a large file in memory."""
        if isinstance(self.records, Records):
            return self.records.stream(ref)
        return iter(self.records[ref])


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
    accepted_entries: list[PackEntry] = []
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
        kind = KINDS.get(entry.kind)
        if kind is None:
            if sha256_of(path) != entry.sha256:
                raise PackRefused(f"{entry.ref}: the file changed after it was packed")
            rejected.append(Rejected(ref=entry.ref, reason=f"kind {entry.kind} has no contract "
                                     f"here (known: {', '.join(sorted(KINDS))})"))
            continue
        # One pass: hash and validate every line, keeping only what admit decides on.
        own: set[DataClass] = set()
        tasks: set[str] = set()
        try:
            for r in Reader(path, entry.ref, kind, entry.sha256):
                if isinstance(r, Score):
                    tasks.add(r.task_id)
                if hasattr(r, "data_class"):
                    own.add(r.data_class)
        except PARSE_ERRORS as error:
            rejected.append(Rejected(ref=entry.ref, reason="does not parse as "
                                     f"{entry.kind}: {_first_line(error)}"))
            continue
        other = sorted(t for t in tasks if t != pack.task_id)
        if other:
            rejected.append(Rejected(ref=entry.ref, reason=f"scores of task "
                                     f"{', '.join(other)}, the pack is for {pack.task_id}"))
            continue
        accepted_entries.append(entry)
        classes.extend(sorted(own))
        if entry.data_class == "public" and own == {"public"}:
            confirming.add(entry.ref)
    if not accepted_entries:
        raise PackRefused(f"{pack.pack_id}: no entry was accepted "
                          f"({'; '.join(f'{r.ref}: {r.reason}' for r in rejected)})")
    accepted = [e.ref for e in accepted_entries]
    data_class = highest(classes)
    unconfirmed = sorted(set(accepted) - _vouched(confirming, accepted, pack))
    kinds = {e.kind for e in accepted_entries}
    admission = Admission(
        pack_id=pack.pack_id, pack_sha256=sha256_of(pack_path), accepted=accepted,
        rejected=rejected, missing_kinds=[k for k in expected_kinds if k not in kinds],
        data_class=data_class, data_class_basis=sorted(confirming), unconfirmed=unconfirmed,
        hosted_allowed=CLASS_ORDER[data_class] == 0 and not unconfirmed,
    )
    return Admitted(admission, Records(root, accepted_entries))


def write_admission(admission: Admission, out: Path) -> Path:
    path = out / ADMISSION_FILE
    path.write_text(admission.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["ADMISSION_FILE", "KINDS", "PACK_FILE", "UNCACHED", "Admitted", "Kind", "Reader",
           "Records", "admit", "write_admission"]
