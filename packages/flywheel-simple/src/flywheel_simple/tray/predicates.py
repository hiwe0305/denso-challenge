"""Seven scorer steps, the success check and failure labels of the tray task (design 3.2-3.4).

Pure logic over TrayState snapshots; the SIMPLE task extracts them from MuJoCo.
Steps are reached in order and stay reached. Success is design 3.4 held without
a break for `t_stable`, and stays once reached. The first failure seen is the
episode's label and is final; there is no success after it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import scene_geometry_with_gap
from flywheel_simple.tray.randomize import EpisodeSample

Failure = Literal[
    "L-PART-DROP", "L-TRAY-TILT", "L-ONE-HAND", "L-PLACE-POSE", "L-TIMEOUT", "L-BALANCE"
]
STEP_NAMES = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")
PART_Z_MARGIN = (0.01, 0.03)  # below the tray floor, above the rim: still "in the tray"


@dataclass(frozen=True)
class TrayState:
    t: float
    tray_pos: NDArray[np.float64]  # (3,) tray underside centre, world
    tray_quat: NDArray[np.float64]  # (4,) wxyz
    part_pos: NDArray[np.float64]  # (6, 3) world
    hand_contacts: tuple[bool, bool]  # left, right handle
    tray_on_table: Literal["A", "B", "none"]
    base_xy: NDArray[np.float64]  # (2,)
    pelvis_height: float
    left_palm: NDArray[np.float64]  # (3,)
    right_palm: NDArray[np.float64]  # (3,)


@dataclass(frozen=True)
class StepReport:
    steps: tuple[bool, ...]  # 7 entries, STEP_NAMES order
    success: bool
    failure: Failure | None


def yaw_error(a: float, b: float) -> float:
    """Absolute angle between two yaws, wrapped to [0, pi]."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def quat_to_mat(q: NDArray[np.float64]) -> NDArray[np.float64]:
    w, x, y, z = (float(v) for v in q / np.linalg.norm(q))
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


@dataclass
class StepTracker:
    """Feed one TrayState per control step; one tracker per episode (or reset())."""

    cfg: TrayConfig
    sample: EpisodeSample
    _steps: list[bool] = field(default_factory=lambda: [False] * 7)
    _success: bool = False
    _failure: Failure | None = None
    _prev: TrayState | None = None
    _stable_since: float | None = None
    _misplaced_since: float | None = None
    _one_hand_since: float | None = None

    def __post_init__(self) -> None:
        geo = scene_geometry_with_gap(self.cfg, self.sample.table_gap)
        self._edge_a = float(geo.table_a_center[0]) - self.cfg.table_depth / 2
        self._edge_b = float(geo.table_b_center[0]) + self.cfg.table_depth / 2

    def reset(self) -> None:
        self._steps = [False] * 7
        self._success, self._failure, self._prev = False, None, None
        self._stable_since = self._misplaced_since = self._one_hand_since = None

    def update(self, s: TrayState) -> StepReport:
        rot = quat_to_mat(s.tray_quat)
        still = self._speed(s) < self.cfg.still_speed
        parts_ok = self._parts_in_tray(s, rot)
        both = all(s.hand_contacts)
        released = not any(s.hand_contacts)
        standing = s.pelvis_height >= self.cfg.fall_height
        in_target = self._in_target(s, rot)
        settled = s.tray_on_table == "B" and released and still

        self._stable_since = self._since(
            self._stable_since, s.t, settled and in_target and standing and parts_ok
        )
        self._misplaced_since = self._since(self._misplaced_since, s.t, settled and not in_target)
        if self._failure is None and not self._success:
            self._success = self._held(self._stable_since, s.t)
        if self._failure is None and not self._success:
            self._failure = self._first_failure(s, rot, parts_ok, both, standing)

        lifted = s.tray_pos[2] - self.cfg.table_height > self.cfg.h_lift
        reached = (
            self._in_front(s, self._edge_a, -1.0) and self._palms_on_handles(s, rot),
            both,
            lifted and s.tray_on_table == "none" and parts_ok,
            both
            and self._edge_a - s.base_xy[0] > self.cfg.approach_zone
            and self._tilt(rot) < math.radians(self.cfg.tilt_max_deg)
            and standing,
            both and self._in_front(s, self._edge_b, 1.0),
            s.tray_on_table == "B" and in_target,
            self._success,
        )
        for k, now in enumerate(reached):
            if now and (k == 0 or self._steps[k - 1]):
                self._steps[k] = True
        self._prev = s
        return StepReport(tuple(self._steps), self._success, self._failure)

    def _first_failure(
        self, s: TrayState, rot: NDArray[np.float64], parts_ok: bool, both: bool, standing: bool
    ) -> Failure | None:
        carrying = self._steps[2] and s.tray_on_table == "none"
        self._one_hand_since = self._since(self._one_hand_since, s.t, carrying and not both)
        if not standing:
            return "L-BALANCE"
        if carrying and self._tilt(rot) > math.radians(self.cfg.tilt_max_deg):
            return "L-TRAY-TILT"
        if not parts_ok:
            return "L-PART-DROP"
        if self._one_hand_since is not None and s.t - self._one_hand_since > self.cfg.contact_grace:
            return "L-ONE-HAND"
        if self._held(self._misplaced_since, s.t):
            return "L-PLACE-POSE"
        if s.t >= self.cfg.episode_limit_s:
            return "L-TIMEOUT"
        return None

    def _since(self, since: float | None, t: float, holds: bool) -> float | None:
        if not holds:
            return None
        return t if since is None else since

    def _held(self, since: float | None, t: float) -> bool:
        return since is not None and t - since >= self.cfg.t_stable - 1e-9

    def _speed(self, s: TrayState) -> float:
        if self._prev is None or s.t <= self._prev.t:
            return 0.0
        return float(np.linalg.norm(s.tray_pos - self._prev.tray_pos) / (s.t - self._prev.t))

    def _tilt(self, rot: NDArray[np.float64]) -> float:
        return math.acos(max(-1.0, min(1.0, float(rot[2, 2]))))

    def _parts_in_tray(self, s: TrayState, rot: NDArray[np.float64]) -> bool:
        if rot[2, 2] <= 0.0:  # upside down: parts in the cavity are under it, not in it
            return False
        local = (s.part_pos - s.tray_pos) @ rot  # world -> tray frame
        half = np.array(self.cfg.tray_footprint) / 2
        inside = np.all(np.abs(local[:, :2]) <= half, axis=1)
        low, high = -PART_Z_MARGIN[0], self.cfg.tray_height + PART_Z_MARGIN[1]
        return bool(np.all(inside & (local[:, 2] >= low) & (local[:, 2] <= high)))

    def _in_target(self, s: TrayState, rot: NDArray[np.float64]) -> bool:
        target = self.sample.target_pose
        dist = math.hypot(s.tray_pos[0] - target.x, s.tray_pos[1] - target.y)
        yaw = math.atan2(rot[1, 0], rot[0, 0])
        return dist <= self.cfg.target_pos_tol and yaw_error(yaw, target.yaw) <= math.radians(
            self.cfg.target_yaw_tol_deg
        )

    def _in_front(self, s: TrayState, edge_x: float, side: float) -> bool:
        """Base on the corridor side of a table edge (side -1: below edge_x, +1: above)."""
        gap = side * (float(s.base_xy[0]) - edge_x)
        across = abs(float(s.base_xy[1]))
        return 0.0 <= gap <= self.cfg.approach_zone and across <= self.cfg.table_length / 2

    def _palms_on_handles(self, s: TrayState, rot: NDArray[np.float64]) -> bool:
        y = self.cfg.tray_length / 2 + self.cfg.handle_depth / 2
        z = self.cfg.tray_height - self.cfg.handle_thickness / 2
        left = s.tray_pos + rot @ np.array([0.0, y, z])
        right = s.tray_pos + rot @ np.array([0.0, -y, z])
        r = self.cfg.r_reach
        return bool(
            np.linalg.norm(s.left_palm - left) <= r and np.linalg.norm(s.right_palm - right) <= r
        )
