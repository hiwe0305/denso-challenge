"""Scripted two-hand planner for the tray task: one phase machine over TrayState (DA-33).

Each step turns the scene state into base velocities, a heading, two wrist poses
and hand closures for StandWalkController. Phases follow the seven scorer steps
of DA-32:

| Phase | Command | Leaves when | Scorer step |
|---|---|---|---|
| APPROACH_A | palms to the ready pose, then walk +x | base within `standoff` of A's edge | 1 |
| REACH | palms to pre-grasp, outside each handle | both palms within `palm_tol` | 1 |
| GRASP | palms onto the handles, then close | both handle contacts for `grasp_hold` | 2 |
| LIFT | palms up `lift_height` | step 3 reached, palms there | 3 |
| BACK_OFF | walk back `backoff` | distance reached | 4 |
| TURN | turn to the heading that lines the tray up with the target | within `turn_tol_deg` | 4 |
| CARRY | walk to the base pose that puts the tray on the target | within `carry_tol` | 4-5 |
| ARRIVE_B | stand, hold the heading | base slower than `arrive_speed` for `arrive_hold` | 5 |
| LOWER | palms down at `lower_speed` | tray on table B | 6 |
| RELEASE | open, palms out by `pregrasp_offset` | no handle contact for `release_hold` | 7 |
| RETREAT | walk back `retreat` | distance reached | 7 |

Every phase has a timeout; a timeout, a StepTracker failure label or a tray on
the floor ends in ABORT. Wrist poses are 4 x 4 in the base frame of
`flywheel_simple.wbc.upper_body` (pelvis xy and yaw, origin at pelvis height).
They stay fixed from the end of LIFT until LOWER, so the tray keeps its pose
relative to the body while walking and turning. SIMPLE's arm PD sags under
gravity, so while reaching, grasping and lifting the planner adds a correction
from the measured palm error, integrated only once the palm is near its target
and not while the hands close on the handles.

Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import TrayConfig, find_config, load_flat_config
from flywheel_simple.tray.geometry import Pose2D, scene_geometry_with_gap
from flywheel_simple.tray.predicates import StepReport, TrayState, yaw_error
from flywheel_simple.tray.randomize import EpisodeSample

PLANNER_CONFIG_RELPATH = Path("configs/sim/tray_planner.yaml")
MIRROR = np.diag([1.0, -1.0, 1.0])  # left <-> right across the xz plane
CORRECTED = ("REACH", "GRASP", "LIFT")


class Phase(Enum):
    APPROACH_A = 1
    REACH = 2
    GRASP = 3
    LIFT = 4
    BACK_OFF = 5
    TURN = 6
    CARRY = 7
    ARRIVE_B = 8
    LOWER = 9
    RELEASE = 10
    RETREAT = 11
    DONE = 12
    ABORT = 13


@dataclass(frozen=True)
class PlannerConfig:
    palm_offset_x: float
    palm_offset_y: float
    palm_offset_z: float
    grasp_roll_deg: float
    grasp_pitch_deg: float
    grasp_yaw_deg: float
    grasp_dz: float
    ready_x: float
    ready_y: float
    ready_z: float
    ready_clear: float
    standoff: float
    vx_approach: float
    pregrasp_offset: float
    palm_tol: float
    grasp_hold: float
    palm_correction_gain: float
    palm_correction_max: float
    palm_correction_window: float
    lift_height: float
    backoff: float
    vx_backoff: float
    turn_rate: float
    turn_tol_deg: float
    heading_hold: float
    vx_carry: float
    vx_min: float
    vx_gain: float
    vy_gain: float
    vy_max: float
    carry_tol: float
    arrive_speed: float
    arrive_hold: float
    lower_speed: float
    release_hold: float
    retreat: float
    vx_retreat: float
    abort_tray_z: float
    timeout_approach_a: float
    timeout_reach: float
    timeout_grasp: float
    timeout_lift: float
    timeout_back_off: float
    timeout_turn: float
    timeout_carry: float
    timeout_arrive_b: float
    timeout_lower: float
    timeout_release: float
    timeout_retreat: float

    @staticmethod
    def default_path() -> Path:
        return find_config(PLANNER_CONFIG_RELPATH)

    @classmethod
    def load(cls, path: Path | None = None) -> PlannerConfig:
        return load_flat_config(cls, path or cls.default_path())

    def timeout(self, phase: Phase) -> float:
        return float(getattr(self, f"timeout_{phase.name.lower()}"))

    @property
    def palm_offsets(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Palm point in each wrist's frame (left, right)."""
        left = np.array([self.palm_offset_x, self.palm_offset_y, self.palm_offset_z])
        return left, MIRROR @ left

    @property
    def grasp_rotation(self) -> NDArray[np.float64]:
        """Left wrist orientation in the tray frame while grasping."""
        return rpy_matrix(
            math.radians(self.grasp_roll_deg),
            math.radians(self.grasp_pitch_deg),
            math.radians(self.grasp_yaw_deg),
        )


@dataclass(frozen=True)
class PlannerCommand:
    phase: Phase
    nav: tuple[float, float, float]  # vx, vy (base frame, m/s), vyaw (rad/s, turn flag)
    heading: float  # absolute yaw the lower body turns to and holds while |vyaw| >= 0.1
    left_wrist: NDArray[np.float64]  # 4 x 4, base frame
    right_wrist: NDArray[np.float64]
    hand_closure: tuple[float, float]
    abort_reason: str | None


def rpy_matrix(roll: float, pitch: float, yaw: float) -> NDArray[np.float64]:
    cr, sr, cp, sp, cy, sy = (
        math.cos(roll),
        math.sin(roll),
        math.cos(pitch),
        math.sin(pitch),
        math.cos(yaw),
        math.sin(yaw),
    )
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    out: NDArray[np.float64] = rz @ ry @ rx
    return out


def base_transform(base: Pose2D, pelvis_height: float) -> NDArray[np.float64]:
    """World pose of the planner's base frame: pelvis xy and yaw, origin at pelvis height."""
    out = np.eye(4)
    out[:3, :3] = rpy_matrix(0.0, 0.0, base.yaw)
    out[:3, 3] = [base.x, base.y, pelvis_height]
    return out


def handle_points(
    cfg: TrayConfig, tray_pos: NDArray[np.float64], tray_yaw: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """World centres of the left (+y) and right (-y) handle bars, as StepTracker measures them."""
    rot = rpy_matrix(0.0, 0.0, tray_yaw)
    y = cfg.tray_length / 2 + cfg.handle_depth / 2
    z = cfg.tray_height - cfg.handle_thickness / 2
    return tray_pos + rot @ np.array([0.0, y, z]), tray_pos + rot @ np.array([0.0, -y, z])


def tray_yaw_of(quat: NDArray[np.float64]) -> float:
    w, x, y, z = (float(v) for v in quat)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass
class _Carry:
    """What LIFT fixes for the rest of the carry."""

    palms: tuple[NDArray[np.float64], NDArray[np.float64]]  # base frame
    rotations: tuple[NDArray[np.float64], NDArray[np.float64]]  # wrists, base frame
    heading: float  # base yaw that lines the tray up with the target
    goal: NDArray[np.float64]  # base xy that puts the tray on the target


@dataclass
class TrayPlanner:
    cfg: PlannerConfig
    tray_cfg: TrayConfig
    sample: EpisodeSample
    phase: Phase = Phase.APPROACH_A
    _entered_t: float | None = None
    _entry_base: Pose2D | None = None
    _since: float | None = None  # start of the condition a phase waits on
    _closing: bool = False
    _correction: list[NDArray[np.float64]] = field(
        default_factory=lambda: [np.zeros(3), np.zeros(3)]
    )
    _grasp_palms: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None
    _carry: _Carry | None = None
    _lowered: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None
    _prev: tuple[float, Pose2D] | None = None
    _hold: PlannerCommand | None = None
    _abort_reason: str | None = None

    def __post_init__(self) -> None:
        geo = scene_geometry_with_gap(self.tray_cfg, self.sample.table_gap)
        self._edge_a = float(geo.table_a_center[0]) - self.tray_cfg.table_depth / 2

    def reset(self) -> None:
        fresh = TrayPlanner(self.cfg, self.tray_cfg, self.sample)
        for f in fields(self):
            setattr(self, f.name, getattr(fresh, f.name))

    def step(self, state: TrayState, base: Pose2D, report: StepReport) -> PlannerCommand:
        """One command for this control step."""
        if self._entered_t is None:
            self._enter(self.phase, state, base)
        if self.phase not in (Phase.DONE, Phase.ABORT):
            reason = self._abort_reason_for(state, report)
            if reason is not None:
                self._abort_reason = reason
                self._enter(Phase.ABORT, state, base)
        cmd = self._command(state, base)
        self._prev = (state.t, base)
        return cmd

    # -- phases ---------------------------------------------------------------

    def _abort_reason_for(self, state: TrayState, report: StepReport) -> str | None:
        if report.failure is not None:
            return report.failure
        if state.tray_pos[2] < self.cfg.abort_tray_z:
            return "tray_on_floor"
        assert self._entered_t is not None
        if state.t - self._entered_t > self.cfg.timeout(self.phase):
            return f"timeout:{self.phase.name}"
        return None

    def _enter(self, phase: Phase, state: TrayState, base: Pose2D) -> None:
        self.phase = phase
        self._entered_t = state.t
        self._entry_base = base
        self._since = None

    def _command(self, state: TrayState, base: Pose2D) -> PlannerCommand:
        cfg = self.cfg
        p = self.phase
        if p in (Phase.DONE, Phase.ABORT):
            return self._stand(state, base)

        if p is Phase.APPROACH_A:
            palms = self._ready_palms()
            ready = min(state.left_palm[2], state.right_palm[2]) >= (
                self.tray_cfg.table_height + cfg.ready_clear
            )
            if self._edge_a - base.x <= cfg.standoff:
                self._enter(Phase.REACH, state, base)
                return self._command(state, base)
            nav = (cfg.vx_approach, 0.0, cfg.heading_hold) if ready else (0.0, 0.0, 0.0)
            return self._emit(state, base, palms, nav, heading=self._entry_yaw)

        if p is Phase.REACH:
            palms = self._handle_palms(state, base, outward=cfg.pregrasp_offset)
            if self._palms_at(state, base, palms):
                self._enter(Phase.GRASP, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0))

        if p is Phase.GRASP:
            # Targets freeze once the hands start closing: a gripped tray moves
            # with the palms, and chasing it would carry it off.
            if self._grasp_palms is None:
                palms = self._handle_palms(state, base, outward=0.0)
                if self._palms_at(state, base, palms):
                    self._closing, self._grasp_palms = True, palms
            else:
                palms = self._grasp_palms
            if self._held(all(state.hand_contacts), state.t, cfg.grasp_hold):
                self._enter(Phase.LIFT, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0), closure=self._closing)

        if p is Phase.LIFT:
            assert self._grasp_palms is not None
            up = np.array([0.0, 0.0, cfg.lift_height])
            palms = (self._grasp_palms[0] + up, self._grasp_palms[1] + up)
            lifted = state.tray_on_table == "none" and (
                state.tray_pos[2] - self.tray_cfg.table_height > self.tray_cfg.h_lift
            )
            if lifted and self._palms_at(state, base, palms):
                self._carry = self._plan_carry(state, base, palms)
                self._enter(Phase.BACK_OFF, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0), closure=True)

        carry = self._carry
        assert carry is not None
        if p is Phase.BACK_OFF:
            if self._travelled(base) >= cfg.backoff:
                self._enter(Phase.TURN, state, base)
                return self._command(state, base)
            nav = (cfg.vx_backoff, 0.0, cfg.heading_hold)
            return self._emit(state, base, carry.palms, nav, closure=True, heading=self._entry_yaw)

        if p is Phase.TURN:
            if yaw_error(base.yaw, carry.heading) <= math.radians(cfg.turn_tol_deg):
                self._enter(Phase.CARRY, state, base)
                return self._command(state, base)
            nav = (0.0, 0.0, cfg.turn_rate)
            return self._emit(state, base, carry.palms, nav, closure=True, heading=carry.heading)

        if p is Phase.CARRY:
            d = carry.goal - np.array([base.x, base.y])
            c, s = math.cos(base.yaw), math.sin(base.yaw)
            along, lateral = c * d[0] + s * d[1], -s * d[0] + c * d[1]
            if along <= cfg.carry_tol:
                self._enter(Phase.ARRIVE_B, state, base)
                return self._command(state, base)
            vx = min(cfg.vx_carry, max(cfg.vx_min, cfg.vx_gain * along))
            vy = float(np.clip(cfg.vy_gain * lateral, -cfg.vy_max, cfg.vy_max))
            nav = (vx, vy, cfg.heading_hold)
            return self._emit(state, base, carry.palms, nav, closure=True, heading=carry.heading)

        if p is Phase.ARRIVE_B:
            if self._held(
                self._base_speed(state, base) < cfg.arrive_speed, state.t, cfg.arrive_hold
            ):
                self._enter(Phase.LOWER, state, base)
                return self._command(state, base)
            return self._emit(state, base, carry.palms, (0.0, 0.0, 0.0), closure=True)

        if p is Phase.LOWER:
            assert self._entered_t is not None
            down = np.array([0.0, 0.0, cfg.lower_speed * (state.t - self._entered_t)])
            palms = (carry.palms[0] - down, carry.palms[1] - down)
            if state.tray_on_table == "B":
                self._lowered = palms
                self._enter(Phase.RELEASE, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0), closure=True)

        assert self._lowered is not None
        if p is Phase.RELEASE:
            palms = self._outward(state, base, self._lowered, cfg.pregrasp_offset)
            if self._held(not any(state.hand_contacts), state.t, cfg.release_hold):
                self._lowered = palms
                self._enter(Phase.RETREAT, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0))

        # RETREAT
        if self._travelled(base) >= cfg.retreat:
            self._enter(Phase.DONE, state, base)
            return self._command(state, base)
        nav = (cfg.vx_retreat, 0.0, cfg.heading_hold)
        return self._emit(state, base, self._lowered, nav, heading=self._entry_yaw)

    # -- geometry ------------------------------------------------------------

    def _plan_carry(
        self,
        state: TrayState,
        base: Pose2D,
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
    ) -> _Carry:
        """Heading and base goal that put the lifted tray, held as now, on the target."""
        target = self.sample.target_pose
        rel_yaw = tray_yaw_of(state.tray_quat) - base.yaw
        # The tray is the same after a half turn (D-14): face B, i.e. turn by about pi.
        heading = _wrap(target.yaw - rel_yaw + math.pi)
        c, s = math.cos(base.yaw), math.sin(base.yaw)
        d = state.tray_pos[:2] - np.array([base.x, base.y])
        offset = np.array([c * d[0] + s * d[1], -s * d[0] + c * d[1]])  # tray xy, base frame
        ch, sh = math.cos(heading), math.sin(heading)
        goal = np.array([target.x, target.y]) - np.array(
            [ch * offset[0] - sh * offset[1], sh * offset[0] + ch * offset[1]]
        )
        rotations = (self._wrist_rotation(0, state, base), self._wrist_rotation(1, state, base))
        return _Carry(palms, rotations, heading, goal)

    def _ready_palms(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        cfg = self.cfg
        left = np.array([cfg.ready_x, cfg.ready_y, cfg.ready_z])
        return left, MIRROR @ left

    def _handle_palms(
        self, state: TrayState, base: Pose2D, outward: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Palm targets on (or `outward` outside) both handles, base frame."""
        yaw = tray_yaw_of(state.tray_quat)
        handles = handle_points(self.tray_cfg, state.tray_pos, yaw)
        side = rpy_matrix(0.0, 0.0, yaw)[:, 1]  # tray +y in the world
        lift = np.array([0.0, 0.0, self.cfg.grasp_dz])
        to_base = np.linalg.inv(base_transform(base, state.pelvis_height))
        left = handles[0] + outward * side + lift
        right = handles[1] - outward * side + lift
        return (to_base @ np.r_[left, 1.0])[:3], (to_base @ np.r_[right, 1.0])[:3]

    def _outward(
        self,
        state: TrayState,
        base: Pose2D,
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
        distance: float,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        side = rpy_matrix(0.0, 0.0, tray_yaw_of(state.tray_quat) - base.yaw)[:, 1]
        return palms[0] + distance * side, palms[1] - distance * side

    def _wrist_rotation(
        self, side: int, state: TrayState | None = None, base: Pose2D | None = None
    ) -> NDArray[np.float64]:
        """Wrist orientation in the base frame: the grasp pose, turned with the tray if given."""
        left = self.cfg.grasp_rotation
        rot = left if side == 0 else MIRROR @ left @ MIRROR
        if state is None or base is None:
            return rot
        return rpy_matrix(0.0, 0.0, tray_yaw_of(state.tray_quat) - base.yaw) @ rot

    def _wrist(
        self, palm: NDArray[np.float64], side: int, rot: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """4 x 4 wrist pose whose palm point lands on `palm` (base frame)."""
        pose = np.eye(4)
        pose[:3, :3] = rot
        pose[:3, 3] = palm - rot @ self.cfg.palm_offsets[side]
        return pose

    # -- emit ------------------------------------------------------------------

    def _emit(
        self,
        state: TrayState,
        base: Pose2D,
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
        nav: tuple[float, float, float],
        closure: bool = False,
        heading: float | None = None,
    ) -> PlannerCommand:
        cfg = self.cfg
        if self.phase.name in CORRECTED and not (self.phase is Phase.GRASP and self._closing):
            measured = self._measured_palms(state, base)
            for k in range(2):
                error = palms[k] - measured[k]
                # Only near the target, where the error is the steady sag rather
                # than the arm still on its way.
                if float(np.linalg.norm(error)) > cfg.palm_correction_window:
                    continue
                corr = self._correction[k] + cfg.palm_correction_gain * error
                norm = float(np.linalg.norm(corr))
                if norm > cfg.palm_correction_max:
                    corr = corr * cfg.palm_correction_max / norm
                self._correction[k] = corr
        if self._carry is not None:  # fixed from the end of LIFT on
            rots = list(self._carry.rotations)
        elif self.phase is Phase.APPROACH_A:
            rots = [self._wrist_rotation(k) for k in range(2)]
        else:
            rots = [self._wrist_rotation(k, state, base) for k in range(2)]
        wrists = [self._wrist(palms[k] + self._correction[k], k, rots[k]) for k in range(2)]
        hand = 1.0 if closure else 0.0
        cmd = PlannerCommand(
            phase=self.phase,
            nav=(float(nav[0]), float(nav[1]), float(nav[2])),
            heading=base.yaw if heading is None else heading,
            left_wrist=wrists[0],
            right_wrist=wrists[1],
            hand_closure=(hand, hand),
            abort_reason=None,
        )
        self._hold = cmd
        return cmd

    def _stand(self, state: TrayState, base: Pose2D) -> PlannerCommand:
        """DONE and ABORT: stand where the last command left the wrists; ABORT keeps the grip."""
        hold = self._hold
        if hold is None:
            ready = self._ready_palms()
            wrists = [self._wrist(ready[k], k, self._wrist_rotation(k)) for k in range(2)]
        else:
            wrists = [hold.left_wrist, hold.right_wrist]
        aborted = self.phase is Phase.ABORT
        closure = hold.hand_closure if hold is not None and aborted else (0.0, 0.0)
        return PlannerCommand(
            phase=self.phase,
            nav=(0.0, 0.0, 0.0),
            heading=base.yaw,
            left_wrist=wrists[0],
            right_wrist=wrists[1],
            hand_closure=closure,
            abort_reason=self._abort_reason if aborted else None,
        )

    # -- measurements ----------------------------------------------------------

    def _measured_palms(
        self, state: TrayState, base: Pose2D
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        to_base = np.linalg.inv(base_transform(base, state.pelvis_height))
        return (
            (to_base @ np.r_[state.left_palm, 1.0])[:3],
            (to_base @ np.r_[state.right_palm, 1.0])[:3],
        )

    def _palms_at(
        self,
        state: TrayState,
        base: Pose2D,
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
    ) -> bool:
        measured = self._measured_palms(state, base)
        return all(
            float(np.linalg.norm(measured[k] - palms[k])) <= self.cfg.palm_tol for k in range(2)
        )

    def _held(self, condition: bool, t: float, duration: float) -> bool:
        if not condition:
            self._since = None
            return False
        if self._since is None:
            self._since = t
        return t - self._since >= duration - 1e-9

    def _travelled(self, base: Pose2D) -> float:
        assert self._entry_base is not None
        return math.hypot(base.x - self._entry_base.x, base.y - self._entry_base.y)

    @property
    def _entry_yaw(self) -> float:
        assert self._entry_base is not None
        return self._entry_base.yaw

    def _base_speed(self, state: TrayState, base: Pose2D) -> float:
        if self._prev is None or state.t <= self._prev[0]:
            return 0.0
        t0, b0 = self._prev
        return math.hypot(base.x - b0.x, base.y - b0.y) / (state.t - t0)
