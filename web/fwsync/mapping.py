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
`DROPPED_FIELDS` liệt kê từng trường như vậy kèm lý do để test kiểm được,
chứ không im lặng. Hiện có một trường, `SystemDiagnosis.episode_id` (W13).
`EpisodeMetadata.injected_defect`, trường từng ở đây trước nó, đã ra khỏi
hợp đồng (issue #62, S1-10/7), và
`benchmark_copy_id` thay nó đi thẳng vào cột cùng tên. Artifact còn mang
`injected_defect` giờ bị chính model hợp đồng từ chối (`extra="forbid"`),
nên đáp án lỗi cấy không tới được bảng mà `agent_ro` đọc (luật R8).

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
from flywheel.contracts.diagnosis import SystemDiagnosis
from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Decision,
    FixRateEvent,
    LedgerEntry,
    Release,
    RunPlan,
    Source,
)
from flywheel.contracts.entities import Episode as CatalogEpisode
from flywheel.contracts.entities import QAReport as CatalogQAReport
from flywheel.contracts.training import TrainDiagnosis, TrainingMetric
from pydantic import BaseModel, ValidationError

#: Trường chung của mọi bản ghi catalog (`BaseRecord`) mà bảng web không có
#: cột. `site_id` luôn là `local` ở L0; `schema_version` là phiên bản hợp đồng,
#: không phải dữ liệu.
_BASE_DROPPED = {
    "site_id": "L0 chỉ có một site (`local`); web chưa phân site",
    "schema_version": "phiên bản hợp đồng của dòng, không phải dữ liệu nghiệp vụ",
    "embodiment_id": "bảng web của thực thể này chưa có cột embodiment hay meta",
    "task_id": "bảng web của thực thể này chưa có cột task hay meta",
    "meta": "bảng web của thực thể này chưa có cột meta",
}
#: Thực thể mà bảng web **không** có cột `meta`: `task_id`, `embodiment_id`,
#: `meta` của chúng bị bỏ. Bốn thực thể còn lại (Release, Checkpoint, RunPlan,
#: Decision) giữ ba trường đó trong cột `meta` của bảng web.
_NO_META = ("Source", "Cluster", "FixRateEvent", "LedgerEntry")
_ENTITIES = (*_NO_META, "Release", "Checkpoint", "RunPlan", "Decision")

#: Trường của hợp đồng bị bỏ có chủ ý, và lý do. Test kiểm danh sách này, nên
#: một trường bị bỏ âm thầm sẽ không lọt: mọi trường của model mà mapper
#: không đọc phải có tên ở đây (`test_every_contract_field_is_mapped_or_dropped`).
#: Khoá là `<Model>.<trường>`; mapper bỏ trường đó khỏi mọi cột và `meta`.
DROPPED_FIELDS: dict[str, str] = {
    "SystemDiagnosis.episode_id": (
        "tên `episode_N` của dòng thống kê SIMPLE, đếm lại ở mỗi lượt eval nên không "
        "duy nhất; bản ghi nối với `eval_episodes` bằng `trace_sha256` (W13)"
    ),
    # Dòng `catalog/episode/` và `catalog/qa_report/` mang thêm trường của
    # `BaseRecord` mà model artifact không có.
    "Episode.site_id": _BASE_DROPPED["site_id"],
    "Episode.task_id": "bảng episodes chưa có cột task; task suy từ lô hay run plan",
    "Episode.schema_version": _BASE_DROPPED["schema_version"],
    "QAReport.site_id": _BASE_DROPPED["site_id"],
    "QAReport.task_id": "báo cáo QA thuộc một episode; task là của episode",
    "QAReport.embodiment_id": "báo cáo QA thuộc một episode; embodiment là của episode",
    "QAReport.schema_version": _BASE_DROPPED["schema_version"],
    "QAReport.meta": "episode_qa_reports chưa có cột meta",
    **{f"{model}.{name}": _BASE_DROPPED[name]
       for model in _ENTITIES for name in ("site_id", "schema_version")},
    **{f"{model}.{name}": _BASE_DROPPED[name]
       for model in _NO_META for name in ("task_id", "embodiment_id", "meta")},
    "Cluster.run_plan_id": (
        "chỉ dùng để tra đề xuất (`flywheel_recommendations.run_plan_ref`); "
        "failure_clusters gắn đề xuất, không gắn run plan"
    ),
    "Cluster.failure_class": "failure_clusters chưa có cột failure_class",
    "Cluster.card_uri": "hợp đồng không đặt trường này nữa (DA-39); đường dẫn suy từ id",
    "FixRateEvent.round_id": "fix_rate_events chưa có cột vòng",
    "FixRateEvent.diagnosis": "chẩn đoán là của cụm (`failure_clusters.diagnosis`)",
    "FixRateEvent.task_family": "fix_rate_events chưa có cột họ task",
    "Release.items": "đi sang bảng release_items, mỗi item một dòng",
}

NON_FINITE = ("NaN", "Infinity", "-Infinity")

_MODEL = TypeVar("_MODEL", bound=BaseModel)


class MappingError(ValueError):
    """Một artifact không nạp được, kèm lý do để ghi vào `sync_runs.errors`."""


class NotLoaded(Exception):
    """Một artifact hợp lệ mà web cố ý không nạp, kèm lý do.

    Khác `MappingError`: không có gì sai, nên nó vào `ignored` chứ không vào
    `errors`, và không làm lần nạp thành `partial`. Ví dụ: một RunPlan còn
    `draft` (bảng `run_plans` chỉ giữ plan đã đóng băng).
    """


def refuse_ambiguous(key: str | None, ambiguous: frozenset[str], what: str) -> None:
    """Từ chối một khoá mà hai dòng nguồn trỏ về hai giá trị khác nhau (review #72 điểm 4).

    Giữ giá trị cuối cùng là gán bừa một trong hai, đúng điều W12 cấm: hai lô
    cùng `source_ref` (lô thật và bản sao chấm cắt từ nó) thì episode không
    biết thuộc lô nào.
    """
    if key is not None and key in ambiguous:
        raise MappingError(
            f"{what} `{key}` trỏ về nhiều dòng khác nhau trong cùng lần nạp; "
            f"không gán vào dòng nào"
        )


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
    #: Khoá mà hai lô khác nhau cùng khai: tra vào đó là từ chối.
    ambiguous_sources: frozenset[str] = frozenset()
    ambiguous_interventions: frozenset[str] = frozenset()

    def resolve(self, episode: Episode) -> str:
        refuse_ambiguous(episode.source_id, self.ambiguous_sources,
                         f"episode `{episode.episode_id}`: source_id")
        refuse_ambiguous(episode.intervention_id, self.ambiguous_interventions,
                         f"episode `{episode.episode_id}`: intervention_id")
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


def _catalog_id(payload: Any, field: str, what: str) -> None:
    """Dòng catalog phải mang id của nó.

    Model catalog (`entities.Episode`, `entities.QAReport`) **tự sinh** id
    khi thiếu, nên một dòng thiếu id sẽ thành một bản ghi mới mỗi lần nạp.
    """
    if not isinstance(payload, dict) or not str(payload.get(field) or "").strip():
        raise MappingError(f"{what} catalog thiếu `{field}`; không nạp lại được cùng một dòng")


def map_episode(payload: Any, lookup: DatasetLookup, *, catalog: bool = False) -> dict[str, Any]:
    """Một `Episode` thành một dòng `episodes`.

    `catalog`: dòng đến từ `catalog/episode/` của lõi, ghi bằng
    `entities.Episode` (thêm `site_id`, `task_id`, `schema_version`, xem
    `DROPPED_FIELDS`). Model artifact từ chối ba trường đó.
    """
    episode: Episode
    if catalog:
        _catalog_id(payload, "episode_id", "episode")
        episode = _validated(CatalogEpisode, payload, "episode")
    else:
        episode = _validated(Episode, payload, "episode")
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
        # Mọi episode của bản sao chấm mang mã bản sao, kể cả episode
        # **sạch**, nên C19 chặn được cả chúng khỏi release (issue #62).
        "benchmark_copy_id": meta.benchmark_copy_id,
        # Phần còn lại của `meta` đi nguyên khối, trừ trường bị bỏ.
        "meta": _episode_meta(meta),
    }
    _reject_raw_egocentric(row)
    return row


def _episode_meta(meta: BaseModel) -> dict[str, Any]:
    """`meta` của episode, đã bỏ trường trong `DROPPED_FIELDS`."""
    dumped: dict[str, Any] = meta.model_dump()
    prefix = f"{type(meta).__name__}."
    for field in DROPPED_FIELDS:
        if field.startswith(prefix):
            dumped.pop(field.removeprefix(prefix), None)
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


def map_qa_report(
    payload: Any, known_episodes: set[str], *, catalog: bool = False
) -> dict[str, Any]:
    """Một `QAReport` thành một dòng `episode_qa_reports` (append-only).

    `catalog`: như `map_episode`, dòng `catalog/qa_report/` của lõi.
    """
    report: QAReport
    if catalog:
        _catalog_id(payload, "report_id", "qa report")
        report = _validated(CatalogQAReport, payload, "qa report")
    else:
        report = _validated(QAReport, payload, "qa report")
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
        # `report_id` là danh tính của lần chấm. Bỏ nó thì nạp lại cùng báo cáo
        # không phân biệt được với một lần chấm mới.
        "report_ref": report.report_id,
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


@dataclass(frozen=True)
class TraceLookup:
    """Cách nối một `SystemDiagnosis` thật với dòng `eval_episodes` của nó (W13).

    `SystemDiagnosis.episode_id` là tên `episode_N` mà SIMPLE ghi ở dòng
    thống kê, đếm lại từ đầu ở mỗi lượt eval, nên không làm khoá được: hai
    job khác nhau cùng có `episode_3`. `trace_sha256` thì làm được: nó là
    sha256 của `steps.jsonl` mà phép kiểm đã đọc, mỗi dòng của file đó mang
    `trace_id` duy nhất, nên hai trace khác nhau không trùng hash. Không đổi
    hợp đồng (DESIGN.md §4.4b, phương án 1).

    * ``by_trace`` — ``eval_episodes.trace_sha256`` → ``eval_episode_ref``.
    * ``ambiguous`` — hash mà hai dòng `eval_episodes` cùng mang. Nối vào hash
      đó là chọn bừa một trong hai, nên từ chối như hash không có.

    Giống W12: tra không ra thì từ chối dòng, không gán vào episode nào.
    """

    by_trace: dict[str, str]
    ambiguous: frozenset[str] = frozenset()

    def resolve(self, trace_sha256: str) -> str:
        if trace_sha256 in self.ambiguous:
            raise MappingError(
                f"trace_sha256 `{trace_sha256[:12]}…` có trên nhiều dòng `eval_episodes`; "
                f"không nối được bản ghi kiểm hệ thống vào một episode"
            )
        if trace_sha256 not in self.by_trace:
            raise MappingError(
                f"không có dòng `eval_episodes` nào mang trace_sha256 `{trace_sha256[:12]}…`; "
                f"bản ghi kiểm hệ thống bị từ chối thay vì gán vào một episode bất kỳ (W13)"
            )
        return self.by_trace[trace_sha256]


def map_system_diagnosis(payload: Any, lookup: TraceLookup) -> dict[str, Any]:
    """Một `SystemDiagnosis` của làn DA-13 thành một dòng `system_diagnoses`.

    Validate bằng model hợp đồng trước, nên `clean` kèm mã bị bỏ qua, hay R1
    ghi nhận trên rollout không đồng bộ, bị từ chối ở đây chứ không đợi C17
    của Postgres. `episode_id` bị bỏ có chủ ý (`DROPPED_FIELDS`); khoá nối là
    `trace_sha256`. Hợp đồng không có `measurements`, nên cột đó để `{}`: M6
    khi đó hiện số qua `findings` và `recorded`.
    """
    diagnosis: SystemDiagnosis = _validated(SystemDiagnosis, payload, "system diagnosis")
    return {
        "eval_episode_ref": lookup.resolve(diagnosis.trace_sha256),
        "diagnosis": diagnosis.diagnosis,
        "config_sha256": diagnosis.config_sha256,
        "trace_sha256": diagnosis.trace_sha256,
        "rtc_sha256": diagnosis.rtc_sha256,
        "camera_sha256": diagnosis.camera_sha256,
        "infra_sha256": diagnosis.infra_sha256,
        "infra_status": diagnosis.infra_status,
        "findings": [finding.model_dump() for finding in diagnosis.findings],
        "skipped": [skip.model_dump() for skip in diagnosis.skipped],
        "measurements": {},
        "timing": diagnosis.timing,
        "recorded": [finding.model_dump() for finding in diagnosis.recorded],
        "recorded_skipped": [skip.model_dump() for skip in diagnosis.recorded_skipped],
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
            # mã bản sao chấm, cũng là `EpisodeMetadata.benchmark_copy_id`
            # của mọi episode trong bản sao (#62).
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


#: Dạng `bench_result.json` của DA-31 mà bộ nạp hiểu. `da31-1` thiếu
#: `recall_unmasked_by_kind` và tính báo nhầm khác (hotfix #141), nên nạp nó
#: vào cùng cột với `da31-2` sẽ đặt hai con số khác nghĩa cạnh nhau. `da31-3`
#: (DA-31 nhiệm vụ 5, PR #166) giữ mọi khoá của `da31-2` và thêm
#: `agent_models` mỗi nhóm (W14); kết quả `da31-2` nạp với `agent_models` rỗng
#: (NULL), để M3 ghi "chưa có" thay vì đoán model.
BENCH_VERSIONS = ("da31-2", "da31-3")
_AGENT_MODEL_KEYS = ("copy", "name", "revision", "temperature", "prompt_sha256", "reports")
BENCH_LAYERS = ("code", "agent")
_BENCH_LAYER_KEYS = (
    "recall_by_kind", "masked_by_kind", "recall_unmasked_by_kind", "precision_by_code",
    "false_alarm_on_clean", "false_alarm_not_a_unit", "clean_reports", "natural",
    "seconds_to_report", "uncoded",
)


def map_bench_result(payload: Any, result_sha256: str) -> dict[str, list[dict[str, Any]]]:
    """Một `bench_result.json` của DA-31 thành dòng `defect_bench_groups` và `defect_scores`.

    File này không phải artifact hợp đồng: DA-31 (làn Đánh giá) định nghĩa nó
    ở `flywheel.eval.agentqa.bench.report`, và `web/tests/test_bench_result.py`
    so dạng của nó với hàm thật. Vì vậy mapper kiểm tay, và **nghiêm**: một
    khoá thiếu là từ chối cả file, không bỏ một con số rồi hiện bảng điểm
    thiếu dòng như thể lớp đó không báo gì.

    `result_sha256` là hash của đúng chuỗi JSON (như `bench_result.sha256`),
    do runner tính vì tầng này không mở file. Nó là danh tính của lần chấm:
    chấm lại ra file khác, hash khác, dòng khác (append-only).
    """
    if not isinstance(payload, dict):
        raise MappingError("bench result: phải là một đối tượng JSON")
    version = payload.get("bench_version")
    if version not in BENCH_VERSIONS:
        raise MappingError(
            f"bench result: bench_version {version!r} không nhận; bộ nạp hiểu {BENCH_VERSIONS}"
        )
    head = _require(payload, ("measured_on", "false_alarm_on_clean", "created_at",
                              "manifest_sha256", "inputs", "groups"), "bench result")
    if not isinstance(head["groups"], list) or not head["groups"]:
        raise MappingError("bench result: `groups` rỗng; một lần chấm không nhóm nào là file hỏng")
    groups: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    for index, group in enumerate(head["groups"]):
        where = f"bench result groups[{index}]"
        g = _require(group, ("group", "injected_copy", "clean_copy", "defects", "layers",
                             "split", "agent_quality"), where)
        name = str(g["group"])
        layers = g["layers"]
        if not isinstance(layers, dict) or set(layers) != set(BENCH_LAYERS):
            raise MappingError(f"{where}: `layers` phải có đúng {BENCH_LAYERS}")
        quality = _require(g["agent_quality"], ("ranking", "reviews", "findings"),
                           f"{where}.agent_quality")
        ranking = _rate(quality["ranking"], f"{where}.agent_quality.ranking")
        models = (None if version == "da31-2"
                  else _agent_models(g, (g["injected_copy"], g["clean_copy"]), where))
        per_layer: dict[str, dict[str, Any]] = {}
        for layer in BENCH_LAYERS:
            lw = f"{where}.layers.{layer}"
            body = _require(layers[layer], _BENCH_LAYER_KEYS, lw)
            per_layer[layer] = body
            key = {"result_sha256": result_sha256, "group_name": name, "layer": layer,
                   "created_at": head["created_at"]}
            masked = body["masked_by_kind"]
            for kind, rate in body["recall_by_kind"].items():
                if kind not in masked:
                    raise MappingError(f"{lw}: loại `{kind}` có recall mà không có masked_by_kind")
                scores.append({**key, "metric": "recall", "subject": kind,
                               **_rate(rate, f"{lw}.recall_by_kind.{kind}"),
                               "masked": int(masked[kind]), "bound": None})
            for kind, rate in body["recall_unmasked_by_kind"].items():
                scores.append({**key, "metric": "recall_unmasked", "subject": kind,
                               **_rate(rate, f"{lw}.recall_unmasked_by_kind.{kind}"),
                               "masked": None, "bound": None})
            for code, rate in body["precision_by_code"].items():
                scores.append({**key, "metric": "precision", "subject": code,
                               **_rate(rate, f"{lw}.precision_by_code.{code}"),
                               "masked": None, "bound": None})
            false_alarm = body["false_alarm_on_clean"]
            if not isinstance(false_alarm, dict) or "bound" not in false_alarm:
                raise MappingError(f"{lw}.false_alarm_on_clean: thiếu `bound`")
            scores.append({**key, "metric": "false_alarm", "subject": "*",
                           **_rate(false_alarm, f"{lw}.false_alarm_on_clean"),
                           "masked": None, "bound": "upper"})
        groups.append({
            "result_sha256": result_sha256,
            "bench_version": version,
            "measured_on": head["measured_on"],
            "false_alarm_note": head["false_alarm_on_clean"],
            "group_name": name,
            "injected_copy": g["injected_copy"],
            "clean_copy": g["clean_copy"],
            "defects": int(g["defects"]),
            "split": g["split"],
            "seconds_to_report": {k: v["seconds_to_report"] for k, v in per_layer.items()},
            "clean_reports": {k: v["clean_reports"] for k, v in per_layer.items()},
            "natural": {k: v["natural"] for k, v in per_layer.items()},
            "not_a_unit": {k: v["false_alarm_not_a_unit"] for k, v in per_layer.items()},
            "uncoded": {k: v["uncoded"] for k, v in per_layer.items()},
            "agent_ranking_hit": ranking["hit"],
            "agent_ranking_total": ranking["total"],
            "agent_reviews": quality["reviews"],
            "agent_findings": quality["findings"],
            "agent_models": models,
            "manifest_sha256": head["manifest_sha256"],
            "inputs": head["inputs"],
            "created_at": head["created_at"],
        })
    return {"defect_bench_groups": groups, "defect_scores": scores}


def _agent_models(group: dict[str, Any], copies: tuple[str, str],
                  where: str) -> list[dict[str, Any]]:
    """`agent_models` của một nhóm `da31-3`: mỗi dòng nói bản sao nào, model nào.

    Thiếu khoá là từ chối, như mọi chỗ khác của file: không có model thì một
    con số của cột agent không chạy lại được. Danh sách rỗng thì nhận (bộ chấm
    chạy không báo cáo agent nào); M3 ghi nó là "không có báo cáo agent".
    """
    if "agent_models" not in group:
        raise MappingError(f"{where}: thiếu ['agent_models'] (bắt buộc từ da31-3)")
    models = group["agent_models"]
    if not isinstance(models, list):
        raise MappingError(f"{where}.agent_models: phải là danh sách")
    out = []
    for i, raw in enumerate(models):
        row = _require(raw, _AGENT_MODEL_KEYS, f"{where}.agent_models[{i}]")
        if row["copy"] not in copies:
            raise MappingError(
                f"{where}.agent_models[{i}]: bản `{row['copy']}` không thuộc nhóm {copies}")
        sha = row["prompt_sha256"]
        if not isinstance(sha, str) or len(sha) != 64:
            raise MappingError(f"{where}.agent_models[{i}]: prompt_sha256 không phải sha256")
        if not isinstance(row["reports"], int) or row["reports"] < 1:
            raise MappingError(f"{where}.agent_models[{i}]: reports phải là số nguyên >= 1")
        out.append({key: row[key] for key in _AGENT_MODEL_KEYS})
    return out


def _require(value: Any, keys: tuple[str, ...], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MappingError(f"{where}: phải là một đối tượng JSON")
    missing = [key for key in keys if key not in value]
    if missing:
        raise MappingError(f"{where}: thiếu {missing}")
    return value


def _rate(value: Any, where: str) -> dict[str, int]:
    """`{hit, total, value}` của DA-31 thành hai cột; `value` do view tính lại."""
    if not isinstance(value, dict):
        raise MappingError(f"{where}: phải là {{hit, total, value}}")
    hit, total = value.get("hit"), value.get("total")
    if not isinstance(hit, int) or not isinstance(total, int) or not 0 <= hit <= total:
        raise MappingError(f"{where}: hit={hit!r}, total={total!r} không phải 0 <= hit <= total")
    return {"hit": hit, "total": total}


# ---------------------------------------------------------------------------
# Thực thể catalog của lõi (S1-10) → bảng web (review #72 điểm 1, 2)
# ---------------------------------------------------------------------------
#
# Lõi ghi chín thực thể này bằng model hợp đồng vào `catalog/<bảng>/` và sổ
# chi phí vào `runs/<run_plan>/<job>/ledger.jsonl`. Khoá tự nhiên của web
# (`source_ref`, `decision_ref`, `entry_ref`…) là chính `id` của hợp đồng, nên
# nạp lại cùng artifact trúng đúng dòng cũ.
#
# Mỗi mapper chỉ đặt cột nó biết. Bảng không append-only được upsert bằng
# `dict.update`, nên một cột mà hợp đồng không mang (chẩn đoán của cụm, thí
# nghiệm của checkpoint) không bị một lần nạp lại xoá về None.

#: Trường mỗi mapper đọc, theo model. Cùng `DROPPED_FIELDS` nó phải phủ đúng
#: mọi trường của model (`test_every_contract_field_is_mapped_or_dropped`), nên
#: lõi thêm một trường thì test đỏ cho tới khi có người quyết định nó đi đâu.
MAPPED_FIELDS: dict[str, frozenset[str]] = {
    "Source": frozenset({
        "id", "kind", "uri", "repo", "revision", "path", "sha256", "license",
        "data_class", "clean_for_main_task", "provenance", "downloaded_at",
    }),
    "RunPlan": frozenset({
        "id", "name", "purpose", "branch", "method", "status", "lock_path",
        "lock_sha256", "frozen_at", "body", "task_id", "embodiment_id", "meta",
    }),
    "Release": frozenset({
        "id", "name", "kind", "parent_release_id", "split_plan_cfg_id", "status",
        "manifest_sha256", "holdout_guard_passed", "combined_license", "counts",
        "frozen_at", "task_id", "embodiment_id", "meta",
    }),
    "Checkpoint": frozenset({
        "id", "origin", "method", "branch", "base_source_id", "parent_checkpoint_id",
        "release_id", "seed", "step", "weights_sha256", "uri", "is_final",
        "task_id", "embodiment_id", "meta",
    }),
    "Cluster": frozenset({
        "id", "first_failed_step", "failure_kind", "level", "parent_cluster_id",
        "representative_seed", "member_episode_ids",
    }),
    "FixRateEvent": frozenset({
        "id", "cluster_id", "intervention_id", "intervention_type", "failure_kind",
        "failure_class", "n_conditions", "p_parent", "p_candidate", "fixed",
    }),
    "Decision": frozenset({
        "id", "kind", "subject_kind", "subject_id", "verdict", "metrics", "criteria",
        "signed_by", "reason", "supersedes_decision_id", "task_id", "embodiment_id", "meta",
    }),
    "LedgerEntry": frozenset({
        "id", "activity", "resource_type", "quantity", "unit", "pricebook_id",
        "usd_amount", "human_hours", "measure_kind", "estimate_entry_id", "branch",
        "run_plan_id", "cluster_id", "intervention_id", "job_id", "person_code",
        "reverses_entry_id", "note",
    }),
}

#: Bảng web của mỗi model, cho test so cột với schema.
ENTITY_TABLES: dict[str, str] = {
    "Source": "sources",
    "RunPlan": "run_plans",
    "Release": "releases",
    "Checkpoint": "model_checkpoints",
    "Cluster": "failure_clusters",
    "FixRateEvent": "fix_rate_events",
    "Decision": "decisions",
    "LedgerEntry": "cost_ledger_entries",
}


@dataclass(frozen=True)
class RefLookup:
    """Một bảng tra `khoá → ref` dựng từ artifact của cùng lần nạp.

    Khoá mà hai dòng nguồn trỏ về hai ref khác nhau nằm ở `ambiguous`.
    `require` từ chối khoá đó (và khoá không có); `find` trả None cho cả hai,
    cho chỗ mà việc tra chỉ làm giàu dòng chứ không bắt buộc.
    """

    pairs: dict[str, str]
    ambiguous: frozenset[str] = frozenset()

    def find(self, key: str | None) -> str | None:
        if key is None or key in self.ambiguous:
            return None
        return self.pairs.get(key)

    def require(self, key: str | None, what: str) -> str:
        refuse_ambiguous(key, self.ambiguous, what)
        found = self.find(key)
        if found is None:
            raise MappingError(f"{what} `{key}` không tra được trong lần nạp này")
        return found


_EMPTY = RefLookup({})


@dataclass(frozen=True)
class CatalogLookups:
    """Các bảng tra mà thực thể catalog cần, vì hợp đồng nối chúng khác web.

    * ``recommendation_by_run_plan`` — `flywheel_recommendations.run_plan_ref`
      → `recommendation_ref`. Cụm của lõi gắn run plan; cụm của web gắn đề xuất.
    * ``recommendation_by_intervention`` — `interventions.intervention_ref` →
      `recommendation_ref`, để bút toán của một can thiệp vào ngân sách BR-07.
    * ``experiment_by_run_plan`` — `experiments.run_plan_ref` →
      `experiment_code`, để chi phí train vào đúng thí nghiệm trên M8.
    """

    recommendation_by_run_plan: RefLookup = _EMPTY
    recommendation_by_intervention: RefLookup = _EMPTY
    experiment_by_run_plan: RefLookup = _EMPTY


def _with_meta(entity: BaseModel, extra: dict[str, Any]) -> dict[str, Any]:
    """Cột `meta` của bảng web: trường hợp đồng không có cột riêng, cộng
    `task_id`, `embodiment_id` và `meta` gốc của `BaseRecord`."""
    base = {
        "task_id": getattr(entity, "task_id", None),
        "embodiment_id": getattr(entity, "embodiment_id", None),
        "meta": dict(getattr(entity, "meta", {}) or {}),
    }
    return {**extra, **base}


def map_source(payload: Any) -> dict[str, Any]:
    """Một `Source` thành một dòng `sources`."""
    source: Source = _validated(Source, payload, "source")
    return {
        "source_ref": source.id,
        "url": source.uri,
        "repo": source.repo,
        "revision": source.revision,
        "path": source.path,
        "sha256": source.sha256,
        "license": source.license,
        "data_class": source.data_class,
        "downloaded_at": source.downloaded_at,
        "kind": source.kind,
        "clean_for_main_task": source.clean_for_main_task,
        "provenance": dict(source.provenance),
    }


def map_run_plan(payload: Any) -> dict[str, Any]:
    """Một `RunPlan` **đã đóng băng** thành một dòng `run_plans`.

    `run_plans` chỉ giữ plan đã khoá: `lock_uri`, `config_sha256` và
    `frozen_at` là NOT NULL, vì một job chạy trên plan chưa khoá thì không tái
    lập được. Plan `draft` không sai, nên nó vào `ignored`, không vào `errors`.
    """
    plan: RunPlan = _validated(RunPlan, payload, "run plan")
    if plan.status != "frozen":
        raise NotLoaded(f"run plan `{plan.id}` còn `{plan.status}`; run_plans chỉ giữ plan đã khoá")
    missing = [name for name in ("lock_path", "lock_sha256", "frozen_at")
               if getattr(plan, name) is None]
    if missing:
        raise MappingError(f"run plan `{plan.id}` đã `frozen` mà thiếu {missing}")
    return {
        "run_plan_ref": plan.id,
        "purpose": plan.purpose,
        "branch": plan.branch,
        "method": plan.method,
        "task_id": plan.task_id,
        "lock_uri": plan.lock_path,
        "config_sha256": plan.lock_sha256,
        "frozen_at": plan.frozen_at,
        "meta": _with_meta(plan, {"name": plan.name, "status": plan.status, "body": plan.body}),
    }


def map_release(payload: Any) -> list[tuple[str, dict[str, Any]]]:
    """Một `Release` thành một dòng `releases` và mỗi item một dòng `release_items`.

    Item là dạng của `flywheel.data.release.build._item`: `episode_id`,
    `weight`, `excluded`, `reasons`. Item không có `episode_id` là từ chối cả
    release: bỏ một item là đổi nội dung một release đã băm.
    """
    release: Release = _validated(Release, payload, "release")
    if release.status == "frozen" and (release.manifest_sha256 is None
                                       or release.frozen_at is None):
        raise MappingError(
            f"release `{release.id}` đã `frozen` mà thiếu manifest_sha256 hoặc frozen_at"
        )
    rows: list[tuple[str, dict[str, Any]]] = [("releases", {
        "release_ref": release.id,
        "name": release.name,
        "parent_release_ref": release.parent_release_id,
        "status": release.status,
        "manifest_sha256": release.manifest_sha256,
        "license_summary": release.combined_license,
        "frozen_at": release.frozen_at,
        "meta": _with_meta(release, {
            "kind": release.kind,
            "split_plan_cfg_id": release.split_plan_cfg_id,
            "holdout_guard_passed": release.holdout_guard_passed,
            "counts": dict(release.counts),
        }),
    })]
    for index, item in enumerate(release.items):
        episode = item.get("episode_id")
        if not episode:
            raise MappingError(f"release `{release.id}` items[{index}] thiếu `episode_id`")
        excluded = bool(item.get("excluded", False))
        reasons = "; ".join(str(reason) for reason in item.get("reasons") or [])
        rows.append(("release_items", {
            "release_ref": release.id,
            "episode_ref": str(episode),
            "sample_weight": float(item.get("weight", 1.0)),
            "excluded": excluded,
            "exclude_reason": (reasons or "excluded") if excluded else None,
        }))
    return rows


def map_checkpoint(payload: Any) -> dict[str, Any]:
    """Một `Checkpoint` thành một dòng `model_checkpoints`.

    Hợp đồng không nối checkpoint với thí nghiệm (thí nghiệm là khái niệm của
    web), nên dòng không mang `experiment_code`: không gán thí nghiệm mặc
    định. Upsert giữ `experiment_code` mà một artifact web khác đã đặt.
    """
    checkpoint: Checkpoint = _validated(Checkpoint, payload, "checkpoint")
    return {
        "checkpoint_ref": checkpoint.id,
        "parent_checkpoint_ref": checkpoint.parent_checkpoint_id,
        "release_ref": checkpoint.release_id,
        "method": checkpoint.method,
        "step": checkpoint.step,
        "weights_sha256": checkpoint.weights_sha256,
        "uri": checkpoint.uri,
        "train_seed": checkpoint.seed,
        "meta": _with_meta(checkpoint, {
            "origin": checkpoint.origin,
            "branch": checkpoint.branch,
            "base_source_id": checkpoint.base_source_id,
            "is_final": checkpoint.is_final,
        }),
    }


#: Số đại diện tối đa của một cụm (CHECK của `failure_clusters`).
MAX_REPRESENTATIVES = 5


def map_cluster(payload: Any, lookups: CatalogLookups) -> dict[str, Any]:
    """Một `Cluster` thành một dòng `failure_clusters`.

    Đề xuất của cụm tra qua run plan; không tra được thì từ chối (như W12).
    Hợp đồng không chọn episode đại diện, nên `representative_refs` là tối đa
    năm thành viên đầu theo thứ tự lõi ghi. Chẩn đoán không có trong hợp đồng
    và không bị đặt ở đây.
    """
    cluster: Cluster = _validated(Cluster, payload, "cluster")
    if not cluster.member_episode_ids:
        raise MappingError(f"cluster `{cluster.id}` không có thành viên nào")
    if cluster.representative_seed is None:
        raise MappingError(f"cluster `{cluster.id}` thiếu representative_seed")
    return {
        "cluster_ref": cluster.id,
        "recommendation_ref": lookups.recommendation_by_run_plan.require(
            cluster.run_plan_id, f"cluster `{cluster.id}`: run_plan_id"
        ),
        "failed_step": cluster.first_failed_step,
        "failure_code": cluster.failure_kind,
        "level": cluster.level,
        "member_count": len(cluster.member_episode_ids),
        "representative_refs": list(cluster.member_episode_ids[:MAX_REPRESENTATIVES]),
        "representative_seed": cluster.representative_seed,
        "parent_cluster_ref": cluster.parent_cluster_id,
    }


def map_fix_rate_event(payload: Any) -> dict[str, Any]:
    """Một `FixRateEvent` thành một dòng `fix_rate_events` (append-only)."""
    event: FixRateEvent = _validated(FixRateEvent, payload, "fix rate event")
    if event.cluster_id is None:
        raise MappingError(f"fix rate event `{event.id}` thiếu cluster_id")
    if not 0 <= event.fixed <= event.n_conditions:
        raise MappingError(
            f"fix rate event `{event.id}`: fixed={event.fixed} ngoài [0, {event.n_conditions}]"
        )
    return {
        "event_ref": event.id,
        "intervention_kind": event.intervention_type,
        "cluster_ref": event.cluster_id,
        "intervention_ref": event.intervention_id,
        "failure_code": event.failure_kind,
        "failure_class": event.failure_class,
        "n_conditions": event.n_conditions,
        "p_parent": event.p_parent,
        "p_candidate": event.p_candidate,
        "fixed_count": event.fixed,
    }


def map_decision(payload: Any) -> dict[str, Any]:
    """Một `Decision` thành một dòng `decisions`.

    Hợp đồng không mang `source_action_id`, nên một quyết định của lõi không
    tự đánh dấu hành động nào là APPLIED; chỉ câu trả lời trong inbox (dạng
    web, xem `run_fake_core`) làm được việc đó. Người ký là mã người, không
    phải id `app_users`, nên nó vào `meta`.
    """
    decision: Decision = _validated(Decision, payload, "decision")
    return {
        "decision_ref": decision.id,
        "kind": decision.kind,
        "target_kind": decision.subject_kind,
        "target_id": decision.subject_id,
        "measures": dict(decision.metrics),
        "criteria": dict(decision.criteria),
        "conclusion": decision.verdict,
        "reason": decision.reason,
        "meta": _with_meta(decision, {
            "signed_by": decision.signed_by,
            "supersedes_decision_id": decision.supersedes_decision_id,
        }),
    }


#: Đơn vị mà một dòng GPU tính bằng giờ. Lõi ghi `resource_type:
#: gpu_hour_<card>`, `unit: hour` (fixture `LedgerEntry.json`).
GPU_HOUR_UNITS = ("hour", "hours", "h")
MEASURE_KINDS = ("estimated", "measured")


def _gpu_hours(resource_type: str, unit: str, quantity: float) -> float | None:
    if resource_type.startswith("gpu") and unit in GPU_HOUR_UNITS:
        return float(quantity)
    return None


def map_ledger_entry(payload: Any, lookups: CatalogLookups) -> dict[str, Any]:
    """Một `LedgerEntry` thành **một** dòng `cost_ledger_entries` (review #72 điểm 2).

    Ước tính và thực đo là hai bút toán riêng (`measure_kind`), dòng thực đo
    trỏ về dòng ước tính qua `estimate_entry_ref` (CLAUDE.md, 03 bản 0.9). Sai
    số dự báo là phép nối hai dòng đó, không phải phép trừ hai cột.

    Giờ người đổi sang phút (cột của web); giờ GPU là `quantity` khi dòng là
    tài nguyên GPU tính bằng giờ, None khi không phải. Thí nghiệm và đề xuất
    chỉ được điền khi tra ra đúng một; không ra thì để trống, không từ chối.
    """
    entry: LedgerEntry = _validated(LedgerEntry, payload, "ledger entry")
    recommendation = (lookups.recommendation_by_intervention.find(entry.intervention_id)
                      or lookups.recommendation_by_run_plan.find(entry.run_plan_id))
    row = {
        "entry_ref": entry.id,
        "entry_kind": "REVERSAL" if entry.reverses_entry_id else "ENTRY",
        "reverses_entry_ref": entry.reverses_entry_id,
        "activity": entry.activity,
        "resource_type": entry.resource_type,
        "quantity": entry.quantity,
        "unit": entry.unit,
        "price_book_name": entry.pricebook_id,
        "measure_kind": entry.measure_kind,
        "estimate_entry_ref": entry.estimate_entry_id,
        "usd_amount": entry.usd_amount,
        "human_minutes": entry.human_hours * 60,
        "gpu_hours": _gpu_hours(entry.resource_type, entry.unit, entry.quantity),
        "experiment_code": lookups.experiment_by_run_plan.find(entry.run_plan_id),
        "recommendation_ref": recommendation,
        "intervention_ref": entry.intervention_id,
        "cluster_ref": entry.cluster_id,
        "run_plan_ref": entry.run_plan_id,
        "branch": entry.branch,
        "job_id": entry.job_id,
        "operator_code": entry.person_code,
        "note": entry.note,
    }
    check_ledger_row(row, f"ledger entry `{entry.id}`")
    return row


def check_ledger_row(row: dict[str, Any], where: str) -> None:
    """Luật R5 trên một dòng sổ chi phí, cho cả dòng lõi lẫn dòng mock.

    Model hợp đồng đã cưỡng chế nó cho dòng lõi; dòng mock đi đường khoan
    dung nên phải kiểm ở đây, nếu không M8 sẽ hiện một sổ mà lõi không bao
    giờ ghi ra được.
    """
    kind = row.get("measure_kind")
    if kind not in MEASURE_KINDS:
        raise MappingError(f"{where}: measure_kind {kind!r} phải là một trong {MEASURE_KINDS}")
    if not isinstance(row.get("usd_amount"), (int, float)):
        raise MappingError(f"{where}: thiếu usd_amount")
    linked = row.get("estimate_entry_ref")
    if kind == "measured" and not linked:
        raise MappingError(f"{where}: dòng thực đo phải trỏ về dòng ước tính (estimate_entry_ref)")
    if kind == "estimated" and linked:
        raise MappingError(f"{where}: dòng ước tính không trỏ về dòng ước tính nào")
