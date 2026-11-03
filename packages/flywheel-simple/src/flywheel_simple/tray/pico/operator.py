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

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.config import find_config, load_flat_config
from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.pico.virtual import (
    JoystickShaper,
    Style,
    StyleFollower,
    YawStick,
    robot_to_teleop,
)
from flywheel_simple.tray.planner import MIRROR, Phase, TrayPlanner
from flywheel_simple.tray.predicates import StepReport, TrayState

Array = NDArray[np.float64]

OPERATOR_CONFIG_RELPATH = Path("configs/sim/tray_virtual_teleop.yaml")
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
    joystick_accel: float
    turn_rate: float
    yaw_gain: float
    yaw_rate_min: float
    yaw_engage_deg: float
    yaw_release_deg: float
    give_up_s: float
    done_wait_s: float

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
    """One operator for a stream of episodes; `reset` with each episode's planner."""

    def __init__(
        self,
        cfg: OperatorConfig,
        style: Style | None = None,
        style_seed: int = 0,
        dt: float = CONTROL_DT,
    ) -> None:
        self.cfg = cfg
        self.style = style
        self.style_seed = style_seed
        self.dt = dt
        self.ctrl0 = cfg.ctrl0()
        accel = style.joystick_accel if style is not None else cfg.joystick_accel
        self._sticks = (JoystickShaper(accel, dt), JoystickShaper(accel, dt))
        self._yaw = YawStick(
            dt,
            rate_max=cfg.turn_rate,
            gain=cfg.yaw_gain,
            rate_min=cfg.yaw_rate_min,
            engage=math.radians(cfg.yaw_engage_deg),
            release=math.radians(cfg.yaw_release_deg),
        )
        self._followers: tuple[StyleFollower, StyleFollower] | None = None
        if style is not None:
            self._followers = (
                StyleFollower(style, dt, seed=2 * style_seed),
                StyleFollower(style, dt, seed=2 * style_seed + 1),
            )
        self.planner: TrayPlanner | None = None
        self.calibration: Calibration | None = None
        self._stage = "activate"
        self._t_stage = 0.0
        self.last_phase: Phase | None = None
        self.timeline: list[tuple[str, float]] = []  # (stage or planner phase, sim time entered)
        self.abort_reason: str | None = None

    def reset(self, planner: TrayPlanner) -> None:
        """A new episode: activation is pressed again, as SIMPLE deactivates teleop on reset."""
        self.planner = planner
        self.calibration = None
        self._stage = "activate"
        self._t_stage = 0.0
        self.last_phase = None
        self.timeline = []
        self.abort_reason = None
        for stick in self._sticks:
            stick.reset()
        self._yaw.reset()

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
            if calibration is None or report is None or state.t - self._t_stage < self.cfg.engage_s:
                return self._idle(stage="engage")
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
            for k in range(2):
                targets[k][:3, 3] = self._followers[k].step(targets[k][:3, 3])
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
        vyaw, target_yaw = self._yaw.step(cmd.heading, base.yaw)
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

    def _start(self, calibration: Calibration) -> None:
        """Plan from the calibration wrist poses: where the pipeline holds the arms now."""
        assert self.planner is not None
        self.calibration = calibration
        left, right = calibration.ee0
        self.planner.start(left, right)
        if self._followers is not None:
            for follower, ee in zip(self._followers, calibration.ee0):
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


def _clip(value: float, limit: float) -> float:
    return float(np.clip(value, -limit, limit))
