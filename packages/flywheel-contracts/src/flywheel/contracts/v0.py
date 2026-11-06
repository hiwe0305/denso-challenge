"""Temporary v0 records for the empty-loop adapters.

These deliberately small models unblock S1-08. S2 replaces them with the
canonical entity models delivered by S1-10 without changing adapter behavior.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FailureClass = Literal["approach", "grasp", "carry", "place", "balance"]
FailureClassRule = Literal["approach", "grasp", "carry", "place", "balance", "from_failed_stage"]
StepStatus = Literal["pass", "fail", "not_attempted", "unknown"]
UnknownReason = Literal["missing_signal", "signal_all_null", "step_not_in_trace", "no_verdict"]
InfraStatus = Literal["ok", "simulator_error", "policy_error", "timeout", "out_of_memory"]
Scalar = bool | float | int | str


class V0Model(BaseModel):
    """Strict, immutable base for records crossing an adapter boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskRef(V0Model):
    task_id: str
    version: str = "v0"


class CheckpointRef(V0Model):
    checkpoint_id: str


class EpisodeRef(V0Model):
    episode_id: str


class DatasetRef(V0Model):
    dataset_id: str
    uri: str


class Condition(V0Model):
    condition_id: str
    task: TaskRef
    seed: int
    values: dict[str, Scalar] = Field(default_factory=dict)
    vector: tuple[float, ...] = ()


class TraceRef(V0Model):
    """A rollout trace (flywheel.contracts.trace; PO decisions G1, G1b on PR #48, 3/11/2026).

    `uri` names the directory `<trace_id>/` (its last path component is `trace_id`) holding
    `steps.jsonl`, `camera_params.jsonl` and `rollout_result.json`; `sha256` is the sha256
    of `steps.jsonl`.
    """

    trace_id: str
    uri: str
    sha256: str | None = None


class StateRef(V0Model):
    trace: TraceRef
    step: int = Field(ge=0)


class VisualOverride(V0Model):
    values: dict[str, Scalar] = Field(default_factory=dict)


class FaultSpec(V0Model):
    kind: str
    parameters: dict[str, Scalar] = Field(default_factory=dict)


class RecordSpec(V0Model):
    cameras: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()


class ControlChannelGroup(V0Model):
    name: str
    command_channels: tuple[str, ...]
    state_channels: tuple[str, ...]


class ControlSpec(V0Model):
    controller: Literal["decoupled_wbc", "amo", "fake_2d"]
    groups: tuple[ControlChannelGroup, ...]


class PolicyEndpoint(V0Model):
    endpoint_id: str
    uri: str = "inprocess://policy"


class RolloutRequest(V0Model):
    job_id: str
    task: TaskRef
    condition: Condition
    level: int = Field(ge=0)
    rollout_seed: int
    start_state: StateRef | None = None
    visual_override: VisualOverride | None = None
    fault: FaultSpec | None = None
    max_steps: int = Field(gt=0)
    record: RecordSpec = Field(default_factory=RecordSpec)
    timing: Literal["sync", "async"] = "sync"
    latency_profile_ref: str | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> RolloutRequest:
        if self.timing == "async" and not self.latency_profile_ref:
            raise ValueError("async timing requires latency_profile_ref")
        return self


class ResourceUsage(V0Model):
    wall_seconds: float = Field(ge=0)
    gpu_seconds: float = Field(default=0, ge=0)


class RolloutResult(V0Model):
    job_id: str
    trace_ref: TraceRef | None
    sim_success: bool | None
    infra_status: InfraStatus
    usage: ResourceUsage
    camera_params_hash: str | None
    adapter_info: AdapterInfo
    # The request's timing, copied by the producer. None means the producer did
    # not say (older records): readers must not take it for sync (FR21).
    timing: Literal["sync", "async"] | None = None
    # Async timing outcome, kept apart from sim_success (decision E2, 3/11/2026).
    # None for sync rollouts and older producers; "not_checked" when an async
    # rollout had no usable RTC log.
    timing_verdict: Literal["ok", "starved", "not_checked"] | None = None
    starved_steps: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_timing(self) -> RolloutResult:
        # timing None stays legal with a verdict: runner.json records written
        # before `timing` existed carry one.
        if self.timing == "sync" and (
            self.timing_verdict is not None or self.starved_steps is not None
        ):
            raise ValueError("a sync rollout has no timing_verdict or starved_steps")
        return self


class PolicySpec(V0Model):
    embodiment: str
    observation_keys: tuple[str, ...]
    action_schema: tuple[str, ...]
    chunk_size: int = Field(gt=0)
    hz: float = Field(gt=0)


class ReleaseManifest(V0Model):
    release_id: str
    frozen: bool = True


class MixSpec(V0Model):
    weights: dict[str, float]


class ResourceEstimate(V0Model):
    wall_seconds: float = Field(ge=0)
    gpu_seconds: float = Field(default=0, ge=0)


class TrainSpec(V0Model):
    job_id: str
    dataset: DatasetRef
    parent: CheckpointRef
    seed: int


class TrainResult(V0Model):
    job_id: str
    checkpoint: CheckpointRef | None
    infra_status: InfraStatus
    usage: ResourceUsage


class PlanRequest(V0Model):
    job_id: str
    task: TaskRef
    condition: Condition
    until_stage: int | None = Field(default=None, ge=0)


class PlanResult(V0Model):
    job_id: str
    feasible: bool
    state: StateRef | None = None


class GenerationRequest(V0Model):
    job_id: str
    task: TaskRef
    condition: Condition
    count: int = Field(gt=0)


class GenerationResult(V0Model):
    job_id: str
    episodes: tuple[EpisodeRef, ...]
    infra_status: InfraStatus
    usage: ResourceUsage


class TeleopRequest(V0Model):
    job_id: str
    task: TaskRef
    condition: Condition | None = None
    start_state: StateRef | None = None


class TeleopTicket(V0Model):
    job_id: str
    ticket_id: str


class TeleopResult(V0Model):
    job_id: str
    episodes: tuple[EpisodeRef, ...]
    collection_minutes: float = Field(ge=0)
    reset_minutes: float = Field(ge=0)


class StageSpec(V0Model):
    name: str
    failure_class: FailureClass
    # None means an older task has not declared its signals; () means none are needed.
    signals: tuple[str, ...] | None = None


class FailureKindSpec(V0Model):
    kind: str
    failure_class: FailureClassRule


class ConditionSchema(V0Model):
    names: tuple[str, ...]


class SignalSpec(V0Model):
    name: str
    unit: str


class ScorerParams(V0Model):
    thresholds: dict[str, float] = Field(default_factory=dict)


class StageEvaluation(V0Model):
    # Legacy task producers keep reporting booleans. When a four-state result is
    # provided it must agree for attempted steps; not_attempted maps to False.
    stage_success: tuple[bool | None, ...]
    stage_status: tuple[StepStatus, ...] | None = None
    unknown_reason: tuple[UnknownReason | None, ...] | None = None
    step_enter_s: tuple[float | None, ...] | None = None
    step_exit_s: tuple[float | None, ...] | None = None
    first_failed_stage: int | None = Field(default=None, ge=0)
    failure_kind: str | None = None
    failure_class: FailureClass | None = None

    @model_validator(mode="after")
    def validate_step_details(self) -> StageEvaluation:
        import math

        n = len(self.stage_success)
        for name in ("stage_status", "unknown_reason", "step_enter_s", "step_exit_s"):
            values = getattr(self, name)
            if values is not None and len(values) != n:
                raise ValueError(f"{name} must have one entry per stage")
        if self.stage_status is not None:
            legacy = {"pass": True, "fail": False, "not_attempted": False, "unknown": None}
            if any(
                legacy[status] is not outcome
                for status, outcome in zip(self.stage_status, self.stage_success, strict=True)
            ):
                raise ValueError("stage_status must agree with stage_success")
            if self.unknown_reason is not None and any(
                (status == "unknown") != (reason is not None)
                for status, reason in zip(self.stage_status, self.unknown_reason, strict=True)
            ):
                raise ValueError("unknown_reason must be set only for unknown stages")
        elif self.unknown_reason is not None:
            raise ValueError("unknown_reason requires stage_status")
        for values in (self.step_enter_s, self.step_exit_s):
            if values is not None and any(
                value is not None and (not math.isfinite(value) or value < 0) for value in values
            ):
                raise ValueError("stage timestamps must be finite nonnegative seconds")
        if self.step_enter_s is not None and self.step_exit_s is not None:
            if any(
                start is not None and end is not None and end < start
                for start, end in zip(self.step_enter_s, self.step_exit_s, strict=True)
            ):
                raise ValueError("stage exit cannot precede entry")
        return self


from flywheel.contracts.protocols import AdapterInfo  # noqa: E402

RolloutResult.model_rebuild()
