"""Unit tests for configuration YAML models (AC 2)."""

from pathlib import Path

import pytest
import yaml
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.contracts.configs import (
    ConditionFieldSpec,
    ConditionSchemaConfig,
    EmbodimentConfig,
    FailureKindSpecConfig,
    PriceBookConfig,
    PriceRateConfig,
    SplitPlanConfig,
    StageSpecConfig,
    TaskConfig,
)
from pydantic import ValidationError


def test_embodiment_config_and_hash() -> None:
    action_layout = ActionLayout(
        dimensions=[
            ActionDimension(
                name="joint_arm_left_0",
                group="arm_left",
                masked=False,
                limit_low=-1.5,
                limit_high=1.5,
            )
        ]
    )
    cfg = EmbodimentConfig(
        name="g1_sonic_dwbc",
        version="1.0.0",
        domain="sim",
        controller="sonic_dwbc",
        action_layout=action_layout,
    )
    assert cfg.domain == "sim"
    assert cfg.action_layout == action_layout
    assert len(cfg.cfg_hash()) == 64
    assert cfg.cfg_id().startswith("cfg_")
    assert len(cfg.cfg_id()) == 4 + 16


def test_task_config_and_hash() -> None:
    cond_schema = ConditionSchemaConfig(
        version="1.0.0",
        fields=[
            ConditionFieldSpec(name="box_x", type="float", bounds=[-0.2, 0.2]),
            ConditionFieldSpec(name="box_y", type="float", bounds=[-0.1, 0.1]),
        ],
    )
    stages = [
        StageSpecConfig(stage_no=1, name="approach", failure_class="approach"),
        StageSpecConfig(stage_no=2, name="grasp", failure_class="grasp"),
    ]
    failure_kinds = [
        FailureKindSpecConfig(
            code="L-REACH", description="Failed to reach target", failure_class="approach"
        ),
        FailureKindSpecConfig(
            code="L-GRASP", description="Failed to grasp object", failure_class="grasp"
        ),
    ]
    task = TaskConfig(
        task_id="g1_locomotion_pick_between_tables",
        family="pick_place",
        condition_schema=cond_schema,
        stages=stages,
        failure_kinds=failure_kinds,
    )
    assert task.task_id == "g1_locomotion_pick_between_tables"
    assert len(task.stages) == 2
    assert task.cfg_id().startswith("cfg_")


def test_split_plan_config_validates_default_yaml() -> None:
    """Feedback item 3: SplitPlanConfig must validate configs/splits/default.yaml."""
    yaml_path = Path(__file__).resolve().parents[4] / "configs" / "splits" / "default.yaml"
    assert yaml_path.is_file(), f"Expected configs/splits/default.yaml at {yaml_path}"

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cfg = SplitPlanConfig.model_validate(data)
    assert cfg.version == 1
    assert "train" in cfg.seed_ranges
    assert "dev" in cfg.seed_ranges
    assert "holdout" in cfg.seed_ranges
    assert cfg.cfg_id().startswith("cfg_")


def test_pricebook_config() -> None:
    pb = PriceBookConfig(
        name="standard_oct_2026",
        rates=[
            PriceRateConfig(
                resource_type="gpu_hour_a100",
                unit="hour",
                usd_per_unit=3.00,
                is_assumption=True,
                note="Colab / rented cloud rate",
            ),
            PriceRateConfig(
                resource_type="operator_hour",
                unit="hour",
                usd_per_unit=25.00,
                human_hours_per_unit=1.0,
                is_assumption=True,
                note="Teleop engineer hour",
            ),
        ],
    )
    assert len(pb.rates) == 2
    assert pb.cfg_id().startswith("cfg_")


def test_config_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        EmbodimentConfig(
            name="robot",
            unsupported_field="invalid",  # type: ignore[call-arg]
        )
