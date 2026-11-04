"""`human_actions` in sink mode (DESIGN.md §4.4a, §7.2, §7.3).

Until Postgres exists the API writes every human action as one line of
``<state>/human_actions.jsonl``. That file is exactly what
``fwsync export --actions`` reads, so the write loop of milestone M4
(click → outbox → core → re-import) runs end to end without a database.

Two rules carried over from the schema:

* The same ``Idempotency-Key`` returns the same ``action_id`` (C16), also
  across a restart, because the store is reloaded from the file.
* The file is append-only. A later status change is a new line, never an edit.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Row = dict[str, Any]


@dataclass
class ActionStore:
    directory: Path
    _rows: dict[str, Row] = field(default_factory=dict)
    _by_key: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._rows[row["id"]] = row
                    if row.get("idempotency_key"):
                        self._by_key[row["idempotency_key"]] = row["id"]

    @property
    def path(self) -> Path:
        return self.directory / "human_actions.jsonl"

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
            existing = self._by_key.get(key)
            if existing is not None:
                return self._rows[existing]
            row: Row = {
                "id": f"act_{len(self._rows) + 1:04d}",
                "action_kind": kind,
                "target_kind": target_kind,
                "target_id": target_id,
                "payload": payload,
                "reason": reason,
                "sync_status": "PENDING",
                "reject_reason": None,
                "idempotency_key": key,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "exported_at": None,
                "applied_at": None,
            }
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._rows[row["id"]] = row
            self._by_key[key] = row["id"]
            return row

    def status(self, action_id: str) -> Row | None:
        """v_action_status, without the user and job columns sink mode has no table for."""
        row = self._rows.get(action_id)
        if row is None:
            return None
        return {
            "action_id": row["id"],
            "action_kind": row["action_kind"],
            "target_kind": row["target_kind"],
            "target_id": row["target_id"],
            "sync_status": row["sync_status"],
            "reason": row["reason"],
            "reject_reason": row["reject_reason"],
            "created_at": row["created_at"],
            "exported_at": row["exported_at"],
            "applied_at": row["applied_at"],
        }
