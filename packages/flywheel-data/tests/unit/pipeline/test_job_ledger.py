"""Every data-lane job writes an estimated and a measured LedgerEntry (PO 4/11/2026)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from flywheel.data.ledger import default_run_plan_id, job_ledger
from flywheel.store.ledger_append import read_job_ledger
from flywheel.store.paths import StorePaths


def ticking(*values: float) -> Callable[[], float]:
    times = iter(values)
    return lambda: next(times)


def test_a_job_writes_its_estimate_then_a_measurement_pointing_at_it(store: Path) -> None:
    with job_ledger(
        "qa", "data_qa", 12.0, note="assumed 1 ms per frame", clock=ticking(10.0, 13.5),
        today=date(2026, 11, 4),
    ) as job:
        job.notes.append("99 episodes")
    rows = read_job_ledger(job.run_plan_id, job.job_id, StorePaths(store))

    assert job.run_plan_id == "g0-DA-03-20261104"
    assert [r["measure_kind"] for r in rows] == ["estimated", "measured"]
    estimate, measured = rows
    assert estimate["quantity"] == 12.0 and estimate["note"] == "assumed 1 ms per frame"
    assert measured["quantity"] == 3.5
    assert measured["estimate_entry_id"] == estimate["id"]
    assert {r["job_id"] for r in rows} == {job.job_id}
    assert {r["run_plan_id"] for r in rows} == {"g0-DA-03-20261104"}
    assert measured["note"] == "wall seconds of data_qa, ok; 99 episodes"


def test_a_failed_job_still_records_what_it_spent(store: Path) -> None:
    with pytest.raises(RuntimeError), job_ledger(
        "pipeline", "data_release", 1.0, note="n", clock=ticking(0.0, 2.0),
        run_plan_id="rp_1",
    ) as job:
        raise RuntimeError("refused")
    rows = read_job_ledger("rp_1", job.job_id, StorePaths(store))
    assert [r["measure_kind"] for r in rows] == ["estimated", "measured"]
    assert rows[1]["note"] == "wall seconds of data_release, failed: RuntimeError"


def test_another_story_names_its_own_run_plan() -> None:
    assert default_run_plan_id("DA-27", date(2026, 11, 9)) == "g0-DA-27-20261109"
