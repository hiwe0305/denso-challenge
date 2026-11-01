"""Thresholds are read from the config file, never defaulted in code (DA-08 task 5)."""

from __future__ import annotations

import typing
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.config import (
    ConfigError,
    TrainThresholds,
    config_sha256,
    load_train_thresholds,
)

TRAIN_YAML = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis" / "train.yaml"


def complete() -> dict[str, Any]:
    """A mapping with every section and key the detectors ask for."""
    return {
        "t1": {"k": 10.0, "window_steps": 500},
        "t2": {"n_steps": 2000, "min_relative_drop": 0.05, "baseline_val_count": 3},
        "t3": {"m_measurements": 3},
        "t4": {"window_steps": 2000, "min_group_drop": 0.05, "ref_group_drop": 0.30},
        "t5": {"window_steps": 1000, "epsilon": 1.0e-6},
        "t6": {"min_std_ratio": 0.30},
        "t7": {"max_relative_drop": 0.10},
        "t8": {"frozen_tolerance": 0.0, "max_grad_norm": 10.0, "max_exceedances": 5},
        "o1": {"max_error_by_group": {}, "max_error_ratio": 2.0},
        "o2": {"max_slope": 0.05, "max_ratio": 3.0},
        "o3": {"max_offset_steps": 5},
        "o4": {"max_fraction": 0.0},
    }


def test_a_complete_mapping_loads() -> None:
    cfg = TrainThresholds.from_mapping(complete())
    assert cfg.t1.k == pytest.approx(10.0) and cfg.t1.window_steps == 500
    assert cfg.o1.max_error_by_group == {}


def test_a_missing_key_is_an_error_not_a_default() -> None:
    data = complete()
    del data["t1"]["k"]
    with pytest.raises(ConfigError, match="t1.k"):
        TrainThresholds.from_mapping(data)


def test_a_missing_section_is_an_error() -> None:
    data = complete()
    del data["o4"]
    with pytest.raises(ConfigError, match="o4"):
        TrainThresholds.from_mapping(data)


def test_a_misspelled_threshold_does_not_pass_unnoticed() -> None:
    # a key nobody reads means the number the author wrote is not the number in use
    data = complete()
    data["t6"]["min_std_ration"] = 0.30
    with pytest.raises(ConfigError, match="min_std_ration"):
        TrainThresholds.from_mapping(data)


def test_a_threshold_that_is_not_a_number_is_an_error() -> None:
    data = complete()
    data["t1"]["k"] = "ten"
    with pytest.raises(ConfigError, match="t1.k"):
        TrainThresholds.from_mapping(data)
    data = complete()
    data["t1"]["window_steps"] = 500.5
    with pytest.raises(ConfigError, match="t1.window_steps"):
        TrainThresholds.from_mapping(data)


def test_a_group_budget_must_map_names_to_numbers() -> None:
    data = complete()
    data["o1"]["max_error_by_group"] = {"hand": "low"}
    with pytest.raises(ConfigError, match="max_error_by_group"):
        TrainThresholds.from_mapping(data)


def test_the_hash_is_stable_across_reads(tmp_path: Path) -> None:
    path = tmp_path / "train.yaml"
    path.write_text("t1:\n  k: 10.0\n", encoding="utf-8")
    assert config_sha256(path) == config_sha256(path)
    assert len(config_sha256(path)) == 64


def test_the_hash_changes_with_the_content(tmp_path: Path) -> None:
    # the artifact records this hash, so two runs with different thresholds can
    # never look like the same run (AC 4)
    first, second = tmp_path / "a.yaml", tmp_path / "b.yaml"
    first.write_text("t1:\n  k: 10.0\n", encoding="utf-8")
    second.write_text("t1:\n  k: 12.0\n", encoding="utf-8")
    assert config_sha256(first) != config_sha256(second)


def test_the_shipped_yaml_loads_with_the_hash_of_the_bytes_it_was_read_from() -> None:
    cfg, digest = load_train_thresholds(TRAIN_YAML)
    assert cfg.t1.window_steps == 500 and cfg.o4.max_fraction == pytest.approx(0.0)
    assert digest == config_sha256(TRAIN_YAML)


def test_a_file_that_is_not_a_mapping_of_sections_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "train.yaml"
    path.write_text("- t1\n- t2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_train_thresholds(path)


def test_every_threshold_the_detectors_read_has_a_key_in_the_shipped_yaml() -> None:
    sections = yaml.safe_load(TRAIN_YAML.read_text(encoding="utf-8"))
    for name, section_type in typing.get_type_hints(TrainThresholds).items():
        assert name in sections, f"configs/eval/diagnosis/train.yaml has no section `{name}`"
        assert set(sections[name]) == set(section_type.__dataclass_fields__)


def test_the_shipped_yaml_marks_every_uncalibrated_number() -> None:
    # AC 3: a number that has not been measured yet must say so where it is written
    for line in TRAIN_YAML.read_text(encoding="utf-8").splitlines():
        body, _, comment = line.partition("#")
        if body.strip().endswith(":") or not body.strip():
            continue  # a section header or a comment line carries no value
        assert "giả định" in comment or "chốt" in comment, f"no source on: {line}"
