"""What the F-SYS checks read, and the one place a contract change stops (DA-13 AC 1, 3).

Reading is kept away from judging, the split DA-36 made in `scorer/reader.py`.
This module turns bytes on disk into arrays and says what is missing; it never
decides whether the controller tracked its commands. Every check takes a
`SystemInputs` and nothing else, so a field renamed in `flywheel.contracts`
reaches this module and goes no further.

**The trace log is read by field name, not through the contract yet.**
`TraceStep` and `CameraParams` are proposed in Contract change #31 (Long, PR
#48) and are not on master, so `TraceRow` and `CameraView` here hold exactly
the fields of that proposal and nothing of their own. When #48 merges they are
replaced by `flywheel.contracts.trace.TraceStep` and `CameraParams`, which is
task 7 of the story - the same way DA-36 held `ScoreRecord` until `Score`
landed. Nothing downstream reads these two classes, only the arrays they
produce, so the swap does not reach the checks.

**The RTC log and the probe results do come through contracts.**
`RTCInferenceRecord`, `ProbeP1`, `ProbeP3` and `ProbeP4` are on master, so R1,
R2 and the stage attribution read the contract types directly.

**A value that is not finite is read as missing, not as a number.** `json.loads`
accepts `NaN`, and every comparison against a NaN is false, so a trace whose
tracking error is NaN on every cycle would clear every threshold it was checked
against and come back as a clean controller. That is the silent pass FR21
forbids, so a NaN or an infinity - as a JSON number or as the strings `"NaN"`,
`"Infinity"`, `"-Infinity"` the contract allows - becomes a gap here and
reaches the checks as one, which is what makes the first step of spec section
6.4, "thiếu tín hiệu → CHƯA RÕ", fire on it.

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
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
from flywheel.contracts.artifacts import ProbeP1, ProbeP3, ProbeP4, RTCInferenceRecord
from numpy.typing import NDArray
from pydantic import ValidationError

Values = NDArray[np.float64]

_ARTIFACT = TypeVar("_ARTIFACT", ProbeP1, ProbeP3, ProbeP4)

# The fields of `TraceStep` (Contract change #31) each check needs. Named here
# so a trace that lacks one is reported by the name the writer used.
TRACK_FIELDS = ("cmd_upper", "meas_upper", "cmd_lower", "meas_lower")
SYNC_FIELDS = ("t_state", "t_image")


class ReaderError(ValueError):
    """A trace, RTC log or camera file no check of this story may run on."""


@dataclass(frozen=True)
class TraceRow:
    """One control cycle, with the fields of `TraceStep` (Contract change #31).

    A gap - a null or non-finite `t_state` or vector entry, a non-finite
    `t_image` - is nan. `t_image` is None only where the writer logged null,
    which `TraceStep` defines as "no new camera frame on this cycle" and which
    is not a gap. A vector logged as null is the empty tuple; `_matrix` turns
    it into a row of nan as wide as the others.
    """

    step: int
    t_state: float
    t_image: float | None
    cmd_upper: tuple[float, ...]
    meas_upper: tuple[float, ...]
    cmd_lower: tuple[float, ...]
    meas_lower: tuple[float, ...]
    dropped_frames: int


@dataclass(frozen=True)
class CameraView:
    """The calibration of one camera, with the fields of `CameraParams` (#31).

    `reference_sha256` is the hash of the reference pinned at G0 that the
    episode ran against, copied by the SimpleSim hook from the RunPlan
    (decision Q3, 3/11/2026). It is not a hash of the values in this object;
    if one is ever needed it is a different field.
    """

    uid: str
    mount: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    pose: tuple[float, ...]
    reference_sha256: str


@dataclass(frozen=True)
class TraceLog:
    """One episode's control trace as arrays, plus what it does not carry.

    `absent_fields` is what the writer never logged and `gap_counts` is what it
    logged as null or as a value that is not finite. Both cost a check its
    verdict, and both are reported in the words of the field, because "chẩn
    đoán CHƯA RÕ, đề xuất thu thêm bằng chứng" is only actionable if it says
    which evidence to collect (spec section 6.4, step 1).
    """

    episode_id: str
    rows: tuple[TraceRow, ...]
    absent_fields: tuple[str, ...]
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
        measurement is not a cycle that tracked perfectly.
        """
        commands = _matrix(self.rows, f"cmd_{part}")
        measured = _matrix(self.rows, f"meas_{part}")
        if commands.size == 0 or measured.size == 0:
            return np.empty(0, dtype=np.float64)
        if commands.shape != measured.shape:
            raise ReaderError(
                f"`cmd_{part}` và `meas_{part}` khác số kênh ({commands.shape[1]} so với "
                f"{measured.shape[1]}), không ghép được thành sai số bám lệnh"
            )
        difference = commands - measured
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
    cameras: tuple[CameraView, ...] = ()
    infra_status: str | None = None
    has_rtc_log: bool = False
    has_camera_params: bool = False


@dataclass(frozen=True)
class StageInputs:
    """The probe evidence the stage attribution reads (AC 3).

    Every field is optional: a hypothesis that has no probe behind it is not
    stated, and the row says which probe it was waiting for. `t7` is the
    forgetting finding of DA-08, passed in rather than recomputed, so the two
    stories cannot disagree about whether a checkpoint forgot.
    """

    p1: ProbeP1 | None = None
    p3: ProbeP3 | None = None
    p4: ProbeP4 | None = None
    t7: bool = False
    out_of_domain: bool = False
    closed_loop_failed: bool = True
    failed_step: int | None = None
    action_groups: tuple[str, ...] = ()
    frames: tuple[str, ...] = field(default_factory=tuple)


TRACE_NAME = "trace.jsonl"
RTC_NAME = "rtc.jsonl"
CAMERA_NAME = "camera_params.json"
EPISODE_NAME = "episode.json"


def load_episode(path: Path) -> SystemInputs:
    """Read an episode directory, or the trace inside one, off disk.

    The layout is file names rather than a manifest, because a rollout writes
    its trace, its RTC log and its camera parameters as separate files and
    nothing in the contracts ties them together yet. Naming the trace directly
    is allowed, and the rest is looked for beside it.
    """
    trace_path = path if path.is_file() else path / TRACE_NAME
    if not trace_path.is_file():
        raise ReaderError(f"{path}: không tìm thấy {TRACE_NAME}")
    directory = trace_path.parent
    rtc_path = directory / RTC_NAME
    camera_path = directory / CAMERA_NAME
    return SystemInputs(
        trace=read_trace_log(trace_path),
        rtc=read_rtc_log(rtc_path) if rtc_path.is_file() else (),
        cameras=read_camera_params(camera_path) if camera_path.is_file() else (),
        infra_status=_infra_status(directory / EPISODE_NAME),
        has_rtc_log=rtc_path.is_file(),
        has_camera_params=camera_path.is_file(),
    )


def read_trace_log(path: Path) -> TraceLog:
    """Read a JSONL control trace, one `TraceStep` object per line."""
    data = _read_bytes(path)
    rows = _read_rows(data, path)
    parsed = tuple(_trace_row(row, path, number) for number, row in enumerate(rows, start=1))
    absent = _absent_fields(rows)
    return TraceLog(
        episode_id=_episode_id(rows) or path.stem,
        rows=parsed,
        absent_fields=absent,
        gap_counts=_gap_counts(parsed, absent),
        dropped_frames=sum(row.dropped_frames for row in parsed),
        trace_sha256=hashlib.sha256(data).hexdigest(),
    )


def read_rtc_log(path: Path) -> tuple[RTCInferenceRecord, ...]:
    """Read a JSONL RTC inference log through `RTCInferenceRecord` (R1, R2)."""
    rows = _read_rows(_read_bytes(path), path)
    records = []
    for number, row in enumerate(rows, start=1):
        try:
            records.append(RTCInferenceRecord.model_validate(row))
        except ValidationError as error:
            raise ReaderError(
                f"`{path}` dòng {number} không phải RTCInferenceRecord: {error}"
            ) from error
        # a chunk the client never recorded is not a chunk that arrived on time
    return tuple(records)


def read_camera_params(path: Path) -> tuple[CameraView, ...]:
    """Read the camera parameters of an episode: one object, or a list of them (R5)."""
    parsed = _read_json(path)
    entries = parsed if isinstance(parsed, list) else [parsed]
    return tuple(_camera_view(entry, path) for entry in entries)


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


def _trace_row(row: dict[str, Any], path: Path, number: int) -> TraceRow:
    t_state = _scalar(row.get("t_state"), "t_state", path, number)
    return TraceRow(
        step=_step(row, path, number),
        t_state=math.nan if t_state is None else t_state,
        t_image=_scalar(row.get("t_image"), "t_image", path, number),
        cmd_upper=_vector(row.get("cmd_upper"), "cmd_upper", path, number),
        meas_upper=_vector(row.get("meas_upper"), "meas_upper", path, number),
        cmd_lower=_vector(row.get("cmd_lower"), "cmd_lower", path, number),
        meas_lower=_vector(row.get("meas_lower"), "meas_lower", path, number),
        dropped_frames=_dropped(row.get("dropped_frames"), path, number),
    )


def _camera_view(entry: Any, path: Path) -> CameraView:
    if not isinstance(entry, dict):
        raise ReaderError(f"`{path}` phải là đối tượng CameraParams hoặc danh sách các đối tượng")
    pose = _vector(entry.get("pose"), "pose", path, 1)
    if len(pose) != 7 or not all(math.isfinite(value) for value in pose):
        raise ReaderError(
            f"`{path}`: `pose` phải có 7 số hữu hạn [x, y, z, qw, qx, qy, qz], "
            f"gặp {entry.get('pose')!r}"
        )
    return CameraView(
        uid=_text(entry, "uid", path),
        mount=_text(entry, "mount", path),
        width=_dimension(entry, "width", path),
        height=_dimension(entry, "height", path),
        fx=_required_number(entry, "fx", path),
        fy=_required_number(entry, "fy", path),
        cx=_required_number(entry, "cx", path),
        cy=_required_number(entry, "cy", path),
        pose=pose,
        reference_sha256=_text(entry, "reference_sha256", path),
    )


def _absent_fields(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    """Fields of `TraceStep` that no row of the file carries at all.

    A field present on some rows and absent on others is a gap, counted by
    `_gap_counts`; a field no row carries is the writer not logging it, which
    is a different thing to tell the engineer to go and collect.
    """
    present = {key for row in rows for key in row}
    return tuple(name for name in (*TRACK_FIELDS, *SYNC_FIELDS) if name not in present)


def _gap_counts(rows: Iterable[TraceRow], absent: tuple[str, ...]) -> dict[str, int]:
    """Rows whose value for a logged field is a gap: null or not finite.

    `t_image` is the exception: null there means no new frame (`TraceRow`),
    so only a non-finite image timestamp is counted. A field in `absent` is
    left out: it is not logged at all, which is already
    reported, and counting it here as well would report the same gap twice
    under two names and tell the engineer to collect it twice.
    """
    counts = {name: 0 for name in (*TRACK_FIELDS, *SYNC_FIELDS) if name not in absent}
    for row in rows:
        if "t_state" in counts and not math.isfinite(row.t_state):
            counts["t_state"] += 1
        if "t_image" in counts and row.t_image is not None and not math.isfinite(row.t_image):
            counts["t_image"] += 1
        for name in TRACK_FIELDS:
            if name not in counts:
                continue
            values = getattr(row, name)
            if not values or not all(math.isfinite(value) for value in values):
                counts[name] += 1
    return {name: count for name, count in counts.items() if count}


def _matrix(rows: Sequence[TraceRow], name: str) -> NDArray[np.float64]:
    """One field of every row as a 2-D array, nan for a gap.

    A vector logged as null (or empty) is a cycle with no measurement, so it
    becomes a row of nan as wide as the others and `_gap_counts` has already
    counted it; refusing it would stop the reader on exactly the traces a
    `max_gap_fraction` above zero is meant to let through. Two rows of
    different non-zero widths cannot be stacked, and a trace that changes its
    channel count mid-episode is a trace nobody can compute a norm over, so
    that still raises rather than being padded.
    """
    vectors = [getattr(row, name) for row in rows]
    widths = {len(vector) for vector in vectors} - {0}
    if not widths:
        return np.empty((0, 0), dtype=np.float64)
    if len(widths) > 1:
        raise ReaderError(f"`{name}` đổi số kênh giữa episode ({sorted(widths)})")
    (width,) = widths
    gap = (math.nan,) * width
    return np.array([vector or gap for vector in vectors], dtype=np.float64)


def _column(rows: Sequence[TraceRow], name: str) -> Values:
    values = [getattr(row, name) for row in rows]
    if not values or all(value is None for value in values):
        return np.empty(0, dtype=np.float64)
    return np.array([np.nan if value is None else value for value in values], dtype=np.float64)


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
    try:
        return json.loads(_read_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReaderError(f"`{path}` không phải JSON đọc được: {error}") from error


def _artifact(path: Path, model: type[_ARTIFACT]) -> _ARTIFACT:
    try:
        return model.model_validate(_read_json(path))
    except ValidationError as error:
        raise ReaderError(f"`{path}` không phải {model.__name__}: {error}") from error


def _infra_status(path: Path) -> str | None:
    """`infra_status` of the episode, for R6, or None where the file is not there."""
    if not path.is_file():
        return None
    parsed = _read_json(path)
    if not isinstance(parsed, dict):
        raise ReaderError(f"`{path}` phải là một đối tượng JSON")
    status = parsed.get("infra_status")
    if status is None:
        return None
    if not isinstance(status, str) or not status.strip():
        raise ReaderError(f"`{path}`: `infra_status` phải là chuỗi khác rỗng, gặp {status!r}")
    return status


def _episode_id(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        value = row.get("episode_id")
        if isinstance(value, str) and value:
            return value
    return None


def _step(row: dict[str, Any], path: Path, number: int) -> int:
    value = row.get("step", number - 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReaderError(
            f"`{path}` dòng {number}: `step` phải là số nguyên không âm, gặp {value!r}"
        )
    return value


def _dropped(value: Any, path: Path, number: int) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReaderError(
            f"`{path}` dòng {number}: `dropped_frames` phải là số nguyên không âm, gặp {value!r}"
        )
    return value


# The strings `TraceStep` (Contract change #31) encodes a non-finite value as.
NON_FINITE = ("NaN", "Infinity", "-Infinity")


def _scalar(value: Any, name: str, path: Path, number: int) -> float | None:
    """A number, nan for a non-finite one, or None for a null.

    The two are kept apart because `t_image` gives them different meanings
    (`TraceRow`); every other field treats both as a gap.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value not in NON_FINITE:
            raise ReaderError(
                f"`{path}` dòng {number}: `{name}` phải là số, null hoặc "
                f"{'/'.join(NON_FINITE)}, gặp {value!r}"
            )
        # not a measurement, so it becomes a gap rather than a number
        return math.nan
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReaderError(f"`{path}` dòng {number}: `{name}` phải là số hoặc null, gặp {value!r}")
    return float(value) if math.isfinite(value) else math.nan


def _vector(value: Any, name: str, path: Path, number: int) -> tuple[float, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ReaderError(f"`{path}` dòng {number}: `{name}` phải là danh sách số, gặp {value!r}")
    scalars = (_scalar(item, name, path, number) for item in value)
    return tuple(math.nan if item is None else item for item in scalars)


def _text(entry: dict[str, Any], key: str, path: Path) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReaderError(f"`{path}`: `{key}` phải là chuỗi khác rỗng, gặp {value!r}")
    return value


def _required_number(entry: dict[str, Any], key: str, path: Path) -> float:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ReaderError(f"`{path}`: `{key}` phải là số hữu hạn, gặp {value!r}")
    return float(value)


def _dimension(entry: dict[str, Any], key: str, path: Path) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ReaderError(f"`{path}`: `{key}` phải là số nguyên dương, gặp {value!r}")
    return value
