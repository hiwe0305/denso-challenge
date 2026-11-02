"""Scripted two-hand planner for the tray task: one phase machine over TrayState (DA-33).

Each step turns the scene state into base velocities, a heading, two wrist poses
and hand closures for StandWalkController. Phases follow the seven scorer steps
of DA-32:

| Phase | Command | Leaves when | Scorer step |
|---|---|---|---|
| APPROACH_A | walk square to tray, raise hands at `raise_at` | `approach_dist`, `standoff` | 1 |
| REACH | palms to pre-grasp outside the handles, base kept | moved, palms within `palm_tol` | 1 |
| GRASP | grip points `squeeze` inside the handles | both handle contacts for `grasp_hold` | 2 |
| LIFT | palms up `lift_height` at `lift_speed` | ramp done, tray lifted for `lift_hold` | 3 |
| BACK_OFF | walk back `backoff` | distance reached | 4 |
| TURN | turn to the heading that lines the tray up with the target | within `turn_tol_deg` | 4 |
| CARRY | walk to the base pose that puts the tray on the target | within `carry_tol` | 4-5 |
| ARRIVE_B | stand, hold the heading | base slower than `arrive_speed` for `arrive_hold` | 5 |
| LOWER | palms down, shifted onto the target | tray flat on table B for `lower_hold` | 6 |
| RELEASE | open, then out `pregrasp_offset` + `squeeze` | no handle contact `release_hold` | 7 |
| RETREAT | walk back `retreat`, lower the hands to rest | hands at rest | 7 |

Every phase has a timeout; a timeout, a StepTracker failure label or a tray on
the floor ends in ABORT. Wrist poses are 4 x 4 in the base frame of
`flywheel_simple.wbc.upper_body` (pelvis xy and yaw, origin at pelvis height).
They stay fixed from the end of LIFT until LOWER, so the tray keeps its pose
relative to the body while walking and turning. SIMPLE's arm PD sags under
gravity, so while reaching (and grasping and lifting, in height) the planner adds a
correction from the measured palm error, integrated only once the palm is near its
target.

The default grasp is a Dex3 finger pinch under the handle lips (D-19); the
squeeze with the backs of both fists (D-18) is a configuration of the same planner.

decoupled_wbc reaches a new arm target within one control step, so a phase change
that moves the wrist targets would make the arm lunge. The planner turns each such
jump into an offset that decays along a minimum-jerk profile (bell-shaped speed, as
in human reaching); the targets' continuous motion passes through unchanged (D-20).
The arms keep the robot's standing pose (from `start`) while walking to table A and
go back to it at the end, fingers slightly curled (D-21).

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
# Bump when the phase logic changes; config values are hashed into the recorded
# planner_version separately (recorder.planner_version).
PLANNER_VERSION = "da33-planner-4"
MIRROR = np.diag([1.0, -1.0, 1.0])  # left <-> right across the xz plane
# Measured-palm correction per phase: axes it acts on. GRASP and LIFT correct height
# only: across the handles the squeezing hands are blocked on purpose.
# Phases in which the hands level the held tray (when `level_gain` is not 0).
LEVELLED = ("LIFT", "BACK_OFF", "TURN", "CARRY", "ARRIVE_B", "LOWER")
CORRECTED = {
    "REACH": np.ones(3),
    "GRASP": np.array([0.0, 0.0, 1.0]),
    "LIFT": np.array([0.0, 0.0, 1.0]),
}


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
    grip_x: float
    grip_y: float
    grip_z: float
    grasp_dy: float
    grasp_dz: float
    squeeze: float
    hand_closure_open: float
    hand_closure_rest: float
    grasp_close_after: float
    ready_x: float
    ready_y: float
    ready_z: float
    ready_clear: float
    ready_roll_deg: float
    ready_pitch_deg: float
    ready_yaw_deg: float
    raise_at: float
    standoff: float
    approach_dist: float
    vx_approach: float
    pregrasp_offset: float
    pregrasp_dz: float
    palm_tol: float
    grasp_hold: float
    palm_correction_gain: float
    palm_correction_max: float
    palm_correction_window: float
    lift_height: float
    lift_speed: float
    lift_hold: float
    lift_pull: float
    level_gain: float
    level_max_deg: float
    keep_tol: float
    keep_vx: float
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
    arrive_lat_tol: float
    lower_speed: float
    place_shift_max: float
    place_gain: float
    place_height_tol: float
    place_tilt_deg: float
    lower_hold: float
    lower_settle: float
    lower_tray_clear: float
    release_hold: float
    release_dz: float
    release_back: float
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
    smooth_speed: float
    smooth_rot_speed_deg: float
    smooth_min_s: float
    hand_close_s: float

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
    def grip_points(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """The point of each hand put on its handle, in that wrist's frame (left, right)."""
        left = np.array([self.grip_x, self.grip_y, self.grip_z])
        return left, MIRROR @ left

    def grasp_rotation_side(self, side: int) -> NDArray[np.float64]:
        """Wrist orientation in the tray frame while grasping; the right hand mirrored."""
        left = self.grasp_rotation
        return left if side == 0 else MIRROR @ left @ MIRROR

    def ready_rotation_side(self, side: int) -> NDArray[np.float64]:
        """Wrist orientation of the ready pose, base frame; the right hand mirrored."""
        left = rpy_matrix(
            math.radians(self.ready_roll_deg),
            math.radians(self.ready_pitch_deg),
            math.radians(self.ready_yaw_deg),
        )
        return left if side == 0 else MIRROR @ left @ MIRROR

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


def grasp_palms_world(
    cfg: PlannerConfig,
    tray_cfg: TrayConfig,
    tray_pos: NDArray[np.float64],
    tray_yaw: float,
    outward: float = 0.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """World palm points of the grasp (left, right).

    Each hand's grip point sits on its handle centre, `grasp_dy` + `outward` away
    from the tray and `grasp_dz` up, with the wrist at the grasp orientation turned
    with the tray.
    """
    yaw_rot = rpy_matrix(0.0, 0.0, tray_yaw)
    handles = handle_points(tray_cfg, tray_pos, tray_yaw)
    out = cfg.grasp_dy + outward
    palms = []
    for side, sign in ((0, 1.0), (1, -1.0)):
        wrist_rot = yaw_rot @ cfg.grasp_rotation_side(side)
        grip = handles[side] + yaw_rot @ np.array([0.0, sign * out, cfg.grasp_dz])
        offset = cfg.palm_offsets[side] - cfg.grip_points[side]
        palms.append(grip + wrist_rot @ offset)
    return palms[0], palms[1]


def tray_yaw_of(quat: NDArray[np.float64]) -> float:
    w, x, y, z = (float(v) for v in quat)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _tilt(quat: NDArray[np.float64]) -> float:
    """Angle between the tray's up axis and the world's (rad)."""
    w, x, y, z = (float(v) for v in quat / np.linalg.norm(quat))
    return math.acos(max(-1.0, min(1.0, 1 - 2 * (x * x + y * y))))


def _pitch(quat: NDArray[np.float64]) -> float:
    """Rotation of the tray about its own y axis (the line between the handles), rad."""
    w, x, y, z = (float(v) for v in quat / np.linalg.norm(quat))
    return math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))


def _axis_angle(axis: NDArray[np.float64], angle: float) -> NDArray[np.float64]:
    """Rotation matrix for `angle` about the unit vector `axis` (Rodrigues)."""
    k = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
    out: NDArray[np.float64] = np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k
    return out


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def min_jerk(tau: float) -> float:
    """Minimum-jerk profile on [0, 1]: 0 to 1 with zero speed and acceleration at both ends."""
    tau = min(1.0, max(0.0, tau))
    return tau**3 * (10.0 + tau * (6.0 * tau - 15.0))


def _rotvec(rot: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation vector (axis x angle) of a rotation matrix; inverse of `_axis_angle`."""
    w = np.array([rot[2, 1] - rot[1, 2], rot[0, 2] - rot[2, 0], rot[1, 0] - rot[0, 1]])
    sin2 = float(np.linalg.norm(w))  # 2 sin(angle)
    angle = math.atan2(sin2, float(np.trace(rot)) - 1.0)
    if sin2 > 1e-9:
        return np.asarray(angle / sin2 * w)
    if angle < 1.0:
        return np.zeros(3)
    # A half turn: the axis is the column of rot + I with the largest norm.
    sym = rot + np.eye(3)
    axis = sym[:, int(np.argmax(np.linalg.norm(sym, axis=0)))]
    return np.asarray(math.pi * axis / float(np.linalg.norm(axis)))


def _rotation(rotvec: NDArray[np.float64]) -> NDArray[np.float64]:
    angle = float(np.linalg.norm(rotvec))
    return np.eye(3) if angle < 1e-12 else _axis_angle(rotvec / angle, angle)


@dataclass(frozen=True)
class _Blend:
    """A jump in nominal targets, `offset` = before - after, decaying to 0 along min jerk."""

    t0: float
    duration: float
    offset: NDArray[np.float64]  # wrists: (hand, [palm shift, rotation vector], xyz); hands: (2,)

    def weight(self, t: float) -> float:
        return 1.0 - min_jerk((t - self.t0) / self.duration)


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
    _correction: list[NDArray[np.float64]] = field(
        default_factory=lambda: [np.zeros(3), np.zeros(3)]
    )
    _grasp_world: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None  # squeeze
    _station: Pose2D | None = None  # base pose kept while reaching and grasping
    _closing: bool = False  # GRASP has started closing the hands
    _on_b_since: float | None = None  # LOWER: tray resting on table B since
    _level_angle: float = 0.0  # hands' turn against the tray's pitch (rad)
    _arrive_goal: NDArray[np.float64] | None = None  # ARRIVE_B base goal, world xy
    _place_shift: NDArray[np.float64] | None = None  # hands' shift while lowering, base frame
    _carry: _Carry | None = None
    _lowered: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None
    _prev: tuple[float, Pose2D] | None = None
    _hold: PlannerCommand | None = None
    _abort_reason: str | None = None
    # Smoothing (D-20): the last nominal targets (phase, palms, wrist rotations), the
    # nominal hand closure, and the jumps still decaying.
    _nominal: (
        tuple[tuple[Phase, int] | None, list[NDArray[np.float64]], list[NDArray[np.float64]]] | None
    ) = None
    _hand: float | None = None
    _commanded: list[NDArray[np.float64]] | None = None  # last smoothed palms, base frame
    _release_rots: list[NDArray[np.float64]] | None = None  # wrists held while opening
    # The robot's standing pose from `start` (palms, wrist rotations; base frame): the arms
    # hang there while walking to table A and go back there at the end.
    _rest: tuple[list[NDArray[np.float64]], list[NDArray[np.float64]]] | None = None
    _raised: bool = False  # APPROACH_A has raised the hands
    _stepped_back: bool = False  # RETREAT has walked back `retreat`
    _wrist_blends: list[_Blend] = field(default_factory=list)
    _hand_blends: list[_Blend] = field(default_factory=list)

    def __post_init__(self) -> None:
        geo = scene_geometry_with_gap(self.tray_cfg, self.sample.table_gap)
        self._edge_a = float(geo.table_a_center[0]) - self.tray_cfg.table_depth / 2

    def reset(self) -> None:
        fresh = TrayPlanner(self.cfg, self.tray_cfg, self.sample)
        for f in fields(self):
            setattr(self, f.name, getattr(fresh, f.name))

    def start(self, left_wrist: NDArray[np.float64], right_wrist: NDArray[np.float64]) -> None:
        """The wrist poses the robot holds now (base frame), hands open: the first targets
        move from there. Without it the first command goes straight to the targets."""
        wrists = (left_wrist, right_wrist)
        palms = [(w @ np.r_[o, 1.0])[:3] for w, o in zip(wrists, self.cfg.palm_offsets)]
        rots = [w[:3, :3].copy() for w in wrists]
        self._nominal = (None, palms, rots)
        self._rest = ([p.copy() for p in palms], [r.copy() for r in rots])
        self._hand = 0.0

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
            # Square up to the tray: face its yaw, centre on it, stop `approach_dist`
            # short of its centre, or at `standoff` from the table edge (the torso hits
            # the table closer). Level 1 moves the tray 5 cm and turns it 10 deg, which
            # put a handle out of reach from a fixed spot in front of the table.
            tray_yaw = tray_yaw_of(state.tray_quat)
            c, s = math.cos(tray_yaw), math.sin(tray_yaw)
            d = state.tray_pos[:2] - np.array([base.x, base.y])
            along, lateral = c * d[0] + s * d[1], -s * d[0] + c * d[1]
            if along <= cfg.approach_dist or self._edge_a - base.x <= cfg.standoff:
                self._enter(Phase.REACH, state, base)
                return self._command(state, base)
            vy = float(np.clip(cfg.vy_gain * lateral, -cfg.vy_max, cfg.vy_max))
            nav = (cfg.vx_approach, vy, cfg.heading_hold)
            rest = cfg.hand_closure_rest
            # Walk with the arms in the standing pose, fingers curled, until the pelvis is
            # `raise_at` from table A's edge: they reach 0.35 m ahead at pelvis height, under
            # the table top. Then stop, raise the hands above it (wrists still neutral), and
            # walk on; REACH turns the wrists to the grasp.
            if self._rest is not None and not self._raised:
                if self._edge_a - base.x > cfg.raise_at:
                    at_rest, rest_rots = self._rest
                    hanging = (at_rest[0], at_rest[1])
                    return self._emit(
                        state, base, hanging, nav, heading=tray_yaw, rots=rest_rots, hand=rest
                    )
            self._raised = True
            palms = self._ready_palms()
            ready = min(state.left_palm[2], state.right_palm[2]) >= (
                self.tray_cfg.table_height + cfg.ready_clear
            )
            if not ready:
                stand = (0.0, 0.0, 0.0)
                return self._emit(state, base, palms, stand, heading=tray_yaw, hand=rest, segment=1)
            return self._emit(state, base, palms, nav, heading=tray_yaw, hand=rest, segment=1)

        if p is Phase.REACH:
            if self._station is None:
                self._station = base
            above = np.array([0.0, 0.0, cfg.pregrasp_dz])
            outside = self._handle_palms(state, base, outward=cfg.pregrasp_offset)
            palms = (outside[0] + above, outside[1] + above)
            if self._arrived(state, base, palms):
                self._enter(Phase.GRASP, state, base)
                return self._command(state, base)
            return self._emit(
                state, base, palms, self._keep_station(base), heading=self._station.yaw
            )

        if p is Phase.GRASP:
            # Squeeze: both grip points go `squeeze` inside the handles' outer faces,
            # so the arm PD presses the tray between the hands. The hands stop at the
            # faces and never arrive, so the targets are fixed in the world when GRASP
            # starts; the base may still slide while the arms push.
            assert self._station is not None
            if self._grasp_world is None:
                self._grasp_world = grasp_palms_world(
                    cfg, self.tray_cfg, state.tray_pos, tray_yaw_of(state.tray_quat), -cfg.squeeze
                )
            palms = self._to_base(state, base, self._grasp_world)
            # A pinch slides in open and closes once the hands are at the handles (or
            # after `grasp_close_after`); a squeeze (0) closes at once.
            assert self._entered_t is not None
            waited = state.t - self._entered_t >= cfg.grasp_close_after
            if not self._closing and (waited or self._arrived(state, base, palms)):
                self._closing = True
            if self._held(all(state.hand_contacts), state.t, cfg.grasp_hold):
                self._enter(Phase.LIFT, state, base)
                return self._command(state, base)
            nav = self._keep_station(base)
            return self._emit(
                state, base, palms, nav, closure=self._closing, heading=self._station.yaw
            )

        if p is Phase.LIFT:
            assert self._grasp_world is not None and self._entered_t is not None
            # Ramp up: a 10 cm step in the target jerks the squeezed tray.
            rise = min(cfg.lift_height, cfg.lift_speed * (state.t - self._entered_t))
            # Pull the hands toward the body as they rise: at full reach (far trays,
            # palms 0.44 m ahead) the loaded arms raised the hands 2-3 cm of 15.
            assert self._station is not None
            pull = cfg.lift_pull * rise / cfg.lift_height
            yaw = self._station.yaw
            up = np.array([-pull * math.cos(yaw), -pull * math.sin(yaw), rise])
            lifting = (self._grasp_world[0] + up, self._grasp_world[1] + up)
            palms = self._to_base(state, base, lifting)
            lifted = state.tray_on_table == "none" and (
                state.tray_pos[2] - self.tray_cfg.table_height > self.tray_cfg.h_lift
            )
            # The loaded arms sag far below the target (4.5 cm of 12 measured), so
            # LIFT ends on the tray staying lifted once the ramp is done.
            at_top = rise >= cfg.lift_height
            if at_top and self._held(lifted, state.t, cfg.lift_hold):
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
            # CARRY ends on the distance ahead only; step until the tray is within
            # `arrive_lat_tol` of the target ahead and sideways, as the hands can only
            # shift it by `place_shift_max` (8.6 cm sideways was left on seed 12). The
            # goal comes from the tray's error when ARRIVE_B starts, not from LIFT: the
            # tray shifts in the hands on the way (5.7 cm short on seed 22). Stepping
            # on the live tray error chased its sway and timed out.
            if self._arrive_goal is None:
                target = self.sample.target_pose
                error = np.array([target.x, target.y]) - state.tray_pos[:2]
                self._arrive_goal = np.array([base.x, base.y]) + error
            d = self._arrive_goal - np.array([base.x, base.y])
            c, s = math.cos(base.yaw), math.sin(base.yaw)
            along, lateral = c * d[0] + s * d[1], -s * d[0] + c * d[1]
            assert self._entered_t is not None
            budget = state.t - self._entered_t < cfg.timeout_arrive_b - cfg.arrive_hold - 1.0
            if budget and max(abs(along), abs(lateral)) > cfg.arrive_lat_tol:
                self._since = None
                vx = math.copysign(cfg.keep_vx, along) if abs(along) > cfg.arrive_lat_tol else 0.0
                vy = (
                    math.copysign(cfg.keep_vx, lateral)
                    if abs(lateral) > cfg.arrive_lat_tol
                    else 0.0
                )
                nav = (vx, vy, cfg.heading_hold)
                return self._emit(
                    state, base, carry.palms, nav, closure=True, heading=carry.heading
                )
            if self._held(
                self._base_speed(state, base) < cfg.arrive_speed, state.t, cfg.arrive_hold
            ):
                self._enter(Phase.LOWER, state, base)
                return self._command(state, base)
            return self._emit(state, base, carry.palms, (0.0, 0.0, 0.0), closure=True)

        if p is Phase.LOWER:
            assert self._entered_t is not None
            # Closed loop: the loaded arms pull the tray back as they bend down (6 cm
            # on seed 7 with a finger pinch), so the shift keeps tracking the error.
            error = self._place_error(state, base)
            if self._place_shift is None:
                self._place_shift = error
            elif state.tray_on_table == "none":
                self._place_shift = self._capped(self._place_shift + cfg.place_gain * error)
            down = np.array([0.0, 0.0, cfg.lower_speed * (state.t - self._entered_t)])
            move = self._place_shift - down
            palms = (carry.palms[0] + move, carry.palms[1] + move)
            # Release only once the tray sits flat: a corner touching first counted as
            # "on B", and opening then dropped the tray off target.
            flat = (
                state.tray_on_table == "B"
                and state.tray_pos[2] - self.tray_cfg.table_height <= cfg.place_height_tol
                and _tilt(state.tray_quat) <= math.radians(cfg.place_tilt_deg)
            )
            # Or once it has rested on B for `lower_settle`: hands that still hold it a
            # few degrees tilted keep it from ever counting as flat; opening settles it.
            if state.tray_on_table == "B":
                self._on_b_since = state.t if self._on_b_since is None else self._on_b_since
            else:
                self._on_b_since = None
            settled = (
                self._on_b_since is not None and state.t - self._on_b_since >= cfg.lower_settle
            )
            # Palm-up hold (D-25): the wrists under the handle lip reach the table before the
            # tray does and prop it up, so let go while it is still this close above B.
            near = (
                cfg.lower_tray_clear > 0
                and state.tray_pos[2] - self.tray_cfg.table_height <= cfg.lower_tray_clear
            )
            if self._held(flat, state.t, cfg.lower_hold) or settled or near:
                self._lowered = palms
                self._enter(Phase.RELEASE, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0), closure=True)

        assert self._lowered is not None
        if p is Phase.RELEASE:
            # Open while going down `release_dz`, wrists as LOWER left them, then move out.
            # Hands moving out while still opening dragged the tray by a hooked thumb (level
            # 0 seed 0: 9.9 deg tilt); fingers opening in place pried the lip up (2.9 cm,
            # 8.4 deg); going down takes them off its underside. Moving only outward left
            # the fingers hooked under the lip.
            assert self._entered_t is not None and self._nominal is not None
            if self._release_rots is None:
                self._release_rots = [r.copy() for r in self._nominal[2]]
            drop = np.array([0.0, 0.0, cfg.release_dz])
            if state.t - self._entered_t < cfg.hand_close_s:
                lowering = (self._lowered[0] + drop, self._lowered[1] + drop)
                stand = (0.0, 0.0, 0.0)
                return self._emit(state, base, lowering, stand, rots=self._release_rots)
            back = cfg.pregrasp_offset + cfg.squeeze
            out = self._outward(state, base, self._lowered, back)
            # Palm-up hold (D-25): a wrist under the near end of the handle stayed caught
            # when the arm could only reach part of the way out; pull back as well.
            toward_robot = np.array([-cfg.release_back, 0.0, 0.0])
            palms = (out[0] + drop + toward_robot, out[1] + drop + toward_robot)
            if self._held(not any(state.hand_contacts), state.t, cfg.release_hold):
                self._lowered = palms
                self._enter(Phase.RETREAT, state, base)
                return self._command(state, base)
            return self._emit(state, base, palms, (0.0, 0.0, 0.0), segment=1)

        # RETREAT: step back until the fingers clear table B, then lower the hands to the
        # standing pose (fingers curled) and finish once they are there.
        if self._travelled(base) >= cfg.retreat:
            self._stepped_back = True
        if not self._stepped_back:
            nav = (cfg.vx_retreat, 0.0, cfg.heading_hold)
            return self._emit(state, base, self._lowered, nav, heading=self._entry_yaw)
        lowered = self._nominal is not None and self._nominal[0] == (Phase.RETREAT, 1)
        if self._rest is None or (lowered and not self._wrist_blends):
            self._enter(Phase.DONE, state, base)
            return self._command(state, base)
        at_rest, rest_rots = self._rest
        hand = cfg.hand_closure_rest
        stand = (0.0, 0.0, 0.0)
        return self._emit(
            state, base, (at_rest[0], at_rest[1]), stand, rots=rest_rots, hand=hand, segment=1
        )

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

    def _place_error(self, state: TrayState, base: Pose2D) -> NDArray[np.float64]:
        """Tray-to-target xy error in the base frame, capped at `place_shift_max`.

        Walking ends a few centimetres off the target (5.9 cm measured on seed 13,
        level 1); the arms take up the rest while lowering.
        """
        target = self.sample.target_pose
        d = np.array([target.x, target.y]) - state.tray_pos[:2]
        c, s = math.cos(base.yaw), math.sin(base.yaw)
        return self._capped(np.array([c * d[0] + s * d[1], -s * d[0] + c * d[1], 0.0]))

    def _capped(self, shift: NDArray[np.float64]) -> NDArray[np.float64]:
        norm = float(np.linalg.norm(shift))
        if norm > self.cfg.place_shift_max:
            return shift * (self.cfg.place_shift_max / norm)
        return shift

    def _level(
        self,
        state: TrayState,
        palms: list[NDArray[np.float64]],
        rots: list[NDArray[np.float64]],
    ) -> list[NDArray[np.float64]]:
        """Turn both wrists about the line through the palms against the tray's pitch.

        The held tray pitches about that line (10-14 deg seen with a finger pinch)
        while the contacts stay put on it: the hands turn with it, so turning them
        back levels it. The angle integrates `level_gain` x pitch, capped. The palms
        lie on the line, so only the wrist rotations change.
        """
        pitch = _pitch(state.tray_quat)
        cap = math.radians(self.cfg.level_max_deg)
        self._level_angle = float(
            np.clip(self._level_angle + self.cfg.level_gain * pitch, -cap, cap)
        )
        axis = palms[1] - palms[0]
        turn = _axis_angle(axis / float(np.linalg.norm(axis)), self._level_angle)
        return [turn @ r for r in rots]

    def _keep_station(self, base: Pose2D) -> tuple[float, float, float]:
        """Step forward when the base has slid back from where REACH started.

        Measured: the base slides back ~5 cm as the arms reach forward, which puts
        the handles out of reach.
        """
        assert self._station is not None
        c, s = math.cos(self._station.yaw), math.sin(self._station.yaw)
        behind = c * (self._station.x - base.x) + s * (self._station.y - base.y)
        if behind > self.cfg.keep_tol:
            return (self.cfg.keep_vx, 0.0, self.cfg.heading_hold)
        return (0.0, 0.0, 0.0)

    def _to_base(
        self,
        state: TrayState,
        base: Pose2D,
        points: tuple[NDArray[np.float64], NDArray[np.float64]],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        to_base = np.linalg.inv(base_transform(base, state.pelvis_height))
        return (to_base @ np.r_[points[0], 1.0])[:3], (to_base @ np.r_[points[1], 1.0])[:3]

    def _ready_palms(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        cfg = self.cfg
        left = np.array([cfg.ready_x, cfg.ready_y, cfg.ready_z])
        return left, MIRROR @ left

    def _handle_palms(
        self, state: TrayState, base: Pose2D, outward: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Palm targets of the grasp (or `outward` outside it), base frame."""
        left, right = grasp_palms_world(
            self.cfg, self.tray_cfg, state.tray_pos, tray_yaw_of(state.tray_quat), outward
        )
        to_base = np.linalg.inv(base_transform(base, state.pelvis_height))
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
        rot = self.cfg.grasp_rotation_side(side)
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
        rots: list[NDArray[np.float64]] | None = None,
        segment: int = 0,
        hand: float | None = None,
    ) -> PlannerCommand:
        """Command for `palms` (base frame); `rots` overrides the phase's wrist rotations,
        `hand` the closure (`closure` picks closed or `hand_closure_open`).

        A new `segment` within a phase marks a switch of the nominal targets that is
        smoothed like a phase change.
        """
        cfg = self.cfg
        if rots is None:
            if self._carry is not None:  # fixed from the end of LIFT on
                rots = list(self._carry.rotations)
            elif self.phase is Phase.APPROACH_A:
                rots = [cfg.ready_rotation_side(k) for k in range(2)]
            else:
                rots = [self._wrist_rotation(k, state, base) for k in range(2)]
            if self.phase.name in LEVELLED and cfg.level_gain != 0.0:
                # Levelling is part of the nominal targets: RELEASE drops it (up to
                # `level_max_deg`), and that turn is smoothed like any other jump.
                corrected = [palms[k] + self._correction[k] for k in range(2)]
                rots = self._level(state, corrected, rots)
        smooth_palms, smooth_rots = self._smoothed(state.t, (self.phase, segment), palms, rots)
        axes = CORRECTED.get(self.phase.name)
        # The measured palms answer the last step's smoothed targets; correcting against
        # those takes up the sag on the way too (the GRASP correction pushes the fingers
        # down under the handle lip) without integrating the move itself.
        commanded = self._commanded or smooth_palms
        self._commanded = smooth_palms
        if axes is not None:
            measured = self._measured_palms(state, base)
            for k in range(2):
                error = axes * (commanded[k] - measured[k])
                # Only near the target, where the error is the steady sag rather
                # than the arm still on its way.
                if float(np.linalg.norm(error)) > cfg.palm_correction_window:
                    continue
                corr = self._correction[k] + cfg.palm_correction_gain * error
                norm = float(np.linalg.norm(corr))
                if norm > cfg.palm_correction_max:
                    corr = corr * cfg.palm_correction_max / norm
                self._correction[k] = corr
        wrists = [
            self._wrist(smooth_palms[k] + self._correction[k], k, smooth_rots[k]) for k in range(2)
        ]
        if hand is None:
            hand = 1.0 if closure else cfg.hand_closure_open
        closures = self._hand_closure(state.t, hand)
        cmd = PlannerCommand(
            phase=self.phase,
            nav=(float(nav[0]), float(nav[1]), float(nav[2])),
            heading=base.yaw if heading is None else heading,
            left_wrist=wrists[0],
            right_wrist=wrists[1],
            hand_closure=closures,
            abort_reason=None,
        )
        self._hold = cmd
        return cmd

    def _smoothed(
        self,
        t: float,
        key: tuple[Phase, int],
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
        rots: list[NDArray[np.float64]],
    ) -> tuple[list[NDArray[np.float64]], list[NDArray[np.float64]]]:
        """Palms and wrist rotations to command: the nominal ones plus the decaying jumps.

        A phase change, a new segment of one (`key`), or the first step after `start` may
        move the nominal targets by centimetres in one step; that jump becomes a blend
        decaying over max(`smooth_min_s`, distance / `smooth_speed`, angle /
        `smooth_rot_speed_deg`), both hands together.
        Blends add up, so a new jump while one decays keeps position and speed continuous.
        """
        cfg = self.cfg
        if self._nominal is not None and self._nominal[0] != key:
            _, before, before_rots = self._nominal
            offset = np.array(
                [[before[k] - palms[k], _rotvec(rots[k].T @ before_rots[k])] for k in range(2)]
            )
            dist = float(np.max(np.linalg.norm(offset[:, 0], axis=1)))
            angle = float(np.max(np.linalg.norm(offset[:, 1], axis=1)))
            if dist > 1e-9 or angle > 1e-9:
                duration = max(
                    cfg.smooth_min_s,
                    dist / cfg.smooth_speed,
                    angle / math.radians(cfg.smooth_rot_speed_deg),
                )
                self._wrist_blends.append(_Blend(t, duration, offset))
        self._nominal = (key, [p.copy() for p in palms], [r.copy() for r in rots])
        self._wrist_blends = [b for b in self._wrist_blends if b.weight(t) > 0.0]
        out_palms, out_rots = [], []
        for k in range(2):
            palm, rot = palms[k].copy(), rots[k]
            for b in reversed(self._wrist_blends):  # newest first, next to the nominal
                w = b.weight(t)
                palm = palm + w * b.offset[k, 0]
                rot = rot @ _rotation(w * b.offset[k, 1])
            out_palms.append(palm)
            out_rots.append(rot)
        return out_palms, out_rots

    def _hand_closure(self, t: float, nominal: float) -> tuple[float, float]:
        """Both hands' closure: a change of the nominal one ramps over `hand_close_s`."""
        if self._hand is not None and nominal != self._hand:
            offset = np.full(2, self._hand - nominal)
            self._hand_blends.append(_Blend(t, self.cfg.hand_close_s, offset))
        self._hand = nominal
        self._hand_blends = [b for b in self._hand_blends if b.weight(t) > 0.0]
        out = nominal + sum((b.weight(t) * b.offset for b in self._hand_blends), np.zeros(2))
        left, right = (float(v) for v in np.clip(out, 0.0, 1.0))
        return left, right

    def _stand(self, state: TrayState, base: Pose2D) -> PlannerCommand:
        """DONE and ABORT: hold the last command's wrists and hands (ABORT keeps the grip)."""
        hold = self._hold
        rest = (self.cfg.hand_closure_rest, self.cfg.hand_closure_rest)
        if hold is None:
            ready = self._ready_palms()
            rots = [self.cfg.ready_rotation_side(k) for k in range(2)]
            wrists = [self._wrist(ready[k], k, rots[k]) for k in range(2)]
        else:
            wrists = [hold.left_wrist, hold.right_wrist]
        aborted = self.phase is Phase.ABORT
        closure = hold.hand_closure if hold is not None else rest
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
        axes: NDArray[np.float64] | None = None,
    ) -> bool:
        """Both measured palms within `palm_tol` of `palms`, along `axes` (default all)."""
        mask = np.ones(3) if axes is None else axes
        measured = self._measured_palms(state, base)
        return all(
            float(np.linalg.norm(mask * (measured[k] - palms[k]))) <= self.cfg.palm_tol
            for k in range(2)
        )

    def _arrived(
        self,
        state: TrayState,
        base: Pose2D,
        palms: tuple[NDArray[np.float64], NDArray[np.float64]],
    ) -> bool:
        """The smoothed move has ended and both measured palms are at its final targets.

        Not the measured palms alone: sagging arms put them within `palm_tol` of the
        pre-grasp pose while the commanded ones were still on the way (seed 22, level 1:
        REACH ended after 0.16 s and the hands cut down onto the handles).
        """
        return not self._wrist_blends and self._palms_at(state, base, palms)

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
