"""Tests for the deterministic planar simulator."""

from __future__ import annotations

from pathlib import Path

from flywheel.contracts import PolicyEndpoint, RolloutRequest, SimulatorAdapter, TaskRef
from flywheel.testkit.fakes import FakeSim2D


def make_request(sim: FakeSim2D, job_id: str, seed: int = 17) -> RolloutRequest:
    task = TaskRef(task_id="toy-pick-place")
    condition = sim.materialize_conditions(task, [seed], level=0)[0]
    return RolloutRequest(
        job_id=job_id,
        task=task,
        condition=condition,
        level=0,
        rollout_seed=29,
        max_steps=5,
    )


def test_fake_sim_is_a_runtime_simulator_adapter(tmp_path: Path) -> None:
    assert isinstance(FakeSim2D(tmp_path), SimulatorAdapter)


def test_same_seed_produces_identical_condition_vectors(tmp_path: Path) -> None:
    sim = FakeSim2D(tmp_path)
    task = TaskRef(task_id="toy-pick-place")

    first = sim.materialize_conditions(task, [42], level=1)[0]
    second = sim.materialize_conditions(task, [42], level=1)[0]

    assert first == second
    assert len(first.vector) == 4


def test_same_seed_produces_byte_identical_traces(tmp_path: Path) -> None:
    endpoint = PolicyEndpoint(endpoint_id="fake-policy")
    first_sim = FakeSim2D(tmp_path / "first")
    second_sim = FakeSim2D(tmp_path / "second")

    first = first_sim.rollout(make_request(first_sim, "job-1"), endpoint)
    second = second_sim.rollout(make_request(second_sim, "job-1"), endpoint)

    assert first.trace_ref is not None
    assert second.trace_ref is not None
    assert first.trace_ref.sha256 == second.trace_ref.sha256
    assert Path(first.trace_ref.uri).read_bytes() == Path(second.trace_ref.uri).read_bytes()


def test_rollout_is_idempotent_by_job_id(tmp_path: Path) -> None:
    sim = FakeSim2D(tmp_path)
    request = make_request(sim, "repeatable-job")
    endpoint = PolicyEndpoint(endpoint_id="fake-policy")

    first = sim.rollout(request, endpoint)
    second = sim.rollout(request, endpoint)

    assert first == second
    assert len(list((tmp_path / request.job_id).glob("trace.json"))) == 1


def test_control_spec_has_paired_planar_channels(tmp_path: Path) -> None:
    spec = FakeSim2D(tmp_path).control_spec(TaskRef(task_id="toy-pick-place"))

    assert spec.controller == "fake_2d"
    assert spec.groups[0].command_channels == ("command_x", "command_y")
    assert spec.groups[0].state_channels == ("gripper_x", "gripper_y")
