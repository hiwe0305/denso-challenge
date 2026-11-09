"""Calibrate the thresholds of the system check from good runs (DA-37 AC 4, 6).

`configs/eval/diagnosis/system.yaml` ships τ_track and τ_sync as assumptions.
AC 4 replaces them with the 99th percentile measured where nothing was wrong:

* **τ_track, upper and lower body apart** (spec section 6.4): the norm of
  (command sent - state measured) per control cycle, on **successful teleop
  episodes**. A controller that tracks no worse than it did while a person got
  the task done is a controller nobody has evidence against.

The per-cycle measurement is DA-13's own (`TraceLog.tracking_error`), read
through DA-13's own loader (`load_episode`), so the threshold and the check it
feeds are computed the same way: wrapped heading, a cycle with a gap is nan
and left out, never read as zero error.

**The cycles of every episode are pooled, then the percentile is taken.** A
threshold is a statement about one cycle of a healthy run, and pooling gives
each cycle one vote; a percentile of per-episode percentiles would give a
short episode the weight of a long one.

**A value always travels with its sample count** (AC 4). Under 100 samples the
99th percentile is nearly the largest value, which is a different claim, so
such a value is flagged `few_samples` and the command says so.

**Which episodes count is decided from the files, and said.** An episode
counts when its `rollout_result.json` says `infra_status` ok and
`sim_success` true. Teleop demonstrations have no SIMPLE flag; they count only
when the caller declares the set to be successful demonstrations
(`declared_demos`), and each episode then records that its success was
declared rather than measured. Every episode left out is listed with why.

The report has no time and no path, so the same episodes give the same bytes
and the same hash (AC 6); it is stored like the scorer check's report: bytes
in the blob store, one line in `<store>/scorer/tau.jsonl`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from flywheel.contracts.v0 import RolloutResult
from flywheel.eval.diagnosis.system.reader import (
    ROLLOUT_NAME,
    STEPS_NAME,
    SystemInputs,
    Values,
    load_episode,
    percentile,
)
from flywheel.store.blobs import put_blob
from flywheel.store.paths import StorePaths
from pydantic import BaseModel, ConfigDict, ValidationError

#: AC 4: every τ is the 99th percentile of its measurement on good runs.
CALIBRATION_PERCENTILE = 99.0
#: Under this many samples the 99th percentile is close to the largest value.
FEW_SAMPLES = 100
TAU_RECORDS = Path("scorer") / "tau.jsonl"

SuccessSource = Literal["sim_success", "declared_demo"]


class TauError(ValueError):
    """A set of episodes no threshold may be calibrated from."""


class TauValue(BaseModel):
    """One calibrated threshold, with the evidence it stands on (AC 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # The key in `system.yaml`, so the value can be carried there unchanged.
    key: str
    unit: str
    # None when no sample was measured: no threshold, rather than a zero one.
    value: float | None
    percentile: float = CALIBRATION_PERCENTILE
    samples: int
    episodes: int
    # Cycles of the counted episodes that carried no measurement (a gap).
    skipped_cycles: int
    few_samples: bool
    method: str


class EpisodeUsed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    trace_sha256: str
    success: SuccessSource


class EpisodeLeftOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    reason: str


class TauReport(BaseModel):
    """The calibration of AC 4: each value, how it was computed, and what it read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    values: list[TauValue]
    episodes: list[EpisodeUsed]
    left_out: list[EpisodeLeftOut]

    def canonical(self) -> bytes:
        """The bytes the report is stored and hashed as."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()

    def value(self, key: str) -> TauValue:
        return next(item for item in self.values if item.key == key)


@dataclass(frozen=True)
class Candidate:
    """One trace on disk, as read, before deciding whether it counts."""

    inputs: SystemInputs
    # From `rollout_result.json`; None where the file is absent.
    sim_success: bool | None = None


_TRACK = (
    ("upper", "tau_track_upper", "rad"),
    ("lower", "tau_track_lower", "chuẩn hỗn hợp: rad, m, m/s"),
)


def calibrate_teleop(candidates: Sequence[Candidate], declared_demos: bool = False) -> TauReport:
    """τ_track of each half of the body from the successful episodes (AC 4)."""
    _refuse_duplicates(candidates)
    used: list[tuple[Candidate, SuccessSource]] = []
    left_out: list[EpisodeLeftOut] = []
    for candidate in sorted(candidates, key=lambda c: c.inputs.trace.trace_id):
        verdict = _success(candidate, declared_demos)
        if isinstance(verdict, EpisodeLeftOut):
            left_out.append(verdict)
        else:
            used.append((candidate, verdict))
    if not used:
        raise TauError(
            "không có episode thành công nào để hiệu chỉnh"
            + (f"; bỏ {len(left_out)}: {left_out[0].reason}" if left_out else "")
        )
    values = [
        _pooled(
            key,
            unit,
            [c.inputs.trace.tracking_error(part) for c, _ in used],
            f"chuẩn (lệnh gửi - trạng thái đo) thân {_PART_NAMES[part]} mỗi chu kỳ "
            "(`TraceLog.tracking_error` của DA-13), gộp mọi chu kỳ rồi lấy phân vị",
        )
        for part, key, unit in _TRACK
    ]
    return TauReport(
        values=values,
        episodes=[
            EpisodeUsed(
                trace_id=c.inputs.trace.trace_id,
                trace_sha256=c.inputs.trace.trace_sha256,
                success=source,
            )
            for c, source in used
        ],
        left_out=left_out,
    )


_PART_NAMES = {"upper": "trên", "lower": "dưới"}


def _success(candidate: Candidate, declared_demos: bool) -> SuccessSource | EpisodeLeftOut:
    trace_id = candidate.inputs.trace.trace_id
    infra = candidate.inputs.infra_status
    if infra is not None and infra != "ok":
        return EpisodeLeftOut(trace_id=trace_id, reason=f"lỗi hạ tầng `{infra}`")
    if candidate.sim_success is True:
        return "sim_success"
    if candidate.sim_success is False:
        return EpisodeLeftOut(trace_id=trace_id, reason="SIMPLE báo trượt")
    if declared_demos:
        return "declared_demo"
    return EpisodeLeftOut(
        trace_id=trace_id,
        reason=(
            "không có cờ thành công (`rollout_result.json` thiếu hoặc `sim_success` rỗng); "
            "nếu đây là demo teleop thành công thì khai bằng `--demos`"
        ),
    )


def _pooled(key: str, unit: str, series: Iterable[Values], method: str) -> TauValue:
    arrays = [np.asarray(values, dtype=np.float64) for values in series]
    pooled = np.concatenate(arrays) if arrays else np.empty(0, dtype=np.float64)
    finite = np.isfinite(pooled)
    samples = int(finite.sum())
    statistic = percentile(pooled, CALIBRATION_PERCENTILE)
    return TauValue(
        key=key,
        unit=unit,
        value=statistic if np.isfinite(statistic) else None,
        samples=samples,
        episodes=sum(1 for values in arrays if np.isfinite(values).any()),
        skipped_cycles=int(pooled.size - samples),
        few_samples=samples < FEW_SAMPLES,
        method=method,
    )


def _refuse_duplicates(candidates: Sequence[Candidate]) -> None:
    seen: dict[str, str] = {}
    for candidate in candidates:
        trace = candidate.inputs.trace
        held = seen.get(trace.trace_id)
        if held is not None and held != trace.trace_sha256:
            raise TauError(f"trace `{trace.trace_id}` có hai bản `{STEPS_NAME}` khác nhau")
        seen[trace.trace_id] = trace.trace_sha256


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------


def read_candidates(paths: Sequence[Path]) -> list[Candidate]:
    """Every trace directory `<trace_id>/` under the given paths, read strictly.

    A path is a trace directory itself or any directory above some; a trace
    found twice through two paths is read once. A file that does not parse
    stops the run with its name (`ReaderError`, `TauError`) instead of
    shrinking the set the percentile is taken on.
    """
    directories: set[Path] = set()
    for path in paths:
        if (path / STEPS_NAME).is_file():
            directories.add(path.resolve())
            continue
        found = {steps.parent.resolve() for steps in path.rglob(STEPS_NAME)}
        if not found:
            raise TauError(f"không có `{STEPS_NAME}` nào dưới `{path}`")
        directories |= found
    return [_candidate(directory) for directory in sorted(directories)]


def _candidate(directory: Path) -> Candidate:
    inputs = load_episode(directory)
    result_path = directory / ROLLOUT_NAME
    if not result_path.is_file():
        return Candidate(inputs)
    try:
        result = RolloutResult.model_validate_json(result_path.read_bytes())
    except (OSError, ValidationError) as error:  # load_episode read it already
        raise TauError(f"`{result_path}` không đọc được: {error}") from error
    return Candidate(inputs, result.sim_success)


def store_tau_report(report: TauReport, store_path: Path) -> tuple[str, Path]:
    """Put the report in the blob store and list it; return its hash and the list."""
    digest = put_blob(report.canonical(), StorePaths(store_path))
    line = {
        "report_sha256": digest,
        "episodes": len(report.episodes),
        "values": {
            item.key: {"value": item.value, "samples": item.samples} for item in report.values
        },
    }
    index = store_path / TAU_RECORDS
    index.parent.mkdir(parents=True, exist_ok=True)
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    return digest, index
