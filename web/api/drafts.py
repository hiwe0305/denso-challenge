"""Experiment drafts in sink mode: the W table `experiment_drafts` (DESIGN.md §4.4, §7.2).

A draft is the web's own record, edited freely while `DRAFT`, so unlike
`human_actions` it is not append-only: the store keeps one JSON file in the
API's state directory and rewrites it. Submitting freezes it: the draft turns
`SUBMITTED`, carries the `EXPERIMENT_SUBMIT` action, and never changes again
here; `ACCEPTED` or `REJECTED` come back from the core (W7).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from web.contracts.enums import ALL
from web.fwsync import actions as log

Row = dict[str, Any]

TASKS = ALL["task_id"]
METHODS = ALL["method"]
EDITABLE = ("task_id", "branch", "method", "hypothesis", "base_checkpoint_ref",
            "run_plan_ref", "hyperparams", "release_mix")


class DraftError(ValueError):
    """A draft body the store refuses, with the code the API returns."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_body(body: Row, *, partial: bool) -> Row:
    """The editable fields of a body, typed. Rules of the domain wait for submit (BR-01)."""
    unknown = sorted(set(body) - set(EDITABLE))
    if unknown:
        raise DraftError("BAD_DRAFT", f"trường không sửa được: {unknown}")
    out = {k: body[k] for k in EDITABLE if k in body}
    if not partial:
        required = ("task_id", "branch", "method", "base_checkpoint_ref")
        missing = [k for k in required if not out.get(k)]
        if missing:
            raise DraftError("BAD_DRAFT", f"thiếu {missing}")
    if "task_id" in out and out["task_id"] not in TASKS:
        raise DraftError("BAD_DRAFT", f"task_id {out['task_id']!r} không có; chỉ {TASKS}")
    if "method" in out and out["method"] not in METHODS:
        raise DraftError("BAD_DRAFT", f"method {out['method']!r} không có; chỉ {METHODS}")
    if "hyperparams" in out and not isinstance(out["hyperparams"], dict):
        raise DraftError("BAD_DRAFT", "hyperparams phải là đối tượng")
    if "release_mix" in out:
        mix = out["release_mix"]
        if not isinstance(mix, list) or not all(
            isinstance(m, dict) and isinstance(m.get("release_id"), str)
            and isinstance(m.get("mix_weight"), (int, float)) and 0 < m["mix_weight"] <= 1
            for m in mix
        ):
            raise DraftError("BAD_DRAFT", "release_mix là [{release_id, mix_weight ∈ (0, 1]}]")
    return out


@dataclass
class DraftStore:
    directory: Path
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def path(self) -> Path:
        return self.directory / "experiment_drafts.json"

    def _load(self) -> list[Row]:
        if not self.path.exists():
            return []
        loaded: list[Row] = json.loads(self.path.read_text(encoding="utf-8"))
        return loaded

    def _save(self, rows: list[Row]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8", newline="\n")

    def list(self) -> list[Row]:
        return list(reversed(self._load()))  # newest first

    def get(self, draft_id: str) -> Row | None:
        return next((d for d in self._load() if d["id"] == draft_id), None)

    def create(self, body: Row, created_by: str) -> Row:
        fields = check_body(body, partial=False)
        with self._lock:
            rows = self._load()
            now = log.now_iso()
            row: Row = {
                "id": f"drf_{len(rows) + 1:04d}", "task_id": fields["task_id"],
                "branch": fields["branch"], "method": fields["method"],
                "hypothesis": fields.get("hypothesis"),
                "base_checkpoint_ref": fields["base_checkpoint_ref"],
                "run_plan_ref": fields.get("run_plan_ref"),
                "hyperparams": fields.get("hyperparams") or {},
                "release_mix": fields.get("release_mix") or [],
                "status": "DRAFT", "submit_action_id": None, "experiment_id": None,
                "reject_reason": None, "created_by": created_by,
                "created_at": now, "updated_at": now,
            }
            rows.append(row)
            self._save(rows)
            return row

    def patch(self, draft_id: str, body: Row) -> Row | None:
        fields = check_body(body, partial=True)
        with self._lock:
            rows = self._load()
            row = next((d for d in rows if d["id"] == draft_id), None)
            if row is None:
                return None
            if row["status"] != "DRAFT":
                raise DraftError("ALREADY_SUBMITTED", "bản nháp đã nộp; không sửa được nữa")
            row.update(fields, updated_at=log.now_iso())
            self._save(rows)
            return row

    def mark_submitted(self, draft_id: str, action_id: str) -> Row:
        with self._lock:
            rows = self._load()
            row = next(d for d in rows if d["id"] == draft_id)
            row.update(status="SUBMITTED", submit_action_id=action_id, updated_at=log.now_iso())
            self._save(rows)
            return row
