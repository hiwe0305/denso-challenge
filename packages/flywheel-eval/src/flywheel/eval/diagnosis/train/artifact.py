"""One diagnosis run: every code, the record it leaves, and where it is kept.

This is where the twelve detectors of DA-08 become one answer about one
checkpoint. Three rules shape it.

**An input nobody has is a skip, not a pass.** A job directory without a probe
result cannot be judged on O1-O4, and a log written without an action layout
cannot be judged per dimension. Those come out as `skipped` entries naming the
file that is missing, and they travel into the artifact, because a
`TrainDiagnosis` whose `findings` and `skipped` are both empty says the
checkpoint is clean - a claim nobody measured (FR21, AC 4).

**The artifact is the contract record.** `TrainDiagnosis` of
`flywheel.contracts` is written as it stands, including the `DiagnosisSkip`
list; the lane adds no field of its own. A value that is not finite is encoded
as the string the contract defines, since `allow_inf_nan=False` keeps the JSON
valid - T1 on a NaN loss is exactly that case.

**The store is append-only.** A second run on the same job appends a second
record; nothing is rewritten and nothing is deleted. Until `flywheel.store`
offers a writer, the lane keeps them as one JSONL file per store directory,
which is the same guarantee in the simplest form that holds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import ProbeP3, ProbeP4
from flywheel.contracts.training import (
    DiagnosisFinding,
    DiagnosisSkip,
    NonFinite,
    TrainDiagnosis,
)
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.dimensions import detect_t5, detect_t6
from flywheel.eval.diagnosis.train.divergence import detect_t1
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.forgetting import detect_t7
from flywheel.eval.diagnosis.train.gradients import detect_t8
from flywheel.eval.diagnosis.train.groups import detect_t4
from flywheel.eval.diagnosis.train.learning import detect_t2, detect_t3
from flywheel.eval.diagnosis.train.offline import detect_o1, detect_o2, detect_o3, detect_o4
from flywheel.eval.diagnosis.train.reader import (
    LayoutView,
    ReaderError,
    TrainSeries,
    read_action_layout,
    read_probe_p3,
    read_probe_p4,
    read_series,
)

TRAIN_CODES = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8")
OFFLINE_CODES = ("O1", "O2", "O3", "O4")

METRICS_NAME = "metrics.jsonl"
LAYOUT_NAME = "action_layout.json"
PROBE_P3_NAME = "probe_p3.json"
PROBE_P4_NAME = "probe_p4.json"
PROBE_P4_PARENT_NAME = "probe_p4_parent.json"

STORE_RECORDS = Path("diagnosis") / "train.jsonl"


@dataclass(frozen=True)
class JobInputs:
    """Everything one diagnosis run reads, with None for what the job does not have.

    The log is required - without it there is no job to diagnose. Everything
    else is optional and its absence costs the codes that need it, by name.
    """

    series: TrainSeries
    layout: LayoutView | None = None
    probe_p3: ProbeP3 | None = None
    probe_p4: ProbeP4 | None = None
    probe_p4_parent: ProbeP4 | None = None


def load_job(path: Path) -> JobInputs:
    """Read a job directory, or the `metrics.jsonl` inside one, off disk.

    The layout is the file names rather than a manifest, because a train job
    writes its log and its probe results as separate files and nothing in the
    contracts ties them together yet. Naming the log directly is allowed, and
    the probe results are then looked for beside it.
    """
    metrics = path if path.is_file() else path / METRICS_NAME
    if not metrics.is_file():
        raise ReaderError(f"{path}: không tìm thấy {METRICS_NAME}")
    directory = metrics.parent
    return JobInputs(
        series=read_series(metrics),
        layout=_layout(directory / LAYOUT_NAME),
        probe_p3=_p3(directory / PROBE_P3_NAME),
        probe_p4=_p4(directory / PROBE_P4_NAME),
        probe_p4_parent=_p4(directory / PROBE_P4_PARENT_NAME),
    )


def diagnose_all(job: JobInputs, cfg: TrainThresholds) -> DetectorResult:
    """Every F-TRAIN and F-OFF code on one job, in the order of the fault table.

    Each code is judged on its own signals, so an input one code needs never
    costs another code its verdict.
    """
    results = [
        detect_t1(job.series, cfg),
        detect_t2(job.series, cfg),
        detect_t3(job.series, cfg),
        detect_t4(job.series, cfg),
    ]
    if job.layout is None:
        results.append(_missing_layout("T5"))
        results.append(_missing_layout("T6"))
    else:
        results.append(detect_t5(job.series, cfg, job.layout))
        results.append(detect_t6(job.series, cfg, job.layout))
    results.append(_t7(job, cfg))
    results.append(detect_t8(job.series, cfg))
    results.extend(_offline(job, cfg))
    return DetectorResult(
        findings=[finding for result in results for finding in result.findings],
        skipped=[skip for result in results for skip in result.skipped],
    )


def build_artifact(job: JobInputs, result: DetectorResult, config_sha256: str) -> TrainDiagnosis:
    """The `TrainDiagnosis` record of one run, both lists of it (AC 4)."""
    checkpoint_id = job.series.checkpoint_id
    if not checkpoint_id:
        raise ReaderError("log không ghi checkpoint_id, không biết artifact thuộc checkpoint nào")
    return TrainDiagnosis(
        checkpoint_id=checkpoint_id,
        config_sha256=config_sha256,
        findings=[_contract_finding(finding) for finding in result.findings],
        skipped=[DiagnosisSkip(code=skip.code, reason=skip.reason) for skip in result.skipped],
    )


def write_artifact(artifact: TrainDiagnosis, store_path: Path) -> Path:
    """Append the record to the store and return the file it went into (AC 4).

    Append-only: an earlier diagnosis of the same checkpoint stays where it is,
    so two runs under two threshold files can be told apart by their
    `config_sha256` instead of one silently replacing the other.
    """
    path = store_path / STORE_RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(artifact.model_dump_json() + "\n")
    return path


def _t7(job: JobInputs, cfg: TrainThresholds) -> DetectorResult:
    if job.probe_p4 is None:
        return DetectorResult(
            skipped=[Skipped("T7", f"job không có kết quả probe P4 (`{PROBE_P4_NAME}`)")]
        )
    return detect_t7(job.probe_p4, job.probe_p4_parent, cfg)


def _offline(job: JobInputs, cfg: TrainThresholds) -> list[DetectorResult]:
    """O1-O4, or the skips that say which probe or layout they needed.

    A job that ran P4 has P3 inside it, so the separate P3 file is only the
    first place to look; without either, all four codes go unjudged.
    """
    probe = job.probe_p3 or (job.probe_p4.p3 if job.probe_p4 is not None else None)
    if probe is None:
        return [
            DetectorResult(
                skipped=[Skipped(code, f"job không có kết quả probe P3 (`{PROBE_P3_NAME}`)")]
            )
            for code in OFFLINE_CODES
        ]
    results = [detect_o1(probe, cfg), detect_o2(probe, cfg), detect_o3(probe, cfg)]
    if job.layout is None:
        results.append(_missing_layout("O4"))
    else:
        results.append(detect_o4(probe, cfg, job.layout))
    return results


def _missing_layout(code: str) -> DetectorResult:
    return DetectorResult(
        skipped=[
            Skipped(
                code,
                f"job không có action_layout (`{LAYOUT_NAME}`), không biết chiều nào là chiều nào",
            )
        ]
    )


def _contract_finding(finding: Finding) -> DiagnosisFinding:
    return DiagnosisFinding(
        code=finding.code,  # type: ignore[arg-type]
        start_step=finding.start_step,
        group=finding.group,
        dim=finding.dim,
        value=_contract_value(finding.value),
        threshold=finding.threshold,
        stop_job=finding.stop_job,
    )


def _contract_value(value: float) -> float | NonFinite:
    """A measurement as the contract stores it; `allow_inf_nan=False` forbids the floats."""
    if np.isnan(value):
        return "NaN"
    if np.isposinf(value):
        return "Infinity"
    if np.isneginf(value):
        return "-Infinity"
    return value


def _layout(path: Path) -> LayoutView | None:
    return LayoutView(read_action_layout(path)) if path.is_file() else None


def _p3(path: Path) -> ProbeP3 | None:
    return read_probe_p3(path) if path.is_file() else None


def _p4(path: Path) -> ProbeP4 | None:
    return read_probe_p4(path) if path.is_file() else None
