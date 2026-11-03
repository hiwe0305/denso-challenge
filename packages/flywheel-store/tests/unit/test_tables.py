"""Unit tests for append-only partition tables and concurrent writing (AC 5)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flywheel.contracts.entities import Condition, Source
from flywheel.store.paths import StorePaths
from flywheel.store.tables import TableWriter, read_table_records, write_record
from pydantic import ValidationError


def test_table_writer_append_and_read(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    cond1 = Condition(condition_seed=1, layout_hash="a" * 64)
    cond2 = Condition(condition_seed=2, layout_hash="b" * 64)

    writer = TableWriter("condition", paths=paths)
    writer.append(cond1)
    writer.append(cond2)

    records = read_table_records("condition", paths=paths)
    assert len(records) == 2
    assert records[0]["condition_seed"] == 1
    assert records[1]["condition_seed"] == 2
    assert records[0]["site_id"] == "local"


def test_table_writer_rejects_invalid_dict(tmp_path: Path) -> None:
    """Feedback item 4: TableWriter validates records against table model, rejecting garbage."""
    paths = StorePaths(root=tmp_path)
    writer = TableWriter("episode", paths=paths)

    # Raw garbage dict is rejected with ValidationError
    with pytest.raises(ValidationError):
        writer.append({"garbage": 1})

    with pytest.raises(ValidationError):
        write_record("episode", {"garbage": 1}, paths=paths)


def test_concurrent_partition_writers(tmp_path: Path) -> None:
    """AC 5: Concurrent writers write to separate part-<ulid>.jsonl without lock contention."""
    paths = StorePaths(root=tmp_path)
    num_writers = 4
    records_per_writer = 25

    def _worker(worker_id: int) -> None:
        writer = TableWriter("condition", paths=paths)
        for i in range(records_per_writer):
            cond = Condition(
                condition_seed=worker_id * 1000 + i,
                layout_hash=f"{worker_id:04x}" + "0" * 60,
                values={"worker": worker_id, "index": i},
            )
            writer.append(cond)

    with ThreadPoolExecutor(max_workers=num_writers) as executor:
        futures = [executor.submit(_worker, w) for w in range(num_writers)]
        for f in futures:
            f.result()

    part_files = list((paths.table_dir("condition")).glob("part-*.jsonl"))
    assert len(part_files) == num_writers

    all_records = read_table_records("condition", paths=paths)
    assert len(all_records) == num_writers * records_per_writer

    seeds = {r["condition_seed"] for r in all_records}
    assert len(seeds) == num_writers * records_per_writer


@pytest.mark.parametrize("table", ["scores", "ledger_entry", "evidence_card"])
def test_writer_refuses_a_table_outside_the_catalog(tmp_path: Path, table: str) -> None:
    """PO review 3/11 item 6: an unknown table no longer takes any BaseModel unchecked.

    `ledger_entry` is refused too: the ledger lives under runs/, and a part file
    under catalog/ledger_entry/ would never reach the ledger_entry view.
    """
    paths = StorePaths(root=tmp_path)
    record = Source(uri="https://example.com", sha256="3" * 64, downloaded_at="2026-11-03")
    with pytest.raises(ValueError, match="not a catalog table"):
        TableWriter(table, paths=paths)
    with pytest.raises(ValueError, match="not a catalog table"):
        write_record(table, record, paths=paths)
    assert not (paths.catalog_dir / table).exists()
