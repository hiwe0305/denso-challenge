import json
from pathlib import Path

import pytest
from flywheel.contracts.diagnosis import StageAttribution, SystemDiagnosis
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "packages/flywheel-contracts/schemas"
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"


@pytest.mark.parametrize("model", [SystemDiagnosis, StageAttribution])
def test_examples_and_schemas(model: type) -> None:
    assert json.loads((SCHEMAS / f"{model.__name__}.json").read_text(encoding="utf-8")) == (
        model.model_json_schema()
    )
    example = (FIXTURES / f"{model.__name__}.json").read_text(encoding="utf-8")
    value = model.model_validate_json(example)
    assert model.model_validate_json(value.model_dump_json()) == value


def test_system_requires_skips_and_never_marks_incomplete_check_clean() -> None:
    base = {
        "episode_id": "ep",
        "diagnosis": "clean",
        "config_sha256": "a" * 64,
        "trace_sha256": "b" * 64,
        "findings": [],
    }
    with pytest.raises(ValidationError):
        SystemDiagnosis.model_validate(base)
    with pytest.raises(ValidationError):
        SystemDiagnosis.model_validate({**base, "skipped": [{"code": "R5", "reason": "missing"}]})
    unknown = SystemDiagnosis.model_validate(
        {**base, "diagnosis": "unknown", "skipped": [{"code": "R5", "reason": "missing"}]}
    )
    assert unknown.skipped[0].code == "R5"


@pytest.mark.parametrize("code", ["R0", "T1", "R7"])
def test_system_rejects_non_system_codes(code: str) -> None:
    with pytest.raises(ValidationError):
        SystemDiagnosis.model_validate(
            {
                "episode_id": "ep",
                "diagnosis": "runtime",
                "config_sha256": "a" * 64,
                "trace_sha256": "b" * 64,
                "findings": [{"code": code, "value": 1}],
                "skipped": [],
            }
        )


def test_attribution_requires_unavailable_and_keeps_hypothesis_unconfirmed() -> None:
    base = {
        "episode_id": "ep",
        "table_sha256": "a" * 64,
        "hypotheses": [
            {
                "row_id": "r1",
                "attribute_to": "stage1",
                "intervention": "collect",
                "consumes_budget": False,
            }
        ],
    }
    with pytest.raises(ValidationError):
        StageAttribution.model_validate(base)
    attribution = StageAttribution.model_validate({**base, "unavailable": []})
    assert attribution.hypotheses[0].confirmed is False
