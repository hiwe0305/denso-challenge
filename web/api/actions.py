"""`human_actions` in sink mode (DESIGN.md §4.4a, §7.2, §7.3).

Until Postgres exists the API writes every human action as one creation line
of ``<state>/human_actions.jsonl``; ``fwsync`` appends the status lines
(``web/fwsync/actions.py`` describes the format). The API never edits a line,
and it reads status by folding the file, so a status written by ``fwsync`` in
another process shows up on the next read.

* The same ``Idempotency-Key`` returns the same ``action_id`` (C16), also
  across a restart, because the keys are rebuilt from the file.
* Each sync run is one line of ``<state>/sync_runs.jsonl`` (table ``sync_runs``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from web.fwsync import actions as log

Row = dict[str, Any]


@dataclass
class ActionStore:
    directory: Path
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.directory / "human_actions.jsonl"

    @property
    def runs_path(self) -> Path:
        return self.directory / "sync_runs.jsonl"

    def _state(self) -> dict[str, Row]:
        return log.fold(log.read_lines(self.path))

    def record(
        self,
        key: str,
        kind: str,
        target_kind: str,
        target_id: str,
        payload: Row,
        reason: str | None,
    ) -> Row:
        with self._lock:
            state = self._state()
            for existing in state.values():
                if existing.get("idempotency_key") == key:
                    return existing
            row: Row = {
                "id": f"act_{len(state) + 1:04d}",
                "action_kind": kind,
                "target_kind": target_kind,
                "target_id": target_id,
                "payload": payload,
                "reason": reason,
                "sync_status": "PENDING",
                "reject_reason": None,
                "idempotency_key": key,
                "created_at": log.now_iso(),
                "exported_at": None,
                "applied_at": None,
            }
            log.append(self.path, [row])
            return row

    @staticmethod
    def _view(row: Row) -> Row:
        """v_action_status, without the user and job columns sink mode has no table for."""
        return {
            "action_id": row["id"],
            "action_kind": row["action_kind"],
            "target_kind": row.get("target_kind"),
            "target_id": row.get("target_id"),
            "sync_status": row["sync_status"],
            "reason": row.get("reason"),
            "reject_reason": row.get("reject_reason"),
            "created_at": row.get("created_at"),
            "exported_at": row.get("exported_at"),
            "applied_at": row.get("applied_at"),
        }

    def by_key(self, key: str) -> Row | None:
        """The action already recorded under an Idempotency-Key, in the shape of `status`."""
        row = next((r for r in self._state().values() if r.get("idempotency_key") == key), None)
        return self._view(row) if row else None

    def status(self, action_id: str) -> Row | None:
        row = self._state().get(action_id)
        return self._view(row) if row else None

    def list_actions(self, sync_status: str | None) -> list[Row]:
        """Newest first, the order the bell and M10 read them in."""
        rows = [self._view(r) for r in self._state().values()]
        if sync_status:
            rows = [r for r in rows if r["sync_status"] == sync_status]
        return list(reversed(rows))

    def add_run(self, run: Row) -> Row:
        log.append(self.runs_path, [run])
        return run

    def runs(self) -> list[Row]:
        return list(reversed(log.read_lines(self.runs_path)))
