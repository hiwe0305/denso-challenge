"""Bộ mock `mock/demo-17-11/` (DESIGN.md Phụ lục C).

Bộ mock là thứ FE và bộ nạp chạy trên đó suốt tới khi lõi sinh dữ liệu thật,
nên nó phải tuân đúng những luật mà dữ liệu thật phải tuân. Một bộ mock có
episode egocentric còn raw nằm trong release, hay một cụm có `member_count`
không khớp số episode lỗi, sẽ dạy FE vẽ sai mà không ai biết.

Ba nhóm kiểm:

* **Khớp generator.** File trên đĩa đúng từng byte với bản sinh lại.
* **Nạp sạch, nạp lại không đổi gì.** Không dòng bị từ chối, không trường lạ;
  lần nạp thứ hai không chèn gì mới.
* **Bất biến của câu chuyện và của schema.** C14, C17, C9, C10, C11, R8, và
  các con số mà demo sẽ nói thành lời: bốn cụm bốn chẩn đoán, hai cụm tiêu
  ngân sách, code bắt 6/10 agent bắt thêm 2.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from web.contracts.enums import CONTRACT, SPEC
from web.fwsync.runner import run_import
from web.fwsync.sink import APPEND_ONLY, JsonlSink
from web.mock.generate import OUT, render

DEV_SIZE = 90
TWO_TABLE_STEPS = 6  # spec §5.1


def _load(name: str) -> Any:
    text = (OUT / name).read_text(encoding="utf-8")
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line]
    return json.loads(text)


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    return {
        path.name: _load(path.name)
        for path in OUT.iterdir()
        if path.suffix in (".json", ".jsonl")
    }


# ---------------------------------------------------------------------------
# khớp generator
# ---------------------------------------------------------------------------


def test_the_committed_mock_matches_the_generator() -> None:
    rendered = render()
    on_disk = {
        path.name: path.read_text(encoding="utf-8") for path in OUT.iterdir() if path.is_file()
    }
    assert set(on_disk) == set(rendered), (
        "thư mục mock lệch danh sách file; chạy `uv run python -m web.mock.generate`"
    )
    stale = sorted(name for name in rendered if on_disk[name] != rendered[name])
    assert not stale, f"{stale} lệch generator; chạy `uv run python -m web.mock.generate`"


def test_the_generator_is_deterministic() -> None:
    # Một seed, không đồng hồ, không `hash()` của Python: chạy lại đúng từng byte.
    assert render() == render()


def test_the_readme_says_this_is_not_measured_data() -> None:
    readme = (OUT / "README.md").read_text(encoding="utf-8")
    assert "không phải số đo" in readme
    assert "--origin mock" in readme


# ---------------------------------------------------------------------------
# nạp
# ---------------------------------------------------------------------------


def test_the_mock_imports_with_no_rejection_and_no_unknown_field(tmp_path: Path) -> None:
    result = run_import(OUT, JsonlSink(directory=tmp_path / "sink"), origin="mock")

    assert result.status == "ok", result.errors[:3]
    assert result.unknown_fields == {}
    assert result.ignored == []


def test_every_loaded_row_is_labelled_mock(tmp_path: Path) -> None:
    sink = JsonlSink(directory=tmp_path / "sink")
    run_import(OUT, sink, origin="mock")

    origins = {row["origin"] for rows in sink.rows.values() for row in rows}
    assert origins == {"mock"}


def test_reimporting_the_mock_inserts_nothing(tmp_path: Path) -> None:
    out = tmp_path / "sink"
    run_import(OUT, JsonlSink(directory=out), origin="mock")
    second = JsonlSink(directory=out)
    run_import(OUT, second, origin="mock")

    for table, counts in second.counts().items():
        assert counts["inserted"] == 0, f"`{table}` chèn thêm {counts['inserted']} dòng khi nạp lại"
        assert counts["rejected"] == 0
        if table in APPEND_ONLY:
            assert counts["updated"] == 0, f"bảng append-only `{table}` bị sửa"


# ---------------------------------------------------------------------------
# episode, QA, release
# ---------------------------------------------------------------------------


def test_every_enum_value_is_one_the_web_knows(data: dict[str, Any]) -> None:
    for episode in data["episodes.jsonl"]:
        assert episode["kind"] in CONTRACT["episode_kind"]
        assert episode["source_kind"] in CONTRACT["source_kind"]
        assert episode["deid_status"] in CONTRACT["deid_status"]
        assert episode["split"] in SPEC["split"]
    for row in data["eval_episodes.jsonl"]:
        assert set(row["step_status"]) <= set(SPEC["step_status"])
        assert len(row["step_status"]) == TWO_TABLE_STEPS
        assert row["infra_status"] in CONTRACT["infra_status"]
        if row["failure_code"]:
            assert row["failure_code"] in SPEC["failure_code_two_table"]
    for row in data["system_diagnoses.jsonl"]:
        assert row["diagnosis"] in SPEC["system_diagnosis"]
    for row in data["failure_clusters.jsonl"]:
        assert row["diagnosis"] in SPEC["cluster_diagnosis"]
    for row in data["experiments.jsonl"]:
        assert row["branch"] in SPEC["branch_two_table"]


def test_only_human_robot_demos_are_roots(data: dict[str, Any]) -> None:
    # `r_demo` của M8 đếm đúng cờ này; một episode máy sinh hay một video
    # egocentric mang is_root sẽ làm sai chỉ số chính của bài toán kinh tế.
    for episode in data["episodes.jsonl"]:
        if episode["is_root"]:
            assert episode["operator_kind"] == "human"
            assert episode["kind"] in ("teleop_demo", "teleop_correction", "recovery")
            assert episode["source_kind"] != "egocentric"


def test_raw_egocentric_never_leaves_annotate(data: dict[str, Any]) -> None:
    # C14 / BR-09.
    raw = {
        e["episode_id"]
        for e in data["episodes.jsonl"]
        if e["source_kind"] == "egocentric" and e["deid_status"] == "raw"
    }
    assert raw, "bộ mock phải có ca egocentric raw để M2 vẽ được khoá"
    assert all(
        e["split"] == "unassigned" for e in data["episodes.jsonl"] if e["episode_id"] in raw
    )
    assert not raw & {item["episode_ref"] for item in data["release_items.jsonl"]}
    assert not raw & {report["episode_id"] for report in data["qa_reports.jsonl"]}


def test_no_benchmark_copy_episode_enters_a_release(data: dict[str, Any]) -> None:
    # C19 / BR-08.
    bench = {
        e["episode_id"] for e in data["episodes.jsonl"] if e["source_id"] == "src_bench_kbd"
    }
    assert not bench & {item["episode_ref"] for item in data["release_items.jsonl"]}


def test_the_frozen_release_hash_names_its_items(data: dict[str, Any]) -> None:
    frozen = next(r for r in data["releases.jsonl"] if r["status"] == "frozen")
    refs = sorted(
        item["episode_ref"]
        for item in data["release_items.jsonl"]
        if item["release_ref"] == frozen["release_ref"]
    )
    expected = hashlib.sha256(f"mock:{','.join(refs)}".encode()).hexdigest()
    assert frozen["manifest_sha256"] == expected


def test_an_excluded_release_item_says_why(data: dict[str, Any]) -> None:
    excluded = [item for item in data["release_items.jsonl"] if item["excluded"]]
    assert excluded and all(item["exclude_reason"] for item in excluded)


def test_every_non_pass_qa_verdict_has_a_reason(data: dict[str, Any]) -> None:
    for report in data["qa_reports.jsonl"]:
        assert report["decision"] == "pass" or report["reasons"]


def test_the_answer_key_is_nowhere_but_the_manifest(data: dict[str, Any]) -> None:
    # R8. Đáp án lỗi cấy chỉ nằm trong `defect_manifest.json` (nhóm S). Không
    # episode nào, không báo cáo QA nào, mang tham số của lỗi đã cấy.
    answers = {
        json.dumps(d["parameters"], sort_keys=True)
        for d in data["defect_manifest.json"]["defects"]
    }
    episodes = (OUT / "episodes.jsonl").read_text(encoding="utf-8")
    assert "injected_defect" not in episodes
    assert not any(answer in episodes for answer in answers)


# ---------------------------------------------------------------------------
# eval và kiểm hệ thống
# ---------------------------------------------------------------------------


def _eval_rows(data: dict[str, Any], evaluation: str) -> list[dict[str, Any]]:
    return [row for row in data["eval_episodes.jsonl"] if row["evaluation_ref"] == evaluation]


@pytest.mark.parametrize("evaluation", ["ev_A_dev", "ev_B_dev"])
def test_evaluation_counts_match_their_episodes(data: dict[str, Any], evaluation: str) -> None:
    rows = _eval_rows(data, evaluation)
    summary = next(e for e in data["evaluations.jsonl"] if e["evaluation_ref"] == evaluation)
    assert len(rows) == summary["total_episodes"] == DEV_SIZE
    assert summary["success_count"] == sum(1 for row in rows if row["sim_success"])
    assert summary["infra_failed_count"] == sum(1 for row in rows if row["infra_status"] != "ok")


def test_four_infra_failures_carry_no_policy_verdict(data: dict[str, Any]) -> None:
    # 03 §4.3 luật 8: simulator sập không bao giờ là sim_success = FALSE.
    infra = [row for row in data["eval_episodes.jsonl"] if row["infra_status"] != "ok"]
    assert len(infra) == 4
    assert all(row["sim_success"] is None and row["scorer_success"] is None for row in infra)


@pytest.mark.parametrize("evaluation", ["ev_A_dev", "ev_B_dev"])
def test_the_scorer_stays_within_five_points_of_the_simulator(
    data: dict[str, Any], evaluation: str
) -> None:
    # §1 điểm 9: lệch quá 5% nghĩa là scorer hỏng; bộ mock không được tự kể
    # một câu chuyện mà scorer hỏng.
    scored = [row for row in _eval_rows(data, evaluation) if row["infra_status"] == "ok"]
    sim = sum(1 for row in scored if row["sim_success"]) / len(scored)
    scorer = sum(1 for row in scored if row["scorer_success"]) / len(scored)
    assert abs(sim - scorer) < 0.05


def test_branch_b_beats_branch_a_on_dev(data: dict[str, Any]) -> None:
    rates = {
        e["evaluation_ref"]: e["success_count"] / (e["total_episodes"] - e["infra_failed_count"])
        for e in data["evaluations.jsonl"]
        if e["split"] == "dev"
    }
    assert rates["ev_B_dev"] > rates["ev_A_dev"]


def test_an_unknown_failure_has_neither_a_step_nor_a_class(data: dict[str, Any]) -> None:
    # Thiếu tín hiệu là "chưa rõ", không phải "trượt" (spec §5.1); L-UNKNOWN
    # không có lớp lỗi chung (03 §4.3).
    unknown = [row for row in data["eval_episodes.jsonl"] if row["failure_code"] == "L-UNKNOWN"]
    assert unknown
    for row in unknown:
        assert row["failure_class"] is None and row["first_failed_step"] is None
        assert "unknown" in row["step_status"] and "fail" not in row["step_status"]


def test_system_diagnoses_obey_c17(data: dict[str, Any]) -> None:
    for row in data["system_diagnoses.jsonl"]:
        if row["diagnosis"] == "clean":
            assert row["findings"] == [] and row["skipped"] == []
        if row["findings"]:
            assert row["diagnosis"] not in ("clean", "unknown")


def test_the_mock_has_an_unknown_system_check_for_br12(data: dict[str, Any]) -> None:
    # Ca chứng minh BR-12: một phép kiểm không chạy được không bao giờ hiện là
    # "không có lỗi". Thiếu ca này thì FE không có gì để vẽ `SkippedList`.
    unknown = [row for row in data["system_diagnoses.jsonl"] if row["diagnosis"] == "unknown"]
    assert unknown
    assert all({skip["code"] for skip in row["skipped"]} == {"R1", "R2"} for row in unknown)
    assert all("latency_p99_s" not in row["measurements"] for row in unknown)


def test_every_system_diagnosis_belongs_to_a_failed_b_episode(data: dict[str, Any]) -> None:
    failed = {
        row["eval_episode_ref"]
        for row in _eval_rows(data, "ev_B_dev")
        if row["infra_status"] == "ok" and not row["sim_success"]
    }
    assert {row["eval_episode_ref"] for row in data["system_diagnoses.jsonl"]} == failed


# ---------------------------------------------------------------------------
# Failure → Data
# ---------------------------------------------------------------------------


def test_four_clusters_with_four_diagnoses(data: dict[str, Any]) -> None:
    diagnoses = sorted(row["diagnosis"] for row in data["failure_clusters.jsonl"])
    assert diagnoses == sorted(
        ["HE_THONG_CONTROLLER", "NGOAI_MIEN", "THIEU_VUNG_PHU", "KY_NANG_YEU"]
    )


def test_exactly_two_clusters_spend_the_data_budget(data: dict[str, Any]) -> None:
    # Câu quan trọng nhất của demo (Phụ lục C).
    spend = [
        row for row in data["failure_clusters.jsonl"]
        if row["diagnosis"] in SPEC["data_budget_diagnosis"]
    ]
    assert len(spend) == 2


def test_each_cluster_counts_exactly_its_member_episodes(data: dict[str, Any]) -> None:
    failed = [
        row for row in _eval_rows(data, "ev_B_dev")
        if row["infra_status"] == "ok" and not row["sim_success"]
    ]
    for cluster in data["failure_clusters.jsonl"]:
        key = (cluster["failed_step"], cluster["failure_code"], cluster["level"])
        members = {
            row["eval_episode_ref"]
            for row in failed
            if (row["first_failed_step"], row["failure_code"], row["level"]) == key
        }
        assert cluster["member_count"] == len(members)
        assert 1 <= len(cluster["representative_refs"]) <= 5
        assert set(cluster["representative_refs"]) <= members


def test_interventions_go_only_to_data_budget_clusters(data: dict[str, Any]) -> None:
    budget = {
        row["cluster_ref"]
        for row in data["failure_clusters.jsonl"]
        if row["diagnosis"] in SPEC["data_budget_diagnosis"]
    }
    for intervention in data["interventions.jsonl"]:
        assert intervention["cluster_ref"] in budget
        assert intervention["kind"] in SPEC["intervention_kind"]
        assert intervention["n_eff"] == min(intervention["n_failures"], 10)
        # g = n_eff / 90 × f̄, f̄ = prior Beta(1, 1) = 0.5 (§5.3 bước 11).
        assert intervention["expected_gain_pp"] == round(intervention["n_eff"] / 90 * 50, 3)


def test_the_system_cluster_gets_a_repair_ticket_and_no_diagnostic_rollouts(
    data: dict[str, Any],
) -> None:
    # Hệ thống trước, dữ liệu sau: cụm hệ thống dừng ở bước 4.
    system = {
        row["cluster_ref"]
        for row in data["failure_clusters.jsonl"]
        if row["diagnosis"].startswith("HE_THONG")
    }
    assert {t["cluster_ref"] for t in data["repair_tickets.jsonl"]} == system
    assert not system & {run["cluster_ref"] for run in data["diagnostic_runs.jsonl"]}


def test_a_skipped_diagnostic_check_says_why(data: dict[str, Any]) -> None:
    skipped = [run for run in data["diagnostic_runs.jsonl"] if run["outcome"] == "skipped"]
    assert skipped and all(run["skip_reason"] for run in skipped)


# ---------------------------------------------------------------------------
# sổ chi phí và lỗi cấy
# ---------------------------------------------------------------------------


def test_the_reversal_negates_its_original_exactly(data: dict[str, Any]) -> None:
    # C9: đúng dấu, đúng đối tượng.
    ledger = {row["entry_ref"]: row for row in data["ledger.jsonl"]}
    reversals = [row for row in ledger.values() if row["entry_kind"] == "REVERSAL"]
    assert len(reversals) == 1
    reversal = reversals[0]
    original = ledger[reversal["reverses_entry_ref"]]
    for field in ("quantity", "measured_usd", "measured_gpu_hours"):
        assert reversal[field] == -original[field]
    for field in ("activity", "resource_type", "experiment_code", "branch"):
        assert reversal.get(field) == original.get(field)


def test_every_ledger_entry_has_a_target_and_estimates_have_an_owner(data: dict[str, Any]) -> None:
    targets = ("dataset_code", "experiment_code", "evaluation_ref", "recommendation_ref",
               "intervention_ref")
    for row in data["ledger.jsonl"]:
        assert any(row.get(name) for name in targets), row["entry_ref"]  # C11
        if row.get("estimated_usd") is not None:  # C10
            assert row.get("recommendation_ref") or row.get("intervention_ref")


def test_code_catches_six_of_ten_and_the_agent_two_more(data: dict[str, Any]) -> None:
    # Câu M3 nói thành lời: "code bắt 6/10, agent bắt thêm 2".
    caught: dict[str, set[str]] = {"code": set(), "agent": set()}
    for score in data["defect_scores.jsonl"]:
        if score["tp"]:
            caught[score["detector"]].add(score["code"])
    total = len(data["defect_manifest.json"]["defects"])
    assert total == 10
    assert len(caught["code"]) == 6
    assert len(caught["agent"] - caught["code"]) == 2


def test_seven_data_defects_and_three_train_log_defects(data: dict[str, Any]) -> None:
    # Phụ lục C: 4 ở tầng 2, 3 ở tầng 4, 3 trong log train. Tầng không có
    # trong hợp đồng của DefectManifest, nên test chỉ kiểm được họ mã.
    codes = Counter(d["code"][0] for d in data["defect_manifest.json"]["defects"])
    assert codes == {"D": 7, "T": 3}


def test_every_defect_targets_something_that_exists(data: dict[str, Any]) -> None:
    episodes = {e["episode_id"] for e in data["episodes.jsonl"]}
    for defect in data["defect_manifest.json"]["defects"]:
        target = defect["target_ref"]
        assert target in episodes or target.endswith("metrics.jsonl"), target
