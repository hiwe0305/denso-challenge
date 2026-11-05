"""Bốn việc của `fwsync`: import, export, verify, fake-core (DESIGN.md §5.5).

Mỗi việc là một hàm thuần trên một `Sink`, nên `cli.py` chỉ phân tích tham số
và in kết quả, còn test chạy được không cần Postgres.

Luật xuyên suốt: **một dòng sai không làm đổ cả lần nạp.** Artifact nào không
ánh xạ được thì bị từ chối, lý do vào `SyncResult.errors`, và bộ nạp chạy
tiếp dòng khác (§2, lưới an toàn). Hình dạng `errors` khớp `sync_runs.errors`:
`[{bảng, ref, code, message}]`.

Thứ tự nạp theo khoá ngoại, không theo thứ tự file: `episodes` cần `datasets`
trước, `episode_qa_reports` cần `episodes` trước. `IMPORT_ORDER` khai thứ tự
đó một lần.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from web.fwsync import actions as log
from web.fwsync.mapping import (
    DatasetLookup,
    MappingError,
    map_defect_manifest,
    map_episode,
    map_probe_result,
    map_qa_report,
    map_train_diagnosis,
    map_training_metric,
)
from web.fwsync.sink import JsonlSink, Sink
from web.fwsync.source import TOLERANT_TABLES, Record, SourceScan, scan, tolerant_row

#: Thứ tự nạp theo khoá ngoại. Bảng không có trong danh sách được nạp sau
#: cùng, theo tên: chúng là bảng chưa ai khai thứ tự, và nạp sau thì an toàn
#: hơn nạp trước.
IMPORT_ORDER: tuple[str, ...] = (
    "sources",
    "price_books",
    "run_plans",
    "datasets",
    "pipeline_stage_runs",
    "releases",
    "episodes",
    "release_items",
    "episode_qa_reports",
    "experiments",
    "experiment_datasets",
    "model_checkpoints",
    "training_metrics",
    "train_diagnoses",
    "probe_results",
    "sim_evaluations",
    "eval_episodes",
    "system_diagnoses",
    "flywheel_recommendations",
    "failure_clusters",
    "diagnostic_runs",
    "interventions",
    "fix_rate_events",
    "repair_tickets",
    "flywheel_algo_steps",
    "decisions",
    "cost_ledger_entries",
    "defect_manifests",
    "defect_scores",
)

#: Cột được nhận cho bảng đi đường khoan dung. Giữ ở đây thay vì đọc từ
#: schema.sql vì bộ nạp phải chạy được khi chưa có database;
#: `test_loader_matches_schema.py` so hai bên để chúng không lệch.
TOLERANT_COLUMNS: dict[str, frozenset[str]] = {
    "sources": frozenset(
        {
            "source_ref", "url", "repo", "revision", "sha256", "license",
            "downloaded_at", "kind", "clean_for_main_task", "provenance",
        }
    ),
    "datasets": frozenset(
        {
            "dataset_code", "source_ref", "source_kind", "source_detail",
            "data_class", "license", "status", "has_seeded_faults",
            "episode_count", "note",
        }
    ),
    "releases": frozenset(
        {
            "release_ref", "name", "parent_release_ref", "split_plan_sha256",
            "status", "manifest_sha256", "manifest_uri", "license_summary",
            "frozen_at", "meta",
        }
    ),
    "pipeline_stage_runs": frozenset(
        {
            "dataset_code", "stage_number", "attempt_no", "is_current", "status",
            "qa_code_decision", "qa_agent_verdict", "qa_agent_report",
            "started_at", "finished_at", "log_uri", "metrics",
        }
    ),
    "release_items": frozenset(
        {"release_ref", "episode_ref", "sample_weight", "excluded", "exclude_reason"}
    ),
    "run_plans": frozenset(
        {
            "run_plan_ref", "purpose", "branch", "method", "task_id", "lock_uri",
            "config_sha256", "frozen_at", "seed_range", "meta",
        }
    ),
    "experiments": frozenset(
        {
            "experiment_code", "run_plan_ref", "task_id", "branch", "method",
            "hypothesis", "base_source_ref", "status", "train_seed",
            "hyperparams", "started_at", "finished_at",
        }
    ),
    "model_checkpoints": frozenset(
        {
            "checkpoint_ref", "experiment_code", "parent_checkpoint_ref",
            "release_ref", "method", "step", "weights_sha256", "uri",
            "is_best", "is_latest", "train_seed", "meta",
        }
    ),
    "sim_evaluations": frozenset(
        {
            "evaluation_ref", "checkpoint_ref", "run_plan_ref", "task_id", "condition_set_id",
            "split", "level", "renderer", "eval_mode", "scorer_version",
            "total_episodes", "success_count", "infra_failed_count",
            "sealed_until", "started_at", "finished_at",
        }
    ),
    "eval_episodes": frozenset(
        {
            "eval_episode_ref", "evaluation_ref", "episode_index", "condition_id", "level",
            "episode_seed", "rollout_seed", "scorer_version", "sim_success",
            "scorer_success", "infra_status", "step_status",
            "first_failed_step", "failure_code", "failure_class",
            "failure_time_s", "camera_params_hash", "video_uri",
            "trajectory_log_uri", "details",
        }
    ),
    "system_diagnoses": frozenset(
        {
            "eval_episode_ref", "diagnosis", "config_sha256", "trace_sha256",
            "infra_status", "findings", "skipped", "measurements",
        }
    ),
    "defect_scores": frozenset(
        {
            "manifest_ref", "scorer_version", "detector", "agent_model", "code",
            "tp", "fp", "fn", "false_alarm_rate", "latency_s",
        }
    ),
    "experiment_datasets": frozenset(
        {"experiment_code", "release_ref", "mix_weight", "episodes_used"}
    ),
    "price_books": frozenset(
        {"name", "sha256", "rates", "cell_hour_usd", "effective_from", "note"}
    ),
    "flywheel_recommendations": frozenset(
        {
            "recommendation_ref", "run_plan_ref", "checkpoint_ref", "evaluation_ref",
            "task_id", "round_no", "status", "budget_usd", "budget_human_minutes",
            "budget_gpu_hours", "started_at", "finished_at",
        }
    ),
    "failure_clusters": frozenset(
        {
            "cluster_ref", "recommendation_ref", "failed_step", "failure_code", "level",
            "member_count", "representative_refs", "representative_seed",
            "diagnosis", "diagnosis_source", "override_reason",
            "parent_cluster_ref", "checks", "card_uri",
        }
    ),
    "diagnostic_runs": frozenset(
        {
            "cluster_ref", "step_no", "check_name", "representative_episode_ref",
            "rollout_count", "outcome", "skip_reason", "value", "threshold",
            "gpu_seconds",
        }
    ),
    "interventions": frozenset(
        {
            "intervention_ref", "recommendation_ref", "cluster_ref", "kind",
            "target_quantity", "unit", "spec", "n_failures", "n_eff",
            "expected_gain_pp", "estimated_usd", "estimated_human_minutes",
            "estimated_gpu_hours", "status", "approved_quantity", "due_at",
            # `dataset_code` không phải cột của bảng; bộ nạp đọc nó để dựng
            # bảng tra của W12 rồi bỏ. Khai ở đây để nó không bị báo là
            # trường lạ trên mỗi lần nạp.
            "dataset_code",
        }
    ),
    "fix_rate_events": frozenset(
        {
            "intervention_kind", "cluster_ref", "intervention_ref", "failure_code",
            "failure_class", "n_conditions", "p_parent", "p_candidate",
            "fixed_count",
        }
    ),
    "repair_tickets": frozenset(
        {
            "cluster_ref", "diagnosis", "title", "detail", "status",
            "rebaseline_required",
        }
    ),
    "flywheel_algo_steps": frozenset(
        {
            "recommendation_ref", "cluster_ref", "eval_episode_ref", "step_no",
            "status", "skip_reason", "rollout_count", "started_at",
            "finished_at", "detail",
        }
    ),
    "decisions": frozenset(
        {
            "decision_ref", "kind", "target_kind", "target_id", "measures",
            "criteria", "conclusion", "reason", "source_action_id",
        }
    ),
    "cost_ledger_entries": frozenset(
        {
            "entry_ref", "entry_kind", "reverses_entry_ref", "activity",
            "resource_type", "quantity", "unit", "price_book_name",
            "estimated_usd", "measured_usd", "estimated_human_minutes",
            "measured_human_minutes", "estimated_gpu_hours", "measured_gpu_hours",
            "dataset_code", "experiment_code", "evaluation_ref",
            "recommendation_ref", "intervention_ref", "cluster_ref",
            "run_plan_ref", "branch", "job_id", "operator_code", "note",
        }
    ),
}


@dataclass
class SyncResult:
    """Kết quả một lần chạy, đúng hình dạng một dòng `sync_runs`."""

    direction: str
    source_dir: str
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    unknown_fields: dict[str, list[str]] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """`ok`, `partial` hay `failed`, đúng CHECK của bảng `sync_runs`.

        Có lỗi mà vẫn báo `ok` là cách che mất dòng bị từ chối, nên `ok` đòi
        `errors` rỗng.
        """
        if not self.errors:
            return "ok"
        if any(count["inserted"] or count["updated"] for count in self.counts.values()):
            return "partial"
        return "failed"

    def as_sync_run(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "source_dir": self.source_dir,
            "counts": self.counts,
            "errors": self.errors,
            "status": self.status,
        }


ORIGINS = ("core", "mock")


@dataclass(frozen=True)
class ExperimentLookup:
    """Cách suy ra thí nghiệm của một dòng telemetry hay chẩn đoán train.

    `TrainingMetric` và `TrainDiagnosis` của hợp đồng không nói thuộc thí
    nghiệm nào, và hợp đồng cấm trường lạ, nên không thể bắt lõi gắn thêm một
    `experiment_code`. Hai trường chúng có sẵn là đủ để tra:

    * ``by_run_plan`` — ``TrainingMetric.run_plan_id`` → thí nghiệm. Một thí
      nghiệm của nhánh là một RunPlan đóng băng (03 §4.3).
    * ``by_checkpoint`` — ``checkpoint_id`` → thí nghiệm sinh ra checkpoint đó.

    Giống `DatasetLookup` của W12: tra không ra thì từ chối dòng, không gán
    vào một thí nghiệm mặc định.
    """

    by_run_plan: dict[str, str]
    by_checkpoint: dict[str, str]

    def for_metric(self, payload: Any, where: str) -> str:
        run_plan = payload.get("run_plan_id") if isinstance(payload, dict) else None
        checkpoint = payload.get("checkpoint_id") if isinstance(payload, dict) else None
        if run_plan in self.by_run_plan:
            return self.by_run_plan[run_plan]
        if checkpoint in self.by_checkpoint:
            return self.by_checkpoint[checkpoint]
        raise MappingError(
            f"{where}: không suy được thí nghiệm từ run_plan_id={run_plan!r} hay "
            f"checkpoint_id={checkpoint!r}; cần experiments.jsonl và checkpoints.jsonl "
            f"cùng thư mục"
        )

    def for_diagnosis(self, payload: Any, where: str) -> str:
        checkpoint = payload.get("checkpoint_id") if isinstance(payload, dict) else None
        if checkpoint in self.by_checkpoint:
            return self.by_checkpoint[checkpoint]
        raise MappingError(
            f"{where}: không suy được thí nghiệm từ checkpoint_id={checkpoint!r}; "
            f"cần checkpoints.jsonl cùng thư mục"
        )


@dataclass(frozen=True)
class Lookups:
    """Mọi bảng tra một lần nạp cần, dựng từ chính các artifact vừa đọc."""

    dataset: DatasetLookup
    experiment: ExperimentLookup


def run_import(source_dir: Path, sink: Sink, origin: str = "core") -> SyncResult:
    """Nạp một thư mục artifact vào sink. Chạy lại cho cùng kết quả.

    `origin` đóng dấu lên **mọi** dòng: `mock` cho bộ mock, `core` cho output
    thật của lõi. Đó là thuộc tính của nguồn, không của từng artifact, nên nó
    là tham số chứ không phải trường đọc từ file: một artifact thật lỡ mang
    `origin: mock` không được làm FE dán nhãn sai (DESIGN.md §4.4b).

    Hai thứ hợp đồng không mang được tra từ chính các artifact vừa đọc: lô
    của một episode (W12) và thí nghiệm của một dòng telemetry.
    """
    if origin not in ORIGINS:
        raise ValueError(f"origin `{origin}` không có; chỉ {ORIGINS}")
    found: SourceScan = scan(source_dir)
    result = SyncResult(direction="import", source_dir=str(source_dir), ignored=found.ignored)
    lookups = Lookups(dataset=_dataset_lookup(found), experiment=_experiment_lookup(found))
    loaded_episodes: set[str] = set()

    for table in _ordered(found.tables):
        for record in found.by_table(table):
            try:
                rows = _map(record, lookups, loaded_episodes)
            except (MappingError, ValueError) as error:
                result.errors.append(_error(record, error))
                if isinstance(sink, JsonlSink):
                    sink.reject(record.table)
                continue
            for target, row in rows:
                unknown = row.pop("__unknown__", None)
                if unknown:
                    result.unknown_fields.setdefault(target, [])
                    for name in unknown:
                        if name not in result.unknown_fields[target]:
                            result.unknown_fields[target].append(name)
                row["origin"] = origin
                sink.write(target, row)
                if target == "episodes":
                    # Báo cáo QA chỉ nhận episode đã nạp thật, nên một episode
                    # bị từ chối kéo theo báo cáo của nó thay vì để một dòng
                    # QA trỏ vào khoảng trống.
                    loaded_episodes.add(row["episode_ref"])

    sink.commit()
    result.counts = sink.counts()
    return result


def _ordered(tables: list[str]) -> list[str]:
    known = [table for table in IMPORT_ORDER if table in tables]
    rest = sorted(table for table in tables if table not in IMPORT_ORDER)
    return known + rest


def _dataset_lookup(found: SourceScan) -> DatasetLookup:
    return DatasetLookup(
        by_source=_pairs(found, "datasets", "source_ref", "dataset_code"),
        by_intervention=_pairs(found, "interventions", "intervention_ref", "dataset_code"),
    )


def _experiment_lookup(found: SourceScan) -> ExperimentLookup:
    return ExperimentLookup(
        by_run_plan=_pairs(found, "experiments", "run_plan_ref", "experiment_code"),
        by_checkpoint=_pairs(found, "model_checkpoints", "checkpoint_ref", "experiment_code"),
    )


def _pairs(found: SourceScan, table: str, key: str, value: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for record in found.by_table(table):
        if isinstance(record.payload, dict):
            left, right = record.payload.get(key), record.payload.get(value)
            if left and right:
                pairs[str(left)] = str(right)
    return pairs


def _map(
    record: Record, lookups: Lookups, loaded_episodes: set[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Một artifact thành một hoặc nhiều dòng, kèm bảng đích của từng dòng."""
    table = record.table
    if table == "episodes":
        return [("episodes", map_episode(record.payload, lookups.dataset))]
    if table == "episode_qa_reports":
        return [("episode_qa_reports", map_qa_report(record.payload, loaded_episodes))]
    if table == "training_metrics":
        experiment = lookups.experiment.for_metric(record.payload, record.where)
        return [("training_metrics", map_training_metric(record.payload, experiment))]
    if table == "train_diagnoses":
        experiment = lookups.experiment.for_diagnosis(record.payload, record.where)
        diagnosis = map_train_diagnosis(record.payload, experiment)
        return [(target, row) for target, rows in diagnosis.items() for row in rows]
    if table == "probe_results":
        return [("probe_results", map_probe_result(record.payload))]
    if table == "defect_manifests":
        manifest = map_defect_manifest(record.payload)
        head: dict[str, Any] = manifest["manifest"]
        rows: list[tuple[str, dict[str, Any]]] = [("defect_manifests", head)]
        for item in manifest["items"]:
            rows.append(("defect_items", {"manifest_ref": head["manifest_ref"], **item}))
        return rows
    if table in TOLERANT_TABLES:
        allowed = TOLERANT_COLUMNS.get(table)
        if allowed is None:
            raise MappingError(
                f"{record.where}: bảng `{table}` đi đường khoan dung nhưng chưa khai "
                f"cột được nhận trong TOLERANT_COLUMNS"
            )
        row, unknown = tolerant_row(record.payload, allowed, record.where)
        if unknown:
            row["__unknown__"] = unknown
        return [(table, row)]
    raise MappingError(f"{record.where}: chưa có mapper cho bảng `{table}`")


def _error(record: Record, error: Exception) -> dict[str, Any]:
    return {
        "table": record.table,
        "ref": record.where,
        "code": type(error).__name__,
        "message": str(error),
    }


# ---------------------------------------------------------------------------
# export · human_actions đang PENDING → artifact trong outbox
# ---------------------------------------------------------------------------


def run_export(actions: list[dict[str, Any]], outbox: Path) -> SyncResult:
    """Xuất các hành động đang PENDING thành artifact trong outbox (§3.2).

    `actions` truyền vào thay vì truy vấn, để hàm này thuần và test được. Mỗi
    artifact mang `source_action_id`: lõi phải chép trường đó sang artifact
    kết quả, nếu không `fwsync import` không biết hành động nào đã được áp
    dụng (W7). Đây là chỗ duy nhất trường đó được đặt.
    """
    result = SyncResult(direction="export", source_dir=str(outbox))
    outbox.mkdir(parents=True, exist_ok=True)
    written = 0
    for action in actions:
        action_id = action.get("id")
        kind = action.get("action_kind")
        if not action_id or not kind:
            result.errors.append(
                {
                    "table": "human_actions",
                    "ref": str(action_id),
                    "code": "MappingError",
                    "message": "hành động thiếu `id` hoặc `action_kind`",
                }
            )
            continue
        artifact = {
            "source_action_id": action_id,
            "action_kind": kind,
            "target_kind": action.get("target_kind"),
            "target_id": action.get("target_id"),
            "payload": action.get("payload", {}),
            "reason": action.get("reason"),
        }
        path = outbox / f"{kind.lower()}-{action_id}.json"
        path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written += 1
    result.counts = {
        "human_actions": {
            "inserted": written,
            "updated": 0,
            "rejected": len(result.errors),
        }
    }
    return result


# ---------------------------------------------------------------------------
# verify · so DB với nguồn, không tự sửa
# ---------------------------------------------------------------------------


def run_verify(source_dir: Path, loaded: dict[str, int]) -> SyncResult:
    """So số dòng giữa nguồn và những gì đã nạp. Báo chênh, **không tự sửa**.

    Tự sửa là cách một lỗi của bộ nạp biến thành một con số sai mà không ai
    truy được (§9.4, "không bao giờ sửa số trong DB bằng tay").
    """
    found = scan(source_dir)
    result = SyncResult(direction="verify", source_dir=str(source_dir), ignored=found.ignored)
    in_source: dict[str, int] = {}
    for record in found.records:
        in_source[record.table] = in_source.get(record.table, 0) + 1
    for table in sorted(set(in_source) | set(loaded)):
        expected = in_source.get(table, 0)
        actual = loaded.get(table, 0)
        result.counts[table] = {"inserted": actual, "updated": 0, "rejected": 0}
        if expected != actual:
            result.errors.append(
                {
                    "table": table,
                    "ref": str(source_dir),
                    "code": "CountMismatch",
                    "message": f"nguồn có {expected} dòng, đã nạp {actual}",
                }
            )
    return result


# ---------------------------------------------------------------------------
# fake-core · lõi giả, để nghiệm thu mốc M4 khi lõi thật chưa sẵn sàng
# ---------------------------------------------------------------------------

#: Hành động nào sinh artifact kết quả gì. Lõi thật làm nhiều hơn thế; lõi giả
#: chỉ đủ để vòng ghi end-to-end chạy được và FE thấy trạng thái đổi.
FAKE_CORE_REPLIES: dict[str, str] = {
    "RECOMMENDATION_DECISION": "decisions",
    "DIAGNOSIS_OVERRIDE": "decisions",
    "HOLDOUT_UNSEAL": "decisions",
    "STAGE_REVIEW": "decisions",
    "EXPERIMENT_SUBMIT": "experiments",
    "INTAKE_SUBMIT": "datasets",
}


def run_fake_core(outbox: Path, destination: Path) -> SyncResult:
    """Đọc outbox, sinh artifact kết quả mang `source_action_id` (Phụ lục C).

    Đây **không** phải lõi. Nó tồn tại để chứng minh vòng ghi khép lại: bấm
    duyệt → artifact trong outbox → kết quả → `fwsync import` thấy
    `source_action_id` và đánh dấu hành động là APPLIED. Thiếu nó thì mốc M4
    phải đợi lõi thật.
    """
    result = SyncResult(direction="import", source_dir=str(outbox))
    destination.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in sorted(outbox.glob("*.json")):
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            result.errors.append(
                {
                    "table": "human_actions",
                    "ref": path.name,
                    "code": type(error).__name__,
                    "message": str(error),
                }
            )
            continue
        kind = artifact.get("action_kind")
        action_id = artifact.get("source_action_id")
        target = FAKE_CORE_REPLIES.get(str(kind))
        if target is None or not action_id:
            result.errors.append(
                {
                    "table": "human_actions",
                    "ref": path.name,
                    "code": "MappingError",
                    "message": f"lõi giả chưa trả lời `{kind}`",
                }
            )
            continue
        reply = {
            # Trường này là cả lý do lõi giả tồn tại: nó nối kết quả về hành
            # động đã sinh ra nó.
            "source_action_id": action_id,
            "decision_ref": f"dec_fake_{action_id}",
            "kind": _decision_kind(str(kind)),
            "target_kind": artifact.get("target_kind"),
            "target_id": artifact.get("target_id"),
            "conclusion": f"lõi giả đã áp dụng {kind}",
            "reason": artifact.get("reason"),
        }
        # Same layout as the core, `<table>/part-<id>.jsonl`: `table_of` reads the
        # table from the folder. A flat `decisions-<id>.jsonl` matched no table,
        # so `fwsync import` skipped every reply and nothing became APPLIED.
        folder = destination / target
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"part-{action_id}.jsonl").write_text(
            json.dumps(reply, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written += 1
    result.counts = {
        "decisions": {"inserted": written, "updated": 0, "rejected": len(result.errors)}
    }
    return result


@dataclass
class CycleResult:
    """One pass of the write loop in sink mode (`POST /sync/run`, §5.5)."""

    exported: list[str]
    applied: list[str]
    export: SyncResult
    fake_core: SyncResult | None
    imported: SyncResult | None

    @property
    def status(self) -> str:
        parts = [r for r in (self.export, self.fake_core, self.imported) if r is not None]
        if all(r.status == "ok" for r in parts):
            return "ok"
        return "partial" if self.exported or self.applied else "failed"


def run_cycle(
    actions: Path,
    outbox: Path,
    inbox: Path,
    sink: Sink,
    *,
    fake_core: bool,
    origin: str = "core",
) -> CycleResult:
    """export → (fake core) → import the inbox → mark what came back APPLIED.

    Without the fake core this exports and imports whatever the real core has
    put in the inbox; with it the loop closes on one machine (Appendix C).
    """
    waiting = log.pending(actions)
    export = run_export(waiting, outbox)
    written = {
        str(row["id"]) for row in waiting
        if (outbox / f"{str(row['action_kind']).lower()}-{row['id']}.json").exists()
    }
    exported = log.mark(actions, sorted(written), "EXPORTED")
    replies = run_fake_core(outbox, inbox) if fake_core else None
    imported: SyncResult | None = None
    applied: list[str] = []
    if inbox.is_dir():
        imported = run_import(inbox, sink, origin=origin)
        applied = log.mark(actions, log.answered_ids(scan(inbox).records), "APPLIED")
    return CycleResult(exported, applied, export, replies, imported)


def _decision_kind(action_kind: str) -> str:
    return {
        "RECOMMENDATION_DECISION": "plan_review",
        "DIAGNOSIS_OVERRIDE": "diagnosis_override",
        "HOLDOUT_UNSEAL": "holdout_unseal",
        "STAGE_REVIEW": "stage_review",
    }.get(action_kind, "milestone")


def digest_of(directory: Path) -> str:
    """Hash nội dung một thư mục nguồn, để `verify` nói được nguồn có đổi không."""
    hasher = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            hasher.update(path.relative_to(directory).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    return hasher.hexdigest()
