"""Closed-loop evaluation runner supporting sync and async modes with RTC logging (DA-23)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.protocols import SimulatorAdapter
from flywheel.contracts.v0 import (
    PolicyEndpoint,
    PolicySpec,
    RolloutRequest,
    RolloutResult,
    TraceRef,
)
from flywheel.loop.runner.config import EvalConfig, load_eval_config


class Runner:
    """Execute reproducible closed-loop rollouts across sync and async modes."""

    def __init__(
        self,
        simulator: SimulatorAdapter,
        staging_root: Path,
        config: EvalConfig | None = None,
        default_timing: Literal["sync", "async"] | None = None,
        policy_spec: PolicySpec | None = None,
    ) -> None:
        self.simulator = simulator
        self.staging_root = staging_root
        self.config = config or load_eval_config()
        self.default_timing = default_timing or self.config.default_timing
        self.control_hz = policy_spec.hz if policy_spec else self.config.control_hz
        self.chunk_size = policy_spec.chunk_size if policy_spec else self.config.chunk_size

    def run_rollout(
        self,
        request: RolloutRequest,
        policy: PolicyEndpoint,
        force_rerun: bool = False,
    ) -> RolloutResult:
        """Run a rollout request with resume support and RTC log collection."""
        job_dir = self.staging_root / request.job_id
        result_path = job_dir / "result.json"
        rtc_path = job_dir / "rtc.jsonl"

        # Validate async profile existence up-front (no silent failure)
        if request.timing == "async" and request.latency_profile_ref:
            profile_path = Path(request.latency_profile_ref)
            if not profile_path.is_file():
                raise FileNotFoundError(
                    f"Latency profile ref not found for async rollout: "
                    f"{request.latency_profile_ref}"
                )

        # Resume support: only reuse if previously finished with infra_status == "ok"
        if not force_rerun and result_path.is_file():
            cached_result = RolloutResult.model_validate_json(
                result_path.read_text(encoding="utf-8")
            )
            if cached_result.infra_status == "ok":
                # For async, ensure rtc.jsonl is also present
                if request.timing == "sync" or rtc_path.is_file():
                    return cached_result

        job_dir.mkdir(parents=True, exist_ok=True)

        # Call simulator rollout (timing and latency profile passed directly in request)
        result = self.simulator.rollout(request, policy)

        # Gom (collect) RTC log if executed in async mode
        if request.timing == "async":
            self._collect_rtc_log(job_dir, result)
        else:
            # Sync mode: ensure no stale delayed rtc.jsonl
            if rtc_path.is_file():
                rtc_path.unlink()

        # Cache completed result if infra_status == "ok"
        if result.infra_status == "ok":
            result_path.write_text(result.model_dump_json(), encoding="utf-8")

        return result

    def _collect_rtc_log(self, job_dir: Path, result: RolloutResult) -> Path:
        """Collect and validate RTC inference log emitted by simulator/client."""
        rtc_path = job_dir / "rtc.jsonl"

        # If not at job_dir/rtc.jsonl, check trace directory
        if not rtc_path.is_file() and result.trace_ref is not None:
            trace_rtc = Path(result.trace_ref.uri).parent / "rtc.jsonl"
            if trace_rtc.is_file() and trace_rtc != rtc_path:
                shutil.copy(trace_rtc, rtc_path)

        # If rtc.jsonl is present, validate every record against RTCInferenceRecord
        if rtc_path.is_file():
            validated_lines: list[str] = []
            for line in rtc_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = RTCInferenceRecord.model_validate_json(line)
                # Verify attached to Trace (AC 2)
                if result.trace_ref is not None and rec.trace_id != result.trace_ref.trace_id:
                    raise ValueError(
                        f"RTC log trace_id '{rec.trace_id}' does not match "
                        f"rollout trace_id '{result.trace_ref.trace_id}'"
                    )
                if not isinstance(rec.boundary_jump, float) or rec.boundary_jump < 0:
                    raise ValueError(
                        f"boundary_jump must be float >= 0, got {rec.boundary_jump!r}"
                    )
                validated_lines.append(rec.model_dump_json())
            rtc_path.write_text(
                "\n".join(validated_lines) + ("\n" if validated_lines else ""),
                encoding="utf-8",
            )

        return rtc_path

    def run_eval(
        self,
        requests: Sequence[RolloutRequest],
        policy: PolicyEndpoint,
        force_rerun: bool = False,
    ) -> list[RolloutResult]:
        """Execute a batch of rollout requests sequentially with resume capability."""
        return [self.run_rollout(req, policy, force_rerun=force_rerun) for req in requests]


def load_trace(trace_ref: TraceRef) -> dict[str, object]:
    """Helper to read trace payload from TraceRef uri."""
    path = Path(trace_ref.uri)
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
