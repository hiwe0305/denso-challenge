"""RTC client for a served Psi0 policy, with one `RTCInferenceRecord` per chunk (DA-19 AC 4).

`serve_psi0_simple --rtc` keeps real-time chunking on the server: it remembers the
previous chunk and conditions the next one on it, freezing the first d rows of the
new chunk to the old plan. With a checkpoint trained with `--model.rtc` and no
`--rtc-inference-delay`, d = max(1, min(Ta // 2, Tp - s, max_delay - 1)), s being
`--min-exec-horizon` (default Ta); 6 with the team's `--action-exec-horizon 24`,
Tp 30, max_delay 8 (Psi0 cda3fdf, serve_psi0_simple.py:161-171). The server reports
it on `/info` as `rtc_inference_delay`. The client's job is the control clock: hand out one
action per control step from a buffer, ask the server for the next chunk when the
buffer runs low, and record what that cost. Per request it logs (DA-25 schema):

* `observation_sent_s`, `chunk_received_s` - seconds since the trace started;
* `delay_steps` (d) - control steps a real-time loop at `hz` would run during the
  inference, `ceil(latency * hz)`. SIMPLE steps the sim synchronously, so nothing
  moves while it waits; d is what RTC would have to cover on hardware, to compare
  with the server's `rtc_inference_delay` (R2 of DA-13), not the model's `max_delay`;
* `buffer_level` - actions left in the buffer when the request went out;
* `chunk_index` - 0, 1, ... within the trace;
* `boundary_jump` - the largest per-dimension change between the last action
  executed from the old chunk and the first one of the new chunk, in the server's
  de-normalised units (radians, metres): a discontinuity RTC is meant to smooth.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import RTCInferenceRecord
from numpy.typing import NDArray

# One `/act` round trip: request body in, `(Ta, Da)` actions out.
Transport = Callable[[dict[str, Any]], NDArray[np.float64]]
Observation = Callable[[bool], dict[str, Any]]


class RTCLog:
    """Appends `RTCInferenceRecord` lines to `rtc.jsonl` in the job directory."""

    def __init__(self, path: Path, job_id: str) -> None:
        self.path = path
        self.job_id = job_id
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: RTCInferenceRecord) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(record.model_dump_json() + "\n")


class RTCClient:
    """One action per control step, refilled from the server when the buffer runs low.

    `act(observe)` takes a callable rather than an observation so the (costly)
    images are only rendered on the steps that actually send a request; `observe`
    receives `reset=True` on the first request of a trace and must return a
    `wire.request(..., session_id=<the trace id>, reset=reset)` body.
    """

    def __init__(
        self,
        transport: Transport,
        log: RTCLog,
        hz: float,
        refill_at: int = 0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._log = log
        self._hz = hz
        self._refill_at = refill_at
        self._clock = clock
        self._buffer: deque[NDArray[np.float64]] = deque()
        self._trace_id = ""
        self._start = 0.0
        self._chunk_index = 0
        self._last: NDArray[np.float64] | None = None

    def reset(self, trace_id: str) -> None:
        """Start a new trace (one rollout): empty buffer, server RTC memory dropped."""
        self._buffer.clear()
        self._trace_id = trace_id
        self._start = self._clock()
        self._chunk_index = 0
        self._last = None

    def act(self, observe: Observation) -> NDArray[np.float64]:
        if not self._trace_id:
            raise RuntimeError("call reset(trace_id) before the first act()")
        if len(self._buffer) <= self._refill_at:
            self._request(observe)
        action = self._buffer.popleft()
        self._last = action
        return action

    def _request(self, observe: Observation) -> None:
        body = observe(self._chunk_index == 0)
        level = len(self._buffer)
        sent = self._clock()
        chunk = self._transport(body)
        received = self._clock()
        if chunk.ndim != 2 or len(chunk) == 0:
            raise RuntimeError(f"expected a (Ta, Da) chunk, got shape {chunk.shape}")
        jump = 0.0 if self._last is None else float(np.max(np.abs(chunk[0] - self._last)))
        self._log.write(
            RTCInferenceRecord(
                job_id=self._log.job_id,
                trace_id=self._trace_id,
                chunk_index=self._chunk_index,
                observation_sent_s=sent - self._start,
                chunk_received_s=received - self._start,
                delay_steps=math.ceil((received - sent) * self._hz),
                buffer_level=level,
                boundary_jump=jump,
            )
        )
        # Synchronous stepping: the old buffer was not consumed while waiting, so the
        # new chunk replaces it rather than skipping d of its actions.
        self._buffer = deque(chunk)
        self._chunk_index += 1
