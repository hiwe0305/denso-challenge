"""Append-only cost ledger recording under runs/<run_plan_id>/<job_id>/ledger.jsonl (03 §7.2, AC 7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flywheel.contracts.base import canonical_json
from flywheel.contracts.entities import LedgerEntry
from flywheel.store.paths import StorePaths


def append_ledger_entry(
    entry: LedgerEntry,
    paths: StorePaths | None = None,
) -> Path:
    """Append a LedgerEntry record to the job's ledger.jsonl file."""
    if paths is None:
        paths = StorePaths()

    run_plan_id = entry.run_plan_id or "default"
    job_id = entry.job_id or "default"
    ledger_path = paths.job_ledger_path(run_plan_id, job_id)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(entry)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    return ledger_path


def read_job_ledger(
    run_plan_id: str,
    job_id: str,
    paths: StorePaths | None = None,
) -> list[dict[str, Any]]:
    """Read all LedgerEntry lines from a job's ledger.jsonl."""
    if paths is None:
        paths = StorePaths()

    ledger_path = paths.job_ledger_path(run_plan_id, job_id)
    if not ledger_path.is_file():
        return []

    entries: list[dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


class LedgerStore:
    """Store interface for cost ledger operations."""

    def __init__(self, paths: StorePaths | None = None) -> None:
        self.paths = paths or StorePaths()

    def append(self, entry: LedgerEntry) -> Path:
        """Append a LedgerEntry to the appropriate job ledger file."""
        return append_ledger_entry(entry, paths=self.paths)

    def read(self, run_plan_id: str, job_id: str) -> list[dict[str, Any]]:
        """Read all ledger entries for a job."""
        return read_job_ledger(run_plan_id, job_id, paths=self.paths)


# Convenience module-level singleton instance
ledger = LedgerStore()
