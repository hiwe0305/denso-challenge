"""Tray task config and scene geometry (DA-32 AC 2). Pure logic, runs in workspace CI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray import TrayConfig, scene_geometry
from flywheel_simple.tray.geometry import Pose2D, rect_corners


def rect_inside(
    pose: Pose2D, size: tuple[float, float], center: np.ndarray, outer: tuple[float, float]
) -> bool:
    """Corners of a yawed rectangle (size = x, y in its own frame) inside an axis-aligned one."""
    corners = rect_corners(pose, size)
    half = np.asarray(outer) / 2
    return bool(np.all(np.abs(corners - np.asarray(center)[:2]) <= half + 1e-9))


def test_corridor_gap_matches_config() -> None:
    cfg = TrayConfig.load()
    g = scene_geometry(cfg)
    a_edge = g.table_a_center[0] + cfg.table_depth / 2
    b_edge = g.table_b_center[0] - cfg.table_depth / 2
    assert b_edge - a_edge == pytest.approx(1.8)


def test_tray_fully_on_table_a_and_target_on_table_b() -> None:
    cfg = TrayConfig.load()
    g = scene_geometry(cfg)
    table = (cfg.table_depth, cfg.table_length)
    assert rect_inside(g.tray_pose, cfg.tray_footprint, g.table_a_center, table)
    assert rect_inside(g.target_pose, cfg.tray_footprint, g.table_b_center, table)


def test_six_compartments_inside_tray() -> None:
    cfg = TrayConfig.load()
    g = scene_geometry(cfg)
    assert g.compartment_centers.shape == (6, 2)
    assert np.all(np.abs(g.compartment_centers[:, 0]) < cfg.tray_footprint[0] / 2)
    assert np.all(np.abs(g.compartment_centers[:, 1]) < cfg.tray_footprint[1] / 2)


def test_robot_spawn_between_tables_closer_to_a() -> None:
    cfg = TrayConfig.load()
    g = scene_geometry(cfg)
    assert g.table_a_center[0] + cfg.table_depth / 2 < g.robot_spawn.x < 0.0


def test_defaults_follow_design_3_1() -> None:
    cfg = TrayConfig.load()
    assert (cfg.table_length, cfg.table_depth, cfg.table_height) == (1.2, 0.8, 0.85)
    assert (cfg.tray_length, cfg.tray_width, cfg.tray_height) == (0.45, 0.30, 0.06)
    assert cfg.corridor == 1.8 and cfg.part_count == 6


def test_config_rejects_unknown_and_missing_keys(tmp_path: Path) -> None:
    text = TrayConfig.default_path().read_text()
    extra = tmp_path / "extra.yaml"
    extra.write_text(text + "\nnot_a_field: 1\n")
    with pytest.raises(ValueError, match="not_a_field"):
        TrayConfig.load(extra)
    missing = tmp_path / "missing.yaml"
    missing.write_text("\n".join(ln for ln in text.splitlines() if not ln.startswith("corridor")))
    with pytest.raises(ValueError, match="corridor"):
        TrayConfig.load(missing)


def test_config_rejects_nested_yaml(tmp_path: Path) -> None:
    nested = tmp_path / "nested.yaml"
    nested.write_text("table:\n  height: 0.85\n")
    with pytest.raises(ValueError, match="line 1"):
        TrayConfig.load(nested)
