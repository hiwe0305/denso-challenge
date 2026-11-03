"""Append-only partitioned tables under catalog/<table_name>/part-<ulid>.jsonl (03 §7.2, AC 5)."""

from __future__ import annotations

import json
from typing import Any

from flywheel.contracts.base import canonical_json, new_ulid
from flywheel.store.paths import StorePaths
from flywheel.store.views import CATALOG_TABLES, TABLE_MODELS
from pydantic import BaseModel


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
        validated = self._validate_record(record)
        line = canonical_json(validated)
        with open(self.part_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def append_many(self, records: list[BaseModel | dict[str, Any]]) -> None:
        """Append multiple records to this partition file."""
        if not records:
            return
        validated_list = [self._validate_record(r) for r in records]
        lines = [canonical_json(r) for r in validated_list]
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
