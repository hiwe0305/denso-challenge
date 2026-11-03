"""Unit tests for Runner, sync vs async evaluation, RTC logging, and resume support (DA-23)."""

from __future__ import annotations

import json
from pathlib import Path

from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.v0 import (
    CheckpointRef,
    Condition,
    RolloutRequest,
    TaskRef,
)
from flywheel.loop.runner import LatencyProfile, Runner
from flywheel.testkit.fakes import FakePolicy, FakeSim2D


def create_request(
    job_id: str,
    timing: str = "sync",
    latency_profile_ref: str | None = None,
    seed: int = 42,
    max_steps: int = 5,
) -> RolloutRequest:
    task_ref = TaskRef(task_id="toy-pick-place")
    condition = Condition(
        condition_id="c1",
        task=task_ref,
        seed=seed,
        values={"part_x": 0.2, "part_y": 0.3, "target_x": 0.8, "target_y": 0.9},
    )
    return RolloutRequest(
        job_id=job_id,
        task=task_ref,
        condition=condition,
        level=0,
        rollout_seed=seed,
        max_steps=max_steps,
        timing=timing,  # type: ignore[arg-type]
        latency_profile_ref=latency_profile_ref,
    )


def test_zero_latency_parity(tmp_path: Path) -> None:
    """AC 3: With zero latency, sync and async modes produce identical traces on the same seed."""
    staging_root = tmp_path / "runs"
    sim = FakeSim2D(staging_root / "sim")
    policy = FakePolicy()
    runner = Runner(sim, staging_root)

    req_sync = create_request("job-sync", timing="sync", seed=100)
    req_async = create_request(
        "job-async",
        timing="async",
        latency_profile_ref=str(tmp_path / "zero.json"),
        seed=100,
    )
    # Save a zero latency profile
    (tmp_path / "zero.json").write_text(
        json.dumps({"name": "zero", "fixed_delay_s": 0.0}), encoding="utf-8"
    )

    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        res_sync = runner.run_rollout(req_sync, endpoint)
        res_async = runner.run_rollout(req_async, endpoint)

    assert res_sync.sim_success == res_async.sim_success
    assert res_sync.trace_ref is not None
    assert res_async.trace_ref is not None

    trace_sync = json.loads(Path(res_sync.trace_ref.uri).read_text(encoding="utf-8"))
    trace_async = json.loads(Path(res_async.trace_ref.uri).read_text(encoding="utf-8"))
    assert trace_sync["frames"] == trace_async["frames"]


def test_async_latency_reveals_boundary_jumps(tmp_path: Path) -> None:
    """AC 3: With non-zero latency, async closed-loop rollout exposes latency-induced jumps."""
    staging_root = tmp_path / "runs"
    sim = FakeSim2D(staging_root / "sim")
    policy = FakePolicy()
    runner = Runner(sim, staging_root, control_hz=50.0, chunk_size=4)

    # 250ms latency profile (larger than chunk duration of 4/50 = 80ms)
    profile_path = tmp_path / "high_latency.json"
    profile_path.write_text(
        json.dumps({"name": "high", "fixed_delay_s": 0.25}), encoding="utf-8"
    )

    req_async = create_request(
        "job-delayed-async",
        timing="async",
        latency_profile_ref=str(profile_path),
        seed=42,
        max_steps=20,
    )

    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        res = runner.run_rollout(req_async, endpoint)

    assert res.sim_success is True
    rtc_file = staging_root / "job-delayed-async" / "rtc.jsonl"
    assert rtc_file.is_file()

    records = [
        RTCInferenceRecord.model_validate_json(line)
        for line in rtc_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) > 0
    # Because delay (250ms) > chunk duration (80ms), boundary jumps occur
    jumps = [r for r in records if r.boundary_jump]
    assert len(jumps) > 0


def test_rtc_inference_logging_schema(tmp_path: Path) -> None:
    """AC 2: RTC inference logs are recorded in job dir and strictly match RTCInferenceRecord."""
    staging_root = tmp_path / "runs"
    sim = FakeSim2D(staging_root / "sim")
    policy = FakePolicy()
    runner = Runner(sim, staging_root, control_hz=50.0, chunk_size=8)

    req = create_request("job-rtc-check", timing="sync", max_steps=16)
    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        runner.run_rollout(req, endpoint)

    rtc_file = staging_root / "job-rtc-check" / "rtc.jsonl"
    assert rtc_file.is_file()

    raw_lines = rtc_file.read_text(encoding="utf-8").splitlines()
    lines = [line.strip() for line in raw_lines if line.strip()]
    assert len(lines) == 2  # 16 steps / 8 chunk_size = 2 chunks

    for idx, line in enumerate(lines):
        rec = RTCInferenceRecord.model_validate_json(line)
        assert rec.job_id == "job-rtc-check"
        assert rec.chunk_index == idx
        assert rec.observation_sent_s >= 0.0
        assert rec.chunk_received_s >= rec.observation_sent_s


def test_runner_resume_support(tmp_path: Path) -> None:
    """Interrupted runs resume without re-executing already completed episodes."""
    staging_root = tmp_path / "runs"
    sim = FakeSim2D(staging_root / "sim")
    policy = FakePolicy()
    runner = Runner(sim, staging_root)

    req = create_request("job-resume", timing="sync")
    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        res1 = runner.run_rollout(req, endpoint)
        mtime1 = (staging_root / "job-resume" / "result.json").stat().st_mtime_ns

        # Second call should load cached result immediately
        res2 = runner.run_rollout(req, endpoint)
        mtime2 = (staging_root / "job-resume" / "result.json").stat().st_mtime_ns

    assert res1.job_id == res2.job_id
    assert mtime1 == mtime2


def test_latency_profile_sampling() -> None:
    """Validate LatencyProfile sampling bounds and fixed delay modes."""
    profile_fixed = LatencyProfile(name="test", fixed_delay_s=0.15)
    assert profile_fixed.sample_delay_s() == 0.15

    profile_zero = LatencyProfile.zero()
    assert profile_zero.sample_delay_s() == 0.0

    profile_samples = LatencyProfile(samples_ms=[100.0, 200.0])
    delay = profile_samples.sample_delay_s()
    assert delay in (0.1, 0.2)

