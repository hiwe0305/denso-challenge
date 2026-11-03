"""Bốn việc của `fwsync` end-to-end trên sink JSONL (DESIGN.md §5.5).

Không cần Postgres: sink tách khỏi pipeline nên cùng một đường mã chạy được
trên `JsonlSink`. Cái test này **không** chứng minh được là CHECK, trigger và
quyền của schema chạy đúng — đó là nghiệm thu mốc M1 trên Postgres thật. Nó
chứng minh đường đọc → ánh xạ → ghi đúng, và đó là phần dễ sai nhất.

Ba tính chất quan trọng hơn cả:

* **Nạp lại cho cùng kết quả** (§5.5, idempotent). Không có nó thì cron 5 phút
  một lần sẽ nhân đôi dữ liệu.
* **Một dòng sai không làm đổ cả lần nạp.** Dòng xấu bị từ chối kèm lý do, các
  dòng khác vẫn vào.
* **Vòng ghi khép lại**: hành động → outbox → lõi giả → kết quả mang
  `source_action_id`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from web.fwsync.cli import app
from web.fwsync.runner import (
    IMPORT_ORDER,
    TOLERANT_COLUMNS,
    run_export,
    run_fake_core,
    run_import,
    run_verify,
)
from web.fwsync.sink import APPEND_ONLY, NATURAL_KEY, JsonlSink, PostgresSink
from web.fwsync.source import TOLERANT_TABLES, SourceError, scan, table_of

runner = CliRunner()

EPISODE: dict[str, Any] = {
    "episode_id": "ep_1",
    "kind": "teleop_demo",
    "operator_kind": "human",
    "is_root": True,
    "condition_id": "cond_1",
    "root_id": None,
    "parent_id": None,
    "source_id": "src_1",
    "intervention_id": None,
    "checkpoint_id": None,
    "rollout_seed": None,
    "sim_success": None,
    "infra_status": None,
    "camera_params_hash": None,
    "run_plan_id": "rp_1",
    "bundle_uri": "data/ep_1",
    "license": "example",
    "data_class": "public",
    "split": "train",
    "source_kind": "teleop",
    "action_quality": "measured",
    "deid_status": "verified",
    "embodiment_id": "g1_sonic_dwbc@1",
    "meta": {
        "source_detail": "psi_data",
        "renderer": "mujoco",
        "synthetic_tier": None,
        "injected_defect": None,
    },
}

DATASET: dict[str, Any] = {
    "dataset_code": "ds_psi_teleop",
    "source_ref": "src_1",
    "source_kind": "teleop",
    "data_class": "public",
    "license": "example",
    "status": "READY_FOR_TRAINING",
    "has_seeded_faults": False,
    "episode_count": 1,
}

QA_REPORT: dict[str, Any] = {
    "report_id": "qa_1",
    "episode_id": "ep_1",
    "threshold_version": "v1",
    "decision": "pass",
    "reasons": [],
    "checks": [{"name": "sync", "value": 0.01, "threshold": 0.1, "passed": True}],
}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Một thư mục nguồn nhỏ nhưng đủ nối: lô, episode, báo cáo QA."""
    folder = tmp_path / "src"
    _write_jsonl(folder / "datasets.jsonl", [DATASET])
    _write_jsonl(folder / "episodes.jsonl", [EPISODE])
    _write_jsonl(folder / "qa_reports.jsonl", [QA_REPORT])
    return folder


def _rows(sink_dir: Path, table: str) -> list[dict[str, Any]]:
    path = sink_dir / f"{table}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# ---------------------------------------------------------------------------
# nhận dạng file
# ---------------------------------------------------------------------------


def test_a_file_name_decides_its_table(tmp_path: Path) -> None:
    assert table_of(tmp_path / "episodes.jsonl") == "episodes"
    assert table_of(tmp_path / "qa_reports.jsonl") == "episode_qa_reports"
    assert table_of(tmp_path / "ledger.jsonl") == "cost_ledger_entries"


def test_a_catalog_part_file_is_named_by_its_folder(tmp_path: Path) -> None:
    # Lõi ghi `catalog/<bảng>/part-<ulid>.jsonl`, nên tên file một mình không
    # nói được nó thuộc bảng nào.
    assert table_of(tmp_path / "episodes" / "part-01.jsonl") == "episodes"


def test_an_unrecognised_file_is_ignored_not_fatal(source: Path) -> None:
    # Lõi còn thêm artifact mới; một file lạ không phải lý do để dừng.
    (source / "something_new.jsonl").write_text('{"a": 1}\n', encoding="utf-8")

    found = scan(source)

    assert "something_new.jsonl" in found.ignored
    assert "episodes" in found.tables


def test_a_source_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="không phải thư mục"):
        scan(tmp_path / "khong-co")


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


def test_import_loads_the_three_tables(source: Path, tmp_path: Path) -> None:
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_import(source, sink)

    assert result.status == "ok", result.errors
    assert _rows(sink.directory, "episodes")[0]["episode_ref"] == "ep_1"
    assert _rows(sink.directory, "datasets")[0]["dataset_code"] == "ds_psi_teleop"
    assert _rows(sink.directory, "episode_qa_reports")[0]["decision"] == "pass"


def test_importing_twice_gives_the_same_result(source: Path, tmp_path: Path) -> None:
    # §5.5: cron chạy 5 phút một lần, nên nạp lại phải upsert chứ không nhân
    # đôi. Bảng append-only là ngoại lệ có chủ ý, test dưới.
    first = JsonlSink(directory=tmp_path / "a")
    run_import(source, first)
    run_import(source, first)

    assert len(_rows(first.directory, "episodes")) == 1
    assert len(_rows(first.directory, "datasets")) == 1
    assert first.counts()["episodes"] == {
        "inserted": 1, "updated": 1, "rejected": 0, "unchanged": 0
    }


def test_reimporting_the_same_qa_report_does_not_duplicate_it(
    source: Path, tmp_path: Path
) -> None:
    # Cron chạy 5 phút một lần trên cùng artifact của lõi. Append-only nghĩa
    # là không sửa dòng đã ghi, không có nghĩa là chèn lại cùng báo cáo; bản
    # cũ của sink làm đúng điều sau và nhân đôi mọi báo cáo QA mỗi lần chạy.
    sink = JsonlSink(directory=tmp_path / "sink")
    run_import(source, sink)
    run_import(source, sink)

    assert "episode_qa_reports" in APPEND_ONLY
    assert len(_rows(sink.directory, "episode_qa_reports")) == 1
    assert sink.counts()["episode_qa_reports"]["unchanged"] == 1


def test_a_new_report_for_the_same_episode_is_a_second_row(
    source: Path, tmp_path: Path
) -> None:
    # Hai lần chấm là hai số đo vì chúng có hai `report_id`, không phải vì
    # cùng một báo cáo được nạp hai lần.
    sink = JsonlSink(directory=tmp_path / "sink")
    run_import(source, sink)
    _write_jsonl(
        source / "qa_reports.jsonl",
        [QA_REPORT, {**QA_REPORT, "report_id": "qa_2", "threshold_version": "v2"}],
    )
    run_import(source, sink)

    assert [row["report_ref"] for row in _rows(sink.directory, "episode_qa_reports")] == [
        "qa_1",
        "qa_2",
    ]


def test_one_bad_row_does_not_stop_the_import(source: Path, tmp_path: Path) -> None:
    # §2, lưới an toàn: dòng xấu bị từ chối kèm lý do, các dòng khác vẫn vào.
    _write_jsonl(
        source / "episodes.jsonl",
        [EPISODE, {**EPISODE, "episode_id": "ep_2", "kind": "khong-phai-kind"}],
    )
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_import(source, sink)

    assert result.status == "partial"
    assert len(_rows(sink.directory, "episodes")) == 1
    assert result.errors[0]["table"] == "episodes"
    assert "episodes.jsonl:2" == result.errors[0]["ref"]


def test_the_error_shape_matches_the_sync_runs_column(source: Path, tmp_path: Path) -> None:
    _write_jsonl(source / "episodes.jsonl", [{"episode_id": "ep_broken"}])

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert set(result.errors[0]) == {"table", "ref", "code", "message"}
    # `partial`, không phải `failed`: lô và báo cáo QA vẫn vào được, chỉ
    # episode bị từ chối. Ca `failed` là ca không nạp được gì, ở test dưới.
    assert result.as_sync_run()["status"] == "partial"


def test_an_import_with_nothing_loaded_is_failed_not_partial(
    source: Path, tmp_path: Path
) -> None:
    # Có lỗi mà vẫn báo `ok` là cách che mất dòng bị từ chối; CHECK của bảng
    # `sync_runs` cũng chặn, và `status` ở đây khớp nó.
    _write_jsonl(source / "datasets.jsonl", [])
    _write_jsonl(source / "episodes.jsonl", [{"episode_id": "x"}])
    _write_jsonl(source / "qa_reports.jsonl", [])

    assert run_import(source, JsonlSink(directory=tmp_path / "sink")).status == "failed"


def test_an_episode_whose_dataset_is_absent_is_refused(tmp_path: Path) -> None:
    # W12: `Episode` không mang `dataset_id`, nên nó được suy từ `datasets`
    # trong cùng thư mục. Không có lô nào trỏ `src_1` thì từ chối, không gán
    # lô mặc định.
    folder = tmp_path / "src"
    _write_jsonl(folder / "episodes.jsonl", [EPISODE])

    result = run_import(folder, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "failed"
    assert "không suy được `dataset_id`" in result.errors[0]["message"]


def test_the_answer_key_never_lands_in_the_sink(source: Path, tmp_path: Path) -> None:
    # Luật R8 end-to-end, không chỉ ở mapper.
    payload = {**EPISODE, "meta": {**EPISODE["meta"], "injected_defect": {"code": "D4"}}}
    _write_jsonl(source / "episodes.jsonl", [payload])
    sink = JsonlSink(directory=tmp_path / "sink")

    run_import(source, sink)

    written = (sink.directory / "episodes.jsonl").read_text(encoding="utf-8")
    assert "injected_defect" not in written
    assert "D4" not in written


def test_an_unknown_field_on_a_tolerant_table_is_dropped_and_reported(
    source: Path, tmp_path: Path
) -> None:
    # Phụ lục B đòi khoan dung với thực thể chưa có schema (S1-10 #36), nhưng
    # khoan dung mà im lặng thì không ai biết lõi đã thêm trường gì.
    _write_jsonl(source / "datasets.jsonl", [{**DATASET, "truong_moi_cua_loi": 7}])

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "ok", result.errors
    assert result.unknown_fields["datasets"] == ["truong_moi_cua_loi"]


def test_every_tolerant_table_declares_its_columns() -> None:
    # Một bảng ở đường khoan dung mà chưa khai cột được nhận sẽ từ chối mọi
    # dòng của nó; thà đỏ ở đây.
    missing = sorted(TOLERANT_TABLES - set(TOLERANT_COLUMNS))
    assert not missing, f"thiếu TOLERANT_COLUMNS cho {missing}"


def test_the_import_order_covers_every_table_the_reader_knows() -> None:
    from web.fwsync.source import FILE_TO_TABLE

    known = set(FILE_TO_TABLE.values())
    # `defect_items` và `train_diagnosis_skips` sinh ra từ mapper của bảng
    # khác, nên chúng không có file nguồn riêng.
    assert known - set(IMPORT_ORDER) == set()


def test_every_natural_key_belongs_to_a_table_the_loader_writes() -> None:
    writable = set(IMPORT_ORDER) | {"defect_items", "train_diagnosis_skips"}
    assert set(NATURAL_KEY) <= writable


# ---------------------------------------------------------------------------
# export và lõi giả
# ---------------------------------------------------------------------------


ACTION: dict[str, Any] = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "action_kind": "RECOMMENDATION_DECISION",
    "target_kind": "interventions",
    "target_id": "bbbbbbbb-0000-0000-0000-000000000002",
    "payload": {"items": [{"intervention_id": "iv_1", "decision": "APPROVE"}]},
    "reason": None,
}


def test_export_writes_one_artifact_carrying_the_action_id(tmp_path: Path) -> None:
    # W7: lõi phải chép `source_action_id` sang artifact kết quả, nếu không
    # `fwsync import` không biết hành động nào đã được áp dụng. Đây là chỗ
    # duy nhất trường đó được đặt.
    outbox = tmp_path / "outbox"

    result = run_export([ACTION], outbox)

    assert result.status == "ok"
    written = list(outbox.glob("*.json"))
    assert len(written) == 1
    artifact = json.loads(written[0].read_text(encoding="utf-8"))
    assert artifact["source_action_id"] == ACTION["id"]
    assert artifact["action_kind"] == "RECOMMENDATION_DECISION"


def test_an_action_without_an_id_is_refused(tmp_path: Path) -> None:
    result = run_export([{"action_kind": "STAGE_REVIEW"}], tmp_path / "outbox")

    assert result.status == "failed"
    assert "thiếu `id`" in result.errors[0]["message"]


def test_the_write_loop_closes_through_the_fake_core(tmp_path: Path) -> None:
    # Nghiệm thu mốc M4 khi lõi thật chưa sẵn sàng: bấm duyệt → outbox → lõi
    # giả → kết quả mang `source_action_id`.
    outbox = tmp_path / "outbox"
    inbox = tmp_path / "inbox"
    run_export([ACTION], outbox)

    result = run_fake_core(outbox, inbox)

    assert result.status == "ok", result.errors
    replies = list(inbox.glob("*.jsonl"))
    assert len(replies) == 1
    reply = json.loads(replies[0].read_text(encoding="utf-8"))
    assert reply["source_action_id"] == ACTION["id"]
    assert reply["kind"] == "plan_review"


def test_the_fake_core_says_what_it_cannot_answer(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "x.json").write_text(
        json.dumps({"source_action_id": "a", "action_kind": "SOFT_DELETE"}), encoding="utf-8"
    )

    result = run_fake_core(outbox, tmp_path / "inbox")

    assert result.status == "failed"
    assert "chưa trả lời" in result.errors[0]["message"]


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def test_verify_reports_a_mismatch_and_does_not_fix_it(source: Path) -> None:
    # §9.4: không bao giờ sửa số trong DB bằng tay. verify báo, người sửa bộ
    # nạp.
    result = run_verify(source, {"episodes": 0, "datasets": 1, "episode_qa_reports": 1})

    assert result.status == "partial"
    mismatch = next(error for error in result.errors if error["table"] == "episodes")
    assert "nguồn có 1 dòng, đã nạp 0" in mismatch["message"]


def test_verify_is_quiet_when_the_counts_agree(source: Path) -> None:
    result = run_verify(source, {"episodes": 1, "datasets": 1, "episode_qa_reports": 1})

    assert result.status == "ok"
    assert result.errors == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_the_cli_imports_and_exits_zero(source: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["import", "--from", str(source), "--out", str(tmp_path / "sink")]
    )

    assert result.exit_code == 0, result.output
    assert "trạng thái: ok" in result.output


def test_the_cli_exits_one_on_a_partial_import(source: Path, tmp_path: Path) -> None:
    # Thoát 0 khi có dòng bị từ chối là cách để lỗi đó không ai thấy trong cron.
    _write_jsonl(source / "episodes.jsonl", [EPISODE, {"episode_id": "ep_broken"}])

    result = runner.invoke(
        app, ["import", "--from", str(source), "--out", str(tmp_path / "sink")]
    )

    assert result.exit_code == 1
    assert "từ chối" in result.output


def test_the_cli_exits_two_when_the_source_is_not_there(tmp_path: Path) -> None:
    result = runner.invoke(app, ["import", "--from", str(tmp_path / "khong-co")])

    assert result.exit_code == 2
    assert "không nạp được" in result.output
    assert "Traceback" not in result.output


def test_the_postgres_sink_says_what_is_missing() -> None:
    # Thay vì một ModuleNotFoundError, nó nói đủ ba thứ còn thiếu.
    with pytest.raises(NotImplementedError, match="PostgreSQL 16"):
        PostgresSink(dsn="postgresql:///flywheel_web")


def test_the_cli_reports_the_postgres_sink_without_a_traceback(
    source: Path, tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        ["import", "--from", str(source), "--sink", "postgres", "--dsn", "postgresql:///x"],
    )

    assert result.exit_code == 2
    assert "sink chưa dựng" in result.output
    assert "Traceback" not in result.output


def test_a_second_import_in_a_new_process_still_upserts(source: Path, tmp_path: Path) -> None:
    # Số đếm phải trung thực: `JsonlSink` đọc lại dòng đã ghi lần trước, nên
    # lần nạp thứ hai báo `updated` đúng như Postgres sẽ báo. Không đọc lại
    # thì hai sink kể hai câu chuyện khác nhau về cùng một lần nạp.
    out = tmp_path / "sink"
    run_import(source, JsonlSink(directory=out))

    second = JsonlSink(directory=out)
    run_import(source, second)

    assert second.counts()["episodes"] == {
        "inserted": 0, "updated": 1, "rejected": 0, "unchanged": 0
    }
    assert len(_rows(out, "episodes")) == 1


def test_an_append_only_table_does_not_grow_across_processes(
    source: Path, tmp_path: Path
) -> None:
    out = tmp_path / "sink"
    run_import(source, JsonlSink(directory=out))
    run_import(source, JsonlSink(directory=out))

    assert len(_rows(out, "episode_qa_reports")) == 1


LEDGER_ENTRY: dict[str, Any] = {
    "entry_ref": "led_1",
    "entry_kind": "ENTRY",
    "activity": "teleop",
    "resource_type": "operator_minutes",
    "quantity": 30,
    "unit": "minute",
    "price_book_name": "pitch_v10",
    "measured_usd": 25.0,
    "dataset_code": "ds_psi_teleop",
}


def test_a_ledger_entry_is_never_updated_by_a_reimport(source: Path, tmp_path: Path) -> None:
    # R4: sổ chi phí chỉ được thêm, sửa sai bằng bút toán đảo. Bản cũ của
    # sink upsert bảng này theo `entry_ref`, nên một artifact nạp lại với số
    # khác sẽ âm thầm ghi đè số đã báo.
    _write_jsonl(source / "ledger.jsonl", [LEDGER_ENTRY])
    sink = JsonlSink(directory=tmp_path / "sink")
    run_import(source, sink)
    _write_jsonl(source / "ledger.jsonl", [{**LEDGER_ENTRY, "measured_usd": 999.0}])
    run_import(source, sink)

    rows = _rows(sink.directory, "cost_ledger_entries")
    assert len(rows) == 1
    assert rows[0]["measured_usd"] == 25.0
    assert sink.counts()["cost_ledger_entries"]["updated"] == 0


def test_every_table_the_loader_writes_has_a_natural_key() -> None:
    # Không có khoá thì không phân biệt được "đã nạp" với "mới", và cron 5
    # phút nhân đôi bảng đó. Bảng append-only cũng không được miễn.
    writable = set(IMPORT_ORDER) | {"defect_items", "train_diagnosis_skips"}
    missing = sorted(writable - set(NATURAL_KEY))
    assert not missing, f"thiếu NATURAL_KEY cho {missing}"
    assert APPEND_ONLY <= set(NATURAL_KEY)


# ---------------------------------------------------------------------------
# telemetry và chẩn đoán train qua runner
# ---------------------------------------------------------------------------
# Bug đã có: runner đòi `experiment_code` trên payload, còn `TrainingMetric`
# của hợp đồng cấm trường lạ, nên MỌI dòng telemetry bị từ chối. Các test dưới
# đưa artifact đúng y hợp đồng, không thêm trường nào, và đòi nó vào được.

METRIC: dict[str, Any] = {
    "run_plan_id": "rp_A",
    "job_id": "job_1",
    "checkpoint_id": "ckpt_A",
    "release_id": "rel_1",
    "attempt": 0,
    "step": 10,
    "epoch": 0,
    "split": "train",
    "loss": 0.5,
    "lr": 1e-4,
    "vlm_frozen": True,
    "wall_time_s": 1.0,
}


@pytest.fixture
def training_source(tmp_path: Path) -> Path:
    folder = tmp_path / "train-src"
    _write_jsonl(
        folder / "experiments.jsonl",
        [{"experiment_code": "exp_A", "run_plan_ref": "rp_A", "task_id": "two_table",
          "branch": "A", "method": "PSI0"}],
    )
    _write_jsonl(
        folder / "checkpoints.jsonl",
        [{"checkpoint_ref": "ckpt_A", "experiment_code": "exp_A", "method": "PSI0",
          "weights_sha256": "b" * 64, "uri": "runs/a", "is_best": True, "is_latest": True}],
    )
    _write_jsonl(
        folder / "training_metrics.jsonl",
        [METRIC, {**METRIC, "split": "val", "loss": "NaN"}],
    )
    _write_jsonl(
        folder / "train_diagnoses.jsonl",
        [{"checkpoint_id": "ckpt_A", "config_sha256": "a" * 64,
          "findings": [{"code": "T1", "start_step": 10, "value": "NaN", "stop_job": True}],
          "skipped": [{"code": "T7", "reason": "job không có kết quả probe P4"}]}],
    )
    return folder


def test_contract_exact_telemetry_loads_through_the_runner(
    training_source: Path, tmp_path: Path
) -> None:
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_import(training_source, sink)

    assert result.status == "ok", result.errors
    metrics = _rows(sink.directory, "training_metrics")
    assert [row["experiment_code"] for row in metrics] == ["exp_A", "exp_A"]
    assert metrics[1]["loss"] is None and metrics[1]["loss_nonfinite"] == "NaN"


def test_a_train_diagnosis_finds_its_experiment_through_the_checkpoint(
    training_source: Path, tmp_path: Path
) -> None:
    sink = JsonlSink(directory=tmp_path / "sink")

    run_import(training_source, sink)

    assert _rows(sink.directory, "train_diagnoses")[0]["experiment_code"] == "exp_A"
    assert _rows(sink.directory, "train_diagnosis_skips")[0]["code"] == "T7"


def test_telemetry_for_an_unknown_run_plan_is_refused(
    training_source: Path, tmp_path: Path
) -> None:
    # Giống W12: tra không ra thì từ chối, không gán vào thí nghiệm mặc định.
    _write_jsonl(
        training_source / "training_metrics.jsonl",
        [{**METRIC, "run_plan_id": "rp_khong_co", "checkpoint_id": "ckpt_khong_co"}],
    )

    result = run_import(training_source, JsonlSink(directory=tmp_path / "sink"))

    assert "không suy được thí nghiệm" in result.errors[0]["message"]


def test_every_row_carries_the_origin_of_its_source(source: Path, tmp_path: Path) -> None:
    # `origin` là thuộc tính của nguồn: FE dán nhãn "mock" theo nó (§4.4b).
    sink = JsonlSink(directory=tmp_path / "sink")

    run_import(source, sink, origin="mock")

    for table in ("datasets", "episodes", "episode_qa_reports"):
        assert {row["origin"] for row in _rows(sink.directory, table)} == {"mock"}


def test_an_artifact_cannot_relabel_itself_as_mock(source: Path, tmp_path: Path) -> None:
    # Một artifact thật lỡ mang `origin: mock` không được làm FE dán nhãn sai:
    # đường khoan dung bỏ trường đó, và runner đóng dấu theo nguồn.
    _write_jsonl(source / "datasets.jsonl", [{**DATASET, "origin": "mock"}])
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_import(source, sink, origin="core")

    assert _rows(sink.directory, "datasets")[0]["origin"] == "core"
    assert result.unknown_fields["datasets"] == ["origin"]


def test_an_unknown_origin_is_refused(source: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="origin"):
        run_import(source, JsonlSink(directory=tmp_path / "sink"), origin="test")
