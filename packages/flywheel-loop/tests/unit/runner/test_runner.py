"""Unit tests for the closed-loop evaluation runner (DA-23).

The runner is driven with the testkit's `FakeSim2D` and `FakePolicy`. `RTCLoggingSim`
adds only what DA-19's `RTCClient` does during a rollout: append one
`RTCInferenceRecord` per chunk to `<job_dir>/rtc.jsonl`. It decides nothing about
success; that stays with FakeSim2D and the runner.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.v0 import (
    CheckpointRef,
    PolicyEndpoint,
    PolicySpec,
    RolloutRequest,
    RolloutResult,
    TaskRef,
)
from flywheel.loop.runner import EvalConfig, LatencyProfile, Runner, load_trace
from flywheel.loop.runner.config import load_eval_config
from flywheel.testkit.fakes import FakePolicy, FakeSim2D

TASK = TaskRef(task_id="toy-pick-place")
SPEC = FakePolicy().describe(CheckpointRef(checkpoint_id="base"))


class RTCLoggingSim(FakeSim2D):
    """FakeSim2D plus the RTC client's log, as `flywheel_psi0.policy.rtc` writes it.

    Like SIMPLE, the sim steps synchronously: nothing moves while a chunk is in flight,
    and the new chunk replaces the buffer. The latency of each request is drawn from the
    request's latency profile (seeded by `rollout_seed`), or is zero in sync mode.
    """

    def __init__(self, staging_root: Path, spec: PolicySpec = SPEC, refill_at: int = 0) -> None:
        super().__init__(staging_root)
        self.spec = spec
        self.refill_at = refill_at
        self.calls = 0

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        self.calls += 1
        result = super().rollout(req, policy)
        if req.timing == "async" and result.trace_ref is not None:
            assert req.latency_profile_ref is not None
            profile = LatencyProfile.from_file(req.latency_profile_ref)
            steps = len(load_trace(result.trace_ref)["frames"])  # type: ignore[arg-type]
            self._log(req.job_id, result.trace_ref.trace_id, steps, profile, req.rollout_seed)
        return result

    def _log(
        self, job_id: str, trace_id: str, steps: int, profile: LatencyProfile, seed: int
    ) -> None:
        rng = random.Random(seed)
        clock, buffer, chunk_index = 0.0, 0, 0
        lines: list[str] = []
        for _ in range(steps):
            if buffer <= self.refill_at:
                latency = profile.sample_delay_s(rng)
                record = RTCInferenceRecord(
                    job_id=job_id,
                    trace_id=trace_id,
                    chunk_index=chunk_index,
                    observation_sent_s=clock,
                    chunk_received_s=clock + latency,
                    delay_steps=math.ceil(latency * self.spec.hz),
                    buffer_level=buffer,
                    boundary_jump=0.0,
                )
                lines.append(record.model_dump_json())
                clock += latency
                buffer = self.spec.chunk_size
                chunk_index += 1
            buffer -= 1
            clock += 1.0 / self.spec.hz
        rtc_path = self._staging_root / job_id / "rtc.jsonl"
        with rtc_path.open("a", encoding="utf-8") as stream:
            stream.write("".join(line + "\n" for line in lines))


def _request(sim: FakeSim2D, seed: int = 7, **update: object) -> RolloutRequest:
    condition = sim.materialize_conditions(TASK, [seed], level=0)[0]
    request = RolloutRequest(
        job_id="job-1",
        task=TASK,
        condition=condition,
        level=0,
        rollout_seed=seed,
        max_steps=5,
    )
    return request.model_copy(update=update)


def _async(sim: FakeSim2D, profile: Path, seed: int = 7, **update: object) -> RolloutRequest:
    return _request(sim, seed, timing="async", latency_profile_ref=str(profile), **update)


def _profile(path: Path, delay_s: float) -> Path:
    return LatencyProfile(name=path.stem, fixed_delay_s=delay_s).to_file(path)


def _endpoint(checkpoint: str = "base") -> PolicyEndpoint:
    with FakePolicy().serve(CheckpointRef(checkpoint_id=checkpoint), "cpu") as endpoint:
        return endpoint


def _runner(sim: FakeSim2D, root: Path, config: EvalConfig | None = None) -> Runner:
    return Runner(sim, root, config=config or EvalConfig(), policy_spec=SPEC)


# Result cache (review finding 2)


def test_same_request_is_served_from_cache(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)
    request = _async(sim, _profile(tmp_path / "zero.json", 0.0))

    first = runner.run_rollout(request, _endpoint())
    second = runner.run_rollout(request, _endpoint())

    assert second == first
    assert sim.calls == 1


def test_changed_seed_reruns_instead_of_returning_the_old_trace(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)

    runner.run_rollout(_request(sim, seed=7), _endpoint())
    result = runner.run_rollout(_request(sim, seed=8), _endpoint())

    assert result.trace_ref is not None
    assert load_trace(result.trace_ref)["rollout_seed"] == 8
    assert sim.calls == 2


def test_changed_checkpoint_reruns(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)

    runner.run_rollout(_request(sim), _endpoint("base"))
    result = runner.run_rollout(_request(sim), _endpoint("child"))

    assert result.trace_ref is not None
    assert load_trace(result.trace_ref)["policy_endpoint"] == "child@cpu"


@pytest.mark.parametrize("change", ["to_sync", "to_async", "profile_content", "config"])
def test_changed_mode_profile_or_config_reruns(tmp_path: Path, change: str) -> None:
    sim = RTCLoggingSim(tmp_path)
    profile = _profile(tmp_path / "profile.json", 0.0)
    sync, async_ = _request(sim), _async(sim, profile)
    first = sync if change == "to_async" else async_
    _runner(sim, tmp_path).run_rollout(first, _endpoint())

    second, config = async_, EvalConfig()
    if change == "to_sync":
        second = sync
    elif change == "profile_content":
        _profile(profile, 0.3)
    elif change == "config":
        config = EvalConfig(control_hz=25.0)
    _runner(sim, tmp_path, config).run_rollout(second, _endpoint())

    assert sim.calls == 2


def test_rerun_replaces_the_old_rtc_log(tmp_path: Path) -> None:
    """The RTC client appends; a rerun must not leave the previous run's chunks behind."""
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)
    request = _async(sim, _profile(tmp_path / "zero.json", 0.0))

    runner.run_rollout(request, _endpoint())
    runner.run_rollout(request, _endpoint(), force_rerun=True)

    lines = (tmp_path / "job-1" / "rtc.jsonl").read_text(encoding="utf-8").splitlines()
    assert [RTCInferenceRecord.model_validate_json(x).chunk_index for x in lines] == [
        0, 1, 2, 3, 4
    ]
    assert sim.calls == 2


def test_failed_infra_result_is_not_reused(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)
    request = _request(sim)
    runner.run_rollout(request, _endpoint())
    cache = tmp_path / "job-1" / "runner.json"
    entry = json.loads(cache.read_text(encoding="utf-8"))
    entry["result"]["infra_status"] = "timeout"
    cache.write_text(json.dumps(entry), encoding="utf-8")

    result = runner.run_rollout(request, _endpoint())

    assert result.infra_status == "ok"
    assert sim.calls == 2


def test_job_id_must_stay_inside_the_staging_root(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path / "runs")
    runner = _runner(sim, tmp_path / "runs")

    with pytest.raises(ValueError, match="job_id"):
        runner.run_rollout(_request(sim, job_id="../escape"), _endpoint())


# Latency profile and eval config


def test_missing_latency_profile_raises_filenotfound(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    request = _async(sim, tmp_path / "does_not_exist.json")

    with pytest.raises(FileNotFoundError, match="Latency profile ref not found"):
        _runner(sim, tmp_path).run_rollout(request, _endpoint())


def test_latency_profile_from_log_and_lognormal(tmp_path: Path) -> None:
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
    assert profile.sample_delay_s() in profile.samples_s

    synth_profile = LatencyProfile(name="synth", p50_ms=160.0, p95_ms=200.0)
    samples = [synth_profile.sample_delay_s() for _ in range(50)]
    assert all(s > 0.0 for s in samples)
    assert 0.10 <= sum(samples) / len(samples) <= 0.25


def test_eval_config_and_purpose_timing() -> None:
    config = load_eval_config()
    assert config.timing_for_purpose("g0_repro") == "sync"
    assert config.timing_for_purpose("he") == "sync"
    assert config.timing_for_purpose("branch_train") == "async"
    assert config.timing_for_purpose("round") == "async"
    assert config.timing_for_purpose("holdout") == "async"
