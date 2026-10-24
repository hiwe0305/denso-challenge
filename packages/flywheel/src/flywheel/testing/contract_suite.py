"""Reusable v0 behavioral checks for adapter implementations."""

from __future__ import annotations

from flywheel.contracts import (
    EpisodeRef,
    GenerationRequest,
    GeneratorAdapter,
    PlanRequest,
    PolicyEndpoint,
    RolloutRequest,
    SimulatorAdapter,
    TeleopRequest,
    TeleopSource,
    TrainerAdapter,
    TrainSpec,
)


class ContractViolation(AssertionError):
    """An adapter's behavior contradicts the v0 contract."""


def check_simulator_contract(
    adapter: SimulatorAdapter,
    request: RolloutRequest,
    policy: PolicyEndpoint,
) -> None:
    """Check capability truthfulness, idempotence, and status separation."""
    first = adapter.rollout(request, policy)
    second = adapter.rollout(request, policy)
    if first != second:
        raise ContractViolation("Simulator is not idempotent for the same job_id")
    if first.job_id != request.job_id:
        raise ContractViolation("Simulator result changed job_id")
    if first.infra_status != "ok" and first.sim_success is not None:
        raise ContractViolation("Infrastructure failures must not be task failures")
    if first.infra_status == "ok" and first.trace_ref is None:
        raise ContractViolation("Successful simulator job has no trace")

    capabilities = adapter.capabilities()
    if capabilities.camera_params and not first.camera_params_hash:
        raise ContractViolation("camera_params=True but no camera parameters hash was returned")
    if capabilities.replay:
        if first.trace_ref is None:
            raise ContractViolation("replay=True but the rollout has no trace")
        replayed = adapter.replay(EpisodeRef(episode_id=request.job_id))
        if replayed != first.trace_ref:
            raise ContractViolation("replay=True but replay did not return the rollout trace")


def check_trainer_contract(adapter: TrainerAdapter, spec: TrainSpec) -> None:
    """Check train idempotence and infrastructure reporting."""
    first = adapter.train(spec)
    second = adapter.train(spec)
    if first != second:
        raise ContractViolation("Trainer is not idempotent for the same job_id")
    if first.job_id != spec.job_id:
        raise ContractViolation("Trainer result changed job_id")
    if first.infra_status != "ok" and first.checkpoint is not None:
        raise ContractViolation("Failed training job must not publish a checkpoint")


def check_generator_contract(
    adapter: GeneratorAdapter,
    request: GenerationRequest,
    plan_request: PlanRequest,
) -> None:
    """Check generate idempotence and claimed planning support."""
    first = adapter.generate(request)
    second = adapter.generate(request)
    if first != second:
        raise ContractViolation("Generator is not idempotent for the same job_id")
    if first.job_id != request.job_id:
        raise ContractViolation("Generator result changed job_id")
    if first.infra_status != "ok" and first.episodes:
        raise ContractViolation("Failed generation job must not publish episodes")
    if adapter.capabilities().plan:
        try:
            plan = adapter.plan(plan_request)
        except Exception as error:
            raise ContractViolation("plan=True but plan() failed") from error
        if plan.job_id != plan_request.job_id:
            raise ContractViolation("Generator plan changed job_id")


def check_teleop_contract(adapter: TeleopSource, request: TeleopRequest) -> None:
    """Check ticket and collection idempotence."""
    first_ticket = adapter.request(request)
    second_ticket = adapter.request(request)
    if first_ticket != second_ticket:
        raise ContractViolation("Teleop request is not idempotent for the same job_id")
    first = adapter.collect(first_ticket)
    second = adapter.collect(second_ticket)
    if first != second:
        raise ContractViolation("Teleop collection is not idempotent for the same job_id")
    if first.job_id != request.job_id:
        raise ContractViolation("Teleop result changed job_id")
