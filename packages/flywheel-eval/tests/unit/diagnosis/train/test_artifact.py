"""The whole run and the record it leaves behind (DA-08 task 6, AC 4, 5).

Two properties matter more than any single detector here. The artifact has to
carry the `skipped` list, because a `TrainDiagnosis` with an empty `findings`
list and no skips says "this checkpoint is clean" and one with skips says
"these codes went unmeasured" - dropping them would turn the second into the
first (FR21). And the store is append-only: running the diagnosis twice on one
job leaves two records, never one overwritten.

The job inputs are files here rather than in-memory series, because the missing
file is the case that matters: a job with no probe result must skip O1-O4 by
name, not pass them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.training import TrainDiagnosis, TrainingMetric
from flywheel.eval.config import load_train_thresholds
from flywheel.eval.diagnosis.train.artifact import (
    OFFLINE_CODES,
    TRAIN_CODES,
    JobInputs,
    build_artifact,
    diagnose_all,
    load_job,
    write_artifact,
)
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.reader import ReaderError

TRAIN_YAML = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis" / "train.yaml"
PROBE_SHA = "a" * 64


def record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_plan_id": "rp",
        "job_id": "job",
        "checkpoint_id": "ckpt-child",
        "release_id": "rel",
        "attempt": 0,
        "step": 0,
        "epoch": 0,
        "split": "train",
        "loss": 1.0,
        "lr": 1e-3,
        "vlm_frozen": True,
        "wall_time_s": 1.0,
    }
    return base | overrides


def write_job(
    directory: Path,
    *,
    records: list[dict[str, Any]] | None = None,
    layout: bool = True,
    probe_p3: bool = True,
    probe_p4: bool = True,
    probe_p4_parent: bool = True,
) -> Path:
    """A job directory as `fw eval diag-train` finds one on disk."""
    directory.mkdir(parents=True, exist_ok=True)
    lines = records if records is not None else _learning_records()
    (directory / "metrics.jsonl").write_text(
        "\n".join(json.dumps(TrainingMetric.model_validate(line).model_dump()) for line in lines),
        encoding="utf-8",
    )
    if layout:
        _write(directory / "action_layout.json", _layout())
    if probe_p3:
        _write(directory / "probe_p3.json", _p3("ckpt-child"))
    if probe_p4:
        _write(directory / "probe_p4.json", _p4("ckpt-child", "ckpt-parent"))
    if probe_p4_parent:
        _write(directory / "probe_p4_parent.json", _p4("ckpt-parent", "ckpt-grandparent"))
    return directory


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _learning_records() -> list[dict[str, Any]]:
    """A job that is learning in every signal, the control of the detector tests."""
    train = [
        record(
            step=step,
            loss=1.0 - 0.0002 * step,
            loss_by_group={"arm": 1.0 - 0.0003 * step, "hand": 1.0 - 0.0003 * step},
            pred_var_by_dim=[0.2, 0.3, 0.1],
            pred_std=[0.45, 0.55, 0.3],
            target_std=[0.5, 0.6, 0.3],
            grad_norm_vlm=0.0,
            grad_norm_action=0.1,
        )
        for step in range(0, 3001, 10)
    ]
    val = [
        record(step=step, split="val", loss=1.05 - 0.0002 * step) for step in range(0, 3001, 500)
    ]
    return train + val


def _layout() -> dict[str, Any]:
    limits = {"limit_low": -1.0, "limit_high": 1.0}
    return {
        "dimensions": [
            {"name": "arm_0", "group": "arm", "masked": False, **limits},
            {"name": "arm_1", "group": "arm", "masked": False, **limits},
            {"name": "pad_0", "group": "pad", "masked": True},
        ]
    }


def _p3(checkpoint_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "probe": "P3",
        "checkpoint_id": checkpoint_id,
        "dataset_sha256": PROBE_SHA,
        "error_by_group": {"arm": 0.10, "hand": 0.12},
        "error_by_chunk_pos": [0.10, 0.10, 0.11, 0.10],
        "hand_event_offset_steps": 0.0,
        "out_of_limit_dims": [],
    }
    return base | overrides


def _p4(checkpoint_id: str, parent_checkpoint_id: str, **p3_overrides: Any) -> dict[str, Any]:
    return {
        "probe": "P4",
        "checkpoint_id": checkpoint_id,
        "parent_checkpoint_id": parent_checkpoint_id,
        "p1": {
            "probe": "P1",
            "checkpoint_id": checkpoint_id,
            "dataset_sha256": PROBE_SHA,
            "accuracy_by_question_type": {"where": 0.80},
        },
        "p3": _p3(checkpoint_id, **p3_overrides),
    }


@pytest.fixture
def cfg_with_hash() -> tuple[Any, str]:
    return load_train_thresholds(TRAIN_YAML)


@pytest.fixture
def clean_job(tmp_path: Path) -> JobInputs:
    return load_job(write_job(tmp_path / "job"))


class TestWholeRun:
    def test_a_learning_job_with_every_input_is_clean_and_skips_nothing(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str]
    ) -> None:
        """The control of the whole story: all twelve codes judged, none raised."""
        cfg, _ = cfg_with_hash

        result = diagnose_all(clean_job, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_every_code_of_the_story_is_accounted_for(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str]
    ) -> None:
        assert sorted(TRAIN_CODES + OFFLINE_CODES) == [
            "O1",
            "O2",
            "O3",
            "O4",
            "T1",
            "T2",
            "T3",
            "T4",
            "T5",
            "T6",
            "T7",
            "T8",
        ]

    def test_a_job_without_probes_skips_the_offline_codes_by_name(
        self, tmp_path: Path, cfg_with_hash: tuple[Any, str]
    ) -> None:
        """No probe result is not a clean action head; it is four unmeasured codes."""
        cfg, _ = cfg_with_hash
        job = load_job(write_job(tmp_path / "job", probe_p3=False, probe_p4=False))

        result = diagnose_all(job, cfg)

        assert result.findings == []
        assert {skip.code for skip in result.skipped} == {"O1", "O2", "O3", "O4", "T7"}
        assert all("probe" in skip.reason for skip in result.skipped)

    def test_a_job_without_an_action_layout_skips_the_per_dimension_codes(
        self, tmp_path: Path, cfg_with_hash: tuple[Any, str]
    ) -> None:
        cfg, _ = cfg_with_hash
        job = load_job(write_job(tmp_path / "job", layout=False))

        result = diagnose_all(job, cfg)

        assert {skip.code for skip in result.skipped} == {"T5", "T6", "O4"}
        assert all("action_layout" in skip.reason for skip in result.skipped)

    def test_a_job_whose_parent_probe_is_missing_skips_t7_only(
        self, tmp_path: Path, cfg_with_hash: tuple[Any, str]
    ) -> None:
        cfg, _ = cfg_with_hash
        job = load_job(write_job(tmp_path / "job", probe_p4_parent=False))

        result = diagnose_all(job, cfg)

        assert [skip.code for skip in result.skipped] == ["T7"]

    def test_an_injected_fault_reaches_the_result(
        self, tmp_path: Path, cfg_with_hash: tuple[Any, str]
    ) -> None:
        cfg, _ = cfg_with_hash
        broken = _learning_records() + [record(step=3010, loss="NaN")]
        job = load_job(write_job(tmp_path / "job", records=broken))

        result = diagnose_all(job, cfg)

        assert [finding.code for finding in result.findings] == ["T1"]
        assert result.findings[0].stop_job is True


class TestArtifact:
    def test_the_artifact_carries_the_hash_of_the_config_it_ran_on(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str]
    ) -> None:
        cfg, digest = cfg_with_hash

        artifact = build_artifact(clean_job, diagnose_all(clean_job, cfg), digest)

        assert artifact.config_sha256 == digest
        assert artifact.checkpoint_id == "ckpt-child"

    def test_skipped_codes_are_in_the_artifact_not_dropped(
        self, tmp_path: Path, cfg_with_hash: tuple[Any, str]
    ) -> None:
        """The artifact has to tell a clean checkpoint from an unjudged one."""
        cfg, digest = cfg_with_hash
        job = load_job(write_job(tmp_path / "job", probe_p3=False, probe_p4=False))

        artifact = build_artifact(job, diagnose_all(job, cfg), digest)

        assert {skip.code for skip in artifact.skipped} == {"O1", "O2", "O3", "O4", "T7"}
        assert all(skip.reason for skip in artifact.skipped)

    def test_a_value_that_is_not_finite_becomes_the_string_the_contract_allows(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str]
    ) -> None:
        """`allow_inf_nan=False`, so T1 on a NaN loss has to be encoded, not dropped."""
        _, digest = cfg_with_hash
        result = DetectorResult(
            findings=[
                Finding("T1", 10, None, None, float("nan"), None, stop_job=True),
                Finding("T1", 20, None, None, float("inf"), None, stop_job=True),
                Finding("T1", 30, None, None, float("-inf"), None, stop_job=True),
            ]
        )

        artifact = build_artifact(clean_job, result, digest)

        assert [finding.value for finding in artifact.findings] == ["NaN", "Infinity", "-Infinity"]

    def test_the_artifact_round_trips_through_json(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str]
    ) -> None:
        _, digest = cfg_with_hash
        result = DetectorResult(
            findings=[Finding("O4", 0, "arm", 1, 1.0, 0.0)],
            skipped=[Skipped("T7", "không có P4 của cha")],
        )

        artifact = build_artifact(clean_job, result, digest)
        again = TrainDiagnosis.model_validate_json(artifact.model_dump_json())

        assert again == artifact


class TestStore:
    def test_two_runs_on_one_job_leave_two_records(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str], tmp_path: Path
    ) -> None:
        """The store is append-only: a second diagnosis never overwrites the first."""
        cfg, digest = cfg_with_hash
        store = tmp_path / "store"
        artifact = build_artifact(clean_job, diagnose_all(clean_job, cfg), digest)

        first = write_artifact(artifact, store)
        second = write_artifact(artifact, store)

        assert first == second
        assert len(first.read_text(encoding="utf-8").strip().splitlines()) == 2

    def test_each_line_of_the_store_is_a_valid_record(
        self, clean_job: JobInputs, cfg_with_hash: tuple[Any, str], tmp_path: Path
    ) -> None:
        cfg, digest = cfg_with_hash
        path = write_artifact(
            build_artifact(clean_job, diagnose_all(clean_job, cfg), digest), tmp_path / "store"
        )

        for line in path.read_text(encoding="utf-8").strip().splitlines():
            assert TrainDiagnosis.model_validate_json(line).checkpoint_id == "ckpt-child"


class TestJobInputs:
    def test_a_job_without_metrics_is_an_error_not_a_verdict(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()

        with pytest.raises(ReaderError, match="metrics.jsonl"):
            load_job(tmp_path / "empty")

    def test_a_metrics_file_can_be_named_directly(self, tmp_path: Path) -> None:
        """`--job` takes the log itself as well as the directory holding it."""
        directory = write_job(tmp_path / "job")

        job = load_job(directory / "metrics.jsonl")

        assert job.series.checkpoint_id == "ckpt-child"
        assert job.layout is not None
