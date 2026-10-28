"""Tests for the deterministic non-simulator fake adapters."""

from __future__ import annotations

from pathlib import Path

from flywheel.contracts import (
    CheckpointRef,
    Condition,
    DatasetRef,
    GenerationRequest,
    GeneratorAdapter,
    MixSpec,
    PolicyAdapter,
    ReleaseManifest,
    TaskRef,
    TeleopRequest,
    TeleopSource,
    TrainerAdapter,
    TrainSpec,
)
from flywheel.testkit.fakes import FakeGenerator, FakePolicy, FakeTeleop, FakeTrainer


def condition() -> Condition:
    task = TaskRef(task_id="toy-pick-place")
    return Condition(condition_id="condition-7", task=task, seed=7)


def test_fakes_satisfy_runtime_protocols(tmp_path: Path) -> None:
    assert isinstance(FakePolicy(), PolicyAdapter)
    assert isinstance(FakeTrainer(tmp_path), TrainerAdapter)
    assert isinstance(FakeGenerator(tmp_path), GeneratorAdapter)
    assert isinstance(FakeTeleop(tmp_path), TeleopSource)


def test_policy_serves_repeatable_endpoint() -> None:
    policy = FakePolicy()
    checkpoint = CheckpointRef(checkpoint_id="base")

    with policy.serve(checkpoint, "cpu") as first:
        with policy.serve(checkpoint, "cpu") as second:
            assert first == second


def test_trainer_is_idempotent_by_job_id(tmp_path: Path) -> None:
    trainer = FakeTrainer(tmp_path)
    spec = TrainSpec(
        job_id="train-1",
        dataset=DatasetRef(dataset_id="data-1", uri="fake://data"),
        parent=CheckpointRef(checkpoint_id="base"),
        seed=13,
    )

    assert trainer.train(spec) == trainer.train(spec)


def test_same_training_seed_produces_same_checkpoint(tmp_path: Path) -> None:
    spec = TrainSpec(
        job_id="train-seeded",
        dataset=DatasetRef(dataset_id="data-1", uri="fake://data"),
        parent=CheckpointRef(checkpoint_id="base"),
        seed=13,
    )

    first = FakeTrainer(tmp_path / "first").train(spec)
    second = FakeTrainer(tmp_path / "second").train(spec)

    assert first.checkpoint == second.checkpoint


def test_dataset_export_is_deterministic(tmp_path: Path) -> None:
    trainer = FakeTrainer(tmp_path)
    release = ReleaseManifest(release_id="release-1")
    mix = MixSpec(weights={"release-1": 1.0})

    first = trainer.export_dataset(release, mix, str(tmp_path / "first"))
    second = trainer.export_dataset(release, mix, str(tmp_path / "second"))

    assert first.dataset_id == second.dataset_id


def test_generator_is_seeded_by_condition_and_idempotent(tmp_path: Path) -> None:
    generator = FakeGenerator(tmp_path)
    req = GenerationRequest(
        job_id="generate-1",
        task=condition().task,
        condition=condition(),
        count=3,
    )

    first = generator.generate(req)
    second = generator.generate(req)

    assert first == second
    assert [episode.episode_id for episode in first.episodes] == [
        "generate-1-0",
        "generate-1-1",
        "generate-1-2",
    ]

    assert FakeGenerator(tmp_path / "fresh").generate(req).episodes == first.episodes


def test_teleop_ticket_and_collection_are_idempotent(tmp_path: Path) -> None:
    teleop = FakeTeleop(tmp_path)
    req = TeleopRequest(job_id="teleop-1", task=condition().task, condition=condition())

    first_ticket = teleop.request(req)
    second_ticket = teleop.request(req)
    first_result = teleop.collect(first_ticket)
    second_result = teleop.collect(second_ticket)

    assert first_ticket == second_ticket
    assert first_result == second_result
    assert teleop.operator_kind() == "machine"
    fresh = FakeTeleop(tmp_path / "fresh")
    assert fresh.collect(fresh.request(req)).episodes == first_result.episodes
