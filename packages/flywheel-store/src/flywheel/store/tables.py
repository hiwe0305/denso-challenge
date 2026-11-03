"""Append-only partitioned tables under catalog/<table_name>/part-<ulid>.jsonl (03 §7.2, AC 5)."""

from __future__ import annotations

import json
from typing import Any

from flywheel.contracts.base import BaseRecord, canonical_json, new_ulid
from flywheel.store.paths import StorePaths


class TableWriter:
    """Process-specific partition writer for an append-only catalog table."""

    def __init__(
        self,
        table_name: str,
        paths: StorePaths | None = None,
        part_id: str | None = None,
    ) -> None:
        self.table_name = table_name
        self.paths = paths or StorePaths()
        self.part_id = part_id or new_ulid()
        self.table_dir = self.paths.table_dir(table_name)
        self.part_path = self.table_dir / f"part-{self.part_id}.jsonl"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.table_dir.mkdir(parents=True, exist_ok=True)

    def append(self, record: BaseRecord | dict[str, Any]) -> None:
        """Append a single record as a JSON line to this partition file."""
        line = canonical_json(record)
        with open(self.part_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def append_many(self, records: list[BaseRecord | dict[str, Any]]) -> None:
        """Append multiple records to this partition file."""
        if not records:
            return
        lines = [canonical_json(r) for r in records]
        with open(self.part_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")


def write_record(
    table_name: str,
    record: BaseRecord | dict[str, Any],
    paths: StorePaths | None = None,
) -> None:
    """Convenience helper to append a record to a new process partition."""
    writer = TableWriter(table_name, paths=paths)
    writer.append(record)


def read_table_records(
    table_name: str,
    paths: StorePaths | None = None,
) -> list[dict[str, Any]]:
    """Read all records across all partition files for a table."""
    if paths is None:
        paths = StorePaths()

    table_dir = paths.table_dir(table_name)
    if not table_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for file_path in sorted(table_dir.glob("part-*.jsonl")):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records
