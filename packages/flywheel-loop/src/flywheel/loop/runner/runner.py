"""Closed-loop evaluation runner supporting sync and async modes with RTC logging (DA-23).

An async rollout is only scored when the job directory holds the RTC log of the
policy's client (DA-19) and that log describes this rollout; anything else gives
`timing_verdict="not_checked"`, with the reason in `runner.json`. The runner then
replays the log on a real-time clock and fills `RolloutResult.timing_verdict`:
"starved" when the robot would have run out of actions while a chunk was in flight,
even though the synchronously stepped sim succeeded. `sim_success` and `infra_status`
always stay the adapter's (decision E2, 3/11/2026): an unjudged timing is not an
infrastructure failure.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Literal, cast

from flywheel.contracts.entities import RunPlan
from flywheel.contracts.protocols import SimulatorAdapter
from flywheel.contracts.v0 import (
    PolicyEndpoint,
    PolicySpec,
    RolloutRequest,
    RolloutResult,
    TraceRef,
)
from flywheel.loop.runner.config import EvalConfig, load_eval_config
from flywheel.loop.runner.rtc_log import (
    RTC_LOG_FILE,
    RTCLogError,
    check_rtc_log,
    read_rtc_log,
    replay_schedule,
)

CACHE_FILE = "runner.json"
# Bump when the runner changes what a cached result means.
CACHE_VERSION = 2


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
        """Run a rollout request with resume support and RTC log collection.

        `<staging_root>/<job_id>/` is the job directory shared with the simulator adapter
        and the policy's RTC client. A result is reused only when `runner.json` holds the
        same cache key, `infra_status == "ok"` and a timing verdict other than
        "not_checked"; otherwise the directory is emptied
        first, because the RTC client appends to `rtc.jsonl` and adapters may keep their
        own per-job files.
        """
        job_dir = self._job_dir(request.job_id)
        cache_path = job_dir / CACHE_FILE

        # Validate async profile existence up-front (no silent failure)
        if request.timing == "async" and request.latency_profile_ref:
            profile_path = Path(request.latency_profile_ref)
            if not profile_path.is_file():
                raise FileNotFoundError(
                    f"Latency profile ref not found for async rollout: "
                    f"{request.latency_profile_ref}"
                )

        key = self.cache_key(request, policy)
        if not force_rerun:
            cached = _read_cache(cache_path, key)
            if cached is not None:
                return cached

        if job_dir.exists():
            shutil.rmtree(job_dir)
        job_dir.mkdir(parents=True)

        # Call simulator rollout (timing and latency profile passed directly in request)
        result = self.simulator.rollout(request, policy).model_copy(
            update={"timing": request.timing}
        )

        # In async mode the RTC log is part of the result: without a log that holds up,
        # the rollout says nothing about latency and must not count as a pass.
        # sim_success always stays the simulator's (decision E2, 3/11/2026).
        entry: dict[str, object] = {"key": key, "error": None}
        if request.timing == "async":
            schedule = None
            if result.infra_status == "ok":
                entry["error"], schedule = self._score_async(job_dir, result)
            result = self._with_timing_verdict(result, schedule)
            # runner.json keeps its own copy of the verdict, for the record.
            entry["timing_verdict"] = result.timing_verdict
            entry["rtc"] = schedule
        entry["result"] = result.model_dump(mode="json")
        cache_path.write_text(json.dumps(entry, sort_keys=True), encoding="utf-8")
        return result

    def cache_key(self, request: RolloutRequest, policy: PolicyEndpoint) -> str:
        """Hash of everything that changes a rollout's result.

        The request carries mode, seeds, condition and limits; the endpoint names the
        checkpoint (`<checkpoint_id>@<device>`); the latency profile is hashed by content,
        since a rewritten file keeps its path.
        """
        profile_sha256 = None
        if request.latency_profile_ref is not None:
            profile_bytes = Path(request.latency_profile_ref).read_bytes()
            profile_sha256 = hashlib.sha256(profile_bytes).hexdigest()
        payload = {
            "version": CACHE_VERSION,
            "request": request.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "simulator": self.simulator.info().model_dump(mode="json"),
            "config": self.config.model_dump(mode="json"),
            "control_hz": self.control_hz,
            "chunk_size": self.chunk_size,
            "latency_profile_sha256": profile_sha256,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _job_dir(self, job_id: str) -> Path:
        if job_id in ("", ".", "..") or Path(job_id).name != job_id:
            raise ValueError(f"job_id must be a single path component, got {job_id!r}")
        return self.staging_root / job_id

    def _score_async(
        self, job_dir: Path, result: RolloutResult
    ) -> tuple[str | None, dict[str, int] | None]:
        """Check an ok async rollout's RTC log and replay its schedule.

        Returns why the log cannot be used and the replayed schedule; exactly one of
        the two is None.
        """
        if result.trace_ref is None:
            return "async rollout returned no trace to tie the RTC log to", None
        try:
            records = read_rtc_log(job_dir / RTC_LOG_FILE)
            check_rtc_log(
                records,
                job_id=result.job_id,
                trace_id=result.trace_ref.trace_id,
                hz=self.control_hz,
                chunk_size=self.chunk_size,
            )
        except RTCLogError as error:
            return str(error), None
        schedule = replay_schedule(records, self.config.refill_level, self.chunk_size)
        return None, asdict(schedule)

    def _with_timing_verdict(
        self, result: RolloutResult, schedule: dict[str, int] | None
    ) -> RolloutResult:
        """Fill `timing_verdict` and `starved_steps`; "not_checked" without a schedule."""
        if schedule is None:
            update: dict[str, object] = {"timing_verdict": "not_checked", "starved_steps": None}
        else:
            starved = schedule["starved_steps"]
            verdict = "starved" if starved > self.config.max_starved_steps else "ok"
            update = {"timing_verdict": verdict, "starved_steps": starved}
        return result.model_copy(update=update)

    def run_eval(
        self,
        requests: Sequence[RolloutRequest],
        policy: PolicyEndpoint,
        force_rerun: bool = False,
    ) -> list[RolloutResult]:
        """Execute a batch of rollout requests sequentially with resume capability."""
        return [self.run_rollout(req, policy, force_rerun=force_rerun) for req in requests]

    def run_plan_eval(
        self,
        plan: RunPlan,
        requests: Sequence[RolloutRequest],
        policy: PolicyEndpoint,
        *,
        latency_profile_ref: str | None = None,
        force_rerun: bool = False,
    ) -> list[RolloutResult]:
        """Apply the configured mode for a RunPlan before executing its requests.

        Async callers supply a profile derived from a real RTC log. The RunPlan
        contract does not yet persist the chosen timing or profile in its lock.
        """
        timing = self.config.timing_for_purpose(plan.purpose)
        if timing == "async" and not latency_profile_ref:
            raise ValueError("async RunPlan evaluation requires a latency profile")
        prepared = [
            RolloutRequest.model_validate(
                {
                    **request.model_dump(),
                    "timing": timing,
                    "latency_profile_ref": latency_profile_ref if timing == "async" else None,
                }
            )
            for request in requests
        ]
        return self.run_eval(prepared, policy, force_rerun=force_rerun)


def _read_cache(path: Path, key: str) -> RolloutResult | None:
    """The cached result if `path` holds an ok, judged result for exactly this key."""
    if not path.is_file():
        return None
    entry = json.loads(path.read_text(encoding="utf-8"))
    if entry.get("key") != key:
        return None
    result = RolloutResult.model_validate(entry["result"])
    if result.infra_status != "ok" or result.timing_verdict == "not_checked":
        return None
    return result


def load_trace(trace_ref: TraceRef) -> dict[str, object]:
    """Helper to read trace payload from TraceRef uri."""
    path = Path(trace_ref.uri)
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
