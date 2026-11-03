"""Unit tests for ledger.append and cost tracking (AC 7)."""

from pathlib import Path

import pytest
from flywheel.contracts.entities import LedgerEntry
from flywheel.store.ledger_append import LedgerStore
from flywheel.store.paths import StorePaths
from flywheel.store.views import open_duckdb
from pydantic import ValidationError


def test_ledger_append_estimated_and_measured_separate(tmp_path: Path) -> None:
    """AC 7: ledger.append records LedgerEntry; estimated and measured are distinct rows."""
    paths = StorePaths(root=tmp_path)
    store = LedgerStore(paths=paths)

    run_plan_id = "rp_demo_round1"
    job_id = "job_train_step1"

    # 1. Append an estimated entry
    entry_est = LedgerEntry(
        activity="train",
        resource_type="gpu_hour_a100",
        quantity=5.0,
        unit="hour",
        usd_amount=15.00,
        human_hours=0.5,
        measure_kind="estimated",
        run_plan_id=run_plan_id,
        job_id=job_id,
        note="Initial plan estimate",
    )
    store.append(entry_est)

    # 2. Append a measured entry linked via estimate_entry_id
    entry_meas = LedgerEntry(
        activity="train",
        resource_type="gpu_hour_a100",
        quantity=4.8,
        unit="hour",
        usd_amount=14.40,
        human_hours=0.4,
        measure_kind="measured",
        estimate_entry_id=entry_est.id,
        run_plan_id=run_plan_id,
        job_id=job_id,
        note="Actual recorded consumption",
    )
    store.append(entry_meas)

    # 3. Read back from file
    entries = store.read(run_plan_id, job_id)
    assert len(entries) == 2
    assert entries[0]["measure_kind"] == "estimated"
    assert entries[0]["usd_amount"] == 15.00
    assert entries[1]["measure_kind"] == "measured"
    assert entries[1]["usd_amount"] == 14.40
    assert entries[1]["estimate_entry_id"] == entry_est.id

    # 4. Verify path format: runs/<run_plan_id>/<job_id>/ledger.jsonl
    expected_path = tmp_path / "sites" / "local" / "runs" / run_plan_id / job_id / "ledger.jsonl"
    assert expected_path.is_file()

    # 5. Query through DuckDB view ledger_entry
    query = """
        SELECT measure_kind, usd_amount, quantity, estimate_entry_id
        FROM ledger_entry
        ORDER BY usd_amount DESC
    """
    con = open_duckdb(paths=paths)
    rows = con.execute(query).fetchall()
    assert len(rows) == 2
    assert rows[0] == ("estimated", 15.00, 5.0, None)
    assert rows[1] == ("measured", 14.40, 4.8, entry_est.id)
    con.close()


def test_ledger_entry_validations() -> None:
    """Feedback item 5: validate measure_kind required and estimate_entry_id restriction."""
    # Missing measure_kind
    with pytest.raises(ValidationError):
        LedgerEntry(  # type: ignore[call-arg]
            activity="eval",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=5.0,
        )

    # Estimated cannot have estimate_entry_id
    with pytest.raises(ValueError, match="estimated entry cannot have an estimate_entry_id"):
        LedgerEntry(
            activity="eval",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=5.0,
            measure_kind="estimated",
            estimate_entry_id="led_12345",
        )


def _gpu_entry(**fields: object) -> LedgerEntry:
    base: dict[str, object] = {
        "activity": "eval",
        "resource_type": "gpu_hour_3060",
        "quantity": 1.0,
        "unit": "hour",
        "usd_amount": 0.2,
        "run_plan_id": "rp_1",
        "job_id": "job_1",
    }
    return LedgerEntry.model_validate({**base, **fields})


def test_measured_entry_needs_an_estimate_that_exists(tmp_path: Path) -> None:
    """PO review 3/11 item 4: a measured row must point at a ledger row that exists."""
    store = LedgerStore(paths=StorePaths(root=tmp_path))
    orphan = _gpu_entry(measure_kind="measured", estimate_entry_id="led_" + "0" * 26)
    with pytest.raises(ValueError, match="does not exist"):
        store.append(orphan)
    assert store.read("rp_1", "job_1") == []


def test_measured_entry_cannot_point_at_another_measured_entry(tmp_path: Path) -> None:
    store = LedgerStore(paths=StorePaths(root=tmp_path))
    estimate = _gpu_entry(measure_kind="estimated")
    store.append(estimate)
    measured = _gpu_entry(measure_kind="measured", estimate_entry_id=estimate.id)
    store.append(measured)

    chained = _gpu_entry(measure_kind="measured", estimate_entry_id=measured.id)
    with pytest.raises(ValueError, match="not an estimated row"):
        store.append(chained)
    assert [row["id"] for row in store.read("rp_1", "job_1")] == [estimate.id, measured.id]


def test_measured_entry_may_point_at_an_estimate_of_another_job(tmp_path: Path) -> None:
    """The estimate can be written by the planning job, the measurement by the job that ran."""
    store = LedgerStore(paths=StorePaths(root=tmp_path))
    estimate = _gpu_entry(measure_kind="estimated", job_id="job_plan")
    store.append(estimate)
    store.append(_gpu_entry(measure_kind="measured", estimate_entry_id=estimate.id))
    assert len(store.read("rp_1", "job_1")) == 1


def test_reversal_must_point_at_an_entry_that_exists(tmp_path: Path) -> None:
    store = LedgerStore(paths=StorePaths(root=tmp_path))
    with pytest.raises(ValidationError):
        _gpu_entry(measure_kind="estimated", quantity=-1.0, reverses_entry_id="whatever")
    ghost = _gpu_entry(
        measure_kind="estimated",
        quantity=-1.0,
        usd_amount=-0.2,
        reverses_entry_id="led_" + "1" * 26,
    )
    with pytest.raises(ValueError, match="does not exist"):
        store.append(ghost)

    estimate = _gpu_entry(measure_kind="estimated")
    store.append(estimate)
    store.append(
        _gpu_entry(
            measure_kind="estimated", quantity=-1.0, usd_amount=-0.2, reverses_entry_id=estimate.id
        )
    )
    assert len(store.read("rp_1", "job_1")) == 2


def test_ledger_refuses_an_id_reused_with_other_content(tmp_path: Path) -> None:
    """PO decision D1 (3/11): the ledger holds one row per id, like the catalog."""
    store = LedgerStore(paths=StorePaths(root=tmp_path))
    estimate = _gpu_entry(measure_kind="estimated")
    store.append(estimate)
    store.append(estimate)  # same content: a harmless re-write, the view counts it once

    inflated = _gpu_entry(measure_kind="estimated", id=estimate.id, usd_amount=99.0)
    with pytest.raises(ValueError, match=f"ledger_entry.*{estimate.id}"):
        store.append(inflated)
    assert [row["usd_amount"] for row in store.read("rp_1", "job_1")] == [0.2, 0.2]
