"""Tests for JSON schemas of L0-lite models (AC 8)."""

import json
from pathlib import Path

import pytest
from flywheel.contracts.configs import (
    EmbodimentConfig,
    PriceBookConfig,
    SplitPlanConfig,
    TaskConfig,
)
from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Condition,
    Decision,
    FixRateEvent,
    LedgerEntry,
    Release,
    RunPlan,
    Score,
    Source,
)

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"

MODELS = [
    Source,
    Condition,
    Release,
    Checkpoint,
    RunPlan,
    Score,
    Cluster,
    FixRateEvent,
    LedgerEntry,
    Decision,
    EmbodimentConfig,
    TaskConfig,
    SplitPlanConfig,
    PriceBookConfig,
]


@pytest.mark.parametrize("model", MODELS)
def test_schema_matches_committed_json(model: type) -> None:
    """Feedback item 7: Verify committed schema files match models without overwriting."""
    schema_file = SCHEMAS_DIR / f"{model.__name__}.json"
    assert schema_file.is_file(), f"Missing schema file: {schema_file}"

    loaded_schema = json.loads(schema_file.read_text(encoding="utf-8"))
    expected_schema = model.model_json_schema()
    assert loaded_schema == expected_schema
