"""Scene geometry of the tray task, computed from TrayConfig (design 3.1).

World frame: x along the corridor, table A at positive x, table B at negative x,
z up, floor at z = 0. The robot spawns between them facing +x (yaw 0): the
elastic band that holds G1 at the start pulls its pelvis towards the identity
orientation, so any other spawn yaw makes it spin. SIMPLE's two-table task uses
the same layout. The tray's long side is along its own y axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from flywheel_simple.tray.config import TrayConfig


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class SceneGeometry:
    table_a_center: np.ndarray  # (2,) xy
    table_b_center: np.ndarray  # (2,) xy
    table_top_z: float
    tray_pose: Pose2D
    target_pose: Pose2D
    compartment_centers: np.ndarray  # (6, 2) in the tray frame
    robot_spawn: Pose2D


def rect_corners(pose: Pose2D, size: tuple[float, float]) -> np.ndarray:
    """World xy of the four corners of a rectangle of `size` (x, y in its frame) at `pose`."""
    hx, hy = size[0] / 2, size[1] / 2
    local = np.array([[hx, hy], [hx, -hy], [-hx, -hy], [-hx, hy]])
    c, s = math.cos(pose.yaw), math.sin(pose.yaw)
    rot = np.array([[c, -s], [s, c]])
    return np.asarray(local @ rot.T + np.array([pose.x, pose.y]))


def scene_geometry(cfg: TrayConfig) -> SceneGeometry:
    return scene_geometry_with_gap(cfg, cfg.corridor)


def scene_geometry_with_gap(cfg: TrayConfig, corridor: float) -> SceneGeometry:
    """Scene geometry with the corridor between the tables replaced by `corridor`."""
    table_x = corridor / 2 + cfg.table_depth / 2
    tray_x = corridor / 2 + cfg.tray_edge_offset
    rows, cols = 3, 2  # along the long side (y) x across (x)
    if rows * cols != cfg.part_count:
        raise ValueError(f"part_count {cfg.part_count} does not fill a {rows} x {cols} grid")
    ys = (np.arange(rows) - (rows - 1) / 2) * cfg.tray_length / rows
    xs = (np.arange(cols) - (cols - 1) / 2) * cfg.tray_width / cols
    compartments = np.array([[x, y] for y in ys for x in xs])
    return SceneGeometry(
        table_a_center=np.array([table_x, 0.0]),
        table_b_center=np.array([-table_x, 0.0]),
        table_top_z=cfg.table_height,
        tray_pose=Pose2D(tray_x, 0.0, 0.0),
        target_pose=Pose2D(-tray_x, 0.0, 0.0),
        compartment_centers=compartments,
        robot_spawn=Pose2D(cfg.robot_spawn_x, 0.0, 0.0),
    )
