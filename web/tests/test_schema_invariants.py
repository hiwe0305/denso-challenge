"""Bất biến của schema kiểm được không cần Postgres (DESIGN.md §4).

Nghiệm thu thật của mốc M1 là chạy `schema.sql` trên PostgreSQL 16 và thử mỗi
luật một ca đúng một ca sai. Máy dev chưa có Postgres (§9.3), nên test này
kiểm phần kiểm được từ văn bản SQL, và nó bắt đúng loại lỗi hay xảy ra nhất
khi schema dài: một luật được ghi trong tài liệu mà không có dòng SQL nào
cưỡng chế, hoặc một bảng mới thêm vào mà quên ba cột chung của nhóm P.

Những gì test này **không** kiểm, và chỉ Postgres kiểm được: thân PL/pgSQL
của trigger, thứ tự khoá ngoại lúc chạy thật, và GRANT có hiệu lực hay không.
`sqlglot` phân tích `CREATE TABLE` và `CREATE VIEW` nhưng bỏ qua `DO $$` như
một khối mờ.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"

# Số bảng theo DESIGN.md §4.1, cộng `jobs` là hạ tầng hàng đợi (§3.1).
GROUP_W = {
    "app_users",
    "sync_runs",
    "human_actions",
    "job_requests",
    "dataset_intakes",
    "experiment_drafts",
    "notifications",
    "agent_chat_sessions",
    "agent_chat_messages",
}
GROUP_S = {"defect_manifests", "defect_items", "defect_bench_groups", "defect_scores"}
INFRASTRUCTURE = {"jobs"}

# Mọi mã ràng buộc tài liệu nói là được cưỡng chế bằng schema hoặc trigger.
# C15 và C16 nằm ở tầng API (compare-and-set, idempotency key), nên không có
# ở đây - và việc chúng vắng mặt là có chủ ý, không phải bỏ sót.
SCHEMA_CONSTRAINTS = (
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
    "C10", "C11", "C12", "C13", "C14", "C17", "C18", "C19",
)
API_ONLY_CONSTRAINTS = ("C15", "C16")


def _sql(name: str) -> str:
    return (SCHEMA_DIR / name).read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Bỏ comment `--` khỏi SQL.

    Cần thiết vì file schema giải thích nhiều: một comment nhắc tên cột đã bị
    bỏ sẽ làm test tưởng cột đó còn đó. Test phải đọc mã, không đọc văn.
    """
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


def _all_sql() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SCHEMA_DIR.glob("*.sql"))
        if path.name != "schema.sql"
    )


def _created_tables(text: str) -> list[str]:
    return re.findall(r"^CREATE TABLE (\w+)", text, re.MULTILINE)


def _created_views(text: str) -> list[str]:
    return re.findall(r"^CREATE VIEW (\w+)", text, re.MULTILINE)


def _p_table_list() -> list[str]:
    """Danh sách bảng P trong vòng thêm ba cột chung (30-group-p-ml.sql).

    Vòng đó cũng là định nghĩa "bảng nào thuộc nhóm P", nên nó là thứ test so
    với danh sách bảng thật.
    """
    text = _sql("30-group-p-ml.sql")
    block = re.search(r"p_tables TEXT\[\] := ARRAY\[(.*?)\];", text, re.DOTALL)
    assert block is not None, "không tìm thấy danh sách bảng P trong 30-group-p-ml.sql"
    return re.findall(r"'(\w+)'", block.group(1))


@pytest.fixture(scope="module")
def tables() -> list[str]:
    return _created_tables(_all_sql())


def test_the_schema_has_42_business_tables(tables: list[str]) -> None:
    business = [name for name in tables if name not in INFRASTRUCTURE]
    assert len(business) == 42, (
        f"có {len(business)} bảng nghiệp vụ, DESIGN.md §4.1 nói 42: "
        f"{sorted(business)}"
    )


def test_the_three_groups_add_up(tables: list[str]) -> None:
    p_tables = set(_p_table_list())
    assert len(GROUP_W) == 9
    assert len(p_tables) == 29, f"nhóm P có {len(p_tables)} bảng, §4.1 nói 29"
    assert len(GROUP_S) == 4
    # Không bảng nào nằm ở hai nhóm, và ba nhóm phủ hết bảng nghiệp vụ.
    assert not (GROUP_W & p_tables) and not (p_tables & GROUP_S)
    covered = GROUP_W | p_tables | GROUP_S | INFRASTRUCTURE
    assert set(tables) == covered, (
        f"bảng không thuộc nhóm nào: {sorted(set(tables) - covered)}; "
        f"khai mà không tạo: {sorted(covered - set(tables))}"
    )


def test_every_p_table_in_the_loop_is_really_created(tables: list[str]) -> None:
    # Một tên viết sai trong vòng sẽ làm `ALTER TABLE` nổ lúc chạy, nhưng ở
    # đây nó đỏ ngay.
    missing = [name for name in _p_table_list() if name not in tables]
    assert not missing, f"vòng thêm cột chung trỏ bảng không tồn tại: {missing}"


def test_group_s_tables_carry_the_common_columns_themselves() -> None:
    # Nhóm S không nằm trong vòng của nhóm P, nên ba cột chung phải viết tay.
    # Thiếu chúng thì FE không dán nhãn `mock` được trên bảng điểm M3.
    text = _code(_sql("50-group-s.sql"))
    for table in sorted(GROUP_S):
        body = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", text, re.DOTALL)
        assert body is not None, f"không tìm thấy {table}"
        for column in ("origin", "sync_run_id", "synced_at"):
            assert column in body.group(1), f"{table} thiếu cột `{column}`"


@pytest.mark.parametrize("code", SCHEMA_CONSTRAINTS)
def test_every_documented_constraint_appears_in_the_sql(code: str) -> None:
    # Bắt đúng loại lỗi khó thấy nhất: tài liệu nói một luật được cưỡng chế,
    # và không dòng SQL nào cưỡng chế nó.
    # Không phân biệt hoa thường: tài liệu viết `C12`, SQL viết
    # `CONSTRAINT c12_delete_reason`. Không dùng `\b` ở cuối vì `_` cũng là ký
    # tự từ, nên `\bc12\b` không khớp `c12_delete_reason`; lookahead chặn chữ
    # số để `C1` không khớp `c12_...`.
    assert re.search(rf"\b{code}(?![0-9])", _all_sql(), re.IGNORECASE), (
        f"luật {code} của DESIGN.md §4.5 không xuất hiện trong web/schema/"
    )


@pytest.mark.parametrize("code", API_ONLY_CONSTRAINTS)
def test_api_only_constraints_are_not_claimed_by_the_schema(code: str) -> None:
    # C15 và C16 là compare-and-set và idempotency key, làm ở tầng API. Một
    # `CONSTRAINT c15_...` trong schema nghĩa là ai đó hiểu sai chỗ cưỡng chế.
    assert not re.search(rf"CONSTRAINT {code.lower()}_", _all_sql())


def test_the_cost_ledger_is_append_only_in_two_layers() -> None:
    # Trigger một mình không đủ: chủ bảng tắt được trigger. Tài liệu nói
    # "trigger **và** REVOKE", nên test đòi cả hai.
    assert "c8_ledger_no_update" in _sql("60-constraints.sql")
    grants = _sql("80-grants.sql")
    assert "REVOKE UPDATE, DELETE ON cost_ledger_entries FROM fw_sync" in grants
    assert "REVOKE" in grants and "cost_ledger_entries" in grants


def test_the_api_role_cannot_write_any_projection_table() -> None:
    # Luật R1. GRANT chạy trong một vòng trên mọi bảng có `sync_run_id`, nên
    # một bảng P thêm sau này tự động bị khoá thay vì phải nhớ thêm vào danh
    # sách.
    grants = _sql("80-grants.sql")
    assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON %I FROM fw_api" in grants
    assert "GRANT SELECT ON %I TO fw_api" in grants


def test_the_agent_role_cannot_reach_the_answer_key() -> None:
    # Luật R8, và lý do nhóm S tồn tại.
    grants = _sql("80-grants.sql")
    assert "REVOKE ALL ON defect_manifests, defect_items FROM agent_ro" in grants
    # Agent chỉ được các view *_agent, không bảng thật.
    # `[^;]*?` để khớp không vượt quá một câu lệnh: `.*?` với DOTALL sẽ bắt
    # đầu từ một GRANT trước đó và kéo qua cả `%I` của vòng fw_api.
    agent_grant = re.search(r"GRANT SELECT ON\s+([^;]*?)\s*TO agent_ro;", grants)
    assert agent_grant is not None
    for name in re.findall(r"\w+", agent_grant.group(1)):
        assert name.endswith("_agent"), f"agent_ro được đọc `{name}`, không phải view *_agent"


def test_no_agent_view_joins_group_s() -> None:
    views = _code(_sql("70-views.sql"))
    for name in _created_views(views):
        if not name.endswith("_agent"):
            continue
        body = re.search(rf"CREATE VIEW {name} AS(.*?);", views, re.DOTALL)
        assert body is not None
        for secret in GROUP_S:
            assert secret not in body.group(1), f"view `{name}` join `{secret}`"


def test_episodes_carries_no_answer_key_column() -> None:
    # Bản 0.3, và chỗ sửa quan trọng nhất của nó: ở bản 0.2 `episodes` mang
    # `injected_defect`, mà agent đọc được episodes qua view, nên cách ly nhóm
    # S không có hiệu lực. 03 bản 1.0 bỏ trường đó; issue #62.
    data = _code(_sql("20-group-p-data.sql"))
    body = re.search(r"CREATE TABLE episodes \((.*?)\n\);", data, re.DOTALL)
    assert body is not None
    assert "injected_defect" not in body.group(1)
    assert "benchmark_copy_id VARCHAR(64)" in body.group(1)


def test_step_status_is_the_four_strings_not_small_ints() -> None:
    # Bản 0.3: khớp `StepStatus` của DA-36 (PR #58), issue #59.
    ml = _code(_sql("30-group-p-ml.sql"))
    body = re.search(r"CREATE TABLE eval_episodes \((.*?)\n\);", ml, re.DOTALL)
    assert body is not None
    assert "step_status TEXT[] NOT NULL" in body.group(1)
    assert "SMALLINT[]" not in body.group(1)
    assert "c18_step_status" in body.group(1)


def test_the_system_check_lives_in_its_own_table_with_a_skipped_list() -> None:
    # Bản 0.3: bốn cột phẳng của bản 0.2 không chở được "chưa chấm được".
    ml = _code(_sql("30-group-p-ml.sql"))
    system = re.search(r"CREATE TABLE system_diagnoses \((.*?)\n\);", ml, re.DOTALL)
    assert system is not None
    for column in ("findings", "skipped", "measurements"):
        assert column in system.group(1), f"system_diagnoses thiếu `{column}`"
    # C17 là CHECK làm cả bảng này có nghĩa: `clean` chỉ khi đã chấm hết.
    assert "c17_clean_is_measured" in system.group(1)
    # Bản 0.5 (PR #146): R1, R2 ghi nhận của rollout đồng bộ có cột riêng, và
    # C20 giữ ba luật validator của `SystemDiagnosis`.
    for column in ("timing", "recorded", "recorded_skipped"):
        assert re.search(rf"^\s*{column} ", system.group(1), re.MULTILINE), (
            f"system_diagnoses thiếu `{column}`"
        )
    for constraint in (
        "c20_recorded_only_on_sync",
        "c20_only_r1_r2_recorded",
        "c20_sync_does_not_count_r1_r2",
    ):
        assert constraint in system.group(1), f"system_diagnoses thiếu `{constraint}`"

    evals = re.search(r"CREATE TABLE eval_episodes \((.*?)\n\);", ml, re.DOTALL)
    assert evals is not None
    for moved in ("tracking_error", "latency_p99_ms", "sync_offset_ms"):
        assert moved not in evals.group(1), (
            f"`{moved}` còn trên eval_episodes; nó phải nằm trong "
            f"system_diagnoses.measurements (bản 0.3)"
        )


def test_train_diagnoses_has_somewhere_to_put_what_it_could_not_judge() -> None:
    # Cùng lý do như system_diagnoses.skipped: một checkpoint không có probe
    # P4 thì T7 không chấm được, không phải không quên (BR-12).
    tables = _created_tables(_sql("30-group-p-ml.sql"))
    assert "train_diagnosis_skips" in tables


def test_every_view_the_document_promises_exists() -> None:
    promised = {
        "v_pipeline_current", "v_dataset_report", "v_defect_detection",
        "v_eval_funnel", "v_system_check", "v_branch_comparison", "v_he_curve",
        "v_cluster_board", "v_cost_by_branch", "v_cost_by_intervention",
        "v_cost_data_allocation", "v_r_demo", "v_action_status", "v_sync_health",
    }
    created = set(_created_views(_all_sql()))
    assert promised <= created, f"thiếu view: {sorted(promised - created)}"


def test_the_driver_includes_every_schema_file() -> None:
    driver = _sql("schema.sql")
    for path in sorted(SCHEMA_DIR.glob("*.sql")):
        if path.name == "schema.sql":
            continue
        assert path.name in driver, f"schema.sql không \\i file `{path.name}`"
