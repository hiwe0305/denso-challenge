"""The two LedgerEntry rows every data-lane job writes (PO decision 4/11/2026, "Cho phụ thuộc").

Each `fw data` command, and DA-27's inject build, runs inside `job_ledger`. Before
the work starts, one estimated row; when it ends, one measured row with the job's
wall seconds and `estimate_entry_id` pointing at the estimate. Estimate and
measurement are two rows and never overwrite each other (CLAUDE.md invariant). Both
go through `flywheel.store.ledger_append`, which keeps the site ledger append-only
under `runs/<run_plan_id>/<job_id>/ledger.jsonl` and checks the link.

Every row names a run plan (PO decision D4). A job started without a RunPlan uses
`g0-<story>-<yyyymmdd>` of the day it starts. A job that raises still gets its
measured row, with the error type in the note, since the time was spent (spec 4.4:
rejected work keeps its cost); the error is raised again.

The estimate is an assumption the caller states in `note`, never a measurement.
Local CPU has no price in the pricebook yet, so `usd_amount` is 0 on both rows.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from flywheel.contracts.base import new_ulid
from flywheel.contracts.entities import LedgerEntry
from flywheel.data.config import store_root
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths

RESOURCE = "cpu_seconds"
UNIT = "s"


@dataclass
class Job:
    """A running job: where its rows go, and the rows written so far."""

    run_plan_id: str
    job_id: str
    estimate: LedgerEntry
    measured: LedgerEntry | None = None
    notes: list[str] = field(default_factory=list)  # appended to the measured row's note


def default_run_plan_id(story: str, today: date | None = None) -> str:
    """`g0-<story>-<yyyymmdd>`: the run plan of a job started without a RunPlan."""
    return f"g0-{story}-{(today or date.today()):%Y%m%d}"


@contextmanager
def job_ledger(
    activity: str,
    command: str,
    estimated_seconds: float,
    *,
    note: str,
    run_plan_id: str | None = None,
    story: str = "DA-03",
    store: Path | None = None,
    clock: Callable[[], float] = time.monotonic,
    today: date | None = None,
) -> Iterator[Job]:
    """Write the estimated row, run the body, then write the measured row.

    `activity` is one of `LedgerEntry.activity` ("pipeline", "qa", "data_generation",
    ...); `command` names the job in its id (`job_<command>_<ULID>`); `note` says what
    the estimate assumes.
    """
    paths = StorePaths(store or store_root())
    plan = run_plan_id or default_run_plan_id(story, today)
    job_id = f"job_{command}_{new_ulid()}"

    def row(quantity: float, kind: str, text: str, estimate_id: str | None) -> LedgerEntry:
        return LedgerEntry.model_validate(
            {
                "activity": activity,
                "resource_type": RESOURCE,
                "quantity": quantity,
                "unit": UNIT,
                "usd_amount": 0.0,
                "measure_kind": kind,
                "estimate_entry_id": estimate_id,
                "run_plan_id": plan,
                "job_id": job_id,
                "note": text,
            }
        )

    estimate = row(estimated_seconds, "estimated", note, None)
    append_ledger_entry(estimate, paths)
    job = Job(plan, job_id, estimate)
    start = clock()
    outcome = "ok"
    try:
        yield job
    except BaseException as exc:
        outcome = f"failed: {type(exc).__name__}"
        raise
    finally:
        text = "; ".join([f"wall seconds of {command}, {outcome}", *job.notes])
        job.measured = row(max(clock() - start, 0.0), "measured", text, estimate.id)
        append_ledger_entry(job.measured, paths)
