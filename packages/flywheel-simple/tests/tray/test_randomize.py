"""Three randomisation levels and disjoint seed ranges (DA-32 AC 5). Pure logic, workspace CI."""

from __future__ import annotations

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig, scene_geometry
from flywheel_simple.tray.geometry import Pose2D, rect_corners, scene_geometry_with_gap
from flywheel_simple.tray.randomize import SEED_RANGES, sample_episode, split_of


def rect_inside(
    pose: Pose2D, size: tuple[float, float], center: np.ndarray, outer: tuple[float, float]
) -> bool:
    half = np.asarray(outer) / 2
    return bool(np.all(np.abs(rect_corners(pose, size) - np.asarray(center)) <= half + 1e-9))


def test_same_seed_same_sample() -> None:
    cfg = TrayConfig.load()
    assert sample_episode(cfg, 2, 7) == sample_episode(cfg, 2, 7)


def test_different_seeds_differ_at_level_1() -> None:
    cfg = TrayConfig.load()
    assert sample_episode(cfg, 1, 7).tray_pose != sample_episode(cfg, 1, 8).tray_pose


def test_level0_is_default_geometry() -> None:
    cfg = TrayConfig.load()
    s = sample_episode(cfg, 0, 123)
    g = scene_geometry(cfg)
    assert s.tray_pose == g.tray_pose and s.target_pose == g.target_pose
    assert s.table_gap == cfg.corridor and s.part_mass == cfg.part_mass and s.light_scale == 1.0


def test_level1_keeps_level2_parameters_at_defaults() -> None:
    cfg = TrayConfig.load()
    for seed in range(50):
        s = sample_episode(cfg, 1, seed)
        assert s.table_gap == cfg.corridor and s.part_mass == cfg.part_mass
        assert s.robot_spawn == scene_geometry(cfg).robot_spawn
        assert abs(s.tray_pose.yaw) <= np.deg2rad(10) + 1e-12


@pytest.mark.parametrize("seed", range(500))
def test_level2_tray_and_target_stay_on_tables(seed: int) -> None:
    cfg = TrayConfig.load()
    s = sample_episode(cfg, 2, seed)
    g = scene_geometry_with_gap(cfg, s.table_gap)
    table = (cfg.table_depth, cfg.table_length)
    assert rect_inside(s.tray_pose, cfg.tray_footprint, g.table_a_center, table)
    assert rect_inside(s.target_pose, cfg.tray_footprint, g.table_b_center, table)


@pytest.mark.parametrize("seed", range(500))
def test_level2_robot_spawn_clears_table_a(seed: int) -> None:
    cfg = TrayConfig.load()
    s = sample_episode(cfg, 2, seed)
    g = scene_geometry_with_gap(cfg, s.table_gap)
    assert g.table_a_center[0] - cfg.table_depth / 2 - s.robot_spawn.x >= 0.25
    assert s.robot_spawn.yaw == 0.0  # the elastic band holds yaw 0 until release


def test_level2_ranges() -> None:
    cfg = TrayConfig.load()
    samples = [sample_episode(cfg, 2, seed) for seed in range(300)]
    gaps = [s.table_gap for s in samples]
    masses = [s.part_mass for s in samples]
    lights = [s.light_scale for s in samples]
    assert 1.6 <= min(gaps) and max(gaps) <= 2.0 and max(gaps) - min(gaps) > 0.3
    assert 0.03 <= min(masses) and max(masses) <= 0.08
    assert 0.8 <= min(lights) and max(lights) <= 1.2


def test_unknown_level_rejected() -> None:
    with pytest.raises(ValueError):
        sample_episode(TrayConfig.load(), 3, 0)


def test_seed_ranges_disjoint_and_split_of() -> None:
    r = SEED_RANGES
    assert not set(r["train"]) & set(r["dev"]) and not set(r["dev"]) & set(r["holdout"])
    assert split_of(5) == "train"
    assert split_of(1_000_005) == "dev"
    assert split_of(2_000_000) == "holdout"
    with pytest.raises(ValueError):
        split_of(1_500_000)
