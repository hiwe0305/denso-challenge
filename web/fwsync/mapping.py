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
from flywheel.contracts.training import TrainDiagnosis, TrainingMetric
from pydantic import BaseModel, ValidationError

#: Trường của hợp đồng bị bỏ có chủ ý, và lý do. Test kiểm danh sách này, nên
#: một trường bị bỏ âm thầm sẽ không lọt.
#: Khoá là `<Model>.<trường>`; mapper bỏ trường đó khỏi mọi cột và `meta`.
DROPPED_FIELDS: dict[str, str] = {
    "SystemDiagnosis.episode_id": (
        "tên `episode_N` của dòng thống kê SIMPLE, đếm lại ở mỗi lượt eval nên không "
        "duy nhất; bản ghi nối với `eval_episodes` bằng `trace_sha256` (W13)"
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
