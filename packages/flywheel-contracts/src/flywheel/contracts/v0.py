"""Temporary v0 records for the empty-loop adapters.

These deliberately small models unblock S1-08. S2 replaces them with the
canonical entity models delivered by S1-10 without changing adapter behavior.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FailureClass = Literal["approach", "grasp", "carry", "place", "balance"]
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


class FailureKindSpec(V0Model):
    kind: str
    failure_class: FailureClass


class ConditionSchema(V0Model):
    names: tuple[str, ...]


class SignalSpec(V0Model):
    name: str
    unit: str


class ScorerParams(V0Model):
    thresholds: dict[str, float] = Field(default_factory=dict)


class StageEvaluation(V0Model):
    stage_success: tuple[bool | None, ...]
    first_failed_stage: int | None = Field(default=None, ge=0)
    failure_kind: str | None = None
    failure_class: FailureClass | None = None


from flywheel.contracts.protocols import AdapterInfo  # noqa: E402

RolloutResult.model_rebuild()
