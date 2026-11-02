"""Episode meta and per-frame tray fields of the recorder; no simulator (DA-33 Task 5)."""

from __future__ import annotations

from dataclasses import asdict, replace

import numpy as np
import pytest
from flywheel_simple.tray.planner import PlannerConfig
from flywheel_simple.tray.predicates import STEP_NAMES
from flywheel_simple.tray.recorder import (
    TRAY_FEATURES,
    FlywheelMeta,
    planner_version,
    tray_frame,
    visuals_revision,
)


def test_meta_marks_synthetic_s1_planned_public_train() -> None:
    meta = asdict(FlywheelMeta(seed=7, level=1, planner_version="p", visuals_revision="none"))
    assert meta["source_kind"] == "synthetic" and meta["source_detail"] == "planner_wbc"
    assert meta["synthetic_tier"] == "S1" and meta["action_quality"] == "planned"
    assert meta["data_class"] == "public" and meta["split"] == "train"
    assert meta["embodiment_id"] == "g1_sonic_dwbc@1" and meta["renderer"] == "mujoco"
    assert (meta["seed"], meta["level"]) == (7, 1)


@pytest.mark.parametrize("seed", [1_000_000, 2_000_000])
def test_meta_refuses_dev_and_holdout_seeds(seed: int) -> None:
    with pytest.raises(ValueError, match="train"):
        FlywheelMeta(seed=seed, level=1, planner_version="p", visuals_revision="none")


def test_planner_version_follows_the_config_values() -> None:
    cfg = PlannerConfig.load()
    assert planner_version(cfg) == planner_version(PlannerConfig.load())
    assert planner_version(cfg) != planner_version(replace(cfg, lift_height=cfg.lift_height + 0.01))


def test_visuals_revision_reads_the_manifest_or_says_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert visuals_revision(None) == "none"
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"revision": "abc123", "assets": []}')
    assert visuals_revision(manifest) == "abc123"


def test_tray_frame_matches_the_declared_features() -> None:
    privileged = {
        "tray_pos": np.array([1.0, 0.0, 0.8]),
        "tray_quat": np.array([1.0, 0.0, 0.0, 0.0]),
        "part_pos": np.zeros((6, 3)),
    }
    frame = tray_frame(privileged, None)
    assert set(frame) == set(TRAY_FEATURES)
    for key, spec in TRAY_FEATURES.items():
        assert frame[key].shape == tuple(spec["shape"]) and frame[key].dtype == np.float64
        assert len(spec["names"]) == spec["shape"][0]
    assert not frame["observation.tray_steps"].any()
    assert len(STEP_NAMES) == TRAY_FEATURES["observation.tray_steps"]["shape"][0]
