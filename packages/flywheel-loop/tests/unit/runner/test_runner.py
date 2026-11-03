"""Unit tests for closed-loop evaluation runner (DA-23)."""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.v0 import (
    Condition,
    PolicyEndpoint,
    ResourceUsage,
    RolloutRequest,
    RolloutResult,
    TaskRef,
    TraceRef,
)
from flywheel.loop.runner.config import load_eval_config
from flywheel.loop.runner.latency import LatencyProfile
from flywheel.loop.runner.runner import Runner, load_trace
from flywheel.testkit.fakes import FakeSim2D


class FakeDelayedSim2D(FakeSim2D):
    """Simulator adapter with realistic Real-Time Chunking (RTC) delay simulation."""

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        job_dir = self._staging_root / req.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        trace_path = job_dir / "trace.json"

        is_async = req.timing == "async"
        delay_s = 0.0
        if is_async and req.latency_profile_ref:
            profile = LatencyProfile.from_file(req.latency_profile_ref)
            delay_s = profile.sample_delay_s(random.Random(req.rollout_seed))

        control_hz = 50.0
        delay_steps = round(delay_s * control_hz)

        values = req.condition.values
        start_x = float(values["part_x"])
        start_y = float(values["part_y"])
        target_x = float(values["target_x"])
        target_y = float(values["target_y"])

        frame_count = min(req.max_steps, 10)
        frames: list[dict[str, object]] = []
        sim_success = True
        boundary_jump = 0.0

        if is_async and delay_steps >= 16:
            # Significant delay causing buffer starvation and tracking failure
            sim_success = False
            curr_x, curr_y = start_x, start_y
            for step in range(frame_count):
                if step >= delay_steps:
                    progress = (step - delay_steps + 1) / frame_count
                    curr_x = start_x + (target_x - start_x) * progress
                    curr_y = start_y + (target_y - start_y) * progress
                frames.append({
                    "step": step,
                    "gripper_x": round(curr_x, 6),
                    "gripper_y": round(curr_y, 6),
                })
            boundary_jump = float(round(math.hypot(0.15, 0.15), 4))
        else:
            # Smooth progress to target
            for step in range(frame_count):
                progress = (step + 1) / frame_count
                x = start_x + (target_x - start_x) * progress
                y = start_y + (target_y - start_y) * progress
                frames.append({
                    "step": step,
                    "gripper_x": round(x, 6),
                    "gripper_y": round(y, 6),
                })
            boundary_jump = 0.0

        trace_id = f"trace-{req.job_id}"
        trace_payload = {
            "condition_id": req.condition.condition_id,
            "frames": frames,
            "policy_endpoint": policy.endpoint_id,
            "rollout_seed": req.rollout_seed,
        }
        trace_bytes = json.dumps(trace_payload, sort_keys=True, separators=(",", ":")).encode()
        trace_path.write_bytes(trace_bytes)
        trace_ref = TraceRef(
            trace_id=trace_id,
            uri=trace_path.as_posix(),
            sha256=hashlib.sha256(trace_bytes).hexdigest(),
        )

        if is_async:
            rtc_path = job_dir / "rtc.jsonl"
            buffer_level = max(0, 16 - delay_steps)
            records = [
                RTCInferenceRecord(
                    job_id=req.job_id,
                    trace_id=trace_id,
                    chunk_index=0,
                    observation_sent_s=0.0,
                    chunk_received_s=round(delay_s, 4),
                    delay_steps=delay_steps,
                    buffer_level=buffer_level,
                    boundary_jump=boundary_jump,
                )
            ]
            rtc_lines = [r.model_dump_json() for r in records]
            rtc_path.write_text("\n".join(rtc_lines) + "\n", encoding="utf-8")

        return RolloutResult(
            job_id=req.job_id,
            trace_ref=trace_ref,
            sim_success=sim_success,
            infra_status="ok",
            usage=ResourceUsage(wall_seconds=0.01),
            camera_params_hash="fake-cam",
            adapter_info=self.info(),
        )


def _make_request(
    task: TaskRef,
    cond: Condition,
    job_id: str,
    timing: str,
    latency_profile_ref: str | None = None,
    seed: int = 42,
) -> RolloutRequest:
    return RolloutRequest(
        job_id=job_id,
        task=task,
        condition=cond,
        level=0,
        rollout_seed=seed,
        max_steps=20,
        timing=timing,  # type: ignore[arg-type]
        latency_profile_ref=latency_profile_ref,
    )


def test_async_zero_latency_matches_sync_parity(tmp_path: Path) -> None:
    """AC 3: With zero latency, sync and async modes produce identical trajectories."""
    staging = tmp_path / "staging"
    sim = FakeDelayedSim2D(staging)
    runner = Runner(sim, staging)

    task = TaskRef(task_id="toy-pick-place")
    cond = sim.materialize_conditions(task, [100], level=0)[0]

    zero_profile_path = LatencyProfile.zero().to_file(tmp_path / "zero.json")

    # 1. Run sync rollout
    req_sync = _make_request(task, cond, "job-sync", timing="sync", seed=100)
    endpoint = PolicyEndpoint(endpoint_id="fake-policy")
    res_sync = runner.run_rollout(req_sync, endpoint)
    assert res_sync.sim_success is True

    # 2. Run async rollout with zero latency
    req_async = _make_request(
        task,
        cond,
        "job-async-zero",
        timing="async",
        latency_profile_ref=str(zero_profile_path),
        seed=100,
    )
    res_async = runner.run_rollout(req_async, endpoint)
    assert res_async.sim_success is True

    # 3. Assert mathematical equivalence of trajectory frames
    trace_sync = load_trace(res_sync.trace_ref)  # type: ignore[arg-type]
    trace_async = load_trace(res_async.trace_ref)  # type: ignore[arg-type]
    assert trace_sync["frames"] == trace_async["frames"]


def test_async_large_latency_reveals_error(tmp_path: Path) -> None:
    """AC 3: Large latency reveals failure in async mode, while sync mode succeeds."""
    staging = tmp_path / "staging"
    sim = FakeDelayedSim2D(staging)
    runner = Runner(sim, staging)

    task = TaskRef(task_id="toy-pick-place")
    cond = sim.materialize_conditions(task, [200], level=0)[0]

    # Large delay profile: 330 ms (17 steps > chunk_size 16)
    delayed_profile = LatencyProfile(name="slow", fixed_delay_s=0.34)
    profile_path = delayed_profile.to_file(tmp_path / "slow.json")

    endpoint = PolicyEndpoint(endpoint_id="fake-policy")

    # Sync mode achieves success
    req_sync = _make_request(task, cond, "job-sync-succ", timing="sync", seed=200)
    res_sync = runner.run_rollout(req_sync, endpoint)
    assert res_sync.sim_success is True

    # Async mode reveals failure due to latency starvation
    req_async = _make_request(
        task,
        cond,
        "job-async-fail",
        timing="async",
        latency_profile_ref=str(profile_path),
        seed=200,
    )
    res_async = runner.run_rollout(req_async, endpoint)
    assert res_async.sim_success is False

    # Check RTC log contains non-zero boundary jump
    rtc_path = staging / "job-async-fail" / "rtc.jsonl"
    assert rtc_path.is_file()
    rec = RTCInferenceRecord.model_validate_json(rtc_path.read_text(encoding="utf-8").strip())
    assert rec.delay_steps == 17
    assert rec.buffer_level == 0  # Starvation
    assert rec.boundary_jump > 0.0
    assert isinstance(rec.boundary_jump, float)


def test_missing_latency_profile_raises_filenotfound(tmp_path: Path) -> None:
    """Feedback item 5: Non-existent profile ref raises FileNotFoundError up-front."""
    staging = tmp_path / "staging"
    sim = FakeDelayedSim2D(staging)
    runner = Runner(sim, staging)

    task = TaskRef(task_id="toy-pick-place")
    cond = sim.materialize_conditions(task, [300], level=0)[0]

    req = _make_request(
        task,
        cond,
        "job-missing",
        timing="async",
        latency_profile_ref=str(tmp_path / "does_not_exist.json"),
    )
    endpoint = PolicyEndpoint(endpoint_id="fake-policy")
    with pytest.raises(FileNotFoundError, match="Latency profile ref not found"):
        runner.run_rollout(req, endpoint)


def test_resume_respects_infra_status(tmp_path: Path) -> None:
    """Feedback item 6: Cache is only reused if infra_status is ok."""
    staging = tmp_path / "staging"
    sim = FakeDelayedSim2D(staging)
    runner = Runner(sim, staging)

    task = TaskRef(task_id="toy-pick-place")
    cond = sim.materialize_conditions(task, [400], level=0)[0]
    req = _make_request(task, cond, "job-resume", timing="sync")
    endpoint = PolicyEndpoint(endpoint_id="fake-policy")

    # Manually write a failed infra_status result
    job_dir = staging / "job-resume"
    job_dir.mkdir(parents=True)
    failed_result = RolloutResult(
        job_id="job-resume",
        trace_ref=None,
        sim_success=False,
        infra_status="timeout",
        usage=ResourceUsage(wall_seconds=0.0),
        camera_params_hash=None,
        adapter_info=sim.info(),
    )
    (job_dir / "result.json").write_text(failed_result.model_dump_json(), encoding="utf-8")

    # Running rollout should not reuse crashed infra_status result, but re-run
    result = runner.run_rollout(req, endpoint)
    assert result.infra_status == "ok"
    assert result.sim_success is True


def test_latency_profile_from_log_and_lognormal(tmp_path: Path) -> None:
    """Feedback item 9: Build profile from real inference log and test lognormal sampling."""
    log_file = tmp_path / "sample_rtc.jsonl"
    lines = [
        json.dumps({"observation_sent_s": 0.0, "chunk_received_s": 0.150}),
        json.dumps({"observation_sent_s": 0.5, "chunk_received_s": 0.670}),
        json.dumps({"observation_sent_s": 1.0, "chunk_received_s": 1.200}),
    ]
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    profile = LatencyProfile.from_log(log_file, name="test_empirical")
    assert profile.name == "test_empirical"
    assert profile.p50_ms == 170.0
    assert len(profile.samples_s) == 3

    # Sample from empirical samples
    val = profile.sample_delay_s()
    assert val in profile.samples_s

    # Lognormal sample from percentiles
    synth_profile = LatencyProfile(name="synth", p50_ms=160.0, p95_ms=200.0)
    samples = [synth_profile.sample_delay_s() for _ in range(50)]
    assert all(s > 0.0 for s in samples)
    assert 0.10 <= sum(samples) / len(samples) <= 0.25


def test_eval_config_and_purpose_timing() -> None:
    """Feedback item 8: Verify eval config mapping RunPlan purposes."""
    config = load_eval_config()
    assert config.timing_for_purpose("g0_repro") == "sync"
    assert config.timing_for_purpose("he") == "sync"
    assert config.timing_for_purpose("branch_train") == "async"
    assert config.timing_for_purpose("round") == "async"
    assert config.timing_for_purpose("holdout") == "async"
