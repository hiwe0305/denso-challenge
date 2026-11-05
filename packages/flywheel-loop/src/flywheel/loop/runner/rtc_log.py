"""Read and check the RTC inference log of one rollout job (DA-23 AC 2).

The policy's RTC client (DA-19, `flywheel_psi0.policy.rtc`) appends one
`RTCInferenceRecord` per chunk to `<job_dir>/rtc.jsonl`. The lane reads it only
through that contract; it never imports the adapter.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flywheel.contracts.artifacts import RTCInferenceRecord
from pydantic import ValidationError

RTC_LOG_FILE = "rtc.jsonl"
# The client stores times relative to the trace start, so the latency recomputed
# from them can differ from the one it took `ceil` of by a rounding error.
_DELAY_TOLERANCE_STEPS = 1e-6


class RTCLogError(ValueError):
    """The RTC log is missing, unreadable, or does not describe this rollout."""


def read_rtc_log(path: Path) -> list[RTCInferenceRecord]:
    """Every record of `path`, validated against `RTCInferenceRecord`."""
    if not path.is_file():
        raise RTCLogError(f"{RTC_LOG_FILE} missing at {path}")
    records: list[RTCInferenceRecord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(RTCInferenceRecord.model_validate_json(line))
        except ValidationError as error:
            raise RTCLogError(f"{path}:{number} is not an RTCInferenceRecord: {error}") from error
    if not records:
        raise RTCLogError(f"{path} has no records")
    return records


def check_rtc_log(
    records: Sequence[RTCInferenceRecord],
    job_id: str,
    trace_id: str,
    hz: float,
    chunk_size: int,
) -> None:
    """Raise `RTCLogError` unless the records are this rollout's, one request at a time.

    Each record must name this job and trace, chunks must count 0, 1, ... in order,
    a request may only go out once the previous chunk came back, `delay_steps` must be
    `ceil(latency * hz)` as the client computes it, and the buffer can never hold more
    than one chunk.
    """
    if not records:
        raise RTCLogError("RTC log has no records")
    previous: RTCInferenceRecord | None = None
    for index, record in enumerate(records):
        where = f"RTC chunk {index}"
        if record.job_id != job_id:
            raise RTCLogError(f"{where}: job_id {record.job_id!r} is not {job_id!r}")
        if record.trace_id != trace_id:
            raise RTCLogError(f"{where}: trace_id {record.trace_id!r} is not {trace_id!r}")
        if record.chunk_index != index:
            raise RTCLogError(f"{where}: chunk_index is {record.chunk_index}, expected {index}")
        if previous is not None and record.observation_sent_s < previous.chunk_received_s:
            raise RTCLogError(
                f"{where}: sent at {record.observation_sent_s} s, before chunk {index - 1} "
                f"came back at {previous.chunk_received_s} s"
            )
        steps = (record.chunk_received_s - record.observation_sent_s) * hz
        low = math.ceil(steps - _DELAY_TOLERANCE_STEPS)
        high = math.ceil(steps + _DELAY_TOLERANCE_STEPS)
        if not low <= record.delay_steps <= high:
            raise RTCLogError(
                f"{where}: delay_steps {record.delay_steps} does not match the recorded "
                f"latency ({steps / hz:.4f} s at {hz} Hz is {high} steps)"
            )
        if record.buffer_level > chunk_size:
            raise RTCLogError(
                f"{where}: buffer_level {record.buffer_level} exceeds chunk size {chunk_size}"
            )
        previous = record


@dataclass(frozen=True)
class RTCSchedule:
    """What an RTC log means for a robot that keeps moving during inference."""

    chunks: int
    max_delay_steps: int
    # Actions a hardware client still holds when it sends the next request.
    refill_level: int
    # Control steps with no action to execute, summed over chunks.
    starved_steps: int
    starved_chunks: int


def replay_schedule(
    records: Sequence[RTCInferenceRecord], refill_level: int, chunk_size: int
) -> RTCSchedule:
    """Replay the log on a real-time clock (async eval, ADR-20, design 8.5).

    SIMPLE steps the sim synchronously and its client asks for a chunk only once the
    buffer is empty, so the logged `buffer_level` is 0 and says nothing about hardware.
    A hardware client sends the request while `refill_level` actions are left (capped
    at the chunk size) and runs them during the inference; chunk k >= 1 then leaves the
    robot without an action for `delay_steps - refill_level` steps. The first request
    is made before the robot moves, so its wait is not a stall.
    """
    level = min(refill_level, chunk_size)
    stalls = [max(0, r.delay_steps - level) for r in records[1:]]
    return RTCSchedule(
        chunks=len(records),
        max_delay_steps=max((r.delay_steps for r in records), default=0),
        refill_level=level,
        starved_steps=sum(stalls),
        starved_chunks=sum(1 for stall in stalls if stall > 0),
    )
