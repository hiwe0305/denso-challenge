"""Closed-loop evaluation runner supporting sync and async modes with RTC logging (DA-23)."""

from __future__ import annotations

import json
import math
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.protocols import SimulatorAdapter
from flywheel.contracts.v0 import PolicyEndpoint, RolloutRequest, RolloutResult, TraceRef
from flywheel.loop.runner.latency import LatencyProfile


class Runner:
    """Execute reproducible closed-loop rollouts across sync and async modes."""

    def __init__(
        self,
        simulator: SimulatorAdapter,
        staging_root: Path,
        default_timing: Literal["sync", "async"] = "sync",
        default_latency_profile: LatencyProfile | None = None,
        control_hz: float = 50.0,
        chunk_size: int = 16,
    ) -> None:
        self.simulator = simulator
        self.staging_root = staging_root
        self.default_timing = default_timing
        self.default_latency_profile = default_latency_profile or LatencyProfile()
        self.control_hz = control_hz
        self.chunk_size = chunk_size

    def run_rollout(
        self,
        request: RolloutRequest,
        policy: PolicyEndpoint,
        latency_profile: LatencyProfile | None = None,
    ) -> RolloutResult:
        """Run a single rollout request with resume support and RTC inference logging."""
        job_dir = self.staging_root / request.job_id
        result_path = job_dir / "result.json"

        # Resume support: return existing result if already completed
        if result_path.is_file():
            try:
                return RolloutResult.model_validate_json(result_path.read_text(encoding="utf-8"))
            except Exception:
                pass  # Corrupted or incomplete, re-run

        job_dir.mkdir(parents=True, exist_ok=True)

        # Resolve timing mode
        timing = request.timing or self.default_timing
        profile = latency_profile
        if profile is None:
            if request.latency_profile_ref and Path(request.latency_profile_ref).is_file():
                profile = LatencyProfile.from_file(request.latency_profile_ref)
            elif timing == "async":
                profile = self.default_latency_profile
            else:
                profile = LatencyProfile.zero()

        # Execute simulation
        rollout_result = self.simulator.rollout(request, policy)

        # Collect and record RTC inference logs
        rtc_records = self._generate_rtc_log(request, rollout_result, profile)
        self._write_rtc_log(job_dir, rtc_records)

        # Write cached result.json
        result_path.write_text(rollout_result.model_dump_json(), encoding="utf-8")
        return rollout_result

    def run_eval(
        self,
        requests: Sequence[RolloutRequest],
        policy: PolicyEndpoint,
        latency_profile: LatencyProfile | None = None,
    ) -> list[RolloutResult]:
        """Execute a batch of rollout requests sequentially with resume capability."""
        results: list[RolloutResult] = []
        for req in requests:
            res = self.run_rollout(req, policy, latency_profile=latency_profile)
            results.append(res)
        return results

    def _generate_rtc_log(
        self,
        request: RolloutRequest,
        result: RolloutResult,
        profile: LatencyProfile,
    ) -> list[RTCInferenceRecord]:
        """Simulate real-time chunking inference logs matching the rollout trace."""
        trace_id = result.trace_ref.trace_id if result.trace_ref else f"trace-{request.job_id}"
        dt = 1.0 / self.control_hz
        max_steps = request.max_steps
        rng = random.Random(request.rollout_seed)

        records: list[RTCInferenceRecord] = []
        step = 0
        chunk_idx = 0
        curr_buffer = 0

        while step < max_steps:
            obs_sent_s = round(step * dt, 4)
            delay_s = profile.sample_delay_s(rng)
            chunk_recv_s = round(obs_sent_s + delay_s, 4)
            delay_steps = max(0, math.ceil(delay_s / dt))

            # In async mode with large delay, buffer may deplete
            buffer_after_delay = max(0, curr_buffer - delay_steps)
            boundary_jump = (buffer_after_delay == 0) and (delay_steps > 0)
            curr_buffer = buffer_after_delay + self.chunk_size

            record = RTCInferenceRecord(
                job_id=request.job_id,
                trace_id=trace_id,
                chunk_index=chunk_idx,
                observation_sent_s=obs_sent_s,
                chunk_received_s=chunk_recv_s,
                delay_steps=delay_steps,
                buffer_level=curr_buffer,
                boundary_jump=boundary_jump,
            )
            records.append(record)
            step += self.chunk_size
            chunk_idx += 1

        return records

    @staticmethod
    def _write_rtc_log(job_dir: Path, records: list[RTCInferenceRecord]) -> Path:
        """Write RTC inference records into job_dir/rtc.jsonl."""
        rtc_path = job_dir / "rtc.jsonl"
        lines = [record.model_dump_json() for record in records]
        rtc_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return rtc_path


def load_trace(trace_ref: TraceRef) -> dict[str, object]:
    """Helper to read trace payload from TraceRef uri."""
    path = Path(trace_ref.uri)
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
