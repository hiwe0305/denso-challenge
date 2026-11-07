"""Sinh bộ mock `mock/demo-17-11/` (DESIGN.md Phụ lục C).

Chạy: ``uv run python -m web.mock.generate``. Không tham số; nó ghi đè thư mục
đích và in số file.

**Mọi con số ở đây là bịa, và phải trông như bịa.** Đây là dữ liệu mẫu để FE
và bộ nạp có cái để chạy trước khi lõi sinh dữ liệu thật; không số nào là số
đo (CLAUDE.md: "số liệu chưa đo ghi là giả định"). Mọi bản ghi nạp từ thư mục
này mang `origin = 'mock'` (`fwsync import --origin mock`), nguồn ghi
`repo: mock://…`, giấy phép ghi `mock-public`, và README đi kèm nói rõ điều đó.

**Sinh, không gõ tay**, vì bộ mock phải nhất quán với chính nó: số thành viên
của một cụm phải bằng đúng số episode eval lỗi mang khoá của cụm đó, bút toán
đảo phải mang đúng số đối của bút toán gốc, `success_count` phải khớp số
episode thành công. Gõ tay 400 dòng thì những thứ đó lệch đúng lúc không ai
nhìn. `web/tests/test_mock.py` so bản trên đĩa với bản sinh lại, và kiểm các
bất biến đó.

**Tất định.** Một seed, không đọc đồng hồ, không dùng `hash()` của Python
(đổi theo tiến trình), JSON ghi với `sort_keys`. Chạy lại cho đúng từng byte.

Câu chuyện bộ mock kể, đúng điều Phụ lục C cần cho demo:

* Năm lô, trong đó một bản sao cấy 10 lỗi, dừng ở tầng 4. Code bắt 6/10,
  agent bắt thêm 2 (M3).
* Bốn thí nghiệm nhánh A, A_07, B, B_FAIL; B_FAIL có T3. Lưới HE 3 biến thể
  × N ∈ {10, 20, 40, 80}, mỗi điểm một release đúng N demo gốc của người.
* Bốn lượt eval dev 90 episode (A, A_07, B, B_FAIL), mỗi lượt 2 episode lỗi
  hạ tầng bị loại khỏi mẫu số; 12 lượt eval dev chỉ có số tổng cho điểm HE.
* Một lượt Failure → Data trên checkpoint B với **bốn cụm, bốn chẩn đoán**:
  lỗi controller, ngoài miền, thiếu vùng phủ, kỹ năng yếu. Chỉ hai cụm sau
  tiêu ngân sách dữ liệu — câu quan trọng nhất của demo.
* Kiểm hệ thống có cả ca `unknown` vì thiếu log RTC, để BR-12 có ca chứng minh.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[2] / "mock" / "demo-17-11"
SEED = 17_11_2026
LICENSE = "mock-public"
TASK = "two_table"
SCORER = "scorer-0.1"
STEP_NAMES = ["tiếp cận", "gắp", "đi", "tới bàn đích", "đặt", "nhả và ổn định"]
HE_VARIANTS = ("V_EGO", "V_EGO10", "V_NOEGO")
HE_SIZES = (10, 20, 40, 80)
#: Egocentric clips each HE variant adds on top of its N robot demos.
HE_EGO_CLIPS = {"V_EGO": 20, "V_EGO10": 10, "V_NOEGO": 0}
#: Invented dev success rate of an HE point: grows with N, egocentric helps.
HE_BASE_RATE = {10: 0.30, 20: 0.42, 40: 0.55, 80: 0.63}
HE_VARIANT_LIFT = {"V_EGO": 0.10, "V_EGO10": 0.04, "V_NOEGO": 0.0}
STEP_CLASS = {1: "approach", 2: "grasp", 3: "carry", 4: "carry", 5: "place", 6: "place"}
CODE_CLASS = {
    "L-GRASP": "grasp",
    "L-WALK": "carry",
    "L-SLIP": "carry",
    "L-PLACE": "place",
    "L-BALANCE": "balance",
}
QA_CHECKS = ["schema", "sync_drop", "action_limits", "stats", "dedup", "labels", "replay"]
QA_THRESHOLDS = {
    "schema": 1.0,
    "sync_drop": 0.02,
    "action_limits": 1.0,
    "stats": 1.0,
    "dedup": 0.95,
    "labels": 1.0,
    "replay": 0.05,
}

Row = dict[str, Any]


def hx(label: str) -> str:
    """Hash 64 hex tất định, cho mọi trường kiểu sha256 của bộ mock."""
    return hashlib.sha256(f"mock:{label}".encode()).hexdigest()


def ts(day: int, hour: int = 9, minute: int = 0) -> str:
    return f"2026-11-{day:02d}T{hour:02d}:{minute:02d}:00Z"


class Mock:
    """Toàn bộ bộ mock, dựng một lần theo đúng thứ tự phụ thuộc."""

    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.files: dict[str, list[Row] | Row] = {}

    # ------------------------------------------------------------------ data
    DATASETS: list[dict[str, Any]] = [
        {"code": "ds_psi_teleop", "source": "src_psi_data", "kind": "teleop",
         "detail": "psi_data", "n": 80, "prefix": "ep_psi"},
        {"code": "ds_kbd_teleop", "source": "src_kbd", "kind": "teleop",
         "detail": "teleop_keyboard", "n": 40, "prefix": "ep_kbd"},
        {"code": "ds_synth_s1", "source": "src_planner_wbc", "kind": "synthetic",
         "detail": "planner_wbc", "n": 50, "prefix": "ep_s1"},
        {"code": "ds_egodex", "source": "src_egodex", "kind": "egocentric",
         "detail": None, "n": 30, "prefix": "ep_ego"},
        {"code": "bench_kbd_teleop", "source": "src_bench_kbd", "kind": "teleop",
         "detail": "teleop_keyboard", "n": 10, "prefix": "ep_bench", "seeded": True},
    ]

    #: Lỗi cấy của bản sao chấm. Đây là **đáp án**: nó chỉ đi vào nhóm S qua
    #: `defect_manifest.json`, không vào episode nào (luật R8). Bộ nạp không có
    #: đường nào đưa nó sang nhóm P.
    DEFECTS: list[tuple[str, str, dict[str, Any]]] = [
        ("ep_bench_00", "D1", {"kind": "missing_column", "column": "left_wrist_cmd"}),
        ("ep_bench_01", "D2", {"kind": "dropped_frames", "drop_frames": 5}),
        ("ep_bench_02", "D3", {"kind": "action_scale", "dim": 12, "scale": 1.8}),
        ("ep_bench_03", "D4", {"kind": "dead_dim", "dim": 31}),
        ("ep_bench_04", "D5", {"kind": "duplicate_episode", "original_id": "ep_bench_07"}),
        ("ep_bench_05", "D6", {"kind": "label_swap", "label_swap": "3<->4"}),
        ("ep_bench_06", "D7", {"kind": "action_sign_flip", "flip_dim": 20}),
    ]
    #: Lỗi cấy vào log train: một bản sao **khác** (DA-27 inject-logs), vì
    #: bộ chấm DA-31 chấm từng nhóm trên một cặp bản có lỗi / bản sạch.
    LOG_DEFECTS: list[tuple[str, str, dict[str, Any]]] = [
        ("runs/exp_BFAIL/metrics.jsonl", "T1", {"kind": "nan_loss", "nan_at_step": 1200}),
        ("runs/exp_BFAIL/metrics.jsonl", "T3", {"kind": "overfit", "overfit_from_step": 1400}),
        ("runs/exp_BFAIL/metrics.jsonl", "T5", {"kind": "dead_dim_train", "dead_dim": 7}),
    ]
    #: Mã nào bộ phát hiện bằng code bắt được, mã nào agent bắt được. Code bắt
    #: 6/10; agent bắt thêm D6 và T3 (M3: "code bắt x, agent bắt thêm y").
    CODE_CATCHES = {"D1", "D2", "D3", "D4", "D7", "T1"}
    AGENT_CATCHES = CODE_CATCHES | {"D6", "T3"}
    #: Quyết định QA của code trên bản sao: chỉ mã code bắt được mới đổi
    #: quyết định; D5 và D6 lọt qua với `pass`.
    BENCH_QA: dict[str, tuple[str, str, str]] = {
        "ep_bench_00": ("reject", "schema", "thiếu cột của action_layout"),
        "ep_bench_01": ("quarantine", "sync_drop", "rơi khung trong frame_index"),
        "ep_bench_02": ("quarantine", "action_limits", "vượt giới hạn vận tốc khớp"),
        "ep_bench_03": ("reject", "stats", "chiều có độ lệch chuẩn 0 mà không mask"),
        "ep_bench_06": ("quarantine", "replay", "phát lại lệch khỏi state đã ghi"),
    }

    def build(self) -> dict[str, list[Row] | Row]:
        self.sources()
        self.price_books()
        self.datasets_and_episodes()
        self.stage_runs()
        self.releases()
        self.run_plans()
        self.experiments()
        self.training()
        self.probes()
        self.evaluations()
        self.flywheel()
        self.decisions()
        self.ledger()
        self.defects()
        return self.files

    # --------------------------------------------------------------- sources
    def sources(self) -> None:
        rows = [
            ("src_psi_data", "dataset", "psi-data, dataset teleop của tác giả Ψ₀", "true"),
            ("src_kbd", "dataset", "teleop bàn phím của đội", "true"),
            ("src_planner_wbc", "dataset", "synthetic S1, planner trong env WBC", "true"),
            ("src_egodex", "dataset", "mẫu EgoDex", "true"),
            ("src_bench_kbd", "dataset", "bản sao chấm Agent QA/QC", "false"),
            ("src_psi0_ckpt", "checkpoint", "checkpoint công bố của Ψ₀", "true"),
        ]
        self.files["sources.jsonl"] = [
            {
                "source_ref": ref,
                "repo": f"mock://{ref}",
                "revision": hx(ref)[:12],
                "sha256": hx(f"{ref}:bytes"),
                "license": LICENSE,
                "downloaded_at": ts(1),
                "kind": kind,
                "clean_for_main_task": clean,
                "provenance": {"note": note, "mock": True},
            }
            for ref, kind, note, clean in rows
        ]

    def price_books(self) -> None:
        # Bốn kịch bản độ nhạy (§6.1 M8). Số là giả định của bộ mock.
        scenarios = {
            "pitch_v10": (2.0, 0.8, 0.025, 0.0),
            "denso": (2.4, 1.1, 0.03, 35.0),
            "cell_dat": (2.0, 0.8, 0.025, 80.0),
            "gpu_dat": (4.0, 0.8, 0.025, 0.0),
        }
        self.price = {name: values for name, values in scenarios.items()}
        self.files["price_books.jsonl"] = [
            {
                "name": name,
                "sha256": hx(f"price:{name}"),
                "rates": {
                    "gpu_hours": {"unit": "hour", "usd_per_unit": gpu},
                    "operator_minutes": {"unit": "minute", "usd_per_unit": op},
                    "storage_gb": {"unit": "GB", "usd_per_unit": storage},
                },
                "cell_hour_usd": cell,
                "effective_from": "2026-10-01",
                "note": "kịch bản độ nhạy của bộ mock, không phải bảng giá thật",
            }
            for name, (gpu, op, storage, cell) in scenarios.items()
        ]

    # ------------------------------------------------- datasets and episodes
    def datasets_and_episodes(self) -> None:
        datasets: list[Row] = []
        episodes: list[Row] = []
        qa: list[Row] = []
        self.episodes_by_dataset: dict[str, list[Row]] = {}
        for spec in self.DATASETS:
            rows = [self._episode(spec, index) for index in range(spec["n"])]
            self.episodes_by_dataset[spec["code"]] = rows
            episodes += rows
            qa += [
                report
                for row in rows
                if (report := self._qa_report(spec["code"], row)) is not None
            ]
            datasets.append(
                {
                    "dataset_code": spec["code"],
                    "source_ref": spec["source"],
                    "source_kind": spec["kind"],
                    "source_detail": spec["detail"],
                    "data_class": "public",
                    "license": LICENSE,
                    "status": "PAUSED_FOR_REVIEW" if spec.get("seeded") else "READY_FOR_TRAINING",
                    "has_seeded_faults": bool(spec.get("seeded")),
                    "episode_count": spec["n"],
                    "note": "bản sao chấm Agent QA/QC, có lỗi cấy" if spec.get("seeded") else None,
                }
            )
        self.files["datasets.jsonl"] = datasets
        self.files["episodes.jsonl"] = episodes
        self.files["qa_reports.jsonl"] = qa

    def _episode(self, spec: dict[str, Any], index: int) -> Row:
        code, kind = spec["code"], spec["kind"]
        ref = (
            f"{spec['prefix']}_{index:03d}"
            if code != "bench_kbd_teleop"
            else f"ep_bench_{index:02d}"
        )
        row: Row = {
            "episode_id": ref,
            "kind": "teleop_demo",
            "operator_kind": "human",
            "is_root": True,
            "condition_id": f"cond_{TASK}_{index:03d}",
            "root_id": None,
            "parent_id": None,
            "source_id": spec["source"],
            "intervention_id": None,
            "checkpoint_id": None,
            "rollout_seed": None,
            "sim_success": None,
            "infra_status": None,
            "camera_params_hash": None,
            # `Episode.run_plan_id` bắt buộc trong hợp đồng. Episode nạp vào
            # chạy dưới RunPlan của lần tái lập G0; `purpose` của hợp đồng không
            # có giá trị "ingest" riêng.
            "run_plan_id": "rp_ingest_g0",
            "bundle_uri": f"mock://bundles/{ref}",
            "license": LICENSE,
            "data_class": "public",
            "split": "train",
            "source_kind": kind,
            "action_quality": "measured",
            "deid_status": "verified",
            "embodiment_id": "g1_sonic_dwbc@1",
            "meta": {
                "source_detail": spec["detail"],
                "renderer": "mujoco",
                "synthetic_tier": None,
                # C19: mọi episode của bản sao chấm, kể cả episode sạch (#62).
                "benchmark_copy_id": code if spec.get("seeded") else None,
            },
        }
        if code == "ds_psi_teleop":
            row["split"] = "train" if index < 64 else "dev"
        elif code == "ds_kbd_teleop":
            row["kind"] = "teleop_demo" if index < 34 else "teleop_correction"
            row["split"] = "train" if index < 32 else "dev"
        elif kind == "synthetic":
            row.update(
                kind="sim_rollout", operator_kind="machine", is_root=False,
                action_quality="planned",
            )
            row["meta"]["synthetic_tier"] = "S1"
        elif kind == "egocentric":
            # Hợp đồng chưa có `kind` riêng cho video egocentric của người, nên
            # bộ mock dùng teleop_demo + source_kind=egocentric. Nó không phải
            # demo robot, nên is_root=False: `r_demo` đếm demo robot (M8).
            row.update(is_root=False, action_quality="none", embodiment_id="human_egocentric@1")
            row["meta"]["renderer"] = None
            if index < 20:
                row["deid_status"] = "blurred"
            else:
                # Còn raw thì không được rời tầng Annotate (C14, BR-09).
                row.update(deid_status="raw", split="unassigned")
        elif spec.get("seeded"):
            row["split"] = "unassigned"
        return row

    def _qa_report(self, dataset: str, episode: Row) -> Row | None:
        ref = episode["episode_id"]
        if episode["deid_status"] == "raw":
            return None  # tầng 4 chưa chạy trên episode còn raw: `qa_not_run`
        decision, failing, reason = "pass", None, None
        index = int(ref.rsplit("_", 1)[1])
        if dataset == "ds_psi_teleop" and index in {5, 23, 47, 71}:
            decision, failing, reason = "flag", "sync_drop", "lệch t_image và t_state gần τ_sync"
        elif dataset == "ds_kbd_teleop" and index in {3, 17}:
            decision, failing, reason = "quarantine", "action_limits", "vượt giới hạn vận tốc khớp"
        elif dataset == "bench_kbd_teleop" and ref in self.BENCH_QA:
            decision, failing, reason = self.BENCH_QA[ref]
        checks = []
        for name in QA_CHECKS:
            threshold = QA_THRESHOLDS[name]
            passed = name != failing
            value = round(threshold * (1.4 if not passed else self.rng.uniform(0.1, 0.6)), 4)
            checks.append({"name": name, "value": value, "threshold": threshold, "passed": passed})
        return {
            "report_id": f"qa_{ref}",
            "episode_id": ref,
            "threshold_version": "qa-v1",
            "decision": decision,
            "reasons": [reason] if reason else [],
            "checks": checks,
        }

    def stage_runs(self) -> None:
        stages = ["INGEST", "NORMALIZE", "ANNOTATE", "QA", "RELEASE", "EXPORT"]
        rows: list[Row] = []

        def run(
            dataset: str, stage: int, attempt: int, status: str, current: bool = True,
            code: str | None = None, agent: str | None = None, note: str | None = None,
        ) -> Row:
            return {
                "dataset_code": dataset,
                "stage_number": stage,
                "attempt_no": attempt,
                "is_current": current,
                "status": status,
                "qa_code_decision": code,
                "qa_agent_verdict": agent,
                "qa_agent_report": (
                    {"verdict": agent, "detected_anomalies": [], "remediation_suggestion": note}
                    if agent else None
                ),
                "started_at": ts(2, 8 + stage) if status != "PENDING" else None,
                "finished_at": ts(2, 9 + stage) if status not in ("PENDING", "RUNNING") else None,
                "log_uri": f"mock://logs/{dataset}/stage{stage}-a{attempt}.log",
                "metrics": {"stage": stages[stage - 1]},
            }

        for spec in self.DATASETS:
            code = spec["code"]
            for stage in (1, 2, 3):
                rows.append(run(code, stage, 1, "PASSED"))
            if code == "ds_psi_teleop":
                # Bốn episode flag; người xem tay rồi FORCE_CONTINUE (BR-04).
                rows.append(run(code, 4, 1, "OVERRIDDEN", code="flag", agent="WARNING",
                                note="lệch đồng bộ gần ngưỡng ở 4 episode"))
                rows += [run(code, s, 1, "PASSED") for s in (5, 6)]
            elif code == "ds_kbd_teleop":
                # Lần 1 dừng vì quarantine; APPLY_FIX_AND_RETRY sinh attempt 2
                # cho tầng 4..6 và hạ is_current của attempt cũ (BR-02).
                rows.append(run(code, 4, 1, "FAILED", current=False, code="quarantine",
                                agent="FAIL", note="sửa giới hạn vận tốc trong bộ đọc"))
                rows += [run(code, s, 1, "PENDING", current=False) for s in (5, 6)]
                rows.append(run(code, 4, 2, "PASSED", code="pass", agent="PASS"))
                rows += [run(code, s, 2, "PASSED") for s in (5, 6)]
            elif spec.get("seeded"):
                rows.append(run(code, 4, 1, "PAUSED_FOR_REVIEW", code="reject", agent="FAIL",
                                note="bản sao chấm, dừng chờ duyệt"))
                rows += [run(code, s, 1, "PENDING") for s in (5, 6)]
            else:
                rows.append(run(code, 4, 1, "PASSED", code="pass", agent="PASS"))
                rows += [run(code, s, 1, "PASSED") for s in (5, 6)]
        self.files["pipeline_stage_runs.jsonl"] = rows

    def releases(self) -> None:
        excluded = {"ep_kbd_003": "QA quarantine: vượt giới hạn vận tốc khớp",
                    "ep_kbd_017": "QA quarantine: vượt giới hạn vận tốc khớp"}
        items: list[Row] = []
        for code in ("ds_psi_teleop", "ds_kbd_teleop", "ds_synth_s1", "ds_egodex"):
            for episode in self.episodes_by_dataset[code]:
                if episode["split"] != "train":
                    continue  # dev ở ngoài release train; raw egocentric đã unassigned
                reason = excluded.get(episode["episode_id"])
                items.append(
                    {
                        "release_ref": "rel_two_table_v1",
                        "episode_ref": episode["episode_id"],
                        "sample_weight": 1.0,
                        "excluded": reason is not None,
                        "exclude_reason": reason,
                    }
                )
        self.release_items = items
        manifest = hx(",".join(sorted(item["episode_ref"] for item in items)))
        self.files["releases.jsonl"] = [
            {"release_ref": "rel_two_table_v1", "name": "two_table v1", "parent_release_ref": None,
             "split_plan_sha256": hx("split-plan-v1"), "status": "frozen",
             "manifest_sha256": manifest, "manifest_uri": "mock://releases/v1/items.parquet",
             "license_summary": LICENSE, "frozen_at": ts(3, 10), "meta": {"items": len(items)}},
            {"release_ref": "rel_two_table_v2", "name": "two_table v2 (nháp)",
             "parent_release_ref": "rel_two_table_v1", "split_plan_sha256": hx("split-plan-v1"),
             "status": "draft", "manifest_sha256": None, "manifest_uri": None,
             "license_summary": LICENSE, "frozen_at": None, "meta": {}},
        ]
        # The draft v2: v1's kept items plus two dev episodes that slipped in.
        # It is the case M4's split guard exists for: a draft that must not be
        # frozen until the two are taken out (DESIGN.md §6.2, M4).
        leaked = [e["episode_id"] for e in self.episodes_by_dataset["ds_psi_teleop"]
                  if e["split"] == "dev"][:2]
        draft = [
            {**item, "release_ref": "rel_two_table_v2"} for item in items if not item["excluded"]
        ] + [
            {"release_ref": "rel_two_table_v2", "episode_ref": ref, "sample_weight": 1.0,
             "excluded": False, "exclude_reason": None}
            for ref in leaked
        ]
        self.draft_release_items = draft
        self.files["release_items.jsonl"] = items

    # ------------------------------------------------------------- training
    EXPERIMENTS: list[tuple[str, str, str, str, str | None]] = [
        # code, branch, hypothesis, run plan, checkpoint cha
        ("exp_A", "A", "HT", "rp_A", None),
        ("exp_A07", "A_07", "HTa", "rp_A07", None),
        ("exp_B", "B", "HT", "rp_B", "ckpt_A"),
        ("exp_BFAIL", "B_FAIL", "HTb", "rp_BFAIL", None),
    ] + [
        # HE (design 27/10 §7.2): three variants × N demos. Each point trains on
        # its own release holding exactly N human root demos, so v_he_curve
        # counts N from the data instead of reading a typed-in number.
        (f"exp_HE_{variant}_{n}", "C", "HE", f"rp_HE_{variant}_{n}", None)
        for variant in HE_VARIANTS for n in HE_SIZES
    ]

    @staticmethod
    def ckpt(experiment: str) -> str:
        return "ckpt_" + experiment.removeprefix("exp_")

    def run_plans(self) -> None:
        rows: list[Row] = [
            {"run_plan_ref": rp, "purpose": "branch_train", "branch": branch, "method": "PSI0",
             "task_id": TASK, "lock_uri": f"mock://runs/{rp}/runplan.lock.json",
             "config_sha256": hx(f"runplan:{rp}"), "frozen_at": ts(3, 12),
             "seed_range": "[1000,1090)", "meta": {}}
            for _, branch, _, rp, _ in self.EXPERIMENTS
        ]
        rows.append({"run_plan_ref": "rp_ingest_g0", "purpose": "g0_repro", "branch": None,
                     "method": None, "task_id": TASK,
                     "lock_uri": "mock://runs/rp_ingest_g0/runplan.lock.json",
                     "config_sha256": hx("runplan:rp_ingest_g0"), "frozen_at": ts(1, 9),
                     "seed_range": None, "meta": {"note": "nạp và chuẩn hoá dữ liệu"}})
        rows.append({"run_plan_ref": "rp_round1", "purpose": "round", "branch": "B",
                     "method": "PSI0", "task_id": TASK,
                     "lock_uri": "mock://runs/rp_round1/runplan.lock.json",
                     "config_sha256": hx("runplan:rp_round1"), "frozen_at": ts(8, 9),
                     "seed_range": "[2000,2090)", "meta": {"round_no": 1}})
        self.files["run_plans.jsonl"] = rows

    def _a07_release(self) -> tuple[str, int]:
        """Branch A_07: 70% of every source of A's release, human demos included."""
        ref = "rel_two_table_a07"
        kept = [item for item in self.release_items
                if item["release_ref"] == "rel_two_table_v1" and not item["excluded"]]
        source_of = {e["episode_id"]: code for code, rows in self.episodes_by_dataset.items()
                     for e in rows}
        by_source: dict[str, list[str]] = {}
        for item in kept:
            by_source.setdefault(source_of[item["episode_ref"]], []).append(item["episode_ref"])
        chosen = [ref_ for refs in by_source.values() for ref_ in refs[: round(0.7 * len(refs))]]
        items = [{"release_ref": ref, "episode_ref": e, "sample_weight": 1.0, "excluded": False,
                  "exclude_reason": None} for e in chosen]
        self.he_release_items += items
        self.he_releases.append(
            {"release_ref": ref, "name": "two_table v1 · 70%",
             "parent_release_ref": "rel_two_table_v1", "split_plan_sha256": hx("split-plan-v1"),
             "status": "frozen", "manifest_sha256": hx(",".join(sorted(chosen))),
             "manifest_uri": "mock://releases/a07/items.parquet", "license_summary": LICENSE,
             "frozen_at": ts(3, 11), "meta": {"items": len(items), "fraction": 0.7}}
        )
        return ref, len(items)

    def _he_release(self, variant: str, n: int) -> tuple[str, int]:
        """A frozen release of N human root demos plus the variant's egocentric clips."""
        ref = f"rel_he_{variant.lower()}_{n}"
        kept = [item for item in self.release_items
                if item["release_ref"] == "rel_two_table_v1" and not item["excluded"]]
        episodes = {e["episode_id"]: e for rows in self.episodes_by_dataset.values()
                    for e in rows}
        demos = [i["episode_ref"] for i in kept
                 if episodes[i["episode_ref"]]["is_root"]
                 and episodes[i["episode_ref"]]["operator_kind"] == "human"][:n]
        ego = [i["episode_ref"] for i in kept
               if episodes[i["episode_ref"]]["source_kind"] == "egocentric"
               ][:HE_EGO_CLIPS[variant]]
        assert len(demos) == n, f"chỉ có {len(demos)} demo người cho {ref}"
        items = [{"release_ref": ref, "episode_ref": e, "sample_weight": 1.0, "excluded": False,
                  "exclude_reason": None} for e in demos + ego]
        self.he_release_items += items
        self.he_releases.append(
            {"release_ref": ref, "name": f"HE {variant} N={n}",
             "parent_release_ref": "rel_two_table_v1", "split_plan_sha256": hx("split-plan-v1"),
             "status": "frozen", "manifest_sha256": hx(",".join(sorted(demos + ego))),
             "manifest_uri": f"mock://releases/he/{variant}_{n}.parquet",
             "license_summary": LICENSE, "frozen_at": ts(3, 11),
             "meta": {"items": len(items), "he_variant": variant, "n_demos": n}}
        )
        return ref, len(items)

    def experiments(self) -> None:
        experiments: list[Row] = []
        links: list[Row] = []
        checkpoints: list[Row] = []
        used = sum(1 for item in self.release_items if not item["excluded"])
        self.he_releases: list[Row] = []
        self.he_release_items: list[Row] = []
        for seed, (code, branch, hypothesis, rp, parent) in enumerate(self.EXPERIMENTS):
            params: Row = {"lr": 1e-4, "steps": 2000}
            release, episodes_used = "rel_two_table_v1", used
            if branch == "A_07":
                release, episodes_used = self._a07_release()
            if hypothesis == "HE":
                variant, n = code.removeprefix("exp_HE_").rsplit("_", 1)
                params.update(he_variant=variant, n_demos=int(n))
                release, episodes_used = self._he_release(variant, int(n))
            experiments.append(
                {"experiment_code": code, "run_plan_ref": rp, "task_id": TASK, "branch": branch,
                 "method": "PSI0", "hypothesis": hypothesis, "base_source_ref": "src_psi0_ckpt",
                 "status": "DONE", "train_seed": 100 + seed, "hyperparams": params,
                 "started_at": ts(4, 8), "finished_at": ts(5, 8)}
            )
            links.append({"experiment_code": code, "release_ref": release,
                          "mix_weight": 1.0, "episodes_used": episodes_used})
            checkpoints.append(
                {"checkpoint_ref": self.ckpt(code), "experiment_code": code,
                 "parent_checkpoint_ref": parent, "release_ref": release,
                 "method": "PSI0", "step": 2000, "weights_sha256": hx(f"weights:{code}"),
                 "uri": f"mock://checkpoints/{code}", "is_best": True, "is_latest": True,
                 "train_seed": 100 + seed, "meta": {}}
            )
        self.files["experiments.jsonl"] = experiments
        self.files["releases.jsonl"] = [*self.files["releases.jsonl"], *self.he_releases]
        self.files["release_items.jsonl"] = [
            *self.release_items, *self.draft_release_items, *self.he_release_items]
        self.files["experiment_datasets.jsonl"] = links
        self.files["checkpoints.jsonl"] = checkpoints

    def training(self) -> None:
        metrics: list[Row] = []
        for code, rp, overfit in (("exp_A", "rp_A", False), ("exp_BFAIL", "rp_BFAIL", True)):
            for step in range(0, 2000, 100):
                metrics.append(self._metric(code, rp, step, "train", overfit))
                if step % 200 == 0:
                    metrics.append(self._metric(code, rp, step, "val", overfit))
        self.files["training_metrics.jsonl"] = metrics
        config = hx("configs/eval/diagnosis/train.yaml")
        no_parent = "checkpoint không có checkpoint cha nên không có P4 để so (T7)"
        self.files["train_diagnoses.jsonl"] = [
            {"checkpoint_id": "ckpt_A", "config_sha256": config, "findings": [],
             "skipped": [{"code": "T7", "reason": no_parent}]},
            {"checkpoint_id": "ckpt_BFAIL", "config_sha256": config,
             "findings": [{"code": "T3", "start_step": 1400, "group": None, "dim": None,
                           "value": 3.0, "threshold": None, "stop_job": False}],
             "skipped": [{"code": "T7", "reason": no_parent}]},
        ]

    def _metric(self, code: str, rp: str, step: int, split: str, overfit: bool) -> Row:
        base = 1.2 * math.exp(-step / 700) + 0.15
        if split == "val":
            base = 1.25 * math.exp(-step / 800) + 0.2
            if overfit and step >= 1400:
                base += 0.05 * ((step - 1200) / 200)  # val tăng trong khi train giảm: T3
        loss = round(base + self.rng.uniform(-0.01, 0.01), 5)
        row: Row = {
            "run_plan_id": rp, "job_id": f"job_{code}", "checkpoint_id": self.ckpt(code),
            "release_id": "rel_two_table_v1", "attempt": 0, "step": step, "epoch": step // 500,
            "split": split, "loss": loss, "lr": round(1e-4 * (0.5 ** (step / 1000)), 8),
            "vlm_frozen": True, "wall_time_s": float(step) * 1.5,
        }
        if split == "train":
            row.update(grad_norm_vlm=0.0, grad_norm_action=round(self.rng.uniform(0.8, 2.5), 4))
        else:
            # Bốn trường chỉ có trên dòng val (issue #44).
            row.update(
                loss_by_group={"arm": round(loss * 1.1, 5), "hand": round(loss * 1.3, 5),
                               "base": round(loss * 0.7, 5)},
                pred_var_by_dim=[0.021, 0.018, 0.012],
                pred_std=[0.14, 0.13, 0.11],
                target_std=[0.15, 0.14, 0.12],
                loss_by_chunk_pos=[round(loss * (0.8 + 0.1 * pos), 5) for pos in range(4)],
            )
        return row

    def probes(self) -> None:
        dataset = hx("probe-set-v1")

        def p1(ckpt: str, accuracy: float) -> Row:
            return {"probe": "P1", "checkpoint_id": ckpt, "dataset_sha256": dataset,
                    "accuracy_by_question_type": {"object": accuracy, "table": accuracy - 0.02,
                                                  "step": accuracy - 0.05}}

        def p3(ckpt: str, arm: float) -> Row:
            return {"probe": "P3", "checkpoint_id": ckpt, "dataset_sha256": dataset,
                    "error_by_group": {"arm": arm, "hand": arm * 1.4, "base": arm * 0.6},
                    "error_by_chunk_pos": [arm, arm * 1.1, arm * 1.25],
                    "hand_event_offset_steps": 1.5, "out_of_limit_dims": []}

        self.files["probes.jsonl"] = [
            p1("ckpt_A", 0.93), p3("ckpt_A", 0.12),
            p1("ckpt_B", 0.94), p3("ckpt_B", 0.09),
            {"probe": "P4", "checkpoint_id": "ckpt_B", "parent_checkpoint_id": "ckpt_A",
             "p1": p1("ckpt_B", 0.94), "p3": p3("ckpt_B", 0.09)},
        ]

    # ----------------------------------------------------------- evaluation
    #: Lỗi theo mức của mỗi lượt eval: (số lượng, mã lỗi, bước hỏng). `None`
    #: ở mã là lỗi hạ tầng, bị loại khỏi mẫu số. Bốn dòng đầu của B là bốn cụm
    #: của lượt Failure → Data.
    OUTCOMES: dict[str, dict[int, list[tuple[int, str | None, int | None]]]] = {
        "B": {
            0: [(1, "L-TIMEOUT", 6), (1, None, None)],
            1: [(6, "L-GRASP", 2), (8, "L-PLACE", 5)],
            2: [(5, "L-WALK", 3), (6, "L-SLIP", 4), (1, "L-UNKNOWN", 5), (1, None, None)],
        },
        "A": {
            0: [(2, "L-GRASP", 2), (1, "L-TIMEOUT", 6), (1, None, None)],
            1: [(7, "L-GRASP", 2), (9, "L-PLACE", 5)],
            2: [(6, "L-WALK", 3), (8, "L-SLIP", 4), (2, "L-COLLIDE", 3), (1, None, None)],
        },
        # A_07: the recipe of A on 70% of the data, a little worse everywhere.
        "A_07": {
            0: [(3, "L-GRASP", 2), (1, "L-TIMEOUT", 6), (1, None, None)],
            1: [(8, "L-GRASP", 2), (10, "L-PLACE", 5)],
            2: [(7, "L-WALK", 3), (9, "L-SLIP", 4), (2, "L-COLLIDE", 3), (1, None, None)],
        },
        # B_FAIL: data collected without the failure analysis; worse than A.
        "B_FAIL": {
            0: [(3, "L-GRASP", 2), (2, "L-TIMEOUT", 6), (1, None, None)],
            1: [(9, "L-GRASP", 2), (11, "L-PLACE", 5), (1, "L-RELEASE", 6)],
            2: [(8, "L-WALK", 3), (10, "L-SLIP", 4), (2, "L-BALANCE", 3), (1, None, None)],
        },
    }

    def evaluations(self) -> None:
        evaluations, episodes = [], []
        self.eval_failures: dict[str, list[Row]] = {}
        for branch, code in (("A", "A"), ("B", "B"), ("A_07", "A07"), ("B_FAIL", "BFAIL")):
            ref = f"ev_{code}_dev"
            rows = self._eval_episodes(ref, branch)
            episodes += rows
            self.eval_failures[branch] = [
                row for row in rows if row["infra_status"] == "ok" and not row["sim_success"]
            ]
            evaluations.append(self._evaluation(ref, f"ckpt_{code}", "dev", rows))
        # HE points: only the summary. The curve needs one rate per point, not
        # the 90 episodes behind it, and 12 x 90 rows would bury the rest.
        for variant in HE_VARIANTS:
            for n in HE_SIZES:
                he = self._evaluation(f"ev_HE_{variant}_{n}_dev", f"ckpt_HE_{variant}_{n}",
                                      "dev", [])
                scored = 90 - 1
                rate = HE_BASE_RATE[n] + HE_VARIANT_LIFT[variant]
                he.update(total_episodes=90, infra_failed_count=1,
                          success_count=round(scored * rate))
                evaluations.append(he)
        holdout = self._evaluation("ev_B_holdout", "ckpt_B", "holdout", [])
        # Holdout niêm phong: chỉ ADMIN xem tới khi mở (BR-10). Số đếm của nó
        # bịa như mọi số khác; nó có mặt để FE vẽ ổ khoá, không để đọc.
        holdout.update(total_episodes=90, success_count=60, infra_failed_count=1,
                       sealed_until="2026-11-20T00:00:00Z",
                       condition_set_id="holdout90_two_table")
        evaluations.append(holdout)
        self.files["evaluations.jsonl"] = evaluations
        self.files["eval_episodes.jsonl"] = episodes

    def _evaluation(self, ref: str, ckpt: str, split: str, rows: list[Row]) -> Row:
        return {
            "evaluation_ref": ref, "checkpoint_ref": ckpt,
            "run_plan_ref": "rp_round1" if ckpt == "ckpt_B" else "rp_" + ckpt.removeprefix("ckpt_"),
            "task_id": TASK, "condition_set_id": f"{split}90_two_table", "split": split,
            "level": None, "renderer": "mujoco", "eval_mode": "sync", "scorer_version": SCORER,
            "total_episodes": len(rows),
            "success_count": sum(1 for row in rows if row["sim_success"]),
            "infra_failed_count": sum(1 for row in rows if row["infra_status"] != "ok"),
            "sealed_until": None, "started_at": ts(7, 9), "finished_at": ts(7, 15),
        }

    def _eval_episodes(self, ref: str, branch: str) -> list[Row]:
        rows: list[Row] = []
        mismatch_left = 1 if branch == "B" else 0
        for level in (0, 1, 2):
            plan: list[tuple[str | None, int | None, bool]] = []
            for count, code, step in self.OUTCOMES[branch][level]:
                plan += [(code, step, code is None)] * count
            plan += [("OK", None, False)] * (30 - len(plan))
            for offset, (code, step, infra) in enumerate(plan):
                index = level * 30 + offset
                row = self._eval_row(ref, index, level, code, step, infra)
                # Một episode B mà scorer nói trượt dù simulator nói đạt: lệch
                # nhỏ, dưới 5%, để M6 có cái để đối chiếu (§1 điểm 9).
                if mismatch_left and row["sim_success"] and level == 2:
                    row["scorer_success"] = False
                    mismatch_left -= 1
                rows.append(row)
        return rows

    def _eval_row(
        self, ref: str, index: int, level: int, code: str | None, step: int | None, infra: bool
    ) -> Row:
        episode_ref = f"ee_{ref.removeprefix('ev_')}_{index:02d}"
        row: Row = {
            "eval_episode_ref": episode_ref,
            # W13: cùng hash mà `_system_diagnoses` ghi, nên một bản ghi kiểm hệ
            # thống dạng hợp đồng nối được vào đúng episode này.
            "trace_sha256": hx(f"trace:{episode_ref}"),
            "evaluation_ref": ref, "episode_index": index,
            "condition_id": f"cond_dev_{index:02d}", "level": level,
            "episode_seed": 2000 + index, "rollout_seed": 5000 + index,
            "scorer_version": SCORER, "camera_params_hash": hx("camera-head@G0"),
            "video_uri": None, "trajectory_log_uri": None,
            "details": {"step_names": STEP_NAMES},
        }
        if infra:
            # Lỗi hạ tầng không mang kết luận về policy (03 §4.3 luật 8).
            row.update(sim_success=None, scorer_success=None, step_status=["unknown"] * 6,
                       infra_status="simulator_error" if level == 0 else "timeout",
                       first_failed_step=None, failure_code=None, failure_class=None,
                       failure_time_s=None)
            return row
        row["infra_status"] = "ok"
        if code == "OK":
            row.update(sim_success=True, scorer_success=True, step_status=["pass"] * 6,
                       first_failed_step=None, failure_code=None, failure_class=None,
                       failure_time_s=None)
            return row
        assert step is not None
        status = ["pass"] * (step - 1)
        if code == "L-UNKNOWN":
            # Thiếu tín hiệu là "chưa rõ", không phải "trượt" (spec §5.1).
            status += ["unknown"] + ["not_attempted"] * (6 - step)
            row["details"]["unknown_steps"] = {
                STEP_NAMES[step - 1]: "trace thiếu tín hiệu contact tay phải"
            }
            failed, klass = None, None
        else:
            status += ["fail"] + ["not_attempted"] * (6 - step)
            failed, klass = step, CODE_CLASS.get(str(code), STEP_CLASS[step])
        row.update(
            sim_success=False, scorer_success=False, step_status=status,
            first_failed_step=failed, failure_code=code, failure_class=klass,
            failure_time_s=round(step * 6.5 + self.rng.uniform(0, 2), 2),
            video_uri=f"mock://videos/{row['eval_episode_ref']}.mp4",
            trajectory_log_uri=f"mock://traces/{row['eval_episode_ref']}.jsonl",
        )
        return row

    # ---------------------------------------------------------- flywheel
    CLUSTERS: list[tuple[str, int, str, int, str]] = [
        # ref, bước hỏng, mã lỗi, mức, chẩn đoán
        ("clu_1", 2, "L-GRASP", 1, "HE_THONG_CONTROLLER"),
        ("clu_2", 3, "L-WALK", 2, "NGOAI_MIEN"),
        ("clu_3", 5, "L-PLACE", 1, "THIEU_VUNG_PHU"),
        ("clu_4", 4, "L-SLIP", 2, "KY_NANG_YEU"),
    ]

    def flywheel(self) -> None:
        members = {
            ref: [
                row for row in self.eval_failures["B"]
                if (row["first_failed_step"], row["failure_code"], row["level"])
                == (step, code, level)
            ]
            for ref, step, code, level, _ in self.CLUSTERS
        }
        self.files["system_diagnoses.jsonl"] = self._system_diagnoses(members)
        self.files["recommendation.json"] = {
            "recommendation_ref": "rec_round1", "run_plan_ref": "rp_round1",
            "checkpoint_ref": "ckpt_B", "evaluation_ref": "ev_B_dev", "task_id": TASK,
            "round_no": 1, "status": "AWAITING_REVIEW", "budget_usd": 400.0,
            "budget_human_minutes": 480.0, "budget_gpu_hours": 24.0,
            "started_at": ts(8, 9), "finished_at": None,
        }
        clusters, runs = [], []
        for ref, step, code, level, diagnosis in self.CLUSTERS:
            group = members[ref]
            clusters.append(
                {"cluster_ref": ref, "recommendation_ref": "rec_round1", "failed_step": step,
                 "failure_code": code, "level": level, "member_count": len(group),
                 "representative_refs": [row["eval_episode_ref"] for row in group[:5]],
                 "representative_seed": 7, "diagnosis": diagnosis, "diagnosis_source": "auto",
                 "override_reason": None, "parent_cluster_ref": None,
                 "checks": self._cluster_checks(ref), "card_uri": f"mock://cards/{ref}.html"}
            )
            runs += self._diagnostic_runs(ref, group)
        self.files["failure_clusters.jsonl"] = clusters
        self.files["diagnostic_runs.jsonl"] = runs
        self.diag_gpu_seconds = sum(run["gpu_seconds"] for run in runs)
        self.files["interventions.jsonl"] = self._interventions()
        self.files["repair_tickets.jsonl"] = [
            {"cluster_ref": "clu_1", "diagnosis": "HE_THONG_CONTROLLER",
             "title": "Sai số bám lệnh thân trên vượt τ_track ở bước gắp, mức 1",
             "detail": "R3 nổ trên cả 6 episode của cụm; kiểm cấu hình stack WBC và ánh xạ khớp",
             "status": "OPEN", "rebaseline_required": True},
        ]
        steps = [
            "chạy policy", "gán nhãn", "gom cụm", "kiểm hệ thống", "kiểm khả thi", "khoanh vùng",
            "kiểm thị giác", "kiểm vùng phủ", "chẩn đoán cụm", "đề xuất can thiệp",
            "chọn trong ngân sách", "thu dữ liệu và đo lại",
        ]
        rollouts = {1: 90, 5: sum(r["rollout_count"] for r in runs if r["step_no"] == 5),
                    6: sum(r["rollout_count"] for r in runs if r["step_no"] == 6),
                    7: sum(r["rollout_count"] for r in runs if r["step_no"] == 7)}
        self.files["flywheel_algo_steps.jsonl"] = [
            {"recommendation_ref": "rec_round1", "cluster_ref": None, "eval_episode_ref": None,
             "step_no": number, "status": "pending" if number == 12 else "done",
             "skip_reason": None, "rollout_count": rollouts.get(number, 0),
             "started_at": None if number == 12 else ts(8, 9, number * 4),
             "finished_at": None if number == 12 else ts(8, 9, number * 4 + 3),
             "detail": {"name": name}}
            for number, name in enumerate(steps, start=1)
        ]

    def _system_diagnoses(self, members: dict[str, list[Row]]) -> list[Row]:
        config = hx("configs/eval/diagnosis/system.yaml@pinned-mock")
        # Bản 0.5 (PR #146, #148): eval SIMPLE là rollout đồng bộ, và `/act`
        # đo 350–460 ms (DA-13 nhiệm vụ 11), nên mọi episode đồng bộ mang R1,
        # R2 ghi nhận mà nhãn không đổi. Số dưới là giả định trong khoảng đó.
        sync_note = (
            "rollout đồng bộ: SIMPLE chờ server rồi mới bước sim, nên độ trễ không làm "
            "hỏng được episode trong sim; ghi nhận, không quy lỗi (quyết định (a) của PO, "
            "5/11/2026)"
        )
        latency_s, slow_chunks = 0.41, 9
        recorded_sync: list[Row] = [
            {"code": "R1", "value": latency_s, "threshold": 0.10, "part": None,
             "where": "chunk 4",
             "detail": f"phân vị 99 của độ trễ chu kỳ suy luận, đơn vị giây; {sync_note}"},
            {"code": "R2", "value": float(slow_chunks), "threshold": 0.0, "part": None,
             "where": "chunk 4",
             "detail": f"{slow_chunks} chunk (trừ chunk 0) có delay_steps trên d = 6 mà RTC "
             f"của server che, lớn nhất 21 bước; {sync_note}"},
        ]
        rows: list[Row] = []
        for row in self.eval_failures["B"]:
            ref = row["eval_episode_ref"]
            measurements: Row = {
                "tracking_error_p99": {"upper": 0.04, "lower": 0.06},
                "latency_p99_s": latency_s, "sync_offset_max_s": 0.006,
            }
            findings: list[Row] = []
            skipped: list[Row] = []
            timing: str | None = "sync"
            recorded: list[Row] = recorded_sync
            diagnosis = "clean"
            if row in members["clu_1"]:
                value = round(0.14 + 0.005 * members["clu_1"].index(row), 3)
                measurements["tracking_error_p99"]["upper"] = value
                findings = [{"code": "R3", "value": value, "threshold": 0.10, "part": "upper",
                             "where": f"dòng trace {400 + row['episode_index']}",
                             "detail": "chuẩn (lệnh - đo) thân trên, phân vị 99"}]
                diagnosis = "controller"
            elif row is members["clu_2"][0]:
                measurements["sync_offset_max_s"] = 0.035
                findings = [{"code": "R4", "value": 0.035, "threshold": 0.02, "part": None,
                             "where": "dòng trace 211",
                             "detail": "lệch lớn nhất giữa t_image và t_state, giây"}]
                diagnosis = "sync"
            elif row in members["clu_3"][:2]:
                # Không có log RTC: R1, R2 không chấm được. CHƯA RÕ, không phải
                # sạch — ca chứng minh BR-12 và C17. Hai trace này ghi trước khi
                # hook nói chế độ (#148), nên `timing` để trống và R1, R2 vẫn
                # tính: trên rollout đồng bộ chúng sẽ chỉ là ghi nhận.
                timing, recorded = None, []
                del measurements["latency_p99_s"]
                no_rtc = (
                    "episode không có log RTC (`rtc.jsonl`), không đo được độ trễ và buffer"
                )
                skipped = [
                    {"code": "R1", "reason": no_rtc},
                    {"code": "R2", "reason": no_rtc},
                ]
                diagnosis = "unknown"
            rows.append(
                {"eval_episode_ref": ref, "diagnosis": diagnosis, "config_sha256": config,
                 "trace_sha256": hx(f"trace:{ref}"), "infra_status": "ok",
                 "findings": findings, "skipped": skipped, "measurements": measurements,
                 "timing": timing, "recorded": recorded, "recorded_skipped": []}
            )
        return rows

    @staticmethod
    def _cluster_checks(ref: str) -> Row:
        checks: dict[str, Row] = {
            "clu_1": {"system": {"controller": 6, "fired": ["R3"]},
                      "skipped": [{
                          "step": 5,
                          "reason": "cụm đã có chẩn đoán hệ thống; "
                          "thứ tự cố định hệ thống trước dữ liệu",
                      }]},
            "clu_2": {"system": {"clean": 4, "sync": 1},
                      "coverage": {"in_train_domain": False, "knn_distance": 2.7,
                                   "threshold": 1.5}},
            "clu_3": {"system": {"clean": 6, "unknown": 2},
                      "coverage": {"in_train_domain": True, "knn_distance": 0.8, "threshold": 1.5}},
            "clu_4": {"system": {"clean": 6},
                      "coverage": {"in_train_domain": True, "knn_distance": 0.6, "threshold": 1.5}},
        }
        return checks[ref]

    @staticmethod
    def _diagnostic_runs(ref: str, group: list[Row]) -> list[Row]:
        if ref == "clu_1":
            return []  # hệ thống trước, dữ liệu sau: cụm hệ thống không đi tiếp (§5.3)
        first = group[0]["eval_episode_ref"]
        # (bước, phép kiểm, kết quả, số rollout, giá trị, lý do bỏ qua)
        plans: dict[str, list[tuple[int, str, str, int, float | None, str | None]]] = {
            "clu_2": [(5, "feasibility", "passed", 5, 1.0, None),
                      (6, "localize", "skipped", 0, None,
                       "không khôi phục được trạng thái ở đầu bước 3 từ trace"),
                      (7, "visual", "passed", 5, 0.8, None)],
            "clu_3": [(5, "feasibility", "passed", 5, 1.0, None),
                      (6, "localize", "failed", 10, 0.2, None),
                      (7, "visual", "passed", 5, 0.8, None)],
            "clu_4": [(5, "feasibility", "passed", 5, 1.0, None),
                      (6, "localize", "failed", 10, 0.3, None),
                      (7, "visual", "passed", 5, 0.7, None)],
        }
        plan = plans[ref]
        return [
            {"cluster_ref": ref, "step_no": step, "check_name": name,
             "representative_episode_ref": first, "rollout_count": rollouts,
             "outcome": outcome, "skip_reason": reason, "value": value,
             "threshold": 0.5 if value is not None else None,
             "gpu_seconds": float(rollouts * 40)}
            for step, name, outcome, rollouts, value, reason in plan
        ]

    def _interventions(self) -> list[Row]:
        # g = n_eff / 90 × f̄, f̄ = α / (α + β) từ fix_rate_events. Chưa có
        # lượt nào khép lại nên f̄ là prior Beta(1, 1) = 0.5 (§5.3 bước 11).
        gpu, operator = self.price["pitch_v10"][0], self.price["pitch_v10"][1]

        def item(ref: str, cluster: str, kind: str, quantity: int, n: int,
                 minutes: float, gpu_hours: float, spec: Row) -> Row:
            return {"intervention_ref": ref, "recommendation_ref": "rec_round1",
                    "cluster_ref": cluster, "kind": kind, "target_quantity": quantity,
                    "unit": "episode", "spec": spec, "n_failures": n, "n_eff": min(n, 10),
                    "expected_gain_pp": round(min(n, 10) / 90 * 0.5 * 100, 3),
                    "estimated_usd": round(minutes * operator + gpu_hours * gpu, 2),
                    "estimated_human_minutes": minutes, "estimated_gpu_hours": gpu_hours,
                    "status": "PROPOSED", "approved_quantity": None, "due_at": None}

        return [
            item("iv_1", "clu_3", "SIM_AROUND_FAILURE", 40, 8, 0.0, 3.0,
                 {"tier": "S1", "step": 5, "level": 1, "radius_m": 0.05}),
            item("iv_2", "clu_3", "TELEOP_CORRECTION", 8, 8, 80.0, 0.0, {"step": 5, "level": 1}),
            item("iv_3", "clu_4", "TELEOP_CORRECTION", 6, 6, 60.0, 0.0, {"step": 4, "level": 2}),
            item("iv_4", "clu_4", "RECOVERY_DATA", 6, 6, 72.0, 0.0, {"step": 4, "level": 2}),
        ]

    def decisions(self) -> None:
        self.files["decisions.jsonl"] = [
            {"decision_ref": "dec_psi_stage4", "kind": "stage_review",
             "target_kind": "pipeline_stage_runs", "target_id": None, "measures": {"flag": 4},
             "criteria": {"qa": "qa-v1"},
             "conclusion": "FORCE_CONTINUE: 4 episode flag là lệch đồng bộ gần ngưỡng, đã xem tay",
             "reason": "lệch dưới τ_sync của bản cứng hơn; không phải lỗi bộ đọc",
             "source_action_id": None},
            {"decision_ref": "dec_kbd_stage4", "kind": "stage_review",
             "target_kind": "pipeline_stage_runs", "target_id": None, "measures": {"quarantine": 2},
             "criteria": {"qa": "qa-v1"},
             "conclusion": "APPLY_FIX_AND_RETRY: sửa giới hạn vận tốc trong bộ đọc, "
                           "chạy lại từ tầng 4",
             "reason": None, "source_action_id": None},
        ]

    # ------------------------------------------------------------- ledger
    def ledger(self) -> None:
        gpu, operator, storage, _ = self.price["pitch_v10"]
        diag_hours = round(self.diag_gpu_seconds / 3600, 3)

        def entry(ref: str, activity: str, resource: str, quantity: float, unit: str,
                  usd: float, **extra: Any) -> Row:
            row: Row = {"entry_ref": ref, "entry_kind": "ENTRY", "reverses_entry_ref": None,
                        "activity": activity, "resource_type": resource, "quantity": quantity,
                        "unit": unit, "price_book_name": "pitch_v10", "measured_usd": usd}
            row.update(extra)
            return row

        rows = [
            entry("led_psi_ingest", "ingest", "storage_gb", 12, "GB", round(12 * storage, 2),
                  dataset_code="ds_psi_teleop"),
            entry("led_kbd_teleop", "teleop", "operator_minutes", 240, "minute",
                  round(240 * operator, 2), measured_human_minutes=240.0,
                  dataset_code="ds_kbd_teleop"),
            entry("led_s1_generate", "synthetic", "gpu_hours", 4, "hour", 4 * gpu,
                  measured_gpu_hours=4.0, dataset_code="ds_synth_s1"),
            entry("led_train_A", "train", "gpu_hours", 10, "hour", 10 * gpu,
                  measured_gpu_hours=10.0, experiment_code="exp_A", branch="A"),
            entry("led_train_B", "train", "gpu_hours", 12, "hour", 12 * gpu,
                  measured_gpu_hours=12.0, experiment_code="exp_B", branch="B"),
            entry("led_train_BFAIL", "train", "gpu_hours", 9, "hour", 9 * gpu,
                  measured_gpu_hours=9.0, experiment_code="exp_BFAIL", branch="B_FAIL"),
            entry("led_eval_B", "eval", "gpu_hours", 2, "hour", 2 * gpu,
                  measured_gpu_hours=2.0, evaluation_ref="ev_B_dev", branch="B"),
            entry("led_diag_round1", "diagnosis", "gpu_hours", diag_hours, "hour",
                  round(diag_hours * gpu, 2), measured_gpu_hours=diag_hours,
                  recommendation_ref="rec_round1"),
            # Ghi trùng một lần train, rồi sửa bằng bút toán đảo (BR-06, C9).
            entry("led_train_A_dup", "train", "gpu_hours", 10, "hour", 10 * gpu,
                  measured_gpu_hours=10.0, experiment_code="exp_A", branch="A",
                  note="ghi trùng job train A"),
        ]
        rows.append(
            {**rows[-1], "entry_ref": "led_train_A_dup_rev", "entry_kind": "REVERSAL",
             "reverses_entry_ref": "led_train_A_dup", "quantity": -10, "measured_usd": -10 * gpu,
             "measured_gpu_hours": -10.0, "note": "đảo bút toán ghi trùng"}
        )
        # Ước tính của bốn can thiệp: cùng dòng với cột thực đo để trống (R5),
        # và gắn khuyến nghị lẫn can thiệp (C10).
        for intervention in self.files["interventions.jsonl"]:
            assert isinstance(intervention, dict)
            rows.append(
                {"entry_ref": f"led_est_{intervention['intervention_ref']}", "entry_kind": "ENTRY",
                 "reverses_entry_ref": None, "activity": "intervention_estimate",
                 "resource_type": (
                     "gpu_hours" if intervention["estimated_gpu_hours"] else "operator_minutes"
                 ),
                 "quantity": intervention["target_quantity"], "unit": "episode",
                 "price_book_name": "pitch_v10", "measured_usd": None,
                 "estimated_usd": intervention["estimated_usd"],
                 "estimated_human_minutes": intervention["estimated_human_minutes"],
                 "estimated_gpu_hours": intervention["estimated_gpu_hours"],
                 "recommendation_ref": "rec_round1",
                 "intervention_ref": intervention["intervention_ref"],
                 "cluster_ref": intervention["cluster_ref"]}
            )
        self.files["ledger.jsonl"] = rows

    # ------------------------------------------------------------ defects
    #: Hai cặp bản sao của bộ chấm: (nhóm, bản có lỗi, bản sạch, số đơn vị
    #: của bản sạch, tên danh sách lỗi cấy). Đơn vị là episode với nhóm dữ
    #: liệu, job với log.
    BENCH_GROUPS: list[tuple[str, str, str, int, str]] = [
        ("data", "bench_kbd_teleop", "bench_kbd_teleop_clean", 10, "DEFECTS"),
        ("logs", "bench_logs_bfail", "bench_logs_bfail_clean", 12, "LOG_DEFECTS"),
    ]

    def defects(self) -> None:
        """Đáp án (`defect_manifest.json`) và kết quả chấm (`bench_result.json`).

        Kết quả theo đúng dạng `da31-2` mà `flywheel.eval.agentqa.bench.report`
        ghi; `web/tests/test_bench_result.py` so khoá của nó với hàm thật.
        """
        self.files["defect_manifest.json"] = [
            {"dataset_id": copy, "seed": 17 + index,
             "defects": [{"target_ref": target, "code": code, "parameters": params}
                         for target, code, params in getattr(self, defects)]}
            for index, (_, copy, _, _, defects) in enumerate(self.BENCH_GROUPS)
        ]
        groups = [self._bench_group(*spec) for spec in self.BENCH_GROUPS]
        hashes = {
            copy: hx(f"manifest:{copy}")
            for _, injected, clean, _, _ in self.BENCH_GROUPS for copy in (injected, clean)
        }
        self.files["bench_result.json"] = {
            "bench_version": "da31-2",
            "measured_on": "injected defects (DA-27), not natural defects",
            "false_alarm_on_clean": (
                "upper bound (cận trên): the clean copy still holds the real data's own"
                " defects, and a report of one of them counts as a false alarm"
            ),
            "created_at": "2026-11-12T03:00:00+00:00",
            "manifest_sha256": dict(sorted(hashes.items())),
            "inputs": {"spec_sha256": hx("bench-spec"), "train_config_sha256": hx("train-cfg"),
                       "system_config_sha256": hx("system-cfg"),
                       "ledger": "g0-DA-31-20261112/job_bench_01"},
            "groups": groups,
        }

    @staticmethod
    def _rate(hit: int, total: int) -> Row:
        return {"hit": hit, "total": total, "value": hit / total if total else None}

    def _bench_group(self, group: str, injected: str, clean: str, units: int,
                     attr: str) -> Row:
        defects: list[tuple[str, str, dict[str, Any]]] = getattr(self, attr)
        kinds = [(str(params["kind"]), code) for _, code, params in defects]
        injected_codes = {code for _, code in kinds}
        # Agent báo nhầm một D2 trên bản có lỗi (precision D2 của agent 1/2) và
        # một D4 trên bản sạch (báo nhầm 1/10, cận trên). Chỉ ở nhóm dữ liệu.
        false_on_injected = [("ep_bench_08", "D2")] if group == "data" else []
        false_on_clean = [("ep_bench_09", "D4")] if group == "data" else []
        layers: Row = {}
        for layer, caught, seconds in (
            ("code", self.CODE_CATCHES, (4.2, 3.9) if group == "data" else (2.1, 2.0)),
            ("agent", self.AGENT_CATCHES, (95.0, 88.0) if group == "data" else (140.0, 131.0)),
        ):
            recall = {kind: self._rate(int(code in caught), 1) for kind, code in kinds}
            wrong = false_on_injected if layer == "agent" else []
            clean_reports = false_on_clean if layer == "agent" else []
            codes = sorted(injected_codes | {code for _, code in wrong})
            precision = {}
            for code in codes:
                hit = int(code in caught and code in injected_codes)
                precision[code] = self._rate(hit, hit + sum(1 for _, c in wrong if c == code))
            layers[layer] = {
                "recall_by_kind": recall,
                "masked_by_kind": {kind: 0 for kind, _ in kinds},
                "recall_unmasked_by_kind": recall,
                "precision_by_code": precision,
                "false_alarm_on_clean": {**self._rate(len(clean_reports), units),
                                         "bound": "upper (cận trên)"},
                "false_alarm_not_a_unit": [],
                "clean_reports": [list(pair) for pair in clean_reports],
                "natural": [],
                "seconds_to_report": {injected: seconds[0], clean: seconds[1]},
                "uncoded": {},
            }
        split = []
        for kind, code in kinds:
            by_code = int(code in self.CODE_CATCHES)
            alone = int(code in self.AGENT_CATCHES)
            adds = int(alone and not by_code)
            split.append({"kind": kind, "code": code, "injected": 1, "by_code": by_code,
                          "agent_adds": adds, "together": by_code + adds, "agent_alone": alone})
        hits = [(target, code) for target, code, _ in defects if code in self.AGENT_CATCHES]
        # Phát hiện sai đứng hạng 5 trong báo cáo: bốn phát hiện đúng đứng trên
        # nó, hai đứng dưới (thứ hạng đúng 4/6 cặp). Phát hiện cuối chưa ai duyệt.
        ordered = hits[:4] + false_on_injected + hits[4:]
        findings: list[Row] = []
        for rank, (target, code) in enumerate(ordered, start=1):
            label = "false" if (target, code) in false_on_injected else "hit"
            review = "unreviewed" if rank == len(ordered) else (
                "agree" if label == "hit" else "override")
            findings.append({
                "copy": injected, "report_id": f"r-{injected}",
                "finding_id": f"r-{injected}-f{rank - 1}", "rank": rank, "target": target,
                "code": code, "label": label, "review": review,
                "reason": "kỹ sư: không phải lỗi" if review == "override" else "",
            })
        for rank, (target, code) in enumerate(false_on_clean, start=1):
            findings.append({
                "copy": clean, "report_id": f"r-{clean}", "finding_id": f"r-{clean}-f{rank - 1}",
                "rank": rank, "target": target, "code": code, "label": "clean",
                "review": "unreviewed", "reason": "",
            })
        trues = [f["rank"] for f in findings if f["copy"] == injected and f["label"] == "hit"]
        falses = [f["rank"] for f in findings if f["copy"] == injected and f["label"] == "false"]
        pairs = [(t, f) for t in trues for f in falses]
        reviews: dict[str, dict[str, int]] = {}
        for f in findings:
            bucket = reviews.setdefault(f["label"], {})
            bucket[f["review"]] = bucket.get(f["review"], 0) + 1
        return {
            "group": group,
            "injected_copy": injected,
            "clean_copy": clean,
            "defects": len(defects),
            "layers": layers,
            "split": split,
            "agent_quality": {
                "ranking": self._rate(sum(1 for t, f in pairs if t < f), len(pairs)),
                "reviews": reviews,
                "findings": findings,
            },
        }


README = """# Bộ mock kịch bản demo 17/11

**Dữ liệu mẫu, không phải số đo.** Mọi con số trong thư mục này là bịa, sinh
bằng `web/mock/generate.py` với một seed cố định. Không dòng nào đến từ một
lần chạy thật của lõi, của SIMPLE hay của Ψ₀.

Nạp bằng `fwsync import --from mock/demo-17-11 --origin mock`, để mọi bản ghi
mang `origin = 'mock'` và FE dán nhãn "mock" lên từng bản ghi (DESIGN.md
§4.4b). Đừng nạp thư mục này với `--origin core`.

Đừng sửa tay. Sửa `web/mock/generate.py` rồi chạy
`uv run python -m web.mock.generate`; `web/tests/test_mock.py` so thư mục này
với bản sinh lại và đỏ nếu lệch.

## Câu chuyện nó kể

- Năm lô: psi-data teleop, teleop bàn phím, synthetic S1, mẫu EgoDex, và một
  bản sao chấm Agent QA/QC có 10 lỗi cấy, dừng ở tầng 4. Code bắt 6/10, agent
  bắt thêm 2.
- Bốn thí nghiệm nhánh A, A_07, B, B_FAIL. B_FAIL có T3. B tốt nhất, B_FAIL
  kém hơn A.
- Lưới HE: V_EGO, V_EGO10, V_NOEGO × N ∈ {10, 20, 40, 80}. Mỗi điểm train
  trên release riêng có đúng N demo gốc của người (cộng 20, 10 hoặc 0 clip
  egocentric), nên `n_demos` đếm được từ dữ liệu. Lượt eval của điểm HE chỉ
  có số tổng, không có episode.
- Bốn lượt eval dev có episode (A, A_07, B, B_FAIL), mỗi lượt 90 episode, 2
  episode lỗi hạ tầng bị loại khỏi mẫu số. Một holdout niêm phong tới 20/11.
- Một lượt Failure → Data trên checkpoint B: bốn cụm, bốn chẩn đoán. Hai cụm là
  lỗi hệ thống và ngoài miền, không tốn ngân sách dữ liệu; hai cụm còn lại mới
  cần thu thêm.

## Giả định của bộ mock, không phải của hệ thống

- **Bản tham chiếu camera coi như đã ghim.** `configs/eval/diagnosis/system.yaml`
  thật để `reference_sha256: null` tới G0, nên chạy DA-13 thật hôm nay thì R5
  không chấm được và mọi episode ra `unknown`. Bộ mock giả như G0 đã xong để
  kể đủ câu chuyện; `config_sha256` của nó trỏ một cấu hình không có thật.
- **Video egocentric dùng `kind = teleop_demo`** với `source_kind = egocentric`
  và `is_root = false`. Hợp đồng chưa có `kind` riêng cho video người, và nó
  không phải demo robot nên không tính vào `r_demo`.
- **Tỉ lệ sửa được là prior Beta(1, 1) = 0.5**, vì chưa lượt nào khép lại; lợi
  ích kỳ vọng của bốn can thiệp tính theo đó.
- **Episode nạp vào gắn RunPlan `rp_ingest_g0`** (`purpose = g0_repro`).
  `Episode.run_plan_id` bắt buộc trong hợp đồng, mà `purpose` chưa có giá trị
  riêng cho việc nạp dữ liệu.
- **Bảng giá** là bốn kịch bản độ nhạy bịa; bút toán tính theo `pitch_v10`.
"""


def render() -> dict[str, str]:
    """Nội dung từng file, đúng bytes mà lệnh này sẽ ghi."""
    files = Mock().build()
    out: dict[str, str] = {}
    for name, content in sorted(files.items()):
        if name.endswith(".jsonl"):
            assert isinstance(content, list)
            out[name] = "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in content
            )
        else:
            out[name] = json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    # Như `write_bench` của DA-31: hash của đúng chuỗi JSON, trong file khoá.
    bench = out["bench_result.json"]
    out["bench_result.sha256"] = hashlib.sha256(bench.encode("utf-8")).hexdigest() + "\n"
    out["README.md"] = README
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rendered = render()
    for stale in OUT.iterdir():
        if stale.is_file() and stale.name not in rendered:
            stale.unlink()
    for name, text in rendered.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(rendered)} file -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
