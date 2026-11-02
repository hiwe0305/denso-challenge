"""Unit tests for DuckDB views auto-creation and index recovery (AC 6)."""

from pathlib import Path

from flywheel.contracts.entities import Condition, Source
from flywheel.store.paths import StorePaths
from flywheel.store.tables import TableWriter
from flywheel.store.views import CATALOG_TABLES, open_duckdb


def test_views_created_on_open_and_queryable(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    con = open_duckdb(paths=paths)

    # All catalog views exist
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    for tbl in CATALOG_TABLES:
        assert tbl in tables
    assert "ledger_entry" in tables

    # Querying empty view returns empty list without error
    res = con.execute("SELECT * FROM condition").fetchall()
    assert res == []
    con.close()


def test_views_reflect_data_and_persist_after_duckdb_deletion(tmp_path: Path) -> None:
    """AC 6: Delete fw.duckdb, reopen it, and obtain the exact same query results."""
    paths = StorePaths(root=tmp_path)

    # 1. Write some records to catalog tables
    cond_writer = TableWriter("condition", paths=paths)
    cond1 = Condition(condition_seed=101, layout_hash="1" * 64, level=1)
    cond2 = Condition(condition_seed=102, layout_hash="2" * 64, level=2)
    cond_writer.append(cond1)
    cond_writer.append(cond2)

    src_writer = TableWriter("source", paths=paths)
    src = Source(
        uri="https://example.com/dataset",
        sha256="3" * 64,
        downloaded_at="2026-11-02T10:00:00Z",
    )
    src_writer.append(src)

    # 2. Open DuckDB and verify query results
    con1 = open_duckdb(paths=paths)
    rows_cond1 = con1.execute("SELECT condition_seed, level, layout_hash FROM condition ORDER BY condition_seed").fetchall()
    rows_src1 = con1.execute("SELECT uri, sha256 FROM source").fetchall()

    assert len(rows_cond1) == 2
    assert rows_cond1[0] == (101, 1, "1" * 64)
    assert rows_cond1[1] == (102, 2, "2" * 64)
    assert len(rows_src1) == 1
    assert rows_src1[0] == ("https://example.com/dataset", "3" * 64)
    con1.close()

    # 3. Delete index/fw.duckdb completely
    assert paths.index_path.is_file()
    paths.index_path.unlink()
    assert not paths.index_path.is_file()

    # 4. Reopen DuckDB: views should auto-recreate and yield identical results
    con2 = open_duckdb(paths=paths)
    rows_cond2 = con2.execute("SELECT condition_seed, level, layout_hash FROM condition ORDER BY condition_seed").fetchall()
    rows_src2 = con2.execute("SELECT uri, sha256 FROM source").fetchall()

    assert rows_cond2 == rows_cond1
    assert rows_src2 == rows_src1
    con2.close()
