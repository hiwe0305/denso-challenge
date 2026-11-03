"""Unit tests for append-only partition tables and concurrent writing (AC 5)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flywheel.contracts.entities import Condition
from flywheel.store.paths import StorePaths
from flywheel.store.tables import TableWriter, read_table_records


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
