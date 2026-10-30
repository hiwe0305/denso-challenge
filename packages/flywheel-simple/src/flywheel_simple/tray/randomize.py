"""Episode randomisation in three levels and the disjoint seed ranges (design 3.5).

Level 0 keeps the default scene. Level 1 moves and turns the tray on table A and
the target zone on table B. Level 2 adds the corridor width, the robot's spawn
distance, the part mass and the light. The robot's spawn yaw is not
randomised: the elastic band that holds G1 at the start pulls it back to yaw 0
before release (docs/g0/tray/decisions.md D-05).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D, rect_corners, scene_geometry_with_gap

Split = Literal["train", "dev", "holdout"]
SEED_RANGES: dict[Split, range] = {
    "train": range(0, 1_000_000),
    "dev": range(1_000_000, 1_001_000),
    "holdout": range(2_000_000, 2_001_000),
}
POSE_JITTER = 0.05  # m, tray and target, levels 1-2
YAW_JITTER = math.radians(10.0)
GAP_RANGE = (1.6, 2.0)  # m, level 2
SPAWN_JITTER = 0.10  # m along x, level 2
PART_MASS_RANGE = (0.03, 0.08)  # kg, level 2
LIGHT_RANGE = (0.8, 1.2)  # level 2
MAX_TRIES = 100


@dataclass(frozen=True)
class EpisodeSample:
    level: int
    seed: int
    tray_pose: Pose2D
    target_pose: Pose2D
    robot_spawn: Pose2D
    table_gap: float
    part_mass: float
    light_scale: float


def split_of(seed: int) -> Split:
    for name, seeds in SEED_RANGES.items():
        if seed in seeds:
            return name
    raise ValueError(f"seed {seed} is outside the train, dev and holdout ranges")


def _on_table(cfg: TrayConfig, pose: Pose2D, table_center: NDArray[np.float64]) -> bool:
    half = np.array([cfg.table_depth, cfg.table_length]) / 2
    return bool(np.all(np.abs(rect_corners(pose, cfg.tray_footprint) - table_center) <= half))


def _jitter(rng: np.random.Generator, pose: Pose2D) -> Pose2D:
    dx, dy = rng.uniform(-POSE_JITTER, POSE_JITTER, size=2)
    return Pose2D(pose.x + dx, pose.y + dy, pose.yaw + rng.uniform(-YAW_JITTER, YAW_JITTER))


def _placed(
    cfg: TrayConfig, rng: np.random.Generator, pose: Pose2D, table_center: NDArray[np.float64]
) -> Pose2D:
    """Jitter `pose`, resampling until the tray footprint lies fully on the table."""
    for _ in range(MAX_TRIES):
        candidate = _jitter(rng, pose)
        if _on_table(cfg, candidate, table_center):
            return candidate
    raise RuntimeError(f"no on-table pose in {MAX_TRIES} tries around {pose}")


def sample_episode(cfg: TrayConfig, level: int, seed: int) -> EpisodeSample:
    """Deterministic episode conditions for (level, seed)."""
    if level not in (0, 1, 2):
        raise ValueError(f"level must be 0, 1 or 2, got {level}")
    rng = np.random.default_rng(seed)
    gap = float(rng.uniform(*GAP_RANGE)) if level == 2 else cfg.corridor
    geo = scene_geometry_with_gap(cfg, gap)
    sample = EpisodeSample(
        level=level,
        seed=seed,
        tray_pose=geo.tray_pose,
        target_pose=geo.target_pose,
        robot_spawn=geo.robot_spawn,
        table_gap=gap,
        part_mass=cfg.part_mass,
        light_scale=1.0,
    )
    if level == 0:
        return sample
    sample = replace(
        sample,
        tray_pose=_placed(cfg, rng, geo.tray_pose, geo.table_a_center),
        target_pose=_placed(cfg, rng, geo.target_pose, geo.table_b_center),
    )
    if level == 1:
        return sample
    spawn = geo.robot_spawn
    return replace(
        sample,
        robot_spawn=Pose2D(spawn.x + rng.uniform(-SPAWN_JITTER, SPAWN_JITTER), spawn.y, 0.0),
        part_mass=float(rng.uniform(*PART_MASS_RANGE)),
        light_scale=float(rng.uniform(*LIGHT_RANGE)),
    )
