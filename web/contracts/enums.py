"""Mọi enum của tầng web, một nguồn duy nhất (DESIGN.md Phụ lục A, luật R3).

Ba nhóm, tách nhau vì **mức bảo đảm khác nhau**, và lẫn chúng là cách web lặng
lẽ lệch khỏi lõi:

* ``CONTRACT`` — giá trị lõi khai trong ``flywheel-contracts``, bằng JSON
  Schema hoặc bằng ``Literal`` trong mã. ``web/tests/test_enum_sync.py`` so
  từng bộ với nguồn của nó, nên một PR hợp đồng đổi giá trị sẽ làm test đỏ
  thay vì làm web hiện sai âm thầm.
* ``SPEC`` — giá trị spec v10.5 và design 27/10 chốt nhưng **chưa có trong
  hợp đồng**: kiểu lỗi của hai task, 11 chẩn đoán cụm, nhánh, phương pháp,
  giả thuyết. Không máy nào kiểm được, nên mỗi bộ ghi rõ mục tài liệu nó lấy
  từ đâu. Khi hợp đồng nhận chúng, chuyển sang ``CONTRACT``.
* ``WEB`` — giá trị của riêng web (``action_kind``, ``sync_status``, vai người
  dùng). Tài liệu này là nguồn; lõi không biết tới chúng.

``web/fe/src/contracts/enums.ts`` sinh ra từ file này bằng
``python -m web.contracts.generate_ts``; test kiểm bản sinh còn khớp, nên FE và
BE không thể lệch nhau.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# CONTRACT · kiểm được bằng máy
# ---------------------------------------------------------------------------

#: Bộ nào đọc từ JSON Schema nào. Khoá là tên bộ trong ``CONTRACT``.
SCHEMA_SOURCE: Final[dict[str, tuple[str, str]]] = {
    "source_kind": ("Episode.json", "properties.source_kind"),
    "source_detail": ("EpisodeMetadata.json", "properties.source_detail.anyOf[0]"),
    "synthetic_tier": ("EpisodeMetadata.json", "properties.synthetic_tier.anyOf[0]"),
    "action_quality": ("Episode.json", "properties.action_quality"),
    "episode_kind": ("Episode.json", "properties.kind"),
    "operator_kind": ("Episode.json", "properties.operator_kind"),
    "data_class": ("Episode.json", "properties.data_class"),
    "deid_status": ("Episode.json", "properties.deid_status"),
    "renderer": ("EpisodeMetadata.json", "properties.renderer.anyOf[0]"),
    "qa_decision": ("QAReport.json", "properties.decision"),
    "replay_mode": ("ReplayReport.json", "properties.mode"),
    "eval_mode": ("RolloutRequest.json", "properties.timing"),
    "train_split": ("TrainingMetric.json", "properties.split"),
    "non_finite": ("TrainingMetric.json", "properties.loss.anyOf[1]"),
}

#: Bộ ghép từ nhiều file, mỗi file khai một ``const``. Tách khỏi
#: ``SCHEMA_SOURCE`` vì hình dạng nguồn khác: không có chỗ nào trong hợp đồng
#: khai cả bốn probe cùng lúc.
MULTI_FILE_SOURCE: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "probe": tuple((f"ProbeP{index}.json", "properties.probe") for index in (1, 2, 3, 4)),
}

#: Bộ nào đọc từ ``Literal`` nào trong mã contract. Giá trị là đường dẫn
#: ``<module>.<tên>`` dưới ``flywheel.contracts``.
LITERAL_SOURCE: Final[dict[str, str]] = {
    "failure_class": "v0.FailureClass",
    "infra_status": "v0.InfraStatus",
    "train_finding_code": "training.FindingCode",
}

CONTRACT: Final[dict[str, tuple[str, ...]]] = {
    # --- Episode và dataset
    "source_kind": ("teleop", "synthetic", "egocentric"),
    "source_detail": (
        "psi_data",
        "teleop_keyboard",
        "teleop_pico",
        "planner_wbc",
        "planner_amo",
    ),
    "synthetic_tier": ("S1", "S2", "S3", "S4"),
    "action_quality": ("measured", "planned", "retargeted", "pseudo", "none"),
    "episode_kind": (
        "teleop_demo",
        "teleop_correction",
        "recovery",
        "sim_rollout",
        "variant",
        "eval_rollout",
        "diag_rollout",
    ),
    "operator_kind": ("human", "machine"),
    "data_class": ("public", "internal", "restricted"),
    "deid_status": ("raw", "blurred", "verified"),
    "renderer": ("mujoco", "isaac"),
    # --- QA và phát lại
    "qa_decision": ("pass", "flag", "quarantine", "reject"),
    "replay_mode": ("kinematic", "dynamic"),
    # --- Eval và train
    "eval_mode": ("sync", "async"),
    "infra_status": (
        "ok",
        "simulator_error",
        "policy_error",
        "timeout",
        "out_of_memory",
    ),
    "failure_class": ("approach", "grasp", "carry", "place", "balance"),
    "train_split": ("train", "val"),
    "train_finding_code": (
        "T1",
        "T2",
        "T3",
        "T4",
        "T5",
        "T6",
        "T7",
        "T8",
        "O1",
        "O2",
        "O3",
        "O4",
    ),
    "non_finite": ("NaN", "Infinity", "-Infinity"),
    "probe": ("P1", "P2", "P3", "P4"),
}

# ---------------------------------------------------------------------------
# SPEC · chốt trong tài liệu, chưa có trong hợp đồng
# ---------------------------------------------------------------------------

#: Mục tài liệu chốt từng bộ. Không có cái nào kiểm được bằng máy, nên dòng
#: này là thứ duy nhất nói nó từ đâu ra.
SPEC_SOURCE: Final[dict[str, str]] = {
    "task_id": "DESIGN.md Phụ lục A [Đề xuất]; đối chiếu contract ở M0",
    "split": "03 §4.3 (cột Condition.split)",
    "pipeline_stage": "design 27/10 §6; DESIGN.md §5.1",
    "stage_run_status": "DESIGN.md §5.1 (enum của luồng, web giữ)",
    "human_review_action": "DESIGN.md §5.1 bước 8",
    "qa_agent_verdict": "design 27/10 §9.1",
    "step_status": "spec v10.5 §5.1; đã hiện thực trong DA-36 StepStatus",
    "system_diagnosis": "spec v10.5 §6.4; đã hiện thực trong DA-13 Diagnosis",
    "failure_code_two_table": "spec v10.5 §5.2",
    "failure_code_tray": "design 28/10 §3.3 [Đề xuất]",
    "cluster_diagnosis": "spec v10.5 §6.9; design 27/10 §10",
    "data_budget_diagnosis": "spec v10.5 §6.9 (3 trong 11)",
    "intervention_kind": "spec v10.5 §6.10",
    "branch_two_table": "spec v10.5 §7.2",
    "branch_tray": "design 28/10 §7",
    "he_variant": "design 27/10 §7.2",
    "method": "spec v10.5 §7.4",
    "hypothesis": "spec v10.5 §3",
    "data_fault_code": "design 27/10 §10 (F-DATA)",
    "system_fault_code": "design 27/10 §10 (F-SYS)",
}

SPEC: Final[dict[str, tuple[str, ...]]] = {
    "task_id": ("two_table", "tray"),
    "split": ("train", "dev", "holdout", "unassigned"),
    "pipeline_stage": ("INGEST", "NORMALIZE", "ANNOTATE", "QA", "RELEASE", "EXPORT"),
    "stage_run_status": (
        "PENDING",
        "RUNNING",
        "QA_EVALUATING",
        "PASSED",
        "PAUSED_FOR_REVIEW",
        "OVERRIDDEN",
        "FAILED",
        "ABORTED",
    ),
    "human_review_action": (
        "RETRY_STAGE",
        "APPLY_FIX_AND_RETRY",
        "FORCE_CONTINUE",
        "ABORT_PIPELINE",
    ),
    "qa_agent_verdict": ("PASS", "WARNING", "FAIL"),
    # Bốn chuỗi của `StepStatus` trong DA-36 (PR #58), không phải mã số 0..3
    # của DESIGN.md v0.2. Issue #59 là PR hợp đồng cho bộ này.
    "step_status": ("pass", "fail", "not_attempted", "unknown"),
    # Kết luận kiểm hệ thống của **một episode** (DA-13, PR #71). Khác
    # `cluster_diagnosis` bên dưới, là kết luận của **một cụm**; bảng ánh xạ ở
    # DESIGN.md §4.4b. Issue #70 là PR hợp đồng.
    "system_diagnosis": (
        "clean",
        "unknown",
        "controller",
        "runtime",
        "sync",
        "calibration",
        "infra",
    ),
    "failure_code_two_table": (
        "L-REACH",
        "L-GRASP",
        "L-SLIP",
        "L-WALK",
        "L-COLLIDE",
        "L-PLACE",
        "L-RELEASE",
        "L-BALANCE",
        "L-TIMEOUT",
        "L-UNKNOWN",
    ),
    "failure_code_tray": (
        "L-PART-DROP",
        "L-TRAY-TILT",
        "L-ONE-HAND",
        "L-PLACE-POSE",
        "L-TIMEOUT",
        "L-BALANCE",
    ),
    "cluster_diagnosis": (
        "CHUA_RO",
        "HE_THONG_CONTROLLER",
        "HE_THONG_RUNTIME",
        "HE_THONG_DONG_BO",
        "HE_THONG_CALIBRATION",
        "KHONG_KHA_THI",
        "TRANG_THAI_DAU_XAU",
        "NHAN_THUC",
        "NGOAI_MIEN",
        "THIEU_VUNG_PHU",
        "KY_NANG_YEU",
    ),
    "data_budget_diagnosis": ("TRANG_THAI_DAU_XAU", "THIEU_VUNG_PHU", "KY_NANG_YEU"),
    "intervention_kind": ("SIM_AROUND_FAILURE", "TELEOP_CORRECTION", "RECOVERY_DATA"),
    "branch_two_table": ("A", "A_07", "B", "C", "B_FAIL", "B_PLUS"),
    "branch_tray": ("TRAY_A", "TRAY_C", "TRAY_B", "TRAY_C_EGO", "TRAY_C_NOEGO"),
    "he_variant": ("V_EGO", "V_EGO10", "V_NOEGO"),
    "method": ("PSI0", "ACT", "DIFFUSION_POLICY"),
    "hypothesis": ("HS", "HT", "HTa", "HTb", "HD", "HE", "HE_T", "M"),
    "data_fault_code": ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"),
    "system_fault_code": ("R1", "R2", "R3", "R4", "R5", "R6"),
}

# ---------------------------------------------------------------------------
# WEB · của riêng web
# ---------------------------------------------------------------------------

WEB: Final[dict[str, tuple[str, ...]]] = {
    "action_kind": (
        "INTAKE_SUBMIT",
        "STAGE_REVIEW",
        "EXPERIMENT_SUBMIT",
        "RECOMMENDATION_DECISION",
        "DIAGNOSIS_OVERRIDE",
        "RELEASE_FREEZE_REQUEST",
        "EVAL_REQUEST",
        "FLYWHEEL_RUN_REQUEST",
        "HOLDOUT_UNSEAL",
        "SOFT_DELETE",
        "CHAT_ACTION_CONFIRM",
    ),
    "sync_status": ("PENDING", "EXPORTED", "APPLIED", "REJECTED"),
    "job_kind": (
        "PIPELINE_RUN",
        "PIPELINE_RETRY_FROM",
        "TRAIN",
        "PROBE",
        "EVAL",
        "RELEASE_FREEZE",
        "FLYWHEEL_RUN",
    ),
    "job_status": ("OPEN", "PICKED", "DONE", "FAILED", "CANCELLED"),
    "draft_status": ("DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"),
    "intervention_decision": ("APPROVE", "APPROVE_EDITED", "REJECT"),
    "origin": ("core", "mock"),
    "user_role": ("DATA_ENGINEER", "ML_ENGINEER", "LEAD", "JUDGE_VIEWER", "ADMIN"),
}

ALL: Final[dict[str, tuple[str, ...]]] = {**CONTRACT, **SPEC, **WEB}

#: Hành động nào bắt buộc có lý do (DESIGN.md §4.4a, BR-04, BR-10).
ACTION_NEEDS_REASON: Final[tuple[str, ...]] = (
    "DIAGNOSIS_OVERRIDE",
    "HOLDOUT_UNSEAL",
    "SOFT_DELETE",
)


def group_of(name: str) -> str:
    """Nhóm của một bộ enum: ``contract``, ``spec`` hay ``web``.

    FE dùng để biết một giá trị lạ là lỗi hợp đồng (phải báo) hay chỉ là giá
    trị tài liệu chưa cập nhật (hiện nguyên văn và ghi log).
    """
    if name in CONTRACT:
        return "contract"
    if name in SPEC:
        return "spec"
    if name in WEB:
        return "web"
    raise KeyError(f"không có bộ enum `{name}`")


def failure_codes(task_id: str) -> tuple[str, ...]:
    """Kiểu lỗi của một task.

    Hai task có hai bộ mã khác nhau và trùng nhau một phần (``L-TIMEOUT``,
    ``L-BALANCE``), nên không có bộ chung: hỏi theo task, đúng cách scorer của
    DA-36 đọc ``FailureKindSpec`` thay vì viết cứng.
    """
    if task_id == "two_table":
        return SPEC["failure_code_two_table"]
    if task_id == "tray":
        return SPEC["failure_code_tray"]
    raise KeyError(f"không có task `{task_id}`; chỉ có {SPEC['task_id']}")
