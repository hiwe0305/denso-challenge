"""Append-only cost ledger recording under runs/<run_plan_id>/<job_id>/ledger.jsonl (03 §7.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flywheel.contracts.base import canonical_json
from flywheel.contracts.entities import LedgerEntry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import complete_lines, refuse_reused_ids


def _ledger_files(paths: StorePaths) -> list[Path]:
    """Every job ledger of the site."""
    return sorted(paths.runs_dir.glob("**/ledger*.jsonl"))


def _measure_kinds(paths: StorePaths) -> dict[str, str]:
    """Map every entry id already in the site's ledger to its measure_kind."""
    kinds: dict[str, str] = {}
    for ledger_path in _ledger_files(paths):
        for line in complete_lines(ledger_path):
            row = json.loads(line)
            kinds[row["id"]] = row["measure_kind"]
    return kinds


def _check_links(entry: LedgerEntry, paths: StorePaths) -> None:
    """A measured row points at an estimated row and a reversal at a row, both on disk.

    The model only checks the shape of the ids; whether they name a real row
    can only be known here. The lookup covers the whole site ledger, not only
    this job, since the estimate may be written by the job that planned the
    work and the measurement by the job that ran it.
    """
    if entry.estimate_entry_id is None and entry.reverses_entry_id is None:
        return
    kinds = _measure_kinds(paths)
    if entry.estimate_entry_id is not None:
        kind = kinds.get(entry.estimate_entry_id)
        if kind is None:
            raise ValueError(
                f"estimate_entry_id '{entry.estimate_entry_id}' does not exist in the ledger"
            )
        if kind != "estimated":
            raise ValueError(
                f"estimate_entry_id '{entry.estimate_entry_id}' is a {kind} row, "
                "not an estimated row"
            )
    if entry.reverses_entry_id is not None and entry.reverses_entry_id not in kinds:
        raise ValueError(
            f"reverses_entry_id '{entry.reverses_entry_id}' does not exist in the ledger"
        )


def append_ledger_entry(
    entry: LedgerEntry,
    paths: StorePaths | None = None,
) -> Path:
    """Append a LedgerEntry record to the job's ledger.jsonl file."""
    if paths is None:
        paths = StorePaths()

    _check_links(entry, paths)
    line = canonical_json(entry)
    refuse_reused_ids("ledger_entry", [json.loads(line)], _ledger_files(paths))
    run_plan_id = entry.run_plan_id or "default"
    job_id = entry.job_id or "default"
    ledger_path = paths.job_ledger_path(run_plan_id, job_id)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
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
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


class LedgerStore:
    """Store interface for cost ledger operations."""

    def __init__(self, paths: StorePaths | None = None) -> None:
        self._paths = paths

    @property
    def paths(self) -> StorePaths:
        """Dynamically resolve StorePaths if not explicitly provided."""
        return self._paths if self._paths is not None else StorePaths()

    def append(self, entry: LedgerEntry) -> Path:
        """Append a LedgerEntry to the appropriate job ledger file."""
        return append_ledger_entry(entry, paths=self.paths)

    def read(self, run_plan_id: str, job_id: str) -> list[dict[str, Any]]:
        """Read all ledger entries for a job."""
        return read_job_ledger(run_plan_id, job_id, paths=self.paths)


# Convenience module-level singleton instance
ledger = LedgerStore()
