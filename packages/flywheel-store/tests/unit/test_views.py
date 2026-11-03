"""Unit tests for DuckDB views auto-creation and index recovery (AC 6)."""

from pathlib import Path

from flywheel.contracts.entities import Condition, Decision, LedgerEntry, Score, Source
from flywheel.store.ledger_append import append_ledger_entry
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


def test_empty_store_views_have_fixed_columns(tmp_path: Path) -> None:
    """Feedback item 2: Empty store views have columns so specific queries succeed."""
    paths = StorePaths(root=tmp_path)
    con = open_duckdb(paths=paths)

    # All three queries from Hieu's review must succeed without BinderException
    res_ledger = con.execute("SELECT measure_kind FROM ledger_entry").fetchall()
    assert res_ledger == []

    res_decision = con.execute("SELECT verdict FROM decision").fetchall()
    assert res_decision == []

    res_episode = con.execute("SELECT id FROM episode").fetchall()
    assert res_episode == []

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

    query_cond = """
        SELECT condition_seed, level, layout_hash
        FROM condition
        ORDER BY condition_seed
    """

    # 2. Open DuckDB and verify query results
    con1 = open_duckdb(paths=paths)
    rows_cond1 = con1.execute(query_cond).fetchall()
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
    rows_cond2 = con2.execute(query_cond).fetchall()
    rows_src2 = con2.execute("SELECT uri, sha256 FROM source").fetchall()

    assert rows_cond2 == rows_cond1
    assert rows_src2 == rows_src1
    con2.close()


def test_score_written_twice_is_one_row(tmp_path: Path) -> None:
    """PO review 3/11 item 3: a re-run scorer on the same trace must not double-count."""
    paths = StorePaths(root=tmp_path)
    score = Score(
        episode_id="ep_1",
        task_id="two-table",
        config_sha256="d" * 64,
        trace_sha256="e" * 64,
        success=True,
    )
    TableWriter("score", paths=paths).append(score)
    TableWriter("score", paths=paths).append(score)  # second process, second part file
    other = Score(
        episode_id="ep_2",
        task_id="two-table",
        config_sha256="d" * 64,
        trace_sha256="f" * 64,
        success=False,
    )
    TableWriter("score", paths=paths).append(other)

    con = open_duckdb(paths=paths)
    assert con.execute("SELECT count(*), count(DISTINCT id) FROM score").fetchone() == (2, 2)
    successes = con.execute("SELECT count(*) FILTER (WHERE success::BOOLEAN) FROM score")
    assert successes.fetchone() == (1,)
    # The store itself stays append-only: both copies are still on disk.
    on_disk = [
        line
        for part in paths.table_dir("score").glob("part-*.jsonl")
        for line in part.read_text(encoding="utf-8").splitlines()
        if score.id in line
    ]
    assert len(on_disk) == 2
    con.close()


def test_event_written_twice_is_one_row(tmp_path: Path) -> None:
    """The same event id appended twice (a retried write) is one event, not two."""
    paths = StorePaths(root=tmp_path)
    decision = Decision(
        kind="dev_gate",
        subject_kind="checkpoint",
        subject_id="ckpt_1",
        signed_by="hieu",
        reason="dev gate",
    )
    writer = TableWriter("decision", paths=paths)
    writer.append(decision)
    writer.append(decision)

    entry = LedgerEntry(
        activity="eval",
        resource_type="gpu_hour_3060",
        quantity=1.0,
        unit="hour",
        usd_amount=0.2,
        measure_kind="estimated",
        run_plan_id="rp_1",
        job_id="job_1",
    )
    append_ledger_entry(entry, paths=paths)
    append_ledger_entry(entry, paths=paths)

    con = open_duckdb(paths=paths)
    assert con.execute("SELECT count(*) FROM decision").fetchone() == (1,)
    assert con.execute("SELECT count(*), sum(usd_amount) FROM ledger_entry").fetchone() == (1, 0.2)
    con.close()


def test_optional_fields_keep_their_sql_type(tmp_path: Path) -> None:
    """`X | None` columns are typed, so rates and sums need no string casts."""
    paths = StorePaths(root=tmp_path)
    writer = TableWriter("score", paths=paths)
    for episode, success, level in (("ep_1", True, 1), ("ep_2", False, 2)):
        writer.append(
            Score(
                episode_id=episode,
                task_id="two-table",
                config_sha256="d" * 64,
                trace_sha256=episode[-1] * 64,
                success=success,
                level=level,
                first_failed_step=None if success else 2,
            )
        )
    estimate = LedgerEntry(
        activity="eval",
        resource_type="gpu_hour_3060",
        quantity=1.0,
        unit="hour",
        usd_amount=0.2,
        measure_kind="estimated",
        run_plan_id="rp_1",
        job_id="job_1",
    )
    append_ledger_entry(estimate, paths=paths)

    con = open_duckdb(paths=paths)
    assert con.execute("SELECT avg(success::INT) FROM score").fetchone() == (0.5,)
    assert con.execute("SELECT max(level), max(first_failed_step) FROM score").fetchone() == (2, 2)
    assert con.execute("SELECT sum(usd_amount) FROM ledger_entry").fetchone() == (0.2,)
    types = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE score)").fetchall())
    assert types["success"] == "BOOLEAN"
    assert types["level"] == "BIGINT"
    assert types["first_failed_step"] == "BIGINT"
    con.close()
