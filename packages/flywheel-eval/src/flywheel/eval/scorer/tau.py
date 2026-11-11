"""Calibrate the thresholds of the system check from good runs (DA-37 AC 4, 6).

`configs/eval/diagnosis/system.yaml` ships τ_track, τ_sync and τ_lat as
assumptions. AC 4 replaces them with the 99th percentile measured where
nothing was wrong:

* **τ_track, upper and lower body apart** (spec section 6.4): from the norm of
  (command sent - state measured) per control cycle, on **successful teleop
  episodes**. A controller that tracks no worse than it did while a person got
  the task done is a controller nobody has evidence against.
* **τ_sync** (task 4): from |t_image - t_state| per cycle that carries a new
  frame, on the same successful episodes. On a SIMPLE rollout every offset is
  0 by construction (`runtime.py`, R4), so a τ_sync of 0 from sim says nothing
  about sensor sync and the command says so.
* **τ_lat** (task 4): from chunk_received_s - observation_sent_s of every
  chunk but chunk 0, in the RTC logs of the **G0 baseline run** (same machine,
  same RTC config), the other source AC 2 of DA-13 keeps apart. Chunk 0 is
  left out as R1 leaves it out: it is the cold start, not the running loop.

**The threshold is calibrated on the statistic the check compares with it.**
Every check judges one episode by one number: R3 by a percentile of that
episode's cycles (`r3.percentile`), R1 by a percentile of its chunks
(`r1.percentile`), R4 by its largest offset. So each good episode is reduced to
that same number first, and τ is the 99th percentile of those numbers across
the good episodes; the sample count is the number of episodes. Pooling the
cycles of every episode and taking one percentile (the first version, review
of #169) measured a different statistic than the check: the per-episode p99
scatters around the pooled p99, and about half of the very episodes the
threshold was calibrated on exceeded it. The report says how many calibration
episodes exceed their own threshold (`exceeded`); with fewer than 100 episodes
the 99th percentile sits between the two largest, so that is at most one.

The per-cycle measurement is DA-13's own (`TraceLog.tracking_error`,
`TraceLog.sync_offset`), read through DA-13's own loader (`load_episode`), and
the per-episode statistic is DA-13's `percentile`, so the threshold and the
check are computed the same way: wrapped heading, a cycle with a gap is nan
and left out, never read as zero error.

**A value always travels with its sample count** (AC 4). Under 100 episodes
the 99th percentile is nearly the largest one, which is a different claim, so
such a value is flagged `few_samples` and the command says so.

**Which episodes count is decided from the files, and said.** An episode
counts when its `rollout_result.json` says `infra_status` ok and
`sim_success` true. Teleop demonstrations have no `rollout_result.json`; they
count only when the caller declares the set to be successful demonstrations
(`declared_demos`), and each episode then records that its success was
declared rather than measured. A rollout SIMPLE could not judge
(`sim_success` empty) is left out even then: it is a rollout, not a demo.
Every episode left out is listed with why.

**A set is one kind of thing.** Episodes with a SIMPLE flag and declared
demos are not pooled, nor rollouts of two adapters, nor two runs
(`run_plan_id`) unless the caller says the runs belong together
(`mixed_runs`, recorded in the report). The same trace found twice with the
same bytes counts once and the copy is listed; with other bytes the run stops.
A G0 trace whose `rollout_result.json` beside the RTC log reports an
infrastructure fault is left out of τ_lat: a crashed trace's wait is the
crash, not the machine. Nothing under a benchmark copy
(`meta/benchmark_copy.json`, DA-27) is read: an injected defect is not a
good run.

The report has no time and no path, so the same episodes give the same bytes
and the same hash (AC 6); it is stored like the scorer check's report: bytes
in the blob store, one line in `<store>/scorer/tau.jsonl`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.v0 import RolloutResult
from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.reader import (
    ROLLOUT_NAME,
    RTC_NAME,
    STEPS_NAME,
    ReaderError,
    SystemInputs,
    Values,
    _rtc_records,
    load_episode,
    percentile,
)
from flywheel.store.blobs import put_blob
from flywheel.store.paths import StorePaths
from pydantic import BaseModel, ConfigDict, ValidationError

#: AC 4: every τ is the 99th percentile, across good episodes, of what the check measures.
CALIBRATION_PERCENTILE = 99.0
#: Under this many episodes the 99th percentile is close to the largest one.
FEW_SAMPLES = 100
#: R4 judges an episode by its largest offset (`runtime.check_r4`), not a configurable one.
LARGEST = 100.0
TAU_RECORDS = Path("scorer") / "tau.jsonl"
#: What DA-27 writes at the root of every benchmark copy (`meta/benchmark_copy.json`).
COPY_MARKER = Path("meta") / "benchmark_copy.json"

SuccessSource = Literal["sim_success", "declared_demo"]


class TauError(ValueError):
    """A set of episodes no threshold may be calibrated from."""


class TauValue(BaseModel):
    """One calibrated threshold, with the evidence it stands on (AC 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # The key in `system.yaml`, so the value can be carried there unchanged.
    key: str
    unit: str
    # None when no episode had a statistic: no threshold, rather than a zero one.
    value: float | None
    # Taken across the episodes' statistics.
    percentile: float = CALIBRATION_PERCENTILE
    # The statistic of one episode, as the check takes it: a percentile of its
    # cycles (100 is the largest, R4).
    episode_percentile: float
    # Episodes (G0 traces for τ_lat) that had a statistic: the sample count.
    samples: int
    # Measured cycles (chunks for τ_lat) behind those statistics.
    cycles: int
    # Cycles of the counted episodes with nothing to measure: a gap, and for
    # τ_sync also a cycle with no new frame.
    skipped_cycles: int
    # Calibration episodes whose own statistic is over the value.
    exceeded: int
    few_samples: bool
    method: str


class EpisodeUsed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    trace_sha256: str
    success: SuccessSource
    run_plan_ids: list[str]
    # `name@version` from `rollout_result.json`; None for a declared demo.
    adapter: str | None


class EpisodeLeftOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str
    reason: str


class RtcLogUsed(BaseModel):
    """One RTC log of the G0 baseline run that τ_lat was read from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: str
    job_ids: list[str]
    chunks: int
    # Traces of the log with no `rollout_result.json` beside it, so their
    # `infra_status` could not be checked.
    unchecked_traces: list[str]


class TauReport(BaseModel):
    """The calibration of AC 4: each value, how it was computed, and what it read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    values: list[TauValue]
    episodes: list[EpisodeUsed]
    left_out: list[EpisodeLeftOut]
    rtc_logs: list[RtcLogUsed]
    # True when the caller declared episodes of several runs to be one set.
    mixed_runs: bool = False

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
class EpisodeStatistics:
    """The statistic each check takes over one episode (`system.yaml`)."""

    track_percentile: float  # r3.percentile
    lat_percentile: float  # r1.percentile
    sync_percentile: float = LARGEST  # r4: the largest offset

    @classmethod
    def of(cls, thresholds: SystemThresholds) -> EpisodeStatistics:
        return cls(
            track_percentile=thresholds.r3.percentile,
            lat_percentile=thresholds.r1.percentile,
        )


@dataclass(frozen=True)
class Candidate:
    """One trace on disk, as read, before deciding whether it counts."""

    inputs: SystemInputs
    # `rollout_result.json` beside the steps; None where the file is absent.
    result: RolloutResult | None = None

    @property
    def adapter(self) -> str | None:
        if self.result is None:
            return None
        info = self.result.adapter_info
        return f"{info.name}@{info.version}"


@dataclass(frozen=True)
class RtcLog:
    """One `rtc.jsonl` as read: its records, the hash of its bytes, its traces' status.

    `infra` maps a trace of the log to the `infra_status` of the
    `rollout_result.json` beside it, None where there is none.
    """

    sha256: str
    records: tuple[RTCInferenceRecord, ...]
    infra: Mapping[str, str | None] = field(default_factory=dict)


_TRACK = (
    ("upper", "tau_track_upper", "rad"),
    ("lower", "tau_track_lower", "chuẩn hỗn hợp: rad, m, m/s"),
)
_PART_NAMES = {"upper": "trên", "lower": "dưới"}


def calibrate(
    candidates: Sequence[Candidate],
    rtc_logs: Sequence[RtcLog] = (),
    statistics: EpisodeStatistics | None = None,
    declared_demos: bool = False,
    mixed_runs: bool = False,
) -> TauReport:
    """Every τ the inputs allow: τ_track and τ_sync from traces, τ_lat from RTC logs (AC 4).

    `statistics` is what each check takes over one episode, read from the
    `system.yaml` the checks run on; it is required as soon as there is input.
    """
    if not candidates and not rtc_logs:
        raise TauError("không có đầu vào: cần trace teleop, log RTC của G0, hoặc cả hai")
    if statistics is None:
        raise TauError("thiếu thống kê từng episode của các check (`system.yaml`)")
    values: list[TauValue] = []
    episodes: list[EpisodeUsed] = []
    left_out: list[EpisodeLeftOut] = []
    if candidates:
        values, episodes, left_out = _teleop(candidates, statistics, declared_demos, mixed_runs)
    logs = _unique_logs(rtc_logs)
    if logs:
        latency, left_g0 = _latency(logs, statistics)
        values.append(latency)
        left_out.extend(left_g0)
    return TauReport(
        values=values,
        episodes=episodes,
        left_out=left_out,
        rtc_logs=[
            RtcLogUsed(
                sha256=log.sha256,
                job_ids=sorted({record.job_id for record in log.records}),
                chunks=len(log.records),
                unchecked_traces=sorted(
                    {r.trace_id for r in log.records} - {t for t, s in log.infra.items() if s}
                ),
            )
            for log in logs
        ],
        mixed_runs=mixed_runs,
    )


def _teleop(
    candidates: Sequence[Candidate],
    statistics: EpisodeStatistics,
    declared_demos: bool,
    mixed_runs: bool,
) -> tuple[list[TauValue], list[EpisodeUsed], list[EpisodeLeftOut]]:
    """τ_track of each half of the body and τ_sync, from the successful episodes."""
    unique, left_out = _unique_traces(candidates)
    used: list[tuple[Candidate, SuccessSource]] = []
    for candidate in unique:
        verdict = _success(candidate, declared_demos)
        if isinstance(verdict, EpisodeLeftOut):
            left_out.append(verdict)
        else:
            used.append((candidate, verdict))
    if not used:
        reasons = [item for item in left_out if not item.reason.startswith("bản giống hệt")]
        raise TauError(
            "không có episode thành công nào để hiệu chỉnh"
            + (f"; bỏ {len(reasons)}: {reasons[0].reason}" if reasons else "")
        )
    _refuse_mixed(used, mixed_runs)
    track = statistics.track_percentile
    values = [
        _calibrated(
            key,
            unit,
            [c.inputs.trace.tracking_error(part) for c, _ in used],
            track,
            f"mỗi episode: phân vị {track:g} của chuẩn (lệnh gửi - trạng thái đo) thân "
            f"{_PART_NAMES[part]} qua các chu kỳ, như R3 (`TraceLog.tracking_error` của DA-13); "
            f"τ là phân vị {CALIBRATION_PERCENTILE:g} của các số đó qua episode",
        )
        for part, key, unit in _TRACK
    ]
    values.append(
        _calibrated(
            "tau_sync_s",
            "s",
            [c.inputs.trace.sync_offset() for c, _ in used],
            statistics.sync_percentile,
            "mỗi episode: |t_image - t_state| lớn nhất qua các chu kỳ có khung ảnh mới, như R4 "
            f"(`TraceLog.sync_offset` của DA-13); τ là phân vị {CALIBRATION_PERCENTILE:g} "
            "của các số đó qua episode",
        )
    )
    _refuse_unmeasured(values, "trace")
    episodes = [
        EpisodeUsed(
            trace_id=c.inputs.trace.trace_id,
            trace_sha256=c.inputs.trace.trace_sha256,
            success=source,
            run_plan_ids=_run_plans(c),
            adapter=c.adapter,
        )
        for c, source in used
    ]
    return values, episodes, left_out


def _latency(
    logs: Sequence[RtcLog], statistics: EpisodeStatistics
) -> tuple[TauValue, list[EpisodeLeftOut]]:
    """τ_lat from the G0 baseline run, one statistic per trace as R1 takes it.

    Chunk 0 is left out as R1 leaves it out; a trace whose result reports an
    infrastructure fault is left out and listed.
    """
    chunks: dict[tuple[str, str], dict[int, RTCInferenceRecord]] = {}
    left_out: dict[str, EpisodeLeftOut] = {}
    for log in logs:
        for record in log.records:
            infra = log.infra.get(record.trace_id)
            if infra is not None and infra != "ok":
                left_out[record.trace_id] = EpisodeLeftOut(
                    trace_id=record.trace_id, reason=f"log RTC của G0: lỗi hạ tầng `{infra}`"
                )
                continue
            if record.chunk_index == 0:
                continue
            held = chunks.setdefault((record.job_id, record.trace_id), {})
            same = held.get(record.chunk_index)
            if same is not None and same != record:
                raise TauError(
                    f"chunk {record.chunk_index} của trace `{record.trace_id}` (job "
                    f"`{record.job_id}`) có hai bản khác nhau trong các log RTC"
                )
            held[record.chunk_index] = record
    series = [
        np.array(
            [r.chunk_received_s - r.observation_sent_s for _, r in sorted(held.items())],
            dtype=np.float64,
        )
        for _, held in sorted(chunks.items())
    ]
    lat = statistics.lat_percentile
    value = _calibrated(
        "tau_lat_s",
        "s",
        series,
        lat,
        f"mỗi trace: phân vị {lat:g} của chunk_received_s - observation_sent_s qua mọi chunk "
        f"trừ chunk 0, như R1, trên log RTC của lần chạy chuẩn G0; τ là phân vị "
        f"{CALIBRATION_PERCENTILE:g} của các số đó qua trace; phải giữ ≤ d / hz "
        "(`system.yaml`, r1)",
    )
    _refuse_unmeasured([value], "log RTC")
    return value, [left_out[trace] for trace in sorted(left_out)]


def _success(candidate: Candidate, declared_demos: bool) -> SuccessSource | EpisodeLeftOut:
    trace_id = candidate.inputs.trace.trace_id
    result = candidate.result
    if result is None:
        if declared_demos:
            return "declared_demo"
        return EpisodeLeftOut(
            trace_id=trace_id,
            reason=(
                f"không có `{ROLLOUT_NAME}` nên không có cờ thành công; "
                "nếu đây là demo teleop thành công thì khai bằng `--demos`"
            ),
        )
    if result.infra_status != "ok":
        return EpisodeLeftOut(trace_id=trace_id, reason=f"lỗi hạ tầng `{result.infra_status}`")
    if result.sim_success is True:
        return "sim_success"
    if result.sim_success is False:
        return EpisodeLeftOut(trace_id=trace_id, reason="SIMPLE báo trượt")
    # A rollout SIMPLE could not judge is not a demo, `--demos` or not.
    return EpisodeLeftOut(trace_id=trace_id, reason="SIMPLE không kết luận (`sim_success` rỗng)")


def _calibrated(
    key: str, unit: str, series: Iterable[Values], episode_percentile: float, method: str
) -> TauValue:
    """τ as the 99th percentile, across episodes, of each episode's own statistic."""
    statistics: list[float] = []
    cycles = skipped = 0
    for values in series:
        array = np.asarray(values, dtype=np.float64)
        measured = int(np.isfinite(array).sum())
        cycles += measured
        skipped += int(array.size) - measured
        statistic = percentile(array, episode_percentile)
        if np.isfinite(statistic):
            statistics.append(statistic)
    calibrated = percentile(np.array(statistics, dtype=np.float64), CALIBRATION_PERCENTILE)
    value = calibrated if np.isfinite(calibrated) else None
    return TauValue(
        key=key,
        unit=unit,
        value=value,
        episode_percentile=episode_percentile,
        samples=len(statistics),
        cycles=cycles,
        skipped_cycles=skipped,
        exceeded=0 if value is None else sum(1 for s in statistics if s > value),
        few_samples=len(statistics) < FEW_SAMPLES,
        method=method,
    )


def _unique_traces(
    candidates: Sequence[Candidate],
) -> tuple[list[Candidate], list[EpisodeLeftOut]]:
    """One candidate per trace: a copy with the same bytes is listed, other bytes stop the run."""
    kept: dict[str, Candidate] = {}
    copies: list[EpisodeLeftOut] = []
    for candidate in sorted(
        candidates, key=lambda c: (c.inputs.trace.trace_id, c.inputs.trace.trace_sha256)
    ):
        trace = candidate.inputs.trace
        held = kept.get(trace.trace_id)
        if held is None:
            kept[trace.trace_id] = candidate
        elif held.inputs.trace.trace_sha256 != trace.trace_sha256:
            raise TauError(f"trace `{trace.trace_id}` có hai bản `{STEPS_NAME}` khác nhau")
        else:
            copies.append(
                EpisodeLeftOut(
                    trace_id=trace.trace_id,
                    reason="bản giống hệt của một trace đã tính, chỉ tính một lần",
                )
            )
    return list(kept.values()), copies


def _unique_logs(logs: Sequence[RtcLog]) -> list[RtcLog]:
    """One log per content: the same file found twice is one log."""
    unique: dict[str, RtcLog] = {}
    for log in logs:
        unique.setdefault(log.sha256, log)
    return [unique[digest] for digest in sorted(unique)]


def _run_plans(candidate: Candidate) -> list[str]:
    return sorted({row.run_plan_id for row in candidate.inputs.trace.rows})


def _refuse_mixed(used: Sequence[tuple[Candidate, SuccessSource]], mixed_runs: bool) -> None:
    """One kind of episode per set: one success source, one adapter, one run unless declared."""
    sources = sorted({source for _, source in used})
    if len(sources) > 1:
        raise TauError(
            "tập trộn episode có cờ SIMPLE với demo khai bằng `--demos`; hiệu chỉnh từng loại riêng"
        )
    adapters = sorted({c.adapter or "-" for c, _ in used})
    if len(adapters) > 1:
        raise TauError(f"tập trộn rollout của nhiều adapter: {', '.join(adapters)}")
    runs = sorted({run for c, _ in used for run in _run_plans(c)})
    if len(runs) > 1 and not mixed_runs:
        raise TauError(
            f"tập trộn {len(runs)} run ({', '.join(runs[:4])}{', …' if len(runs) > 4 else ''}); "
            "nếu các run này cùng một task và cấu hình thì khai bằng `--mixed-runs`"
        )


def _refuse_unmeasured(values: Sequence[TauValue], source: str) -> None:
    if all(item.value is None for item in values):
        raise TauError(
            f"không giá trị nào đo được từ {source}: mọi chu kỳ thiếu tín hiệu hoặc không có mẫu"
        )


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------


def read_candidates(paths: Sequence[Path]) -> list[Candidate]:
    """Every trace directory `<trace_id>/` under the given paths, read strictly.

    A path is a trace directory itself or any directory above some; a trace
    found twice through two paths is read once. A file that does not parse
    stops the run with its name (`ReaderError`, `TauError`) instead of
    shrinking the set the percentile is taken on, and so does a trace inside
    a benchmark copy.
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
    for directory in sorted(directories):
        _refuse_benchmark_copy(directory)
    return [_candidate(directory) for directory in sorted(directories)]


def read_rtc_logs(paths: Sequence[Path]) -> list[RtcLog]:
    """Every `rtc.jsonl` at or under the given paths, read through `RTCInferenceRecord`.

    Each file is read once: the hash and the records come from the same bytes.
    """
    files: set[Path] = set()
    for path in paths:
        found = {path.resolve()} if path.is_file() else {f.resolve() for f in path.rglob(RTC_NAME)}
        if not found:
            raise TauError(f"không có `{RTC_NAME}` nào dưới `{path}`")
        files |= found
    logs = []
    for file in sorted(files):
        _refuse_benchmark_copy(file)
        try:
            data = file.read_bytes()
        except OSError as error:
            raise ReaderError(f"`{file}` không đọc được: {error}") from error
        records = _rtc_records(data, file)
        infra = {trace: _infra_beside(file, trace) for trace in {r.trace_id for r in records}}
        logs.append(RtcLog(hashlib.sha256(data).hexdigest(), records, infra))
    return logs


def _infra_beside(log: Path, trace_id: str) -> str | None:
    """`infra_status` of `<job>/<trace_id>/rollout_result.json`, the log being `<job>/rtc.jsonl`."""
    path = log.parent / trace_id / ROLLOUT_NAME
    if not path.is_file():
        return None
    return _result(path).infra_status


def _refuse_benchmark_copy(path: Path) -> None:
    for folder in (path, *path.parents):
        marker = folder / COPY_MARKER
        if marker.is_file():
            raise TauError(
                f"`{path}` nằm trong bản sao benchmark `{folder}` (`{COPY_MARKER.as_posix()}`): "
                "dữ liệu cấy lỗi không dùng để hiệu chỉnh ngưỡng"
            )


def _candidate(directory: Path) -> Candidate:
    inputs = load_episode(directory)
    result_path = directory / ROLLOUT_NAME
    if not result_path.is_file():
        return Candidate(inputs)
    return Candidate(inputs, _result(result_path))


def _result(path: Path) -> RolloutResult:
    try:
        return RolloutResult.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as error:
        raise TauError(f"`{path}` không đọc được: {error}") from error


def store_tau_report(report: TauReport, store_path: Path) -> tuple[str, Path]:
    """Put the report in the blob store and list it; return its hash and the list."""
    digest = put_blob(report.canonical(), StorePaths(store_path))
    line = {
        "report_sha256": digest,
        "episodes": len(report.episodes),
        "rtc_logs": len(report.rtc_logs),
        "values": {
            item.key: {"value": item.value, "samples": item.samples} for item in report.values
        },
    }
    index = store_path / TAU_RECORDS
    index.parent.mkdir(parents=True, exist_ok=True)
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    return digest, index
