import json
from pathlib import Path

from flywheel.contracts.training import TrainDiagnosis, TrainingMetric

FIXTURES = Path(__file__).parents[2] / "flywheel-testkit/src/flywheel/testkit/fixtures/training"


def test_shared_examples_validate() -> None:
    for path in FIXTURES.glob("*.jsonl"):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines
        for line in lines:
            TrainingMetric.model_validate_json(line)
    TrainDiagnosis.model_validate_json((FIXTURES / "diagnosis.json").read_text(encoding="utf-8"))


def test_exported_schemas_match_models() -> None:
    schemas = Path(__file__).parents[1] / "schemas"
    for model in (TrainingMetric, TrainDiagnosis):
        saved = json.loads((schemas / f"{model.__name__}.json").read_text(encoding="utf-8"))
        assert saved == model.model_json_schema()

