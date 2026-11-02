"""Unit tests for ledger.append and cost tracking (AC 7)."""

from pathlib import Path

from flywheel.contracts.entities import LedgerEntry
from flywheel.store.ledger_append import LedgerStore, append_ledger_entry, read_job_ledger
from flywheel.store.paths import StorePaths
from flywheel.store.views import open_duckdb


def test_ledger_append_estimated_and_measured_separate(tmp_path: Path) -> None:
    """AC 7: ledger.append records LedgerEntry; estimated and measured are distinct."""
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

    # 2. Append a measured entry
    entry_meas = LedgerEntry(
        activity="train",
        resource_type="gpu_hour_a100",
        quantity=4.8,
        unit="hour",
        usd_amount=14.40,
        human_hours=0.4,
        measure_kind="measured",
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

    # 4. Verify path format: runs/<run_plan_id>/<job_id>/ledger.jsonl
    expected_path = tmp_path / "sites" / "local" / "runs" / run_plan_id / job_id / "ledger.jsonl"
    assert expected_path.is_file()

    # 5. Query through DuckDB view ledger_entry
    con = open_duckdb(paths=paths)
    rows = con.execute("SELECT measure_kind, usd_amount, quantity FROM ledger_entry ORDER BY usd_amount DESC").fetchall()
    assert len(rows) == 2
    assert rows[0] == ("estimated", 15.00, 5.0)
    assert rows[1] == ("measured", 14.40, 4.8)
    con.close()
