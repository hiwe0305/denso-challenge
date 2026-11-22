"""The store snapshot of a pack: ledger and fix-rate rows, copied in at step B0 (task 4.7).

`cost_lookup` and `history_lookup` read these rows from the pack, never from the live
store, so a round is a function of its pack. `build_pack` calls `snapshot_tables` once, with
the site store; the files are written under the pack root, one JSON object per line,
canonical (sorted keys) and sorted by id, so the same rows give the same bytes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from flywheel.contracts.entities import FixRateEvent, LedgerEntry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import complete_lines, read_table_records
from pydantic import BaseModel, ValidationError

SNAPSHOT_DIR = "store_snapshot"


def read_ledger(paths: StorePaths) -> tuple[list[LedgerEntry], int]:
    """Every ledger row of the site, and how many lines did not parse."""
    rows: list[LedgerEntry] = []
    bad = 0
    for file in sorted(paths.runs_dir.glob("**/ledger*.jsonl")):
        for line in complete_lines(file):
            try:
                rows.append(LedgerEntry.model_validate(json.loads(line)))
            except (ValueError, ValidationError):
                bad += 1
    return rows, bad


def read_events(paths: StorePaths) -> tuple[list[FixRateEvent], int]:
    """The fix-rate events of the site, and how many rows did not parse."""
    events: list[FixRateEvent] = []
    bad = 0
    for record in read_table_records("fix_rate_event", paths):
        try:
            events.append(FixRateEvent.model_validate(record))
        except ValidationError:
            bad += 1
    return events, bad


@dataclass(frozen=True)
class Snapshot:
    kind: str  # the pack kind of the file
    rows: list[BaseModel]
    unreadable: int


# table name in `round.yaml` -> the pack kind and the reader
TABLES: dict[str, tuple[str, Callable[[StorePaths], tuple[list[BaseModel], int]]]] = {
    "ledger": ("ledger", read_ledger),  # type: ignore[dict-item]
    "fix_rate": ("fix_rate", read_events),  # type: ignore[dict-item]
}


def canonical_lines(rows: list[BaseModel]) -> str:
    """The rows as canonical JSON lines, sorted by id (then by text), so bytes are stable."""
    lines = sorted((str(getattr(r, "id", "")), json.dumps(
        r.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        for r in rows)
    return "".join(f"{line}\n" for _, line in lines)


def read_table(table: str, paths: StorePaths) -> Snapshot:
    kind, reader = TABLES[table]
    rows, bad = reader(paths)
    return Snapshot(kind, rows, bad)


def snapshot_path(root: Path, table: str) -> Path:
    return root / SNAPSHOT_DIR / f"{table}.jsonl"
