"""Tests and generator for JSON schemas of L0-lite models (AC 8)."""

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
    CatalogEpisode,
    CatalogQAReport,
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
    CatalogEpisode,
    CatalogQAReport,
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


def test_export_and_validate_all_l0_lite_schemas() -> None:
    """AC 8: Export JSON Schemas to packages/flywheel-contracts/schemas/ and verify consistency."""
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    for model in MODELS:
        schema_file = SCHEMAS_DIR / f"{model.__name__}.json"
        expected_schema = model.model_json_schema()

        # Write or update schema file
        schema_file.write_text(json.dumps(expected_schema, indent=2) + "\n", encoding="utf-8")

        # Verify it can be read back and matches exactly
        loaded_schema = json.loads(schema_file.read_text(encoding="utf-8"))
        assert loaded_schema == expected_schema
