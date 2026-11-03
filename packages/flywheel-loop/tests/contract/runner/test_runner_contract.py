"""Contract test for Runner batch evaluation against fake adapters (DA-23)."""

from __future__ import annotations

from pathlib import Path

from flywheel.contracts.v0 import (
    CheckpointRef,
    Condition,
    RolloutRequest,
    TaskRef,
)
from flywheel.loop.runner import LatencyProfile, Runner
from flywheel.testkit.fakes import FakePolicy, FakeSim2D


def test_runner_batch_eval_contract(tmp_path: Path) -> None:
    staging_root = tmp_path / "runs"
    sim = FakeSim2D(staging_root / "sim")
    policy = FakePolicy()
    runner = Runner(sim, staging_root)

    profile_path = LatencyProfile.zero().to_file(tmp_path / "zero.json")
    task_ref = TaskRef(task_id="toy-pick-place")
    requests = [
        RolloutRequest(
            job_id=f"batch-job-{i}",
            task=task_ref,
            condition=Condition(
                condition_id=f"c{i}",
                task=task_ref,
                seed=100 + i,
                values={"part_x": 0.1 * i, "part_y": 0.2, "target_x": 0.8, "target_y": 0.9},
            ),
            level=0,
            rollout_seed=100 + i,
            max_steps=5,
            timing="async",
            latency_profile_ref=str(profile_path),
        )
        for i in range(3)
    ]

    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        results = runner.run_eval(requests, endpoint)

    assert len(results) == 3
    for idx, res in enumerate(results):
        assert res.job_id == f"batch-job-{idx}"
        assert res.sim_success is True
        assert res.trace_ref is not None
        job_dir = staging_root / f"batch-job-{idx}"
        assert (job_dir / "result.json").is_file()
