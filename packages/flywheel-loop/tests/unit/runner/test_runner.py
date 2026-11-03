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
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

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
    and the new chunk replaces the buffer. The client runs `max_steps` control steps; the
    latency of each request is drawn from the request's latency profile, seeded by
    `rollout_seed`.
    """

    def __init__(
        self,
        staging_root: Path,
        spec: PolicySpec = SPEC,
        refill_at: int = 0,
        tamper: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    ) -> None:
        super().__init__(staging_root)
        self.spec = spec
        self.refill_at = refill_at
        self.tamper = tamper
        self.calls = 0

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        self.calls += 1
        result = super().rollout(req, policy)
        if req.timing == "async" and result.trace_ref is not None:
            assert req.latency_profile_ref is not None
            profile = LatencyProfile.from_file(req.latency_profile_ref)
            trace_id = result.trace_ref.trace_id
            self._log(req.job_id, trace_id, req.max_steps, profile, req.rollout_seed)
        return result

    def _log(
        self, job_id: str, trace_id: str, steps: int, profile: LatencyProfile, seed: int
    ) -> None:
        rng = random.Random(seed)
        clock, buffer, chunk_index = 0.0, 0, 0
        records: list[dict[str, Any]] = []
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
                records.append(record.model_dump(mode="json"))
                clock += latency
                buffer = self.spec.chunk_size
                chunk_index += 1
            buffer -= 1
            clock += 1.0 / self.spec.hz
        if self.tamper is not None:
            records = self.tamper(records)
        rtc_path = self._staging_root / job_id / "rtc.jsonl"
        with rtc_path.open("a", encoding="utf-8") as stream:
            stream.write("".join(json.dumps(record) + "\n" for record in records))


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
    assert [RTCInferenceRecord.model_validate_json(x).chunk_index for x in lines] == [0, 1, 2, 3, 4]
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


# RTC log in async mode (review findings 3 and 4)


def test_async_without_rtc_log_is_a_reported_failure(tmp_path: Path) -> None:
    sim = FakeSim2D(tmp_path)  # writes a trace but no rtc.jsonl
    runner = _runner(sim, tmp_path)

    result = runner.run_rollout(_async(sim, _profile(tmp_path / "z.json", 0.0)), _endpoint())

    assert result.infra_status == "policy_error"
    assert result.sim_success is None
    entry = json.loads((tmp_path / "job-1" / "runner.json").read_text(encoding="utf-8"))
    assert "rtc.jsonl" in entry["error"]


def test_failed_async_rollout_is_retried_not_cached(tmp_path: Path) -> None:
    sim = FakeSim2D(tmp_path)
    runner = _runner(sim, tmp_path)
    request = _async(sim, _profile(tmp_path / "z.json", 0.0))
    runner.run_rollout(request, _endpoint())

    retry = _runner(RTCLoggingSim(tmp_path), tmp_path).run_rollout(request, _endpoint())

    assert retry.infra_status == "ok"


def _set(field: str, value: object, index: int | None = None) -> Callable[..., Any]:
    def tamper(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, record in enumerate(records):
            if index is None or i == index:
                record[field] = value
        return records

    return tamper


def _swap_chunks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records[1]["chunk_index"], records[2]["chunk_index"] = 2, 1
    return records


def _overlap(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # The second request goes out before the first chunk came back (single flight).
    records[1]["observation_sent_s"] = records[0]["chunk_received_s"] - 0.05
    return records


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        (lambda records: [], "no records"),
        (_set("job_id", "other-job"), "job_id"),
        (_set("trace_id", "other-trace"), "trace_id"),
        (_swap_chunks, "chunk_index"),
        (_set("delay_steps", 99, index=1), "delay_steps"),
        (_set("buffer_level", 500, index=1), "buffer_level"),
        (_set("boundary_jump", -1.0, index=1), "RTCInferenceRecord"),
        (_overlap, "before chunk"),
    ],
    ids=["empty", "job", "trace", "order", "delay", "buffer", "schema", "overlap"],
)
def test_async_rtc_log_is_checked_for_meaning(
    tmp_path: Path, tamper: Callable[..., Any], reason: str
) -> None:
    sim = RTCLoggingSim(tmp_path, tamper=tamper)
    runner = _runner(sim, tmp_path)

    result = runner.run_rollout(_async(sim, _profile(tmp_path / "p.json", 0.1)), _endpoint())

    assert result.infra_status == "policy_error"
    entry = json.loads((tmp_path / "job-1" / "runner.json").read_text(encoding="utf-8"))
    assert reason in entry["error"]


def test_unreadable_rtc_log_is_a_reported_failure(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)
    request = _async(sim, _profile(tmp_path / "p.json", 0.1))
    original = sim.rollout

    def rollout(req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        result = original(req, policy)
        with (tmp_path / req.job_id / "rtc.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("{not json\n")
        return result

    sim.rollout = rollout  # type: ignore[method-assign]
    result = runner.run_rollout(request, _endpoint())

    assert result.infra_status == "policy_error"


def test_valid_async_rtc_log_is_kept_in_the_job_dir(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    runner = _runner(sim, tmp_path)

    result = runner.run_rollout(_async(sim, _profile(tmp_path / "p.json", 0.1)), _endpoint())

    assert result.infra_status == "ok"
    assert result.trace_ref is not None
    lines = (tmp_path / "job-1" / "rtc.jsonl").read_text(encoding="utf-8").splitlines()
    records = [RTCInferenceRecord.model_validate_json(line) for line in lines]
    assert {r.trace_id for r in records} == {result.trace_ref.trace_id}
    assert [r.delay_steps for r in records] == [1] * 5  # ceil(0.1 s * 10 Hz)


# Async mode: the runner replays the real-time schedule (review finding 1, AC 3)

PSI0_LIKE = PolicySpec(
    embodiment="fake-2d",
    observation_keys=SPEC.observation_keys,
    action_schema=SPEC.action_schema,
    chunk_size=16,
    hz=50.0,
)


def _sync_and_async(
    tmp_path: Path,
    delay_s: float,
    spec: PolicySpec = SPEC,
    refill_at: int = 0,
    max_steps: int = 5,
    config: EvalConfig | None = None,
) -> tuple[RolloutResult, RolloutResult]:
    sim = RTCLoggingSim(tmp_path, spec=spec, refill_at=refill_at)
    runner = Runner(sim, tmp_path, config=config or EvalConfig(), policy_spec=spec)
    profile = _profile(tmp_path / "profile.json", delay_s)
    sync = runner.run_rollout(
        _request(sim, seed=11, job_id="sync", max_steps=max_steps), _endpoint()
    )
    async_ = runner.run_rollout(
        _async(sim, profile, seed=11, job_id="async", max_steps=max_steps), _endpoint()
    )
    return sync, async_


def _entry(root: Path, job_id: str) -> dict[str, Any]:
    text = (root / job_id / "runner.json").read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(text))


def test_sync_passes_and_async_reveals_the_latency_failure(tmp_path: Path) -> None:
    sync, async_ = _sync_and_async(tmp_path, delay_s=0.34)

    assert sync.sim_success is True
    # The sim's verdict stays the sim's; the latency failure is the timing verdict.
    assert async_.infra_status == "ok"
    assert async_.sim_success is True
    entry = _entry(tmp_path, "async")
    assert entry["timing_verdict"] == "starved"
    # Chunk size 1 at 10 Hz: a hardware client asks with at most 1 action left
    # (refill_level 8 capped at the chunk), so each of chunks 1-4 leaves
    # ceil(0.34 * 10) - 1 = 3 steps with no action.
    assert entry["rtc"] == {
        "chunks": 5,
        "max_delay_steps": 4,
        "refill_level": 1,
        "starved_chunks": 4,
        "starved_steps": 12,
    }
    assert "timing_verdict" not in _entry(tmp_path, "sync")


def test_zero_latency_async_matches_sync_on_the_same_seed(tmp_path: Path) -> None:
    sync, async_ = _sync_and_async(tmp_path, delay_s=0.0)

    assert async_.infra_status == sync.infra_status == "ok"
    assert async_.sim_success == sync.sim_success is True
    assert _entry(tmp_path, "async")["timing_verdict"] == "pass"
    assert sync.trace_ref is not None and async_.trace_ref is not None
    assert load_trace(async_.trace_ref)["frames"] == load_trace(sync.trace_ref)["frames"]


@pytest.mark.parametrize(
    ("delay_s", "verdict", "starved_steps"),
    [
        (0.06, "pass", 0),  # 3 steps of latency: covered by the 8 actions left
        (0.18, "starved", 3),  # 9 steps: 1 step without an action on chunks 1-3
    ],
)
def test_refill_level_decides_starvation_on_rtc_client_shaped_logs(
    tmp_path: Path, delay_s: float, verdict: str, starved_steps: int
) -> None:
    """Records as RTCClient writes them on SIMPLE: refill when empty, buffer_level 0."""
    sync, async_ = _sync_and_async(tmp_path, delay_s, spec=PSI0_LIKE, max_steps=64)

    lines = (tmp_path / "async" / "rtc.jsonl").read_text(encoding="utf-8").splitlines()
    records = [RTCInferenceRecord.model_validate_json(line) for line in lines]
    assert len(records) == 4
    assert {r.buffer_level for r in records} == {0}
    assert sync.sim_success is async_.sim_success is True
    entry = _entry(tmp_path, "async")
    assert entry["timing_verdict"] == verdict
    assert entry["rtc"]["refill_level"] == 8
    assert entry["rtc"]["starved_steps"] == starved_steps


def test_refill_level_and_starvation_limit_come_from_the_eval_config(tmp_path: Path) -> None:
    config = EvalConfig(refill_level=10, max_starved_steps=0)
    _, async_ = _sync_and_async(tmp_path, 0.18, spec=PSI0_LIKE, max_steps=64, config=config)
    assert _entry(tmp_path, "async")["timing_verdict"] == "pass"

    config = EvalConfig(max_starved_steps=12)
    _sync_and_async(tmp_path / "limit", delay_s=0.34, config=config)
    assert _entry(tmp_path / "limit", "async")["timing_verdict"] == "pass"


def test_eval_yaml_sets_refill_level_to_psi0_max_delay() -> None:
    assert load_eval_config().refill_level == 8


# Latency profile and eval config


def test_missing_latency_profile_raises_filenotfound(tmp_path: Path) -> None:
    sim = RTCLoggingSim(tmp_path)
    request = _async(sim, tmp_path / "does_not_exist.json")

    with pytest.raises(FileNotFoundError, match="Latency profile ref not found"):
        _runner(sim, tmp_path).run_rollout(request, _endpoint())


def test_latency_profile_from_log_and_lognormal(tmp_path: Path) -> None:
    log_file = tmp_path / "sample_rtc.jsonl"
    spans = [(0.0, 0.150), (0.5, 0.670), (1.0, 1.200)]
    records = [
        RTCInferenceRecord(
            job_id="job-1",
            trace_id="trace-job-1",
            chunk_index=index,
            observation_sent_s=sent,
            chunk_received_s=received,
            delay_steps=math.ceil((received - sent) * SPEC.hz),
            buffer_level=0,
            boundary_jump=0.0,
        )
        for index, (sent, received) in enumerate(spans)
    ]
    log_file.write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")

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


def test_eval_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="max_starved_step"):
        EvalConfig.model_validate({"max_starved_step": 3})
