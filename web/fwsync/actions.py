"""The life of a human action in sink mode (DESIGN.md §3.2, §5.5, Appendix A.2).

Until Postgres exists, ``human_actions`` is one append-only JSONL file. Two
kinds of line live in it:

* a **creation** line, written by the API: the whole action, ``PENDING``;
* a **status** line, written by ``fwsync``: ``{"event": "status", "id",
  "sync_status", "at", "reject_reason"}``.

Nothing is ever edited in place, the same rule as the ledger (R4). The
current state of an action is its creation line with every later status line
folded over it, which is what ``fold`` computes.

The lifecycle is ``PENDING → EXPORTED → APPLIED`` (or ``REJECTED``):

* ``fwsync export`` writes an outbox artifact for each PENDING action and
  marks it EXPORTED;
* ``fwsync import --actions`` marks APPLIED every EXPORTED action whose
  ``source_action_id`` comes back in an imported artifact.

A status only moves forward. Seeing ``source_action_id`` for an action that
is already APPLIED changes nothing, so re-running import is harmless (§5.5).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Row = dict[str, Any]

#: Order of the lifecycle; a status line that would move an action backwards is ignored.
RANK = {"PENDING": 0, "EXPORTED": 1, "APPLIED": 2, "REJECTED": 2}
TIME_FIELD = {"EXPORTED": "exported_at", "APPLIED": "applied_at", "REJECTED": "applied_at"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_lines(path: Path) -> list[Row]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def fold(lines: Iterable[Row]) -> dict[str, Row]:
    """Current state of every action, in creation order."""
    state: dict[str, Row] = {}
    for line in lines:
        if line.get("event") == "status":
            row = state.get(str(line.get("id")))
            status = str(line.get("sync_status"))
            if row is None or RANK.get(status, -1) <= RANK.get(row["sync_status"], -1):
                continue
            row["sync_status"] = status
            row[TIME_FIELD[status]] = line.get("at")
            if status == "REJECTED":
                row["reject_reason"] = line.get("reject_reason")
            continue
        if line.get("id") and line.get("action_kind"):
            row = dict(line)
            row.setdefault("sync_status", "PENDING")
            for column in ("exported_at", "applied_at", "reject_reason"):
                row.setdefault(column, None)
            state[str(row["id"])] = row
    return state


def append(path: Path, lines: Iterable[Row]) -> int:
    rows = list(lines)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return len(rows)


def mark(path: Path, ids: Iterable[str], status: str, reason: str | None = None) -> list[str]:
    """Append a status line for each action that this status moves forward."""
    state = fold(read_lines(path))
    at = now_iso()
    moved = [
        i for i in dict.fromkeys(ids)
        if i in state and RANK[status] > RANK.get(state[i]["sync_status"], -1)
    ]
    append(path, (
        {"event": "status", "id": i, "sync_status": status, "at": at, "reject_reason": reason}
        for i in moved
    ))
    return moved


def pending(path: Path) -> list[Row]:
    return [row for row in fold(read_lines(path)).values() if row["sync_status"] == "PENDING"]


def answered_ids(records: Iterable[Any]) -> list[str]:
    """``source_action_id`` of every imported artifact that carries one (W7)."""
    out: list[str] = []
    for record in records:
        payload = getattr(record, "payload", record)
        if isinstance(payload, dict) and payload.get("source_action_id"):
            out.append(str(payload["source_action_id"]))
    return out
