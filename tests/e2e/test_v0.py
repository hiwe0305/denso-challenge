"""Tests for temporary empty-loop records."""

from __future__ import annotations

import pytest
from flywheel.contracts import AdapterInfo
from flywheel.contracts.v0 import (
    Condition,
    FaultSpec,
    RecordSpec,
    ResourceUsage,
    RolloutRequest,
    RolloutResult,
    StageSpec,
    TaskRef,
    TraceRef,
)
from pydantic import ValidationError


def rollout_request() -> RolloutRequest:
    task = TaskRef(task_id="toy-pick-place")
    condition = Condition(condition_id="condition-1", task=task, seed=7, vector=(0.1, 0.2))
    return RolloutRequest(
        job_id="job-1",
        task=task,
        condition=condition,
        level=0,
        rollout_seed=11,
        fault=FaultSpec(kind="none"),
        max_steps=20,
        record=RecordSpec(cameras=("top",), signals=("gripper",)),
    )


def test_rollout_request_round_trips_as_json() -> None:
    request = rollout_request()

    assert RolloutRequest.model_validate_json(request.model_dump_json()) == request


def test_rollout_result_keeps_infrastructure_status_separate_from_task_failure() -> None:
    result = RolloutResult(
        job_id="job-1",
        trace_ref=TraceRef(trace_id="trace-1", uri="trace.json"),
        sim_success=False,
        infra_status="ok",
        usage=ResourceUsage(wall_seconds=0.2),
        camera_params_hash="camera-v0",
        adapter_info=AdapterInfo(name="fake", version="0.1"),
    )

    assert result.infra_status == "ok"
    assert result.sim_success is False


def test_rollout_request_rejects_unknown_fields() -> None:
    payload = rollout_request().model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        RolloutRequest.model_validate(payload)


def test_failure_bearing_specs_require_a_failure_class() -> None:
    with pytest.raises(ValidationError):
        StageSpec.model_validate({"name": "grasp"})
