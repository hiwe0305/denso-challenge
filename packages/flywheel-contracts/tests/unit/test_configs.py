"""Unit tests for configuration YAML models (AC 2)."""

import pytest
from pydantic import ValidationError

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


def test_embodiment_config_and_hash() -> None:
    cfg = EmbodimentConfig(
        name="g1_sonic_dwbc",
        version="1.0.0",
        domain="sim",
        controller="sonic_dwbc",
    )
    assert cfg.domain == "sim"
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
        FailureKindSpecConfig(code="L-REACH", description="Failed to reach target", failure_class="approach"),
        FailureKindSpecConfig(code="L-GRASP", description="Failed to grasp object", failure_class="grasp"),
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


def test_split_plan_config() -> None:
    split = SplitPlanConfig(
        name="g1_two_table_v1",
        seed_ranges={"train": [0, 1000], "dev": [1000, 1200]},
        author_ranges_to_avoid=[[2000, 2100]],
        near_duplicate_threshold_d_dup=0.05,
    )
    assert split.near_duplicate_threshold_d_dup == 0.05
    assert split.cfg_id().startswith("cfg_")


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
            unsupported_field="invalid",
        )
