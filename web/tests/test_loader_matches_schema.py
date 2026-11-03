"""Cột bộ nạp ghi ra phải có chỗ đứng trong schema (DESIGN.md §3.2).

Bộ nạp khai cột được nhận trong `TOLERANT_COLUMNS` thay vì đọc từ
`schema.sql`, vì nó phải chạy được khi chưa có database. Hai danh sách viết
tay ở hai chỗ thì lệch nhau đúng lúc không ai nhìn: lõi đặt tên một trường,
bộ nạp nhận nó, và `PostgresSink` sẽ chết lúc chèn vì bảng không có cột đó.
Test này là chỗ báo.

Quy ước nối hai bên, viết ra một lần ở đây:

* Cột trùng tên với một cột của bảng: ghi thẳng.
* Cột `X_ref`, `X_code` hoặc `X_name`: là **khoá tự nhiên của lõi** trỏ sang
  bảng khác. Sink tra nó ra UUID và ghi vào cột `X_id`, nên bảng phải có
  `X_id`. Artifact của lõi không biết UUID mà web tự sinh, nên đây là cách
  duy nhất để nối.
* Cột nằm trong `LOOKUP_ONLY`: bộ nạp đọc để dựng bảng tra rồi bỏ, không ghi.

Cộng một chiều ngược lại: bảng nào có cột `X_ref` khác ở đâu đó trỏ vào thì
chính nó phải có cột `X_ref` làm khoá tự nhiên, nếu không thì không tra được.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from web.fwsync.runner import TOLERANT_COLUMNS
from web.fwsync.sink import NATURAL_KEY

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"

#: Cột bộ nạp đọc nhưng không ghi. Mỗi dòng phải nói vì sao.
LOOKUP_ONLY: dict[tuple[str, str], str] = {
    # W12: `Episode` không mang `dataset_id`, nên bảng tra lô dựng từ can
    # thiệp. Cột này không thuộc bảng `interventions`.
    ("interventions", "dataset_code"): "dựng bảng tra dataset_id của W12",
}

_NOT_COLUMNS = {"CONSTRAINT", "CHECK", "UNIQUE", "PRIMARY", "FOREIGN", "EXCLUDE"}
_REF_SUFFIXES = ("_ref", "_code", "_name")


def _code(text: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


def _columns() -> dict[str, set[str]]:
    """Cột của mọi bảng, đọc từ `CREATE TABLE` cộng mọi `ADD COLUMN`."""
    text = _code(
        "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SCHEMA_DIR.glob("*.sql"))
            if path.name != "schema.sql"
        )
    )
    tables: dict[str, set[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", text, re.DOTALL):
        columns = set()
        for line in body.splitlines():
            match = re.match(r"\s*(\w+)\s+\S", line)
            if match and match.group(1).upper() not in _NOT_COLUMNS:
                columns.add(match.group(1))
        tables[name] = columns
    # Ba cột chung của nhóm P được thêm bằng một vòng, nên không có trong
    # thân CREATE TABLE.
    for columns in tables.values():
        columns |= {"origin", "sync_run_id", "synced_at"}
    return tables


@pytest.fixture(scope="module")
def schema() -> dict[str, set[str]]:
    return _columns()


def _resolves(column: str, table_columns: set[str]) -> bool:
    if column in table_columns:
        return True
    for suffix in _REF_SUFFIXES:
        if column.endswith(suffix):
            return column.removesuffix(suffix) + "_id" in table_columns
    return False


@pytest.mark.parametrize("table", sorted(TOLERANT_COLUMNS))
def test_every_loader_column_has_a_place_in_the_table(
    table: str, schema: dict[str, set[str]]
) -> None:
    assert table in schema, f"bảng `{table}` không có trong web/schema/"
    homeless = sorted(
        column
        for column in TOLERANT_COLUMNS[table]
        if (table, column) not in LOOKUP_ONLY and not _resolves(column, schema[table])
    )
    assert not homeless, (
        f"bộ nạp ghi {homeless} vào `{table}`, nhưng bảng không có cột đó và "
        f"không có cột `*_id` để tra ra"
    )


def _referenced_keys() -> dict[str, set[str]]:
    """Khoá tự nhiên nào được trỏ tới, theo tên: `checkpoint_ref` → `checkpoint`."""
    wanted: dict[str, set[str]] = {}
    for table, columns in TOLERANT_COLUMNS.items():
        for column in columns:
            if column.endswith("_ref") and (table, column) not in LOOKUP_ONLY:
                wanted.setdefault(column, set()).add(table)
    return wanted


#: Khoá tự nhiên `X_ref` → (bảng giữ nó, cột khoá trên bảng đó). Khai tường
#: minh thay vì suy từ tên: `representative_episode_ref` trỏ về
#: `eval_episodes.eval_episode_ref`, không phải `episodes.episode_ref`, và một
#: phép suy theo tên sẽ chọn sai bảng mà không báo.
REF_OWNER: dict[str, tuple[str, str]] = {
    "source_ref": ("sources", "source_ref"),
    "base_source_ref": ("sources", "source_ref"),
    "release_ref": ("releases", "release_ref"),
    "parent_release_ref": ("releases", "release_ref"),
    "episode_ref": ("episodes", "episode_ref"),
    "run_plan_ref": ("run_plans", "run_plan_ref"),
    "checkpoint_ref": ("model_checkpoints", "checkpoint_ref"),
    "parent_checkpoint_ref": ("model_checkpoints", "checkpoint_ref"),
    "evaluation_ref": ("sim_evaluations", "evaluation_ref"),
    "eval_episode_ref": ("eval_episodes", "eval_episode_ref"),
    "representative_episode_ref": ("eval_episodes", "eval_episode_ref"),
    "recommendation_ref": ("flywheel_recommendations", "recommendation_ref"),
    "cluster_ref": ("failure_clusters", "cluster_ref"),
    "parent_cluster_ref": ("failure_clusters", "cluster_ref"),
    "intervention_ref": ("interventions", "intervention_ref"),
    "decision_ref": ("decisions", "decision_ref"),
    "entry_ref": ("cost_ledger_entries", "entry_ref"),
    "reverses_entry_ref": ("cost_ledger_entries", "entry_ref"),
    "manifest_ref": ("defect_manifests", "manifest_ref"),
}


def test_every_ref_the_loader_writes_has_a_known_owner() -> None:
    unknown = sorted(set(_referenced_keys()) - set(REF_OWNER))
    assert not unknown, f"không biết tra {unknown} ở bảng nào; thêm vào REF_OWNER"


@pytest.mark.parametrize("ref", sorted(REF_OWNER))
def test_every_referenced_table_can_be_looked_up_by_its_ref(
    ref: str, schema: dict[str, set[str]]
) -> None:
    # Chiều ngược: `interventions.cluster_ref` chỉ tra được nếu
    # `failure_clusters` có một cột khoá tự nhiên để tra. Một khoá ghép
    # nhiều cột không đủ: artifact trỏ sang chỉ mang một chuỗi.
    owner, key = REF_OWNER[ref]
    assert key in schema[owner], (
        f"`{ref}` trỏ sang `{owner}`, nhưng `{owner}` không có cột `{key}` để tra"
    )


@pytest.mark.parametrize("ref", sorted(REF_OWNER))
def test_the_sink_upserts_each_owner_on_that_same_key(ref: str) -> None:
    # Bảng được tra bằng `X_ref` thì cũng phải được upsert bằng đúng khoá đó,
    # nếu không nạp lại sẽ sinh dòng thứ hai mang cùng ref.
    owner, key = REF_OWNER[ref]
    assert NATURAL_KEY.get(owner) == (key,), (
        f"NATURAL_KEY của `{owner}` là {NATURAL_KEY.get(owner)}, phải là ({key!r},)"
    )


def test_lookup_only_columns_are_declared_with_a_reason() -> None:
    assert all(reason.strip() for reason in LOOKUP_ONLY.values())
