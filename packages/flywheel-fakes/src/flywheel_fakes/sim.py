"""A deterministic two-dimensional pick-and-place simulator."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from flywheel.contracts import (
    AdapterInfo,
    Condition,
    ControlChannelGroup,
    ControlSpec,
    EpisodeRef,
    PolicyEndpoint,
    ResourceUsage,
    RolloutRequest,
    RolloutResult,
    SimCapabilities,
    StateRef,
    TaskRef,
    TraceRef,
)


class FakeSim2D:
    """Simulate a point gripper moving a part to a target on the unit square."""

    def __init__(self, staging_root: Path) -> None:
        self._staging_root = staging_root

    def info(self) -> AdapterInfo:
        return AdapterInfo(name="fake-sim-2d", version="0.1.0")

    def capabilities(self) -> SimCapabilities:
        return SimCapabilities(camera_params=True, replay=True, max_parallel=1, levels=(0, 1))

    def control_spec(self, task: TaskRef) -> ControlSpec:
        del task
        return ControlSpec(
            controller="fake_2d",
            groups=(
                ControlChannelGroup(
                    name="planar_gripper",
                    command_channels=("command_x", "command_y"),
                    state_channels=("gripper_x", "gripper_y"),
                ),
            ),
        )

    def materialize_conditions(
        self, task: TaskRef, seeds: Sequence[int], level: int
    ) -> list[Condition]:
        conditions: list[Condition] = []
        for seed in seeds:
            rng = random.Random(seed)
            values: dict[str, bool | float | int | str] = {
                "part_x": round(rng.uniform(0.1, 0.4), 6),
                "part_y": round(rng.uniform(0.1, 0.9), 6),
                "target_x": round(rng.uniform(0.6, 0.9), 6),
                "target_y": round(rng.uniform(0.1, 0.9), 6),
                "level": level,
            }
            vector_keys = ("part_x", "part_y", "target_x", "target_y")
            vector = tuple(float(values[key]) for key in vector_keys)
            conditions.append(
                Condition(
                    condition_id=f"{task.task_id}-l{level}-s{seed}",
                    task=task,
                    seed=seed,
                    values=values,
                    vector=vector,
                )
            )
        return conditions

    def rollout(self, req: RolloutRequest, policy: PolicyEndpoint) -> RolloutResult:
        job_dir = self._staging_root / req.job_id
        result_path = job_dir / "result.json"
        if result_path.exists():
            return RolloutResult.model_validate_json(result_path.read_text(encoding="utf-8"))

        job_dir.mkdir(parents=True, exist_ok=True)
        trace_path = job_dir / "trace.json"
        trace_payload = self._simulate(req, policy)
        trace_bytes = json.dumps(trace_payload, sort_keys=True, separators=(",", ":")).encode()
        trace_path.write_bytes(trace_bytes)
        trace_ref = TraceRef(
            trace_id=f"trace-{req.job_id}",
            uri=trace_path.as_posix(),
            sha256=hashlib.sha256(trace_bytes).hexdigest(),
        )
        result = RolloutResult(
            job_id=req.job_id,
            trace_ref=trace_ref,
            sim_success=True,
            infra_status="ok",
            usage=ResourceUsage(wall_seconds=0.0),
            camera_params_hash="fake-camera-v0",
            adapter_info=self.info(),
        )
        result_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result

    def replay(self, episode: EpisodeRef) -> TraceRef:
        result_path = self._staging_root / episode.episode_id / "result.json"
        result = RolloutResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        if result.trace_ref is None:
            raise ValueError(f"Episode {episode.episode_id!r} has no trace")
        return result.trace_ref

    def snapshot(self, trace: TraceRef, step: int) -> StateRef:
        payload = cast(dict[str, Any], json.loads(Path(trace.uri).read_text(encoding="utf-8")))
        frames = cast(list[dict[str, Any]], payload["frames"])
        if step >= len(frames):
            raise IndexError(f"Trace has {len(frames)} frames, not step {step}")
        return StateRef(trace=trace, step=step)

    @staticmethod
    def _simulate(req: RolloutRequest, policy: PolicyEndpoint) -> dict[str, object]:
        values = req.condition.values
        start_x = float(values["part_x"])
        start_y = float(values["part_y"])
        target_x = float(values["target_x"])
        target_y = float(values["target_y"])
        frame_count = min(req.max_steps, 5)
        frames: list[dict[str, object]] = []
        for step in range(frame_count):
            progress = (step + 1) / frame_count
            x = start_x + (target_x - start_x) * progress
            y = start_y + (target_y - start_y) * progress
            frames.append(
                {
                    "step": step,
                    "t_state": round(step * 0.1, 6),
                    "t_image": round(step * 0.1, 6),
                    "gripper_x": round(x, 6),
                    "gripper_y": round(y, 6),
                    "part_x": round(x, 6),
                    "part_y": round(y, 6),
                    "target_x": target_x,
                    "target_y": target_y,
                }
            )
        return {
            "camera_params": {"projection": "orthographic", "width": 64, "height": 64},
            "condition_id": req.condition.condition_id,
            "frames": frames,
            "policy_endpoint": policy.endpoint_id,
            "rollout_seed": req.rollout_seed,
        }
