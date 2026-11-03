"""Self-initializing DuckDB views over catalog partition files and runs ledger (03 §7.2, AC 6)."""

from __future__ import annotations

import typing
from collections.abc import Sequence
from typing import Any

import duckdb
from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Condition,
    Decision,
    Episode,
    FixRateEvent,
    LedgerEntry,
    QAReport,
    Release,
    RunPlan,
    Score,
    Source,
)
from flywheel.store.paths import StorePaths
from pydantic import BaseModel

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

TABLE_MODELS: dict[str, type[BaseModel]] = {
    "source": Source,
    "condition": Condition,
    "episode": Episode,
    "qa_report": QAReport,
    "release": Release,
    "checkpoint": Checkpoint,
    "run_plan": RunPlan,
    "score": Score,
    "cluster": Cluster,
    "fix_rate_event": FixRateEvent,
    "decision": Decision,
    "ledger_entry": LedgerEntry,
}


def _duckdb_type(annotation: Any) -> str:
    """Map python/pydantic field types to DuckDB SQL types."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _duckdb_type(non_none[0])
        return "VARCHAR"
    if origin is typing.Literal:
        first = args[0] if args else ""
        if isinstance(first, int):
            return "BIGINT"
        if isinstance(first, float):
            return "DOUBLE"
        if isinstance(first, bool):
            return "BOOLEAN"
        return "VARCHAR"
    if annotation in (str,):
        return "VARCHAR"
    if annotation in (int,):
        return "BIGINT"
    if annotation in (float,):
        return "DOUBLE"
    if annotation in (bool,):
        return "BOOLEAN"
    if origin in (list, dict, set) or hasattr(annotation, "model_fields"):
        return "JSON"
    return "VARCHAR"


def get_table_columns(table_name: str) -> dict[str, str]:
    """Return dictionary of column names to DuckDB types for a given table."""
    model = TABLE_MODELS.get(table_name)
    if model is None:
        return {"id": "VARCHAR"}
    cols: dict[str, str] = {
        fname: _duckdb_type(finfo.annotation)
        for fname, finfo in model.model_fields.items()
    }
    if "id" not in cols and hasattr(model, "id"):
        cols["id"] = "VARCHAR"
    return cols


# Episode and QAReport carry their own id field; `id` is only a property there.
ID_COLUMNS: dict[str, str] = {
    "episode": "COALESCE(id, episode_id)",
    "qa_report": "COALESCE(id, report_id)",
}


def _view_sql(table_name: str, pattern: str, id_expr: str) -> str:
    """One row per record id over every part file of a table.

    The store is append-only, so a record written twice (a scorer re-run on the
    same trace, a retried write) is on disk twice. An id names one record, so
    the view keeps the copy in the earliest part file and drops the rest; part
    files are named by ULID, so that is the first one written.
    """
    cols = get_table_columns(table_name)
    cols_dict_sql = "{" + ", ".join(f"'{k}': '{v}'" for k, v in cols.items()) + "}"
    return (
        f"CREATE OR REPLACE VIEW {table_name} AS "
        f"SELECT {id_expr} AS id, * EXCLUDE (id, filename) "
        f"FROM read_json('{pattern}', columns={cols_dict_sql}, union_by_name=true, "
        f"filename=true) "
        f"QUALIFY row_number() OVER (PARTITION BY {id_expr} ORDER BY filename) = 1"
    )


def init_views(con: duckdb.DuckDBPyConnection, paths: StorePaths) -> None:
    """Create or replace DuckDB views on catalog tables and runs ledger."""
    # 1. Catalog tables
    for table_name in CATALOG_TABLES:
        table_dir = paths.table_dir(table_name)
        table_dir.mkdir(parents=True, exist_ok=True)

        # Ensure at least one JSONL file exists so read_json glob pattern resolves
        jsonl_files = list(table_dir.glob("*.jsonl"))
        if not jsonl_files:
            init_file = table_dir / "part-00000000000000000000000000.jsonl"
            if not init_file.is_file():
                init_file.write_text("", encoding="utf-8")

        pattern = (table_dir / "*.jsonl").as_posix()
        con.execute(_view_sql(table_name, pattern, ID_COLUMNS.get(table_name, "id")))

    # 2. Cost ledger from runs/**/ledger*.jsonl
    runs_dir = paths.runs_dir
    runs_dir.mkdir(parents=True, exist_ok=True)
    ledger_files = list(runs_dir.glob("**/ledger*.jsonl"))
    if not ledger_files:
        init_ledger = runs_dir / ".init" / "ledger.jsonl"
        init_ledger.parent.mkdir(parents=True, exist_ok=True)
        if not init_ledger.is_file():
            init_ledger.write_text("", encoding="utf-8")

    ledger_pattern = (runs_dir / "**/ledger*.jsonl").as_posix()
    con.execute(_view_sql("ledger_entry", ledger_pattern, "id"))


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
