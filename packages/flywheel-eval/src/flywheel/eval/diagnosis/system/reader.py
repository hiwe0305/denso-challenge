"""What the F-SYS checks read, and the one place a contract change stops (DA-13 AC 1, 3).

Reading is kept away from judging, the split DA-36 made in `scorer/reader.py`.
This module turns bytes on disk into arrays and says what is missing; it never
decides whether the controller tracked its commands. Every check takes a
`SystemInputs` and nothing else, so a field renamed in `flywheel.contracts`
reaches this module and goes no further.

**Every input is read through its contract.** A line of `steps.jsonl` is a
`flywheel.contracts.trace.TraceStep` and a line of `camera_params.jsonl` a
`CameraParams` (Contract change #31, merged as PR #79); the RTC log is
`RTCInferenceRecord` and the probe results `ProbeP1`, `ProbeP3` and `ProbeP4`.
A line the contract refuses - a field missing, a vector not 28 or 7 wide, a
bare JSON `NaN` - raises here with its line number, so what the checks receive
always has every field. Nothing downstream reads the contract types of the
trace, only the arrays `TraceLog` makes of them, so a field renamed in the
contract stops in this module.

**A value that is not finite is read as missing, not as a number.**
`TraceStep` writes one as the string `"NaN"`, `"Infinity"` or `"-Infinity"`,
and every comparison against a NaN is false, so a trace whose tracking error
is NaN on every cycle would clear every threshold it was checked against and
come back as a clean controller. That is the silent pass FR21 forbids, so
each of the three strings becomes a gap here and reaches the checks as one,
which is what makes the first step of spec section 6.4, "thiếu tín hiệu →
CHƯA RÕ", fire on it.

**`t_image: null` is not a gap.** The camera renders slower than the control
loop runs, and `TraceStep` marks a cycle with no new frame by a null
`t_image` (README of the #31 fixtures; the SIMPLE hook of DA-38 sets it once
per chunk). Such a cycle has no image to pair with its state, so it carries
no sync offset and costs R4 nothing; only a non-finite `t_image` is a gap.
Null and non-finite are therefore kept apart: a gap reads as nan, "no new
frame" as None.

**A file that is not there and a file that is corrupt are different.** An
absent RTC log costs R1 and R2 their verdict, by name, and the loader returns
None for it. A file that is there and cannot be parsed raises, because
something was written and nobody knows what it says.

**Every file a verdict is read from is hashed.** R1 and R2 read the RTC log,
R5 the camera parameters and R6 the RolloutResult, so `SystemInputs` carries the
SHA-256 of each beside the trace's; one trace with two RTC logs is then two
records the store can tell apart. The RTC hash is of the whole file, before it
is kept to this trace's chunks, because that is the file that was read.

**The layout is decision G1 of the PO on PR #48** (3/11/2026): a trace is a
directory `<trace_id>/`, the one `TraceRef.uri` points at::

    <job_dir>/
      rtc.jsonl                # RTCClient of DA-19, one per job, keyed by trace_id
      <trace_id>/
        steps.jsonl            # one TraceStep per control cycle
        camera_params.jsonl    # one CameraParams per line, each with trace_id;
                               # absent when the job had no pinned reference
        rollout_result.json    # v0 RolloutResult (infra_status); decision G1b

The three names inside `<trace_id>/` are the contract's (`STEPS_NAME`,
`CAMERA_NAME`, `RESULT_NAME` of `flywheel.contracts.trace`), re-exported below
with the RTC log's, which is this lane's; `rollout_result.json` is decision G1b
of the PO (3/11/2026). The RolloutResult is read through
`flywheel.contracts.v0.RolloutResult`, so an `infra_status` outside the
contract's `InfraStatus` is refused rather than read as a fault. Its
`trace_ref` is checked against the directory it sits in, loudly: `trace_id`
must be the steps' own, `uri` must name this `<trace_id>/` directory, and
`sha256` - the hash of `steps.jsonl` as the hook wrote it - must be the hash of
the steps read, so a result is never paired with steps it is not about. A
camera line or a step of another trace is refused the same way. Either the
directory, the steps file or the RolloutResult file names a trace. A steps
file with no step at all - a rollout cut off before its first cycle - is read
as a trace of zero cycles named after its directory, so R6 still judges the
RolloutResult beside it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

import numpy as np
from flywheel.contracts.artifacts import ProbeP1, ProbeP3, ProbeP4, RTCInferenceRecord
from flywheel.contracts.trace import CAMERA_NAME as CAMERA_NAME
from flywheel.contracts.trace import (
    LOWER_BODY,
    RESULT_NAME,
    UPPER_BODY,
    CameraParams,
    FloatOrNonFinite,
    TraceStep,
)
from flywheel.contracts.trace import STEPS_NAME as STEPS_NAME
from flywheel.contracts.v0 import RolloutResult
from numpy.typing import NDArray
from pydantic import ValidationError

Values = NDArray[np.float64]

_ARTIFACT = TypeVar("_ARTIFACT", ProbeP1, ProbeP3, ProbeP4)
_LINE = TypeVar("_LINE", TraceStep, CameraParams, RTCInferenceRecord)

# Channels whose value is a direction on the circle, by the contract's names:
# the base heading `yaw` (rad, world frame), where +pi and -pi are one heading.
# The waist joints are not on the list although they are angles too: they are
# revolute joints with limits (G1: roll, pitch +-0.52, yaw +-2.618 rad in
# `configs/embodiments/g1.yaml`), so a waist error over pi is a joint that has
# to travel that far, and wrapping it would shrink a real fault.
PERIODIC_CHANNELS = frozenset({"yaw"})
_PERIODIC = {
    part: np.array([name in PERIODIC_CHANNELS for name in names], dtype=bool)
    for part, names in (("upper", UPPER_BODY), ("lower", LOWER_BODY))
}

# The fields of `TraceStep` each check needs, named so a gap is reported by
# the name the writer used.
TRACK_FIELDS = ("cmd_upper", "meas_upper", "cmd_lower", "meas_lower")
SYNC_FIELDS = ("t_state", "t_image")


class ReaderError(ValueError):
    """A trace, RTC log or camera file no check of this story may run on."""


@dataclass(frozen=True)
class TraceLog:
    """One episode's control trace as arrays, plus what it does not carry.

    `gap_counts` is, per field, the cycles the writer logged as a value that
    is not finite. A gap costs a check its verdict and is reported in the words
    of the field, because "chẩn đoán CHƯA RÕ, đề xuất thu thêm bằng chứng" is
    only actionable if it says which evidence to collect (spec section 6.4,
    step 1). `trace_id` is the steps' own, or the directory's name for a steps
    file with no step in it.
    """

    episode_id: str
    trace_id: str
    rows: tuple[TraceStep, ...]
    gap_counts: dict[str, int]
    dropped_frames: int
    trace_sha256: str

    @property
    def num_steps(self) -> int:
        return len(self.rows)

    def tracking_error(self, part: str) -> Values:
        """Norm of (command - measurement) per cycle for one half of the body (R3).

        Spec section 6.4 defines the measurement as the norm of the difference
        between the command sent and the state measured, upper and lower body
        apart. A cycle with a gap on either side is nan, not zero: a dropped
        measurement is not a cycle that tracked perfectly. On a periodic
        channel (`PERIODIC_CHANNELS`) the difference is the shorter way round
        the circle, atan2(sin d, cos d): a target heading of 3.13 rad and a
        measured one of -3.13 rad are 0.023 rad apart, not 6.26.
        """
        commands = _matrix(self.rows, f"cmd_{part}")
        measured = _matrix(self.rows, f"meas_{part}")
        if commands.size == 0 or measured.size == 0:
            return np.empty(0, dtype=np.float64)
        # `TraceStep` fixes the width of both, so the two always line up.
        difference = commands - measured
        periodic = _PERIODIC[part]
        wrapped = difference[:, periodic]
        difference[:, periodic] = np.arctan2(np.sin(wrapped), np.cos(wrapped))
        # A cycle missing one channel is a cycle nobody measured the error of.
        whole = np.isfinite(difference).all(axis=1)
        norms = np.sqrt(np.nansum(np.square(difference), axis=1))
        return np.where(whole, norms, np.nan)

    def sync_offset(self) -> Values:
        """|t_image - t_state| per cycle (R4).

        nan where either timestamp is a gap and where the cycle has no new
        frame: a cycle with no image has no offset to measure.
        """
        state = _column(self.rows, "t_state")
        image = _column(self.rows, "t_image")
        if state.size == 0 or image.size == 0:
            return np.empty(0, dtype=np.float64)
        return np.abs(image - state)

    @property
    def frame_cycles(self) -> int:
        """Cycles that carry a new frame with a finite timestamp on both clocks."""
        return int(np.isfinite(self.sync_offset()).sum())


@dataclass(frozen=True)
class SystemInputs:
    """Everything one system check reads, with None for what the episode lacks.

    The trace is required - without it there is nothing to check. The RTC log,
    the camera parameters and `infra_status` are optional and their absence
    costs the codes that need them, by name.
    """

    trace: TraceLog
    rtc: tuple[RTCInferenceRecord, ...] = ()
    cameras: tuple[CameraParams, ...] = ()
    infra_status: str | None = None
    has_rtc_log: bool = False
    has_camera_params: bool = False
    # SHA-256 of the bytes each optional input was read from, None where absent
    rtc_sha256: str | None = None
    camera_sha256: str | None = None
    infra_sha256: str | None = None


@dataclass(frozen=True)
class StageInputs:
    """The probe evidence the stage attribution reads (AC 3).

    Every field is optional: a hypothesis that has no probe behind it is not
    stated, and the row says which probe it was waiting for. `t7` is the
    forgetting finding of DA-08, passed in rather than recomputed, so the two
    stories cannot disagree about whether a checkpoint forgot; None is "DA-08
    has not been run", which leaves the forgetting row unavailable rather
    than inapplicable.
    """

    p1: ProbeP1 | None = None
    p3: ProbeP3 | None = None
    p4: ProbeP4 | None = None
    t7: bool | None = None
    out_of_domain: bool = False
    closed_loop_failed: bool = True
    failed_step: int | None = None
    action_groups: tuple[str, ...] = ()


# The layout of a trace on disk (decision G1 on PR #48; module docstring). The
# checks, the CLI and the tests import the names from here; the three inside
# <trace_id>/ are the contract's.
ROLLOUT_NAME = RESULT_NAME  # in <trace_id>/; Đã chốt 3/11/2026 [Hiếu] (G1b)
RTC_NAME = "rtc.jsonl"  # in the job dir, the parent of <trace_id>/


def load_episode(path: Path) -> SystemInputs:
    """Read a trace directory `<trace_id>/` off disk, named by itself or a file in it.

    `path` is the directory, its `steps.jsonl` or its `rollout_result.json`.
    The layout is decision G1 (module docstring). The camera parameters and
    the RolloutResult are beside the steps; the RTC log is the job's, in the
    trace directory's parent, and is kept to the chunks of this trace
    (`_of_trace`).
    """
    directory = path if path.is_dir() else path.parent
    trace_path = path if path.is_file() and path.name != ROLLOUT_NAME else directory / STEPS_NAME
    if not trace_path.is_file():
        raise ReaderError(f"{path}: không tìm thấy {STEPS_NAME}")
    rtc_path = directory.parent / RTC_NAME
    camera_path = directory / CAMERA_NAME
    rollout_path = directory / ROLLOUT_NAME
    trace = read_trace_log(trace_path)
    rtc_data = _read_bytes(rtc_path) if rtc_path.is_file() else None
    camera_data = _read_bytes(camera_path) if camera_path.is_file() else None
    episode_data = _read_bytes(rollout_path) if rollout_path.is_file() else None
    rtc = () if rtc_data is None else _rtc_records(rtc_data, rtc_path)
    cameras = () if camera_data is None else _camera_params(camera_data, camera_path)
    return SystemInputs(
        trace=trace,
        rtc=_of_trace(rtc, trace),
        cameras=_cameras_of_trace(cameras, trace, camera_path),
        infra_status=(
            None
            if episode_data is None
            else _infra_status(episode_data, rollout_path, trace, directory)
        ),
        has_rtc_log=rtc_data is not None,
        has_camera_params=camera_data is not None,
        rtc_sha256=_digest(rtc_data),
        camera_sha256=_digest(camera_data),
        infra_sha256=_digest(episode_data),
    )


def read_trace_log(path: Path) -> TraceLog:
    """Read a JSONL control trace, one `TraceStep` per line, all of one trace."""
    data = _read_bytes(path)
    steps = _validated(_read_rows(data, path), path, TraceStep)
    trace_ids = sorted({step.trace_id for step in steps})
    if len(trace_ids) > 1:
        raise ReaderError(
            f"`{path}` có bước của {len(trace_ids)} trace {trace_ids}, không phải của một trace"
        )
    return TraceLog(
        episode_id=steps[0].episode_id if steps else _trace_name(path),
        trace_id=trace_ids[0] if trace_ids else _trace_name(path),
        rows=steps,
        gap_counts=_gap_counts(steps),
        dropped_frames=sum(step.dropped_frames for step in steps),
        trace_sha256=_sha256(data),
    )


def read_rtc_log(path: Path) -> tuple[RTCInferenceRecord, ...]:
    """Read a JSONL RTC inference log through `RTCInferenceRecord` (R1, R2)."""
    return _rtc_records(_read_bytes(path), path)


def _rtc_records(data: bytes, path: Path) -> tuple[RTCInferenceRecord, ...]:
    # a chunk the client never recorded is not a chunk that arrived on time
    return _validated(_read_rows(data, path), path, RTCInferenceRecord)


def _validated(rows: list[dict[str, Any]], path: Path, model: type[_LINE]) -> tuple[_LINE, ...]:
    """Each line through its contract, refused with its line number when the contract says no."""
    lines = []
    for number, row in enumerate(rows, start=1):
        try:
            lines.append(model.model_validate(row))
        except ValidationError as error:
            raise ReaderError(
                f"`{path}` dòng {number} không phải {model.__name__}: {error}"
            ) from error
    return tuple(lines)


def read_camera_params(path: Path) -> tuple[CameraParams, ...]:
    """Read `camera_params.jsonl`: one `CameraParams` per line, one line per camera (R5)."""
    return _camera_params(_read_bytes(path), path)


def _camera_params(data: bytes, path: Path) -> tuple[CameraParams, ...]:
    return _validated(_read_rows(data, path), path, CameraParams)


def _cameras_of_trace(
    cameras: tuple[CameraParams, ...], trace: TraceLog, path: Path
) -> tuple[CameraParams, ...]:
    """The cameras, refused if a line belongs to another trace than the steps beside it."""
    others = sorted({camera.trace_id for camera in cameras} - {trace.trace_id})
    if others:
        raise ReaderError(
            f"`{path}` có camera của trace {others}, không phải `{trace.trace_id}` "
            f"của `{STEPS_NAME}` bên cạnh"
        )
    return cameras


def _trace_name(path: Path) -> str:
    """The name of a steps file with no step in it: its directory (decision G1)."""
    return path.parent.name if path.name == STEPS_NAME else path.stem


def read_probe_p1(path: Path) -> ProbeP1:
    return _artifact(path, ProbeP1)


def read_probe_p3(path: Path) -> ProbeP3:
    return _artifact(path, ProbeP3)


def read_probe_p4(path: Path) -> ProbeP4:
    return _artifact(path, ProbeP4)


def percentile(values: Values, which: float) -> float:
    """The requested percentile over the finite values, or nan where there are none.

    A gap is left out of the statistic rather than counted as zero, and an
    array with nothing finite in it comes back as nan, which the checks read as
    "not measured" instead of as a value under the threshold.
    """
    finite = values[np.isfinite(values)] if values.size else values
    if finite.size == 0:
        return float("nan")
    return float(np.percentile(finite, which))


def _gap_counts(steps: Iterable[TraceStep]) -> dict[str, int]:
    """Steps whose value for a field is a gap: one of the non-finite strings.

    `t_image: null` is not one: `TraceStep` writes it on a cycle with no new
    frame, which has no image to pair and so no offset to miss (module
    docstring). Only a non-finite image timestamp is counted.
    """
    counts = dict.fromkeys((*TRACK_FIELDS, *SYNC_FIELDS), 0)
    for step in steps:
        if not _finite(step.t_state):
            counts["t_state"] += 1
        if step.t_image is not None and not _finite(step.t_image):
            counts["t_image"] += 1
        for name in TRACK_FIELDS:
            if not all(_finite(value) for value in getattr(step, name)):
                counts[name] += 1
    return {name: count for name, count in counts.items() if count}


def _matrix(steps: Sequence[TraceStep], name: str) -> NDArray[np.float64]:
    """One vector field of every step as a 2-D array, nan for a gap."""
    if not steps:
        return np.empty((0, 0), dtype=np.float64)
    return np.array(
        [[_number(value) for value in getattr(step, name)] for step in steps], dtype=np.float64
    )


def _column(steps: Sequence[TraceStep], name: str) -> Values:
    """One timestamp of every step, nan for a gap and for a null `t_image`.

    Empty when no step carries a value at all, the way a trace with no new
    frame anywhere has no image clock to read.
    """
    values = [getattr(step, name) for step in steps]
    if not values or all(value is None for value in values):
        return np.empty(0, dtype=np.float64)
    return np.array(
        [np.nan if value is None else _number(value) for value in values], dtype=np.float64
    )


def _number(value: FloatOrNonFinite) -> float:
    """A float, nan for the strings `TraceStep` writes a non-finite value as."""
    return math.nan if isinstance(value, str) else value


def _finite(value: FloatOrNonFinite) -> bool:
    return not isinstance(value, str) and math.isfinite(value)


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReaderError(f"`{path}` không đọc được: {error}") from error


def _read_rows(data: bytes, path: Path) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReaderError(f"`{path}` không đọc được: {error}") from error
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ReaderError(f"`{path}` dòng {number} không phải JSON: {error}") from error
        if not isinstance(row, dict):
            raise ReaderError(f"`{path}` dòng {number} phải là một đối tượng JSON")
        rows.append(row)
    return rows


def _read_json(path: Path) -> Any:
    return _parse_json(_read_bytes(path), path)


def _parse_json(data: bytes, path: Path) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReaderError(f"`{path}` không phải JSON đọc được: {error}") from error


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(data: bytes | None) -> str | None:
    return None if data is None else _sha256(data)


def _artifact(path: Path, model: type[_ARTIFACT]) -> _ARTIFACT:
    try:
        return model.model_validate(_read_json(path))
    except ValidationError as error:
        raise ReaderError(f"`{path}` không phải {model.__name__}: {error}") from error


def _infra_status(data: bytes, path: Path, trace: TraceLog, directory: Path) -> str:
    """`infra_status` of the episode, for R6, from the RolloutResult beside the steps.

    The result's `trace_ref` must be about these steps (module docstring); a
    mismatch raises, because pairing an infra status with the wrong steps is
    worse than not judging R6.
    """
    try:
        result = RolloutResult.model_validate(_parse_json(data, path))
    except ValidationError as error:
        raise ReaderError(f"`{path}` không phải RolloutResult: {error}") from error
    ref = result.trace_ref
    if ref is None:
        return result.infra_status
    if ref.trace_id != trace.trace_id:
        raise ReaderError(
            f"`{path}` là RolloutResult của trace `{ref.trace_id}`, "
            f"không phải `{trace.trace_id}` của trace bên cạnh"
        )
    if PurePosixPath(ref.uri.rstrip("/")).name != directory.name:
        raise ReaderError(
            f"`{path}`: `trace_ref.uri` là `{ref.uri}`, không trỏ vào thư mục trace "
            f"`{directory.name}/` chứa nó"
        )
    if ref.sha256 is not None and ref.sha256 != trace.trace_sha256:
        raise ReaderError(
            f"`{path}`: `trace_ref.sha256` là `{ref.sha256}` nhưng `{STEPS_NAME}` có sha256 "
            f"`{trace.trace_sha256}`; steps đã đổi sau khi rollout ghi kết quả"
        )
    return result.infra_status


def _of_trace(
    records: tuple[RTCInferenceRecord, ...], trace: TraceLog
) -> tuple[RTCInferenceRecord, ...]:
    """The chunks of this trace in an RTC log that may hold a whole job.

    `RTCClient` of DA-19 writes one `rtc.jsonl` per job and tells the traces
    in it apart by `trace_id`, so the log beside a trace can carry the
    latency of every other episode of the job too.
    """
    return tuple(record for record in records if record.trace_id == trace.trace_id)
