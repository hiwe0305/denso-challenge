"""Self-initializing DuckDB views over catalog partition files and runs ledger (03 §7.2, AC 6)."""

from __future__ import annotations

from collections.abc import Sequence

import duckdb
from flywheel.store.paths import StorePaths

CATALOG_TABLES: Sequence[str] = (
    "source",
    "condition",
    "episode",
    "qa_report",
    "release",
    "checkpoint",
    "run_plan",
    "score",
    "cluster",
    "fix_rate_event",
    "decision",
)


def init_views(con: duckdb.DuckDBPyConnection, paths: StorePaths) -> None:
    """Create or replace DuckDB views on catalog tables and runs ledger."""
    # 1. Catalog tables
    for table_name in CATALOG_TABLES:
        table_dir = paths.table_dir(table_name)
        table_dir.mkdir(parents=True, exist_ok=True)

        # Ensure at least one JSONL file exists so read_json pattern resolves
        jsonl_files = list(table_dir.glob("*.jsonl"))
        if not jsonl_files:
            init_file = table_dir / ".init.jsonl"
            if not init_file.is_file():
                init_file.write_text("", encoding="utf-8")

        pattern = (table_dir / "*.jsonl").as_posix()
        con.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS "
            f"SELECT * FROM read_json('{pattern}', union_by_name=true)"
        )

    # 2. Cost ledger from runs/**/ledger*.jsonl
    runs_dir = paths.runs_dir
    runs_dir.mkdir(parents=True, exist_ok=True)
    ledger_files = list(runs_dir.glob("**/ledger*.jsonl"))
    if not ledger_files:
        init_ledger = runs_dir / ".init" / ".init" / "ledger.jsonl"
        init_ledger.parent.mkdir(parents=True, exist_ok=True)
        if not init_ledger.is_file():
            init_ledger.write_text("", encoding="utf-8")

    ledger_pattern = (runs_dir / "**/ledger*.jsonl").as_posix()
    con.execute(
        "CREATE OR REPLACE VIEW ledger_entry AS "
        f"SELECT * FROM read_json('{ledger_pattern}', union_by_name=true)"
    )


def open_duckdb(
    paths: StorePaths | None = None,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Open index/fw.duckdb and auto-create all views upon opening."""
    if paths is None:
        paths = StorePaths()

    paths.index_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(paths.index_path), read_only=read_only)

    if not read_only:
        init_views(con, paths)

    return con
