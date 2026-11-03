"""Artifact của lõi → dòng bảng nhóm P (DESIGN.md §3.2, §5.5).

Tầng này **thuần**: vào là JSON đã đọc, ra là dict khoá theo tên cột. Không
mở file, không mở kết nối, không đọc đồng hồ. Cùng một artifact vào thì cùng
một dòng ra, nên `fwsync import` chạy lại từ đầu cho cùng kết quả (§5.5,
idempotent) và test chạy được trên CPU không cần Postgres.

Bốn luật của tầng này:

**Validate bằng model của hợp đồng, không bằng tay.** Mỗi mapper gọi
`Model.model_validate` trước khi đọc trường nào. Một artifact sai schema bị
từ chối ở đây kèm lý do, và `fwsync` ghi lý do đó vào `sync_runs.errors` rồi
chạy tiếp dòng khác (§2, lưới an toàn) — không dừng cả lần nạp.

**Trường hợp đồng có mà schema web không có thì bỏ, có chủ ý.**
`EpisodeMetadata.injected_defect` là trường duy nhất như vậy, và nó bị bỏ
**bắt buộc**: 03 bản 1.0 đã bỏ nó khỏi Episode (issue #62), file schema JSON
thì chưa cập nhật, và map nó vào bất cứ cột nào sẽ đưa đáp án lỗi cấy vào
bảng mà `agent_ro` đọc được (luật R8). `DROPPED_FIELDS` liệt kê nó để test
kiểm được, chứ không im lặng.

**Trường schema web cần mà hợp đồng không có thì nói rõ, không tự phát.**
`Episode` không mang `dataset_id`: ở lõi một episode trỏ `source_id` hoặc
`intervention_id`, còn "lô" là khái niệm của web. Mapper nhận một bảng tra
và từ chối dòng không tra được, thay vì gán một lô mặc định. Bản 0.2 còn đòi
`episode_index`, một số không có trong hợp đồng; cột đó đã bỏ khỏi schema.

**Giá trị không hữu hạn đi vào cột riêng.** `loss` là NaN thì vào
`loss_nonfinite`. Nhét NaN vào `loss` làm `AVG()` trả NaN và trắng cả biểu đồ
của M5.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, TypeVar

from flywheel.contracts.artifacts import (
    DefectManifest,
    Episode,
    ProbeP1,
    ProbeP2,
    ProbeP3,
    ProbeP4,
    QAReport,
)
from flywheel.contracts.training import TrainDiagnosis, TrainingMetric
from pydantic import BaseModel, ValidationError

#: Trường của hợp đồng bị bỏ có chủ ý, và lý do. Test kiểm danh sách này, nên
#: một trường bị bỏ âm thầm sẽ không lọt.
DROPPED_FIELDS: dict[str, str] = {
    "EpisodeMetadata.injected_defect": (
        "đáp án lỗi cấy; 03 bản 1.0 đã bỏ khỏi Episode (issue #62). Map nó vào "
        "cột nào cũng đưa đáp án vào bảng mà agent_ro đọc được (luật R8). "
        "Thay bằng `benchmark_copy_id` khi #62 merge."
    ),
}

NON_FINITE = ("NaN", "Infinity", "-Infinity")

_MODEL = TypeVar("_MODEL", bound=BaseModel)


class MappingError(ValueError):
    """Một artifact không nạp được, kèm lý do để ghi vào `sync_runs.errors`."""


@dataclass(frozen=True)
class DatasetLookup:
    """Cách suy ra `episodes.dataset_id` từ một artifact `Episode`.

    Hợp đồng không mang trường đó, nên bộ nạp phải tra. Hai đường, theo đúng
    cách lõi nối episode về nguồn của nó (03 §4.3: "`source_id` hoặc
    `intervention_id`"):

    * ``by_source`` — ``Source.source_ref`` → ``datasets.id``. Lô được tạo từ
      một nguồn tải về.
    * ``by_intervention`` — ``intervention_ref`` → ``datasets.id``. Episode thu
      về từ một can thiệp thuộc lô mà lần thu đó tạo ra.

    Không có đường thứ ba, và không có lô mặc định: gán sai lô làm sai báo cáo
    dataset, phân bổ chi phí (BR-05) và `r_demo`, mà không có gì báo.
    """

    by_source: dict[str, str]
    by_intervention: dict[str, str]

    def resolve(self, episode: Episode) -> str:
        if episode.source_id and episode.source_id in self.by_source:
            return self.by_source[episode.source_id]
        if episode.intervention_id and episode.intervention_id in self.by_intervention:
            return self.by_intervention[episode.intervention_id]
        raise MappingError(
            f"episode `{episode.episode_id}` không suy được `dataset_id`: "
            f"source_id={episode.source_id!r}, "
            f"intervention_id={episode.intervention_id!r} đều không có trong bảng tra. "
            f"`Episode` của hợp đồng không mang `dataset_id` (W12)"
        )


def _validated(model: type[_MODEL], payload: Any, what: str) -> _MODEL:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise MappingError(f"{what} không hợp schema {model.__name__}: {error}") from error


def map_episode(payload: Any, lookup: DatasetLookup) -> dict[str, Any]:
    """Một `Episode` thành một dòng `episodes`."""
    episode: Episode = _validated(Episode, payload, "episode")
    meta = episode.meta
    row: dict[str, Any] = {
        "episode_ref": episode.episode_id,
        "dataset_code": lookup.resolve(episode),
        "kind": episode.kind,
        "source_kind": episode.source_kind,
        "source_detail": meta.source_detail,
        "synthetic_tier": meta.synthetic_tier,
        "action_quality": episode.action_quality,
        "operator_kind": episode.operator_kind,
        "embodiment_id": episode.embodiment_id,
        "is_root": episode.is_root,
        "parent_ref": episode.parent_id,
        "root_ref": episode.root_id,
        "intervention_ref": episode.intervention_id,
        "condition_id": episode.condition_id,
        "run_plan_ref": episode.run_plan_id,
        "split": episode.split,
        "data_class": episode.data_class,
        "license": episode.license,
        "deid_status": episode.deid_status,
        "renderer": meta.renderer,
        "bundle_uri": episode.bundle_uri,
        "checkpoint_ref": episode.checkpoint_id,
        "rollout_seed": episode.rollout_seed,
        "sim_success": episode.sim_success,
        "infra_status": episode.infra_status,
        "camera_params_hash": episode.camera_params_hash,
        # `benchmark_copy_id` chưa có trong hợp đồng (issue #62). Để None
        # thay vì suy từ `injected_defect`: suy như vậy sẽ bỏ sót đúng các
        # episode **sạch** của bản sao, mà C19 phải chặn cả chúng.
        "benchmark_copy_id": None,
        # Phần còn lại của `meta` đi nguyên khối, trừ trường bị bỏ.
        "meta": _episode_meta(meta),
    }
    _reject_raw_egocentric(row)
    return row


def _episode_meta(meta: BaseModel) -> dict[str, Any]:
    """`meta` của episode, đã bỏ trường trong `DROPPED_FIELDS`."""
    dumped: dict[str, Any] = meta.model_dump()
    dumped.pop("injected_defect", None)
    return dumped


def _reject_raw_egocentric(row: dict[str, Any]) -> None:
    """C14 và BR-09 ở phía bộ nạp, trước khi trigger phải ra tay.

    Video người phải qua bước che danh tính trước mọi bước khác (CLAUDE.md,
    bất biến kiến trúc). Trigger trên `episodes` cũng chặn, nhưng chặn ở đây
    cho ra một dòng trong `sync_runs.errors` nói rõ episode nào, thay vì một
    lần nạp đổ vỡ.
    """
    if (
        row["source_kind"] == "egocentric"
        and row["deid_status"] == "raw"
        and row["split"] != "unassigned"
    ):
        raise MappingError(
            f"C14 / BR-09: episode `{row['episode_ref']}` còn deid_status = raw "
            f"nên không được mang split `{row['split']}`"
        )


def map_qa_report(payload: Any, known_episodes: set[str]) -> dict[str, Any]:
    """Một `QAReport` thành một dòng `episode_qa_reports` (append-only)."""
    report: QAReport = _validated(QAReport, payload, "qa report")
    if report.episode_id not in known_episodes:
        raise MappingError(
            f"qa report `{report.report_id}` trỏ episode `{report.episode_id}` chưa nạp"
        )
    if report.decision != "pass" and not report.reasons:
        # CHECK của bảng cũng bắt, nhưng ở đây thì lý do nói rõ report nào.
        raise MappingError(
            f"qa report `{report.report_id}` kết luận `{report.decision}` mà không có lý do"
        )
    return {
        "episode_ref": report.episode_id,
        "threshold_version": report.threshold_version,
        "decision": report.decision,
        "reasons": list(report.reasons),
        "checks": [check.model_dump() for check in report.checks],
    }


def map_training_metric(payload: Any, experiment_code: str) -> dict[str, Any]:
    """Một `TrainingMetric` thành một dòng `training_metrics`."""
    metric: TrainingMetric = _validated(TrainingMetric, payload, "training metric")
    loss, loss_nonfinite = _split_non_finite(metric.loss)
    row = {
        "experiment_code": experiment_code,
        "run_plan_ref": metric.run_plan_id,
        "release_ref": metric.release_id,
        "attempt": metric.attempt,
        "step": metric.step,
        "epoch": metric.epoch,
        "split": metric.split,
        "loss": loss,
        "loss_nonfinite": loss_nonfinite,
        "lr": metric.lr,
        "vlm_frozen": metric.vlm_frozen,
        "loss_by_group": dict(metric.loss_by_group),
        "loss_by_chunk_pos": list(metric.loss_by_chunk_pos),
        "grad_norm_vlm": metric.grad_norm_vlm,
        "grad_norm_action": metric.grad_norm_action,
        "pred_var_by_dim": list(metric.pred_var_by_dim),
        "pred_std": list(metric.pred_std),
        "target_std": list(metric.target_std),
        "hand_open_hist": list(metric.hand_open_hist),
        "vram_gb": metric.vram_gb,
        "throughput": metric.throughput,
        "wall_time_s": metric.wall_time_s,
    }
    return row


def _split_non_finite(value: float | str) -> tuple[float | None, str | None]:
    """Tách một giá trị thành (số, nhãn không hữu hạn); đúng một cái khác None.

    Hợp đồng mã hoá giá trị không hữu hạn thành chuỗi để JSONL còn là JSON
    hợp lệ. Schema web giữ nguyên cách đó: nhét NaN vào cột số làm `AVG()`
    trả NaN và trắng cả biểu đồ của M5.
    """
    if isinstance(value, str):
        if value not in NON_FINITE:
            raise MappingError(f"giá trị `{value}` không phải số và không phải {NON_FINITE}")
        return None, value
    return float(value), None


def map_train_diagnosis(
    payload: Any, experiment_code: str
) -> dict[str, list[dict[str, Any]]]:
    """Một `TrainDiagnosis` thành dòng `train_diagnoses` **và** `train_diagnosis_skips`.

    Hai danh sách, không một. `findings` rỗng không mang được "không có gì để
    chấm", nên `skipped` phải nạp về cùng lúc: một checkpoint không có probe
    P4 thì T7 không chấm được, không phải không quên (BR-12).
    """
    diagnosis: TrainDiagnosis = _validated(TrainDiagnosis, payload, "train diagnosis")
    findings = []
    for finding in diagnosis.findings:
        value, value_nonfinite = _split_non_finite(finding.value)
        findings.append(
            {
                "experiment_code": experiment_code,
                "checkpoint_ref": diagnosis.checkpoint_id,
                "config_sha256": diagnosis.config_sha256,
                "code": finding.code,
                "start_step": finding.start_step,
                "group_name": finding.group,
                "dim": finding.dim,
                "value": value,
                "value_nonfinite": value_nonfinite,
                "threshold": finding.threshold,
                "stop_job": finding.stop_job,
            }
        )
    skips = [
        {
            "experiment_code": experiment_code,
            "checkpoint_ref": diagnosis.checkpoint_id,
            "config_sha256": diagnosis.config_sha256,
            "code": skip.code,
            "reason": skip.reason,
        }
        for skip in diagnosis.skipped
    ]
    return {"train_diagnoses": findings, "train_diagnosis_skips": skips}


#: Bốn probe có hình dạng khác nhau, nên union chứ không phải một kiểu chung:
#: `type[BaseModel]` sẽ làm mất `checkpoint_id` lúc kiểm kiểu.
AnyProbe = ProbeP1 | ProbeP2 | ProbeP3 | ProbeP4

_PROBE_MODELS: dict[str, type[AnyProbe]] = {
    "P1": ProbeP1,
    "P2": ProbeP2,
    "P3": ProbeP3,
    "P4": ProbeP4,
}


def map_probe_result(payload: Any) -> dict[str, Any]:
    """Một `ProbeP1`…`ProbeP4` thành một dòng `probe_results`.

    Payload đi nguyên khối vào cột JSONB: bốn probe có hình dạng khác nhau, và
    tách chúng thành cột sẽ là bốn bảng. Cột `probe` cho phép lọc.
    """
    if not isinstance(payload, dict) or payload.get("probe") not in _PROBE_MODELS:
        raise MappingError(
            f"probe result phải khai `probe` là một trong {sorted(_PROBE_MODELS)}, "
            f"gặp {payload.get('probe') if isinstance(payload, dict) else type(payload).__name__!r}"
        )
    name = str(payload["probe"])
    probe = _validated(_PROBE_MODELS[name], payload, f"probe {name}")
    return {
        "probe": name,
        "checkpoint_ref": probe.checkpoint_id,
        "parent_checkpoint_ref": getattr(probe, "parent_checkpoint_id", None),
        "dataset_sha256": getattr(probe, "dataset_sha256", None),
        "payload": probe.model_dump(),
    }


def map_defect_manifest(payload: Any) -> dict[str, Any]:
    """Một `DefectManifest` thành dòng `defect_manifests` và `defect_items`.

    Đây là **đáp án** của bộ chấm Agent QA/QC. Nó vào nhóm S, mà `agent_ro`
    và `fw_api` đều bị REVOKE (luật R8). Mapper không đưa trường nào của nó
    sang nhóm P: episode của bản sao chỉ mang `benchmark_copy_id`, và cột đó
    nói "thuộc bản sao nào", không nói "lỗi gì".
    """
    manifest: DefectManifest = _validated(DefectManifest, payload, "defect manifest")
    return {
        "manifest": {
            # Hợp đồng không cho manifest một ID riêng; danh tính của nó là
            # mã bản sao chấm, cũng là giá trị `benchmark_copy_id` của mọi
            # episode trong bản sao (#62).
            "manifest_ref": manifest.dataset_id,
            "dataset_ref": manifest.dataset_id,
            "seed": manifest.seed,
            # Khoá đáp án (cột NOT NULL): hash của chính manifest, tính trên
            # JSON chuẩn hoá để hai lần nạp cùng đáp án cho cùng hash.
            "sha256": hashlib.sha256(
                json.dumps(manifest.model_dump(), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        },
        "items": [
            {
                "target_ref": defect.target_ref,
                "code": defect.code,
                "parameters": dict(defect.parameters),
            }
            for defect in manifest.defects
        ],
    }
