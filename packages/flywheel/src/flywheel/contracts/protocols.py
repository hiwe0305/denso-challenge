"""Runtime-checkable boundaries between the core and adapter packages."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Literal, Protocol, runtime_checkable

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


@runtime_checkable
class SimulatorAdapter(Protocol):
    """Run policies and expose simulator state through core-owned records."""

    def info(self) -> AdapterInfo: ...

    def capabilities(self) -> SimCapabilities: ...

    def control_spec(self, task: object) -> object: ...

    def materialize_conditions(
        self, task: object, seeds: Sequence[int], level: int
    ) -> list[object]: ...

    def rollout(self, req: object, policy: object) -> object: ...

    def replay(self, episode: object) -> object: ...

    def snapshot(self, trace: object, step: int) -> object: ...


@runtime_checkable
class PolicyAdapter(Protocol):
    """Describe and serve a policy checkpoint."""

    def info(self) -> AdapterInfo: ...

    def describe(self, ckpt: object) -> object: ...

    def serve(self, ckpt: object, device: str) -> AbstractContextManager[object]: ...


@runtime_checkable
class TrainerAdapter(Protocol):
    """Export training data, estimate resources, and train a policy."""

    def info(self) -> AdapterInfo: ...

    def export_dataset(self, release: object, mix: object, out_uri: str) -> object: ...

    def estimate(self, spec: object) -> object: ...

    def train(self, spec: object) -> object: ...


@runtime_checkable
class GeneratorAdapter(Protocol):
    """Plan and generate synthetic or controller-produced episodes."""

    def info(self) -> AdapterInfo: ...

    def capabilities(self) -> GenCapabilities: ...

    def plan(self, req: object) -> object: ...

    def estimate(self, req: object) -> object: ...

    def generate(self, req: object) -> object: ...


@runtime_checkable
class TeleopSource(Protocol):
    """Collect human- or machine-operated corrections."""

    def info(self) -> AdapterInfo: ...

    def operator_kind(self) -> Literal["human", "machine"]: ...

    def request(self, req: object) -> object: ...

    def collect(self, ticket: object) -> object: ...


@runtime_checkable
class TaskDefinition(Protocol):
    """Pure task decomposition and scoring interface."""

    task_id: str
    version: str
    family: str

    def stages(self) -> Sequence[object]: ...

    def failure_kinds(self) -> Sequence[object]: ...

    def condition_schema(self) -> object: ...

    def required_signals(self) -> Sequence[object]: ...

    def evaluate(self, signals: object, params: object) -> object: ...
