"""The virtual PICO operator: DA-33's TrayPlanner played as PICO controller signals (DA-35 task 5).

A person at the headset thinks in where the robot's hands should go, sees the
tray and the target zone, and moves two controllers, two sticks and the
trigger and grip buttons. The virtual operator does the same with the planner
as its intent:

| Planner says | Operator sends (as PicoStreamer would) |
|---|---|
| wrist poses, base frame | controller poses: `robot_to_teleop` of the styled targets |
| hand closure 0..1 | trigger + grip: one of PICO's three fixed grasps, or open |
| vx, vy | left stick, rate-limited like a thumb (`JoystickShaper`) |
| heading | right stick, steered closed loop on the body's yaw (`YawStick`) |
| ABORT, or DONE without success | gives up: the reset button |

An episode starts as on the headset: the robot stabilises, the operator presses
activation with the controllers at `ctrl0` (WristsPreProcessor calibrates
then), holds still `engage_s` while SIMPLE eases the arms in, then starts the
planner from the calibration wrist poses.

Pure numpy: runs in the workspace. `flywheel_simple.tray.pico.agent` plugs it
into SIMPLE's pipeline.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import find_config, load_flat_config
from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.pico.virtual import (
    STYLE_RANGES,
    TURN_FLAG,
    JoystickShaper,
    Style,
    StyleFollower,
    YawStick,
    robot_to_teleop,
)
from flywheel_simple.tray.planner import MIRROR, Phase, PlannerConfig, TrayPlanner, min_jerk
from flywheel_simple.tray.predicates import StepReport, TrayState

Array = NDArray[np.float64]

OPERATOR_CONFIG_RELPATH = Path("configs/sim/tray_virtual_teleop.yaml")
OPERATOR_VERSION = "da35-virtual-2"  # 2: retargeting IK joint step limit (arm_step_max)
# Phases in which the hands carry the episode's style: away from the tray, raising them
# on the way to table A and lowering them after placing. Measured on 16 conditions
# (DA-35 task 6): plain hands 14 of 16 passed (13 with all seven step flags); styled
# hands with the style faded out only while touching the tray 13 (3); styled sticks with
# plain hands 7 of 8 (7) on conditions where styled hands missed step 1.
STYLED_PHASES = frozenset({Phase.APPROACH_A, Phase.RETREAT, Phase.DONE})
CONTROL_DT = 1.0 / 50
MAX_LINEAR_VEL = 0.5  # m/s, PicoStreamer's full stick
MAX_ANGULAR_VEL = 1.0  # rad/s
GRASPS = ("trigger", "trigger_grip", "grip")  # config `grasp` 0, 1, 2


@dataclass(frozen=True)
class OperatorConfig:
    engage_s: float
    ctrl_x: float
    ctrl_y: float
    ctrl_z: float
    grasp: int
    closure_threshold: float
    style_fade_s: float
    joystick_accel: float
    turn_rate: float
    yaw_gain: float
    yaw_rate_min: float
    yaw_engage_deg: float
    yaw_release_deg: float
    yaw_lead: float
    give_up_s: float
    done_wait_s: float
    rest_dx: float
    rest_dz: float
    arm_step_max: float  # rad per control step, for the retargeting IK (agent.limit_joint_step)

    @staticmethod
    def default_path() -> Path:
        return find_config(OPERATOR_CONFIG_RELPATH)

    @classmethod
    def load(cls, path: Path | None = None) -> OperatorConfig:
        return load_flat_config(cls, path or cls.default_path())

    @property
    def grasp_name(self) -> str:
        return GRASPS[self.grasp]

    def ctrl0(self) -> tuple[Array, Array]:
        """Controller poses at activation, headset frame (z up, yaw-compensated); right mirrored."""
        left = np.eye(4)
        left[:3, 3] = [self.ctrl_x, self.ctrl_y, self.ctrl_z]
        right = np.eye(4)
        right[:3, 3] = MIRROR @ left[:3, 3]
        return left, right


@dataclass(frozen=True)
class Calibration:
    """What WristsPreProcessor fixed at activation: the wrist pose it maps `ctrl0` to, the scale."""

    ee0: tuple[Array, Array]  # left, right; robot model frame
    scale: float


@dataclass(frozen=True)
class PicoSignal:
    """One control step of controller input, before PicoStreamer's packing."""

    controllers: tuple[Array, Array]  # left, right; 4 x 4, headset frame
    closed: tuple[bool, bool]
    navigate_cmd: tuple[float, float, float, float]  # vx, vy, vyaw, target yaw
    activate: bool  # the activation edge (menu + right trigger)
    reset: bool  # the operator gives up on this attempt
    stage: str  # "activate", "engage", a planner phase name, "give_up"


class VirtualOperator:
    """One operator for a stream of episodes; `reset` with each episode's planner and style."""

    def __init__(self, cfg: OperatorConfig, dt: float = CONTROL_DT) -> None:
        self.cfg = cfg
        self.dt = dt
        self.ctrl0 = cfg.ctrl0()
        self.style: Style | None = None
        self.style_seed = 0
        self.planner: TrayPlanner | None = None
        self.calibration: Calibration | None = None
        self._t_calibrated: float | None = None
        self._sticks = (
            JoystickShaper(cfg.joystick_accel, dt),
            JoystickShaper(cfg.joystick_accel, dt),
        )
        self._yaw = self._yaw_stick(cfg.turn_rate)
        self._followers: tuple[StyleFollower, StyleFollower] | None = None
        self._style_offset: list[Array] = [np.zeros(3), np.zeros(3)]  # styled - planned, base
        self._style_weight = 1.0  # how much of the style the hands carry now (0-1)
        self._stage = "activate"
        self._t_stage = 0.0
        self.last_phase: Phase | None = None
        self.timeline: list[tuple[str, float]] = []  # (stage or planner phase, sim time entered)
        self.abort_reason: str | None = None

    def reset(self, planner: TrayPlanner, style: Style | None = None, style_seed: int = 0) -> None:
        """A new episode with its own style (None: plain planner targets, config sticks).

        Activation is pressed again, as SIMPLE deactivates teleop on reset.
        """
        cfg, dt = self.cfg, self.dt
        self.planner = planner
        self.style, self.style_seed = style, style_seed
        accel = cfg.joystick_accel if style is None else style.joystick_accel
        self._sticks = (JoystickShaper(accel, dt), JoystickShaper(accel, dt))
        self._yaw = self._yaw_stick(cfg.turn_rate if style is None else style.turn_rate)
        self._followers = None
        if style is not None:
            self._followers = (
                StyleFollower(style, dt, seed=2 * style_seed),
                StyleFollower(style, dt, seed=2 * style_seed + 1),
            )
        self.calibration = None
        self._t_calibrated = None
        self._stage = "activate"
        self._t_stage = 0.0
        self.last_phase = None
        self.timeline = []
        self.abort_reason = None

    def _yaw_stick(self, rate_max: float) -> YawStick:
        cfg = self.cfg
        return YawStick(
            self.dt,
            rate_max=rate_max,
            gain=cfg.yaw_gain,
            rate_min=cfg.yaw_rate_min,
            engage=math.radians(cfg.yaw_engage_deg),
            release=math.radians(cfg.yaw_release_deg),
            lead=cfg.yaw_lead,
        )

    def step(
        self,
        state: TrayState,
        base: Pose2D,
        report: StepReport | None,
        calibration: Calibration | None,
    ) -> PicoSignal:
        """The signal for this control step; call once per step."""
        if self._stage == "activate":
            self._enter("engage", state.t)
            return self._idle(activate=True, stage="activate")
        if self._stage == "engage":
            if calibration is None or report is None:
                return self._idle(stage="engage")
            if self._t_calibrated is None:
                self._t_calibrated = state.t
            done = (state.t - self._t_calibrated) / self.cfg.engage_s
            if done < 1.0:
                return self._tucking(calibration, min_jerk(done))
            self._start(calibration)
            self._enter("run", state.t)
        if self._stage == "give_up":
            return self._idle(reset=True, stage="give_up")

        assert self.planner is not None and self.calibration is not None and report is not None
        cmd = self.planner.step(state, base, report)
        if cmd.phase is not self.last_phase:
            self.last_phase = cmd.phase
            self._t_stage = state.t
            self.timeline.append((cmd.phase.name, round(state.t, 2)))
            self.abort_reason = cmd.abort_reason
        waited = state.t - self._t_stage
        if (cmd.phase is Phase.ABORT and waited >= self.cfg.give_up_s) or (
            cmd.phase is Phase.DONE and waited >= self.cfg.done_wait_s
        ):
            self._enter("give_up", state.t)
            return self._idle(reset=True, stage="give_up")

        targets = [cmd.left_wrist.copy(), cmd.right_wrist.copy()]
        if self._followers is not None:
            # Careful near the tray: the style fades out over `style_fade_s` when the
            # hands go to the tray and back in once they leave it.
            goal = 1.0 if cmd.phase in STYLED_PHASES else 0.0
            rate = self.dt / self.cfg.style_fade_s
            self._style_weight += float(np.clip(goal - self._style_weight, -rate, rate))
            for k in range(2):
                styled = self._followers[k].step(targets[k][:3, 3])
                self._style_offset[k] = self._style_weight * (styled - targets[k][:3, 3])
                targets[k][:3, 3] = targets[k][:3, 3] + self._style_offset[k]
        ee0, scale = self.calibration.ee0, self.calibration.scale
        controllers = (
            robot_to_teleop(targets[0], ee0[0], self.ctrl0[0], scale),
            robot_to_teleop(targets[1], ee0[1], self.ctrl0[1], scale),
        )
        closed = (
            cmd.hand_closure[0] >= self.cfg.closure_threshold,
            cmd.hand_closure[1] >= self.cfg.closure_threshold,
        )
        vx = self._sticks[0].step(_clip(cmd.nav[0], MAX_LINEAR_VEL))
        vy = self._sticks[1].step(_clip(cmd.nav[1], MAX_LINEAR_VEL))
        # Steer only while the planner asks for a heading (its turn flag, as DA-33's
        # NavIntegrator passes it on): standing with the stick held swayed the body
        # 6 degrees and 5 cm at table B, and ARRIVE_B never settled.
        steer = abs(cmd.nav[2]) >= TURN_FLAG
        vyaw, target_yaw = self._yaw.step(cmd.heading, base.yaw, steer)
        return PicoSignal(
            controllers=controllers,
            closed=closed,
            navigate_cmd=(vx, vy, _clip(vyaw, MAX_ANGULAR_VEL), target_yaw),
            activate=False,
            reset=False,
            stage=cmd.phase.name,
        )

    def _enter(self, stage: str, t: float) -> None:
        self._stage = stage
        self._t_stage = t
        if stage != "run":
            self.timeline.append((stage, round(t, 2)))

    def rest(self, calibration: Calibration) -> tuple[Array, Array]:
        """The wrists' rest pose: the calibration pose moved `rest_dx`, `rest_dz` (robot frame).

        PICO has no half-closed hand, so the fingers stay straight where DA-33's rest
        curls them (D-21): from the calibration pose they touched table A's edge just
        before the planner raises the hands (level 1 seed 22, body 0.41 m from the edge,
        turned 8 degrees). Elbows in, hands nearer the chest, as a person would.
        """
        delta = np.array([self.cfg.rest_dx, 0.0, self.cfg.rest_dz])
        out = []
        for ee in calibration.ee0:
            pose = ee.copy()
            pose[:3, 3] += delta
            out.append(pose)
        return out[0], out[1]

    def _tucking(self, calibration: Calibration, s: float) -> PicoSignal:
        """Engage: the controllers move from activation to the rest pose, `s` of the way."""
        rest, ee0 = self.rest(calibration), calibration.ee0
        targets = []
        for k in range(2):
            pose = ee0[k].copy()
            pose[:3, 3] += s * (rest[k][:3, 3] - ee0[k][:3, 3])
            targets.append(robot_to_teleop(pose, ee0[k], self.ctrl0[k], calibration.scale))
        idle = self._idle(stage="engage")
        return dataclasses.replace(idle, controllers=(targets[0], targets[1]))

    def _start(self, calibration: Calibration) -> None:
        """Plan from the rest pose the hands were brought to while engaging."""
        assert self.planner is not None
        self.calibration = calibration
        left, right = self.rest(calibration)
        self.planner.start(left, right)
        self._style_offset = [np.zeros(3), np.zeros(3)]
        self._style_weight = 1.0
        if self._followers is not None:
            for follower, ee in zip(self._followers, (left, right)):
                follower.reset(ee[:3, 3])

    def _idle(self, activate: bool = False, reset: bool = False, stage: str = "") -> PicoSignal:
        """Controllers at the activation pose, hands open, sticks centred."""
        return PicoSignal(
            controllers=self.ctrl0,
            closed=(False, False),
            navigate_cmd=(0.0, 0.0, 0.0, self._yaw.target_yaw),
            activate=activate,
            reset=reset,
            stage=stage,
        )


def operator_version(cfg: OperatorConfig, planner_cfg: PlannerConfig) -> str:
    """OPERATOR_VERSION plus a hash of the operator, planner and style settings."""
    values = {"operator": asdict(cfg), "planner": asdict(planner_cfg), "styles": STYLE_RANGES}
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:8]
    return f"{OPERATOR_VERSION}+cfg.{digest}"


def _clip(value: float, limit: float) -> float:
    return float(np.clip(value, -limit, limit))
