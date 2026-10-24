"""End-to-end evidence for the empty Failure-to-Data loop."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import pyarrow as pa  # type: ignore[import-untyped]
import pytest
from flywheel.contracts import (
    CheckpointRef,
    DatasetRef,
    GenerationRequest,
    MixSpec,
    ReleaseManifest,
    RolloutRequest,
    ScorerParams,
    TaskRef,
    TrainSpec,
)
from flywheel_fakes import (
    FakeGenerator,
    FakePolicy,
    FakeSim2D,
    FakeTrainer,
    ToyPickPlace,
)

EXPECTED_RECORDS = {
    "01-run.json",
    "02-score.json",
    "03-diagnose.json",
    "04-decide.json",
    "05-acquire.json",
    "06-train.json",
    "07-gate.json",
}


def write_record(job_root: Path, name: str, payload: object) -> None:
    (job_root / name).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


@pytest.mark.e2e_fake
def test_empty_fake_loop_records_every_step(tmp_path: Path) -> None:
    started = perf_counter()
    job_root = tmp_path / "empty-loop"
    job_root.mkdir()
    task_ref = TaskRef(task_id="toy-pick-place")
    task = ToyPickPlace()
    simulator = FakeSim2D(job_root / "sim")
    policy = FakePolicy()
    condition = simulator.materialize_conditions(task_ref, [41], level=0)[0]

    rollout_request = RolloutRequest(
        job_id="run-1",
        task=task_ref,
        condition=condition,
        level=0,
        rollout_seed=43,
        max_steps=5,
    )
    with policy.serve(CheckpointRef(checkpoint_id="base"), "cpu") as endpoint:
        rollout = simulator.rollout(rollout_request, endpoint)
    write_record(job_root, "01-run.json", rollout.model_dump(mode="json"))
    assert rollout.trace_ref is not None

    trace_payload = json.loads(Path(rollout.trace_ref.uri).read_text(encoding="utf-8"))
    evaluation = task.evaluate(
        pa.Table.from_pylist(trace_payload["frames"]),
        ScorerParams(thresholds={"distance": 0.05}),
    )
    write_record(job_root, "02-score.json", evaluation.model_dump(mode="json"))

    diagnosis = {
        "cluster_id": "cluster-1",
        "diagnosis": "skill_gap" if evaluation.first_failed_stage is not None else "clean",
        "fixed_stub": True,
    }
    write_record(job_root, "03-diagnose.json", diagnosis)

    generation_count = 2
    decision = {
        "approved": True,
        "cluster_id": diagnosis["cluster_id"],
        "count": generation_count,
        "route": "fake_generator",
    }
    write_record(job_root, "04-decide.json", decision)

    generator = FakeGenerator(job_root / "acquisition")
    generation = generator.generate(
        GenerationRequest(
            job_id="acquire-1",
            task=task_ref,
            condition=condition,
            count=generation_count,
        )
    )
    write_record(job_root, "05-acquire.json", generation.model_dump(mode="json"))

    trainer = FakeTrainer(job_root / "training")
    dataset = trainer.export_dataset(
        ReleaseManifest(release_id="release-child"),
        MixSpec(weights={"release-child": 1.0}),
        str(job_root / "dataset"),
    )
    training = trainer.train(
        TrainSpec(
            job_id="train-1",
            dataset=DatasetRef(dataset_id=dataset.dataset_id, uri=dataset.uri),
            parent=CheckpointRef(checkpoint_id="base"),
            seed=47,
        )
    )
    write_record(job_root, "06-train.json", training.model_dump(mode="json"))

    gate = {
        "accepted": training.infra_status == "ok" and training.checkpoint is not None,
        "candidate": (
            training.checkpoint.checkpoint_id if training.checkpoint is not None else None
        ),
        "fixed_stub": True,
    }
    write_record(job_root, "07-gate.json", gate)

    records = {path.name for path in job_root.glob("*.json")}
    assert records == EXPECTED_RECORDS
    assert all(json.loads((job_root / name).read_text(encoding="utf-8")) for name in records)
    assert gate["accepted"] is True
    assert perf_counter() - started < 120
