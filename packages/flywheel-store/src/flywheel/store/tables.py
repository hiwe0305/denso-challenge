"""Append-only partitioned tables under catalog/<table_name>/part-<ulid>.jsonl (03 §7.2, AC 5)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from flywheel.contracts.base import canonical_json, new_ulid
from flywheel.store.paths import StorePaths
from flywheel.store.views import CATALOG_TABLES, TABLE_MODELS
from pydantic import BaseModel

# Episode and QAReport name their id field themselves; `id` is a property there.
ID_FIELDS: dict[str, str] = {"episode": "episode_id", "qa_report": "report_id"}


def complete_lines(path: Path) -> list[str]:
    """The JSON lines of a part file, leaving out a last line still being written."""
    lines = path.read_text(encoding="utf-8").split("\n")[:-1]
    return [line for line in lines if line.strip()]


def refuse_reused_ids(
    table_name: str,
    rows: list[dict[str, Any]],
    files: Iterable[Path],
    id_field: str = "id",
) -> None:
    """Refuse a row whose id is already stored, or earlier in `rows`, with other content.

    One id names one record (PO decision D1, 3/11/2026). Writing the same
    record again is harmless, since the views keep one row per id; giving the
    id a second meaning would make the view silently pick one of the two.
    """
    wanted = {row[id_field] for row in rows}
    seen: dict[str, dict[str, Any]] = {}
    for path in files:
        for line in complete_lines(path):
            stored = json.loads(line)
            if stored.get(id_field) in wanted:
                seen.setdefault(stored[id_field], stored)
    for row in rows:
        stored = seen.setdefault(row[id_field], row)
        if stored != row:
            raise ValueError(
                f"{table_name}: id '{row[id_field]}' is already stored with other content; "
                "an id names one record, write the change under a new id"
            )


class TableWriter:
    """Process-specific partition writer for an append-only catalog table."""

    def __init__(
        self,
        table_name: str,
        paths: StorePaths | None = None,
        part_id: str | None = None,
    ) -> None:
        if table_name not in CATALOG_TABLES:
            hint = ""
            if table_name == "ledger_entry":
                # The ledger lives under runs/; a catalog part would never reach its view.
                hint = " (write the cost ledger with ledger.append)"
            raise ValueError(
                f"'{table_name}' is not a catalog table{hint}; "
                f"expected one of {', '.join(CATALOG_TABLES)}"
            )
        self.table_name = table_name
        self.paths = paths or StorePaths()
        self.part_id = part_id or new_ulid()
        self.table_dir = self.paths.table_dir(table_name)
        self.part_path = self.table_dir / f"part-{self.part_id}.jsonl"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.table_dir.mkdir(parents=True, exist_ok=True)

    def _validate_record(self, record: BaseModel | dict[str, Any]) -> BaseModel:
        model_cls = TABLE_MODELS[self.table_name]
        if isinstance(record, model_cls):
            return record
        if isinstance(record, dict):
            return model_cls.model_validate(record)
        if isinstance(record, BaseModel):
            return model_cls.model_validate(record.model_dump(mode="json"))
        raise ValueError(
            f"Invalid record type for table '{self.table_name}': "
            f"expected {model_cls.__name__} or dict, got {type(record)}"
        )

    def append(self, record: BaseModel | dict[str, Any]) -> None:
        """Append a single record as a JSON line to this partition file."""
        self.append_many([record])

    def append_many(self, records: list[BaseModel | dict[str, Any]]) -> None:
        """Append multiple records to this partition file."""
        if not records:
            return
        validated_list = [self._validate_record(r) for r in records]
        lines = [canonical_json(r) for r in validated_list]
        refuse_reused_ids(
            self.table_name,
            [json.loads(line) for line in lines],
            sorted(self.table_dir.glob("part-*.jsonl")),
            ID_FIELDS.get(self.table_name, "id"),
        )
        with open(self.part_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")


def write_record(
    table_name: str,
    record: BaseModel | dict[str, Any],
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
