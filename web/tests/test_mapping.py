"""Tầng ánh xạ của `fwsync`: artifact của lõi → dòng bảng P (DESIGN.md §5.5).

Test chạy trên **file mẫu thật** của `flywheel.testkit`, không phải dict dựng
trong test: một mapper khớp dict tự viết nhưng lệch file mẫu là một mapper sẽ
đổ vỡ lúc nạp thật.

Ba nhóm ca quan trọng hơn cả, vì sai ở đó là sai âm thầm:

* Trường đáp án lỗi cấy **không được** đi sang nhóm P (luật R8).
* `dataset_id` mà hợp đồng không mang thì phải báo, không được gán lô mặc định.
* Giá trị không hữu hạn phải vào cột riêng, không nhét vào cột số.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from web.fwsync.mapping import (
    DROPPED_FIELDS,
    DatasetLookup,
    MappingError,
    map_defect_manifest,
    map_episode,
    map_probe_result,
    map_qa_report,
    map_train_diagnosis,
    map_training_metric,
)

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "flywheel-testkit"
    / "src"
    / "flywheel"
    / "testkit"
    / "fixtures"
)
ARTIFACTS = FIXTURES / "artifacts"

DATASET_ID = "11111111-1111-1111-1111-111111111111"
EXPERIMENT_ID = "22222222-2222-2222-2222-222222222222"


def _artifact(name: str) -> Any:
    return json.loads((ARTIFACTS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def lookup() -> DatasetLookup:
    return DatasetLookup(
        by_source={"src_1": DATASET_ID},
        by_intervention={"iv_1": DATASET_ID},
    )


# ---------------------------------------------------------------------------
# episodes
# ---------------------------------------------------------------------------


def test_the_shipped_episode_fixture_maps(lookup: DatasetLookup) -> None:
    payload = _artifact("Episode")
    payload["source_id"] = "src_1"

    row = map_episode(payload, lookup)

    assert row["episode_ref"] == "ep_1"
    assert row["dataset_id"] == DATASET_ID
    assert row["kind"] == "teleop_demo"
    assert row["source_detail"] == "psi_data"
    assert row["renderer"] == "mujoco"
    assert row["is_root"] is True


def test_the_answer_key_never_reaches_a_group_p_row(lookup: DatasetLookup) -> None:
    # Luật R8, và chỗ sửa quan trọng nhất của bản 0.3. File schema JSON còn
    # trường này, nên mapper phải bỏ nó chủ động; map nó vào `meta` sẽ đưa đáp
    # án vào một bảng mà agent_ro đọc được qua view.
    payload = _artifact("Episode")
    payload["source_id"] = "src_1"
    payload["meta"]["injected_defect"] = {"code": "D4", "parameters": {"dim": 31}}

    row = map_episode(payload, lookup)

    assert "injected_defect" not in row
    assert "injected_defect" not in row["meta"]
    assert "D4" not in json.dumps(row, default=str)
    # Và không suy ra `benchmark_copy_id` từ nó: suy như vậy bỏ sót đúng các
    # episode sạch của bản sao, mà C19 phải chặn cả chúng.
    assert row["benchmark_copy_id"] is None


def test_the_dropped_field_is_declared_with_a_reason() -> None:
    # Một trường bị bỏ âm thầm là một trường không ai review được.
    assert "EpisodeMetadata.injected_defect" in DROPPED_FIELDS
    assert "R8" in DROPPED_FIELDS["EpisodeMetadata.injected_defect"]


def test_an_episode_whose_dataset_cannot_be_resolved_is_refused(
    lookup: DatasetLookup,
) -> None:
    # `Episode` của hợp đồng không mang `dataset_id`. Gán một lô mặc định sẽ
    # làm sai báo cáo dataset, phân bổ chi phí và r_demo mà không gì báo.
    payload = _artifact("Episode")
    payload["source_id"] = None
    payload["intervention_id"] = None

    with pytest.raises(MappingError, match="không suy được `dataset_id`"):
        map_episode(payload, lookup)


def test_an_episode_resolves_through_its_intervention(lookup: DatasetLookup) -> None:
    payload = _artifact("Episode")
    payload["source_id"] = None
    payload["intervention_id"] = "iv_1"
    payload["kind"] = "teleop_correction"

    assert map_episode(payload, lookup)["dataset_id"] == DATASET_ID


def test_a_raw_egocentric_episode_with_a_split_is_refused(lookup: DatasetLookup) -> None:
    # C14 / BR-09 ở phía bộ nạp, nên sync_runs.errors nói rõ episode nào thay
    # vì cả lần nạp đổ vỡ ở trigger.
    payload = _artifact("Episode")
    payload["source_id"] = "src_1"
    payload["source_kind"] = "egocentric"
    payload["deid_status"] = "raw"
    payload["split"] = "train"

    with pytest.raises(MappingError, match="deid_status = raw"):
        map_episode(payload, lookup)


def test_a_raw_egocentric_episode_left_unassigned_is_fine(lookup: DatasetLookup) -> None:
    payload = _artifact("Episode")
    payload["source_id"] = "src_1"
    payload["source_kind"] = "egocentric"
    payload["deid_status"] = "raw"
    payload["split"] = "unassigned"

    assert map_episode(payload, lookup)["split"] == "unassigned"


def test_an_episode_that_is_not_an_episode_is_refused(lookup: DatasetLookup) -> None:
    with pytest.raises(MappingError, match="không hợp schema Episode"):
        map_episode({"episode_id": "ep_2"}, lookup)


# ---------------------------------------------------------------------------
# qa reports
# ---------------------------------------------------------------------------


def test_the_shipped_qa_report_fixture_maps() -> None:
    row = map_qa_report(_artifact("QAReport"), {"ep_1": "ep-uuid"})

    assert row["episode_id"] == "ep-uuid"
    assert row["decision"] == "pass"
    assert row["checks"][0]["name"] == "sync"


def test_a_qa_report_for_an_unknown_episode_is_refused() -> None:
    with pytest.raises(MappingError, match="chưa nạp"):
        map_qa_report(_artifact("QAReport"), {})


def test_a_non_pass_verdict_without_a_reason_is_refused() -> None:
    # Một quyết định `reject` không nói vì sao thì không ai sửa được.
    payload = _artifact("QAReport")
    payload["decision"] = "reject"
    payload["reasons"] = []

    with pytest.raises(MappingError, match="không có lý do"):
        map_qa_report(payload, {"ep_1": "ep-uuid"})


def test_the_invalid_qa_fixture_is_refused() -> None:
    # testkit ships một bản sai schema đúng để test chuyện này.
    payload = json.loads((ARTIFACTS / "invalid-QAReport.json").read_text(encoding="utf-8"))

    with pytest.raises(MappingError, match="không hợp schema QAReport"):
        map_qa_report(payload, {"ep_1": "ep-uuid"})


# ---------------------------------------------------------------------------
# training metrics
# ---------------------------------------------------------------------------


def _metric(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_plan_id": "rp_1",
        "job_id": "job_1",
        "checkpoint_id": "ckpt_1",
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
    base.update(overrides)
    return base


def test_a_training_metric_maps_both_splits() -> None:
    train = map_training_metric(_metric(split="train"), EXPERIMENT_ID)
    val = map_training_metric(_metric(split="val"), EXPERIMENT_ID)

    assert train["split"] == "train" and val["split"] == "val"
    # Một step có hai dòng; khoá của bảng gồm `split` nên cả hai vào được.
    assert train["step"] == val["step"] == 10


def test_a_loss_that_is_not_finite_goes_in_its_own_column() -> None:
    # Nhét NaN vào `loss` làm AVG() trả NaN và trắng cả biểu đồ của M5.
    row = map_training_metric(_metric(loss="NaN"), EXPERIMENT_ID)

    assert row["loss"] is None
    assert row["loss_nonfinite"] == "NaN"


def test_a_finite_loss_leaves_the_non_finite_column_empty() -> None:
    row = map_training_metric(_metric(loss=0.25), EXPERIMENT_ID)

    assert row["loss"] == pytest.approx(0.25)
    assert row["loss_nonfinite"] is None


def test_the_four_val_only_fields_survive_the_mapping() -> None:
    # Quyết định 3/11/2026 (issue #44): bốn trường này chỉ có trên dòng val.
    row = map_training_metric(
        _metric(
            split="val",
            loss_by_group={"arm": 0.3},
            pred_std=[0.1, 0.2],
            target_std=[0.2, 0.3],
            pred_var_by_dim=[0.01, 0.02],
        ),
        EXPERIMENT_ID,
    )

    assert row["loss_by_group"] == {"arm": 0.3}
    assert row["pred_std"] == [0.1, 0.2]
    assert row["target_std"] == [0.2, 0.3]
    assert row["pred_var_by_dim"] == [0.01, 0.02]


# ---------------------------------------------------------------------------
# train diagnoses
# ---------------------------------------------------------------------------


def test_a_train_diagnosis_maps_findings_and_skips_together() -> None:
    # Hai danh sách, không một: `findings` rỗng không mang được "không có gì
    # để chấm" (BR-12).
    payload = {
        "checkpoint_id": "ckpt_1",
        "config_sha256": "a" * 64,
        "findings": [
            {
                "code": "T1",
                "start_step": 100,
                "value": "NaN",
                "threshold": None,
                "stop_job": True,
            }
        ],
        "skipped": [{"code": "T7", "reason": "job không có kết quả probe P4"}],
    }

    rows = map_train_diagnosis(payload, EXPERIMENT_ID)

    assert len(rows["train_diagnoses"]) == 1
    finding = rows["train_diagnoses"][0]
    assert finding["code"] == "T1"
    assert finding["value"] is None and finding["value_nonfinite"] == "NaN"
    assert finding["stop_job"] is True
    assert rows["train_diagnosis_skips"] == [
        {
            "experiment_id": EXPERIMENT_ID,
            "checkpoint_ref": "ckpt_1",
            "config_sha256": "a" * 64,
            "code": "T7",
            "reason": "job không có kết quả probe P4",
        }
    ]


def test_a_clean_diagnosis_still_carries_what_it_could_not_judge() -> None:
    payload = {
        "checkpoint_id": "ckpt_1",
        "config_sha256": "a" * 64,
        "findings": [],
        "skipped": [{"code": "O1", "reason": "job không có kết quả probe P3"}],
    }

    rows = map_train_diagnosis(payload, EXPERIMENT_ID)

    assert rows["train_diagnoses"] == []
    assert len(rows["train_diagnosis_skips"]) == 1


# ---------------------------------------------------------------------------
# probes và defect manifest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["ProbeP1", "ProbeP2", "ProbeP3", "ProbeP4"])
def test_every_shipped_probe_fixture_maps(name: str) -> None:
    row = map_probe_result(_artifact(name))

    assert row["probe"] == name.removeprefix("Probe")
    assert row["checkpoint_ref"] == "ckpt_1"
    assert row["payload"]["probe"] == row["probe"]


def test_p4_carries_its_parent_checkpoint() -> None:
    # P4 là phép đo quên, nên nó vô nghĩa không có checkpoint cha để so.
    assert map_probe_result(_artifact("ProbeP4"))["parent_checkpoint_ref"] == "ckpt_0"


def test_a_probe_without_a_known_name_is_refused() -> None:
    with pytest.raises(MappingError, match="phải khai `probe`"):
        map_probe_result({"probe": "P9", "checkpoint_id": "ckpt_1"})


def test_the_shipped_defect_manifest_maps_into_group_s_only() -> None:
    rows = map_defect_manifest(_artifact("DefectManifest"))

    # `manifest_ref` là mã bản sao chấm: hợp đồng không cho manifest một ID
    # riêng, và đây cũng là giá trị `benchmark_copy_id` khi #62 merge.
    assert rows["manifest"] == {"manifest_ref": "ds_1", "dataset_ref": "ds_1", "seed": 5}
    assert rows["items"] == [
        {"target_ref": "ep_1", "code": "D1", "parameters": {"frame": 1}}
    ]
