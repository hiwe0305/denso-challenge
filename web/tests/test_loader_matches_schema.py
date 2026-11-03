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


# ---------------------------------------------------------------------------
# Đường nghiêm: cột do mapper của hợp đồng ghi ra
# ---------------------------------------------------------------------------
# `TOLERANT_COLUMNS` là một danh sách nên kiểm được tĩnh. Mapper nghiêm thì
# không có danh sách: cột của nó là khoá của dict nó trả về. Nên test chạy
# mapper trên file mẫu thật của testkit rồi kiểm từng khoá theo cùng quy ước.
# Đây là đúng chỗ bug cũ nằm: mapper đặt một mã chuỗi của lõi vào khoá
# `dataset_id` và `episode_id`, mà một cột `*_id` là UUID web tự sinh.


def _strict_rows() -> list[tuple[str, dict[str, object]]]:
    import json

    from web.fwsync.mapping import (
        DatasetLookup,
        map_defect_manifest,
        map_episode,
        map_probe_result,
        map_qa_report,
        map_train_diagnosis,
        map_training_metric,
    )

    fixtures = (
        Path(__file__).resolve().parents[2]
        / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
    )

    def load(name: str) -> dict[str, object]:
        return json.loads((fixtures / f"{name}.json").read_text(encoding="utf-8"))

    episode = load("Episode")
    episode["source_id"] = "src_1"
    rows: list[tuple[str, dict[str, object]]] = [
        ("episodes", map_episode(episode, DatasetLookup({"src_1": "ds"}, {}))),
        ("episode_qa_reports", map_qa_report(load("QAReport"), {"ep_1"})),
        (
            "training_metrics",
            map_training_metric(
                {
                    "run_plan_id": "rp_1", "job_id": "j", "checkpoint_id": "c",
                    "release_id": "r", "attempt": 0, "step": 1, "epoch": 0,
                    "split": "val", "loss": 0.5, "lr": 1e-4, "vlm_frozen": True,
                    "wall_time_s": 1.0,
                },
                "exp_A",
            ),
        ),
    ]
    diagnosis = map_train_diagnosis(
        {
            "checkpoint_id": "ckpt_1",
            "config_sha256": "a" * 64,
            "findings": [{"code": "T2", "start_step": 1, "value": 0.1, "threshold": 0.2}],
            "skipped": [{"code": "T7", "reason": "thiếu P4"}],
        },
        "exp_A",
    )
    rows += [(table, row) for table, table_rows in diagnosis.items() for row in table_rows]
    rows += [("probe_results", map_probe_result(load(f"ProbeP{i}"))) for i in (1, 2, 3, 4)]
    manifest = map_defect_manifest(load("DefectManifest"))
    rows.append(("defect_manifests", manifest["manifest"]))
    rows += [("defect_items", item) for item in manifest["items"]]
    return rows


@pytest.mark.parametrize("table,row", _strict_rows(), ids=lambda value: str(value)[:24])
def test_every_strict_mapper_column_has_a_place_in_the_table(
    table: str, row: dict[str, object], schema: dict[str, set[str]]
) -> None:
    homeless = sorted(column for column in row if not _resolves(column, schema[table]))
    assert not homeless, (
        f"mapper ghi {homeless} vào `{table}`, nhưng bảng không có cột đó và không "
        f"có cột `*_id` để tra ra"
    )


def _uuid_columns() -> dict[str, set[str]]:
    """Cột có kiểu UUID của mọi bảng: đó là ID web tự sinh, mapper không biết."""
    text = _code(
        "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SCHEMA_DIR.glob("*.sql"))
            if path.name != "schema.sql"
        )
    )
    tables: dict[str, set[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", text, re.DOTALL):
        tables[name] = {
            match.group(1)
            for line in body.splitlines()
            if (match := re.match(r"\s*(\w+)\s+UUID\b", line))
        }
    return tables


@pytest.mark.parametrize("table,row", _strict_rows(), ids=lambda value: str(value)[:24])
def test_no_strict_mapper_writes_into_a_uuid_column(
    table: str, row: dict[str, object]
) -> None:
    # Cột UUID là ID web tự sinh. Mapper không biết UUID đó, nên mọi khoá nó
    # ghi vào một cột UUID là một mã chuỗi của lõi đặt nhầm chỗ, đúng bug cũ
    # của `dataset_id` và `episode_id`. Quy tắc đọc kiểu cột từ schema thay vì
    # một danh sách ngoại lệ viết tay: `embodiment_id` và `condition_id` là
    # chuỗi của hợp đồng mang đuôi `_id`, và chúng là VARCHAR, nên tự qua.
    offenders = sorted(column for column in row if column in _uuid_columns()[table])
    assert not offenders, f"mapper của `{table}` ghi mã lõi vào cột UUID {offenders}"


#: Cột UUID mà bộ nạp được ghi, vì giá trị là UUID **của chính web** do lõi
#: chép lại nguyên văn khi trả lời một `human_actions` (W7). Mỗi dòng nói vì
#: sao; một cột không có ở đây mà nhận giá trị từ lõi là một mã chuỗi đặt nhầm
#: vào cột UUID.
ECHOED_WEB_UUIDS: dict[tuple[str, str], str] = {
    ("decisions", "source_action_id"): "id của human_actions mà quyết định này trả lời",
    ("decisions", "target_id"): "UUID bản ghi đích web đã gửi trong hành động",
}


@pytest.mark.parametrize("table", sorted(TOLERANT_COLUMNS))
def test_no_tolerant_column_lands_a_core_key_in_a_uuid_column(table: str) -> None:
    uuid = _uuid_columns().get(table, set())
    offenders = sorted(
        column
        for column in TOLERANT_COLUMNS[table]
        if column in uuid and (table, column) not in ECHOED_WEB_UUIDS
    )
    assert not offenders, (
        f"bộ nạp ghi {offenders} của `{table}` vào cột UUID; dùng `*_ref` để sink tra, "
        f"hoặc khai vào ECHOED_WEB_UUIDS nếu đó là UUID web được lõi chép lại"
    )


def test_echoed_web_uuids_are_declared_with_a_reason() -> None:
    assert all(reason.strip() for reason in ECHOED_WEB_UUIDS.values())
