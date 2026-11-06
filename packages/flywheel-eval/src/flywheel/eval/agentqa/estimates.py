"""The agent's estimates, kept and later set against what was measured (DA-20 AC 6).

Design 9.1: "Ước lượng có khoảng, được lưu; khi có kết quả đo thì so lại". Like
the cost ledger, estimates and measurements are separate rows of one append-only
JSONL file and never overwrite each other: a `measured` row points at the
estimate it answers by `estimate_ref` (`<report_id>/<estimate_id>`).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flywheel.contracts.agentqa import AgentReport


@dataclass(frozen=True)
class Comparison:
    estimate_ref: str
    quantity: str
    low: float
    high: float
    measured: float | None

    @property
    def inside(self) -> bool | None:
        return None if self.measured is None else self.low <= self.measured <= self.high


def _append(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def record_estimates(report: AgentReport, path: Path) -> int:
    """Append one `estimated` row per estimate of `report`; returns how many."""
    return _append(
        path,
        (
            {
                "kind": "estimated",
                "estimate_ref": f"{report.report_id}/{e.estimate_id}",
                "subject_ref": report.subject_ref,
                "model": f"{report.model.name}@{report.model.revision}",
                "prompt_sha256": report.model.prompt_sha256,
                "quantity": e.quantity,
                "low": e.low,
                "high": e.high,
                "unit": e.unit,
                "at": report.created_at.isoformat(),
            }
            for e in report.estimates
        ),
    )


def record_measurement(
    path: Path, estimate_ref: str, value: float, source_ref: str, now: datetime | None = None
) -> None:
    """Append the `measured` row that answers `estimate_ref`; the estimate must exist."""
    if estimate_ref not in {r["estimate_ref"] for r in read(path) if r["kind"] == "estimated"}:
        raise KeyError(f"no estimate {estimate_ref} in {path}")
    _append(
        path,
        [
            {
                "kind": "measured",
                "estimate_ref": estimate_ref,
                "value": value,
                "source_ref": source_ref,
                "at": (now or datetime.now(timezone.utc)).isoformat(),
            }
        ],
    )


def read(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def compare(path: Path) -> list[Comparison]:
    """Each estimate with the latest measurement that answers it (None while unmeasured)."""
    rows = read(path)
    measured: dict[str, float] = {}
    for row in rows:
        if row["kind"] == "measured":
            measured[row["estimate_ref"]] = float(row["value"])
    return [
        Comparison(r["estimate_ref"], r["quantity"], r["low"], r["high"],
                   measured.get(r["estimate_ref"]))
        for r in rows
        if r["kind"] == "estimated"
    ]
