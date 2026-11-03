"""Settings of the S2 generator, read from configs/sim/tray_s2.yaml (DA-35 tasks 8-12)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flywheel_simple.tray.config import find_config, load_flat_config
from flywheel_simple.tray.s2.parents import ParentDemo
from flywheel_simple.tray.s2.segments import Segmentation, segment

S2_CONFIG_RELPATH = Path("configs/sim/tray_s2.yaml")


@dataclass(frozen=True)
class S2Config:
    hold_s: float
    walk_min_s: float
    reach_radius: float
    grasp_hold_s: float
    stitch_min_s: float
    stitch_max_s: float
    gate_pos_tol: float
    gate_yaw_tol_deg: float
    gate_hold_s: float
    settle_speed: float
    place_fix_max_m: float
    place_fix_max_deg: float
    gate_max_s: float
    nav_gain: float
    walk_ff_min: float
    step_speed_min: float
    step_speed_max: float
    step_stop: float
    level1_share: float
    cond_seed_min: int
    cond_seed_max: int

    @staticmethod
    def default_path() -> Path:
        return find_config(S2_CONFIG_RELPATH)

    @classmethod
    def load(cls, path: Path | None = None) -> S2Config:
        return load_flat_config(cls, path or cls.default_path())


def segment_with(demo: ParentDemo, cfg: S2Config) -> Segmentation:
    """`segment` with the cut settings of `cfg`."""
    return segment(
        demo,
        hold_s=cfg.hold_s,
        walk_min_s=cfg.walk_min_s,
        reach_radius=cfg.reach_radius,
        grasp_hold_s=cfg.grasp_hold_s,
    )
