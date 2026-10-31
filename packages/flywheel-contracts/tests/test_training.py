import json

import pytest
from flywheel.contracts.training import DiagnosisFinding, TrainDiagnosis, TrainingMetric
from pydantic import ValidationError


def metric(**changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "run_plan_id": "rp1", "job_id": "job1", "checkpoint_id": "ckpt1",
        "release_id": "rel1", "attempt": 0, "step": 1, "epoch": 0,
        "split": "train", "loss": 0.5, "lr": 0.001, "vlm_frozen": True,
        "wall_time_s": 1.0,
    }
    result.update(changes)
    return result


def test_jsonl_preserves_train_val_and_nonfinite_loss() -> None:
    lines = [metric(), metric(split="val", loss="NaN", step=2)]
    data = "\n".join(json.dumps(line, allow_nan=False) for line in lines)
    parsed = [TrainingMetric.model_validate_json(line) for line in data.splitlines()]
    assert [line.split for line in parsed] == ["train", "val"]
    assert parsed[1].loss == "NaN"


def test_required_step_and_valid_json_numbers() -> None:
    line = metric()
    del line["step"]
    with pytest.raises(ValidationError):
        TrainingMetric.model_validate(line)
    with pytest.raises(ValidationError):
        TrainingMetric.model_validate(metric(loss=float("nan")))


def test_diagnosis_stop_and_schema() -> None:
    finding = DiagnosisFinding(code="T1", start_step=1, value="NaN", stop_job=True)
    diagnosis = TrainDiagnosis(checkpoint_id="ckpt1", config_sha256="a" * 64, findings=[finding])
    assert TrainDiagnosis.model_validate_json(diagnosis.model_dump_json()) == diagnosis
    with pytest.raises(ValidationError):
        DiagnosisFinding(code="T3", start_step=1, value=1, stop_job=True)
    assert "findings" in TrainDiagnosis.model_json_schema()["properties"]
