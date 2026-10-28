"""Run the shared v0 contract suite against every fake adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from flywheel.contracts import (
    CheckpointRef,
    Condition,
    DatasetRef,
    GenerationRequest,
    PlanRequest,
    PolicyEndpoint,
    RolloutRequest,
    RolloutResult,
    TaskRef,
    TeleopRequest,
    TrainSpec,
)
from flywheel.testkit import (
    ContractViolation,
    check_generator_contract,
    check_simulator_contract,
    check_teleop_contract,
    check_trainer_contract,
)
from flywheel.testkit.fakes import FakeGenerator, FakeSim2D, FakeTeleop, FakeTrainer


def fixture_condition() -> Condition:
    task = TaskRef(task_id="toy-pick-place")
    return Condition(condition_id="condition-5", task=task, seed=5)


def rollout_request(simulator: FakeSim2D) -> RolloutRequest:
    task = TaskRef(task_id="toy-pick-place")
    condition = simulator.materialize_conditions(task, [5], level=0)[0]
    return RolloutRequest(
        job_id="contract-rollout",
        task=task,
        condition=condition,
        level=0,
        rollout_seed=7,
        max_steps=5,
    )


def test_simulator_contract(tmp_path: Path) -> None:
    simulator = FakeSim2D(tmp_path)
    check_simulator_contract(
        simulator,
        rollout_request(simulator),
        PolicyEndpoint(endpoint_id="policy"),
    )


def test_trainer_contract(tmp_path: Path) -> None:
    check_trainer_contract(
        FakeTrainer(tmp_path),
        TrainSpec(
            job_id="contract-train",
            dataset=DatasetRef(dataset_id="dataset", uri="fake://dataset"),
            parent=CheckpointRef(checkpoint_id="base"),
            seed=11,
        ),
    )


def test_generator_contract(tmp_path: Path) -> None:
    condition = fixture_condition()
    check_generator_contract(
        FakeGenerator(tmp_path),
        GenerationRequest(
            job_id="contract-generate",
            task=condition.task,
            condition=condition,
            count=2,
        ),
        PlanRequest(
            job_id="contract-plan",
            task=condition.task,
            condition=condition,
            until_stage=1,
        ),
    )


def test_teleop_contract(tmp_path: Path) -> None:
    condition = fixture_condition()
    check_teleop_contract(
        FakeTeleop(tmp_path),
        TeleopRequest(job_id="contract-teleop", task=condition.task, condition=condition),
    )


class LyingCameraSimulator(FakeSim2D):
    """Claim camera support while deliberately omitting camera evidence."""

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        result = super().rollout(req, policy)
        return result.model_copy(update={"camera_params_hash": None})


def test_contract_suite_rejects_a_false_capability_claim(tmp_path: Path) -> None:
    simulator = LyingCameraSimulator(tmp_path)

    with pytest.raises(ContractViolation, match="camera_params=True"):
        check_simulator_contract(
            simulator,
            rollout_request(simulator),
            PolicyEndpoint(endpoint_id="policy"),
        )
