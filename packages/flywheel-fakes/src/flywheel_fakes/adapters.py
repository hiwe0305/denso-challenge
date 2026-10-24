"""Deterministic policy, trainer, generator, and teleoperation fakes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Literal

from flywheel.contracts import (
    AdapterInfo,
    CheckpointRef,
    DatasetRef,
    EpisodeRef,
    GenCapabilities,
    GenerationRequest,
    GenerationResult,
    MixSpec,
    PlanRequest,
    PlanResult,
    PolicyEndpoint,
    PolicySpec,
    ReleaseManifest,
    ResourceEstimate,
    ResourceUsage,
    StateRef,
    TeleopRequest,
    TeleopResult,
    TeleopTicket,
    TraceRef,
    TrainResult,
    TrainSpec,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")


class FakePolicy:
    """Serve an in-process deterministic policy endpoint."""

    def info(self) -> AdapterInfo:
        return AdapterInfo(name="fake-policy", version="0.1.0")

    def describe(self, ckpt: CheckpointRef) -> PolicySpec:
        del ckpt
        return PolicySpec(
            embodiment="fake-2d",
            observation_keys=("gripper_x", "gripper_y", "part_x", "part_y"),
            action_schema=("command_x", "command_y"),
            chunk_size=1,
            hz=10.0,
        )

    def serve(
        self, ckpt: CheckpointRef, device: str
    ) -> AbstractContextManager[PolicyEndpoint]:
        return self._endpoint(ckpt, device)

    @contextmanager
    def _endpoint(self, ckpt: CheckpointRef, device: str) -> Iterator[PolicyEndpoint]:
        yield PolicyEndpoint(endpoint_id=f"{ckpt.checkpoint_id}@{device}")


class FakeTrainer:
    """Export and train tiny JSON artifacts without accelerator work."""

    def __init__(self, staging_root: Path) -> None:
        self._staging_root = staging_root

    def info(self) -> AdapterInfo:
        return AdapterInfo(name="fake-trainer", version="0.1.0")

    def export_dataset(
        self, release: ReleaseManifest, mix: MixSpec, out_uri: str
    ) -> DatasetRef:
        output = Path(out_uri)
        payload = {"mix": mix.weights, "release_id": release.release_id}
        _write_json(output / "dataset.json", payload)
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return DatasetRef(dataset_id=f"fake-{digest}", uri=output.as_posix())

    def estimate(self, spec: TrainSpec) -> ResourceEstimate:
        del spec
        return ResourceEstimate(wall_seconds=0.01, gpu_seconds=0.0)

    def train(self, spec: TrainSpec) -> TrainResult:
        result_path = self._staging_root / "trainer" / spec.job_id / "result.json"
        if result_path.exists():
            return TrainResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        result = TrainResult(
            job_id=spec.job_id,
            checkpoint=CheckpointRef(checkpoint_id=f"fake-{spec.job_id}-s{spec.seed}"),
            infra_status="ok",
            usage=ResourceUsage(wall_seconds=0.01),
        )
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result


class FakeGenerator:
    """Create deterministic episode placeholders for an approved condition."""

    def __init__(self, staging_root: Path) -> None:
        self._staging_root = staging_root

    def info(self) -> AdapterInfo:
        return AdapterInfo(name="fake-generator", version="0.1.0")

    def capabilities(self) -> GenCapabilities:
        return GenCapabilities(variant=True, plan=True)

    def plan(self, req: PlanRequest) -> PlanResult:
        state = None
        if req.until_stage is not None:
            state = StateRef(
                trace=TraceRef(
                    trace_id=f"plan-{req.job_id}",
                    uri=f"fake://plans/{req.job_id}",
                ),
                step=req.until_stage,
            )
        return PlanResult(job_id=req.job_id, feasible=True, state=state)

    def estimate(self, req: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(wall_seconds=req.count * 0.01)

    def generate(self, req: GenerationRequest) -> GenerationResult:
        result_path = self._staging_root / "generator" / req.job_id / "result.json"
        if result_path.exists():
            return GenerationResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        episodes = tuple(EpisodeRef(episode_id=f"{req.job_id}-{index}") for index in range(req.count))
        for episode in episodes:
            _write_json(
                result_path.parent / f"{episode.episode_id}.json",
                {
                    "condition_id": req.condition.condition_id,
                    "episode_id": episode.episode_id,
                    "task_id": req.task.task_id,
                },
            )
        result = GenerationResult(
            job_id=req.job_id,
            episodes=episodes,
            infra_status="ok",
            usage=ResourceUsage(wall_seconds=req.count * 0.01),
        )
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result


class FakeTeleop:
    """Return one deterministic machine-operated correction per ticket."""

    def __init__(self, staging_root: Path) -> None:
        self._staging_root = staging_root

    def info(self) -> AdapterInfo:
        return AdapterInfo(name="fake-teleop", version="0.1.0")

    def operator_kind(self) -> Literal["human", "machine"]:
        return "machine"

    def request(self, req: TeleopRequest) -> TeleopTicket:
        ticket = TeleopTicket(job_id=req.job_id, ticket_id=f"ticket-{req.job_id}")
        path = self._staging_root / "teleop" / req.job_id / "ticket.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(ticket.model_dump_json(), encoding="utf-8")
        return ticket

    def collect(self, ticket: TeleopTicket) -> TeleopResult:
        result_path = self._staging_root / "teleop" / ticket.job_id / "result.json"
        if result_path.exists():
            return TeleopResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        result = TeleopResult(
            job_id=ticket.job_id,
            episodes=(EpisodeRef(episode_id=f"teleop-{ticket.ticket_id}"),),
            collection_minutes=0.01,
            reset_minutes=0.0,
        )
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result
