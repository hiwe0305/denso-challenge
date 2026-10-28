"""Runtime-checkable boundaries between the core and adapter packages."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Literal, Protocol, runtime_checkable

import pyarrow as pa  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field


class AdapterInfo(BaseModel):
    """Identity and reproducibility information reported by an adapter."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    image_digest: str | None = None
    nondeterminism: tuple[str, ...] = ()


class SimCapabilities(BaseModel):
    """Simulator features that the core may safely request."""

    model_config = ConfigDict(frozen=True)

    restore_state: bool = False
    visual_override: bool = False
    fault_injection: bool = False
    camera_params: bool = False
    replay: bool = False
    max_parallel: int = Field(default=1, ge=1)
    levels: tuple[int, ...] = ()


class GenCapabilities(BaseModel):
    """Generation routes implemented by a generator adapter."""

    model_config = ConfigDict(frozen=True)

    sim_rollout: bool = False
    variant: bool = False
    recovery_from_state: bool = False
    plan: bool = False
    controller: bool = False


from flywheel.contracts.v0 import (  # noqa: E402
    CheckpointRef,
    Condition,
    ConditionSchema,
    ControlSpec,
    DatasetRef,
    EpisodeRef,
    FailureKindSpec,
    GenerationRequest,
    GenerationResult,
    MixSpec,
    PlanRequest,
    PlanResult,
    PolicyEndpoint,
    PolicySpec,
    ReleaseManifest,
    ResourceEstimate,
    RolloutRequest,
    RolloutResult,
    ScorerParams,
    SignalSpec,
    StageEvaluation,
    StageSpec,
    StateRef,
    TaskRef,
    TeleopRequest,
    TeleopResult,
    TeleopTicket,
    TraceRef,
    TrainResult,
    TrainSpec,
)


@runtime_checkable
class SimulatorAdapter(Protocol):
    """Run policies and expose simulator state through core-owned records."""

    def info(self) -> AdapterInfo: ...

    def capabilities(self) -> SimCapabilities: ...

    def control_spec(self, task: TaskRef) -> ControlSpec: ...

    def materialize_conditions(
        self, task: TaskRef, seeds: Sequence[int], level: int
    ) -> list[Condition]: ...

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult: ...

    def replay(self, episode: EpisodeRef) -> TraceRef: ...

    def snapshot(self, trace: TraceRef, step: int) -> StateRef: ...


@runtime_checkable
class PolicyAdapter(Protocol):
    """Describe and serve a policy checkpoint."""

    def info(self) -> AdapterInfo: ...

    def describe(self, ckpt: CheckpointRef) -> PolicySpec: ...

    def serve(
        self, ckpt: CheckpointRef, device: str
    ) -> AbstractContextManager[PolicyEndpoint]: ...


@runtime_checkable
class TrainerAdapter(Protocol):
    """Export training data, estimate resources, and train a policy."""

    def info(self) -> AdapterInfo: ...

    def export_dataset(
        self, release: ReleaseManifest, mix: MixSpec, out_uri: str
    ) -> DatasetRef: ...

    def estimate(self, spec: TrainSpec) -> ResourceEstimate: ...

    def train(self, spec: TrainSpec) -> TrainResult: ...


@runtime_checkable
class GeneratorAdapter(Protocol):
    """Plan and generate synthetic or controller-produced episodes."""

    def info(self) -> AdapterInfo: ...

    def capabilities(self) -> GenCapabilities: ...

    def plan(self, req: PlanRequest) -> PlanResult: ...

    def estimate(self, req: GenerationRequest) -> ResourceEstimate: ...

    def generate(self, req: GenerationRequest) -> GenerationResult: ...


@runtime_checkable
class TeleopSource(Protocol):
    """Collect human- or machine-operated corrections."""

    def info(self) -> AdapterInfo: ...

    def operator_kind(self) -> Literal["human", "machine"]: ...

    def request(self, req: TeleopRequest) -> TeleopTicket: ...

    def collect(self, ticket: TeleopTicket) -> TeleopResult: ...


@runtime_checkable
class TaskDefinition(Protocol):
    """Pure task decomposition and scoring interface."""

    task_id: str
    version: str
    family: str

    def stages(self) -> Sequence[StageSpec]: ...

    def failure_kinds(self) -> Sequence[FailureKindSpec]: ...

    def condition_schema(self) -> ConditionSchema: ...

    def required_signals(self) -> Sequence[SignalSpec]: ...

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation: ...
