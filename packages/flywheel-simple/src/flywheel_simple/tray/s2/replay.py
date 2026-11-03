"""Play a parent demo back into SIMPLE's PICO pipeline, frame by frame (DA-35 tasks 9, 10; AC 5).

A recorded frame holds what the pipeline made of the operator's input that
step: the wrist targets of WristsPreProcessor (`action.eef`), the sticks
(`teleop.navigate_command`) and the hands PICO closed. The replay operator
sends controller signals that make the pipeline produce those again:

| Recorded | Replay sends |
|---|---|
| wrist targets, robot frame | controller poses `robot_to_teleop(target)`, this run's calibration |
| Dex3 closed or open | trigger + grip (the parents' grasp) or nothing, one frame ahead |
| navigate command | exact: the same numbers, ahead by NAV_LEAD; variant: regenerated |

The recording lags the operator's input: a frame shows the wrist targets sent
that step, but the hands and vyaw sent one step and vx, vy and the target yaw
sent two steps before (measured on parents-1103b shard-00 episode 0: with these
leads the replayed sticks and hands match the parent's frame for frame).

The pipeline maps controller poses back with the same calibration, so the
wrist targets reach the IK unchanged whatever the calibration was. Frame 0 is
the activation step (recording starts when the operator activates on a stable
robot), so the replay activates on its first step and then plays the parent's
frames one per step. After the last frame the hands hold still and the sticks
are let go; the operator gives up `done_wait_s` later, as the virtual operator
does when its planner is done without success.

With a VariantPlan (flywheel_simple.tray.s2.variant) the replay is closed loop
on the measured pelvis pose:

- wrists: the parent's robot-frame targets blended with the transformed world
  targets brought into the measured robot frame (pelvis position and yaw;
  weight `world_weight`; position interpolated, rotation slerped);
- left stick: the parent's (vx, vy) plus `nav_gain` x the base's error to the
  base reference, in the body frame, rate-limited like a thumb;
- right stick: the parent's vyaw plus the rate at which the transform turns, with
  the target yaw integrated from it as PICO does (an identity variant sends the
  parent's stick unchanged, and the turns keep their direction);
- gates: on reaching a gate frame (end of the walk to table A, end of the
  arrival at table B) the replay holds that frame and steps the base onto its
  reference (corrective steps of `step_speed_min`..`step_speed_max`; the right
  stick steered by `YawStick`, pushed past `gate_yaw_tol_deg` and let go a third
  of the way back) until the body stands still within tolerance for `gate_hold_s`,
  or `gate_max_s` has passed.

Pure numpy: runs in the workspace. `flywheel_simple.tray.s2.streamer` plugs it
into the pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.pico.operator import MAX_LINEAR_VEL, Calibration, PicoSignal
from flywheel_simple.tray.pico.virtual import JoystickShaper, YawStick, robot_to_teleop
from flywheel_simple.tray.predicates import quat_to_mat
from flywheel_simple.tray.s2.config import S2Config
from flywheel_simple.tray.s2.parents import HAND_LEAD, NAV_LEAD, ParentDemo
from flywheel_simple.tray.s2.segments import Segmentation
from flywheel_simple.tray.s2.variant import (
    Planar,
    VariantPlan,
    base_frame,
    pose_matrix,
    wrap,
    yaw_of,
    yaw_of_matrix,
)

Array = NDArray[np.float64]
CONTROL_DT = 1.0 / 50
SETTLE_FRAMES = 11  # the gate's stillness is measured over 0.2 s: the pelvis sways each frame


def eef_matrices(row: Array) -> tuple[Array, Array]:
    """A 14-wide `action.eef` row (left pos, quat wxyz, right pos, quat wxyz) as two 4 x 4."""
    out = []
    for k in (0, 7):
        pose = np.eye(4)
        pose[:3, :3] = quat_to_mat(row[k + 3 : k + 7])
        pose[:3, 3] = row[k : k + 3]
        out.append(pose)
    return out[0], out[1]


def _log(rot: Array) -> Array:
    """Rotation vector of a rotation matrix."""
    cos = max(-1.0, min(1.0, (float(np.trace(rot)) - 1.0) / 2.0))
    angle = math.acos(cos)
    axis = np.array([rot[2, 1] - rot[1, 2], rot[0, 2] - rot[2, 0], rot[1, 0] - rot[0, 1]])
    if angle < 1e-9:
        return np.zeros(3)
    if math.pi - angle < 1e-6:  # half turn: axis from the symmetric part
        k = int(np.argmax(np.diag(rot)))
        v = (rot[:, k] + np.eye(3)[k]) / math.sqrt(2.0 * (1.0 + rot[k, k]))
        return np.asarray(v * angle)
    return np.asarray(axis * (angle / (2.0 * math.sin(angle))))


def _exp(vec: Array) -> Array:
    angle = float(np.linalg.norm(vec))
    if angle < 1e-12:
        return np.eye(3)
    k = vec / angle
    kx = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.asarray(np.eye(3) + math.sin(angle) * kx + (1 - math.cos(angle)) * kx @ kx)


def blend_pose(a: Array, b: Array, w: float) -> Array:
    """`w` of the way from pose `a` to `b`: position interpolated, rotation slerped."""
    if w <= 0.0:
        return a
    if w >= 1.0:
        return b
    out = np.eye(4)
    out[:3, :3] = a[:3, :3] @ _exp(w * _log(a[:3, :3].T @ b[:3, :3]))
    out[:3, 3] = (1 - w) * a[:3, 3] + w * b[:3, 3]
    return out


@dataclass(frozen=True)
class ReplayPlan:
    """Exact replay: one parent's frames as recorded."""

    parent: ParentDemo
    cut: Segmentation

    @property
    def frames(self) -> int:
        return self.parent.frames


class ReplayOperator:
    """Plays one plan per episode (`reset`); `step` once per control step."""

    def __init__(
        self,
        ctrl0: tuple[Array, Array],
        done_wait_s: float,
        cfg: S2Config | None = None,
        dt: float = CONTROL_DT,
    ) -> None:
        self.ctrl0 = ctrl0
        self.done_wait_s = done_wait_s
        self.cfg = cfg
        self.dt = dt
        self.plan: ReplayPlan | VariantPlan | None = None
        self.tau = -1  # steps since activation; -1 before it
        self.ref = 0  # parent frame played
        self._stage = "activate"
        self._t_end: float | None = None
        self.timeline: list[tuple[str, float]] = []
        # frame, seconds held, converged, base error (m, deg) on arriving and on leaving
        self.gate_waits: list[tuple[int, float, bool, float, float, float, float]] = []
        self._sticks = (JoystickShaper(1.0, dt), JoystickShaper(1.0, dt))
        self._yaw = YawStick(dt, rate_max=0.5)
        self._target_yaw = 0.0  # PICO's integrated target yaw, 0 at every episode start
        # frame, since, settled since, base error on arriving (m, rad)
        self._gate: tuple[int, float, float | None, float, float] | None = None
        self._passed: set[int] = set()
        self._stepping = False
        self._recent_xy: list[Array] = []  # pelvis xy over the last SETTLE_FRAMES steps
        self.place_fix: Planar | None = None  # tray-in-hand correction while placing
        self._place_fix_m = np.eye(4)

    def reset(
        self,
        plan: ReplayPlan | VariantPlan,
        joystick_accel: float = 1.0,
        turn_rate: float = 0.5,
        yaw: YawStick | None = None,
    ) -> None:
        """A new episode; the sticks of a variant move at the parent's style (accel, turn rate)."""
        if isinstance(plan, VariantPlan) and self.cfg is None:
            raise ValueError("a variant needs the S2 config")
        self.plan = plan
        self.tau, self.ref = -1, 0
        self._stage = "activate"
        self._t_end = None
        self.timeline = []
        self.gate_waits = []
        self._sticks = (
            JoystickShaper(joystick_accel, self.dt),
            JoystickShaper(joystick_accel, self.dt),
        )
        self._yaw = yaw if yaw is not None else YawStick(self.dt, rate_max=turn_rate)
        self._target_yaw = 0.0
        self._gate, self._passed, self._stepping = None, set(), False
        self._recent_xy = []
        self.place_fix, self._place_fix_m = None, np.eye(4)

    def step(
        self,
        t: float,
        calibration: Calibration | None,
        base: Array | None = None,
        tray: Array | None = None,
    ) -> PicoSignal:
        """This step's signal; variants need the measured pelvis and tray poses (7, world)."""
        plan = self.plan
        assert plan is not None, "reset with a plan first"
        self.tau += 1
        if self.tau == 0:
            self._enter("activate", t)
            return self._idle(activate=True, stage="activate")
        if isinstance(plan, VariantPlan):
            assert base is not None, "a variant replays closed loop on the base pose"
            self._recent_xy = [*self._recent_xy[-(SETTLE_FRAMES - 1) :], base[:2].copy()]
            self._advance(t, base)
            if self.ref >= plan.cut.place_start and self.place_fix is None and tray is not None:
                self._fix_place(plan, min(self.ref, plan.frames - 1), tray)
        else:
            self.ref = self.tau
        ref = min(self.ref, plan.frames - 1)
        ended = self.ref >= plan.frames
        stage = "end" if ended else ("gate" if self._gate else plan.cut.segment_of(ref))
        if ended and self._t_end is None:
            self._t_end = t
        if self._t_end is not None and t - self._t_end >= self.done_wait_s:
            self._enter("give_up", t)
            return self._idle(reset=True, stage="give_up")
        self._enter(stage, t)

        row = plan.parent.eef[ref]
        if calibration is None or not row.any():  # no wrist data yet in this frame
            controllers = self.ctrl0
        else:
            targets = eef_matrices(row)
            if isinstance(plan, VariantPlan) and plan.world_weight[ref] > 0.0:
                assert base is not None
                to_robot = np.linalg.inv(base_frame(base))
                if ref >= plan.cut.place_start:
                    to_robot = to_robot @ self._place_fix_m
                w = float(plan.world_weight[ref])
                targets = (
                    blend_pose(targets[0], to_robot @ plan.wrist_world[ref, 0], w),
                    blend_pose(targets[1], to_robot @ plan.wrist_world[ref, 1], w),
                )
            ee0, scale = calibration.ee0, calibration.scale
            controllers = (
                robot_to_teleop(targets[0], ee0[0], self.ctrl0[0], scale),
                robot_to_teleop(targets[1], ee0[1], self.ctrl0[1], scale),
            )
        if isinstance(plan, VariantPlan):
            assert base is not None
            navigate = self._navigate(plan, ref, base, ended)
        else:
            nav = self._lead(plan, ref)
            if ended:  # sticks let go; PICO keeps its integrated target yaw
                navigate = (0.0, 0.0, 0.0, float(nav[3]))
            else:
                navigate = (float(nav[0]), float(nav[1]), float(nav[2]), float(nav[3]))
        closed = plan.parent.hands_closed[min(ref + HAND_LEAD, plan.frames - 1)]
        return PicoSignal(
            controllers=controllers,
            closed=(bool(closed[0]), bool(closed[1])),
            navigate_cmd=navigate,
            activate=False,
            reset=False,
            stage=stage,
        )

    @staticmethod
    def _lead(plan: ReplayPlan | VariantPlan, ref: int) -> Array:
        """The sticks the parent's operator sent at frame `ref` (see NAV_LEAD)."""
        last = plan.frames - 1
        nav = plan.parent.navigate
        return np.array([nav[min(ref + d, last), k] for k, d in enumerate(NAV_LEAD)])

    # -- variants ---------------------------------------------------------------

    def _error(self, plan: VariantPlan, ref: int, base: Array) -> tuple[Array, float]:
        """Base reference minus measured pelvis: xy in the body frame, yaw."""
        yaw = yaw_of(base)
        d = plan.base_ref[ref, :2] - base[:2]
        c, s = math.cos(yaw), math.sin(yaw)
        return np.array([c * d[0] + s * d[1], -s * d[0] + c * d[1]]), wrap(
            plan.base_ref[ref, 2] - yaw
        )

    def _advance(self, t: float, base: Array) -> None:
        """Next parent frame, unless a gate holds the current one."""
        plan, cfg = self.plan, self.cfg
        assert isinstance(plan, VariantPlan) and cfg is not None
        if self._gate is None:
            self.ref += 1
            if self.ref in plan.gates and self.ref not in self._passed and self.ref < plan.frames:
                e_xy, e_yaw = self._error(plan, self.ref, base)
                self._gate = (self.ref, t, None, float(np.linalg.norm(e_xy)), e_yaw)
        if self._gate is None:
            return
        frame, since, settled, err_in, yaw_in = self._gate
        e_xy, e_yaw = self._error(plan, frame, base)
        speed = 0.0
        if len(self._recent_xy) == SETTLE_FRAMES:
            moved = float(np.linalg.norm(self._recent_xy[-1] - self._recent_xy[0]))
            speed = moved / ((SETTLE_FRAMES - 1) * self.dt)
        # Settled, not only near: a corrective step or turn leaves the body swaying for
        # a while, and the hands then reach for the handles from a moving base.
        within = (
            float(np.linalg.norm(e_xy)) <= cfg.gate_pos_tol
            and abs(e_yaw) <= math.radians(cfg.gate_yaw_tol_deg)
            and speed <= cfg.settle_speed
            and not self._stepping
            and not self._yaw.pushing
        )
        settled = (settled if settled is not None else t) if within else None
        converged = settled is not None and t - settled >= cfg.gate_hold_s
        if converged or t - since >= cfg.gate_max_s:
            out_m, out_deg = float(np.linalg.norm(e_xy)), math.degrees(e_yaw)
            self.gate_waits.append(
                (frame, round(t - since, 2), converged, round(err_in, 3),
                 round(math.degrees(yaw_in), 1), round(out_m, 3), round(out_deg, 1))
            )  # fmt: skip
            self._passed.add(frame)
            self._gate = None
            self._stepping = False
        else:
            self._gate = (frame, since, settled, err_in, yaw_in)

    def _fix_place(self, plan: VariantPlan, ref: int, tray: Array) -> None:
        """Move the placing hands by where the held tray is off its transformed parent pose.

        The target anchor carries the hands, not the tray: a tray held a few centimetres
        off its place in the parent's hands would be put down that far off the zone.
        Like MimicGen's object-centric step for the object in hand, the hands of P move
        by the planar offset between the expected and the measured tray, capped.
        """
        cfg = self.cfg
        assert cfg is not None
        expected = pose_matrix(plan.parent.tray_pose[ref])
        expected = plan.anchors[ref].matrix() @ expected
        want = Pose2D(float(expected[0, 3]), float(expected[1, 3]), yaw_of_matrix(expected))
        have = Pose2D(float(tray[0]), float(tray[1]), yaw_of(tray))
        fix = Planar.between(have, want)
        dist = math.hypot(fix.dx, fix.dy)
        scale = min(1.0, cfg.place_fix_max_m / dist) if dist > 0 else 1.0
        cap = math.radians(cfg.place_fix_max_deg)
        self.place_fix = Planar(fix.dx * scale, fix.dy * scale, max(-cap, min(cap, fix.yaw)))
        self._place_fix_m = self.place_fix.matrix()

    def _navigate(
        self, plan: VariantPlan, ref: int, base: Array, ended: bool
    ) -> tuple[float, float, float, float]:
        cfg = self.cfg
        assert cfg is not None
        e_xy, e_yaw = self._error(plan, ref, base)
        held = self._gate is not None
        if ended:
            v = np.zeros(2)
        elif held:
            # Corrective steps onto the reference, as the planner's keep-station steps.
            dist = float(np.linalg.norm(e_xy))
            if self._stepping and dist <= cfg.step_stop:
                self._stepping = False
            elif not self._stepping and dist > cfg.gate_pos_tol:
                self._stepping = True
            speed = min(cfg.step_speed_max, max(cfg.step_speed_min, cfg.nav_gain * dist))
            v = e_xy / dist * speed if self._stepping else np.zeros(2)
        else:
            ff = self._lead(plan, ref)[:2]
            walking = float(np.linalg.norm(ff)) >= cfg.walk_ff_min
            v = ff + cfg.nav_gain * e_xy if walking else ff.copy()
        v = np.clip(v, -MAX_LINEAR_VEL, MAX_LINEAR_VEL)
        vx, vy = self._sticks[0].step(float(v[0])), self._sticks[1].step(float(v[1]))
        if held:
            # The right stick as the virtual operator steers it, from PICO's current target.
            self._yaw.target_yaw = self._target_yaw
            vyaw, self._target_yaw = self._yaw.step(float(plan.base_ref[ref, 2]), yaw_of(base))
        else:
            # The parent's stick, plus the transform's turn: PICO integrates both into the
            # target yaw, and the lower body turns to it whenever the stick is pushed.
            vyaw = 0.0 if ended else float(self._lead(plan, ref)[2] + plan.yaw_rate[ref])
            self._target_yaw = wrap(self._target_yaw + vyaw * self.dt)
        return (vx, vy, vyaw, self._target_yaw)

    # ---------------------------------------------------------------------------

    def _enter(self, stage: str, t: float) -> None:
        if stage != self._stage or not self.timeline:
            self._stage = stage
            self.timeline.append((stage, round(t, 2)))

    def _idle(self, activate: bool = False, reset: bool = False, stage: str = "") -> PicoSignal:
        return PicoSignal(
            controllers=self.ctrl0,
            closed=(False, False),
            navigate_cmd=(0.0, 0.0, 0.0, self._target_yaw),
            activate=activate,
            reset=reset,
            stage=stage,
        )
