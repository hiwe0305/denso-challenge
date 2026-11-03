"""Play a parent demo back into SIMPLE's PICO pipeline, frame by frame (DA-35 task 9, AC 5).

A recorded frame holds what the pipeline made of the operator's input that
step: the wrist targets of WristsPreProcessor (`action.eef`), the sticks
(`teleop.navigate_command`) and the hands PICO closed. The replay operator
sends controller signals that make the pipeline produce those again:

| Recorded | Replay sends |
|---|---|
| wrist targets, robot frame | controller poses `robot_to_teleop(target)`, this run's calibration |
| Dex3 closed or open | trigger + grip (the parents' grasp) or nothing, one frame ahead |
| navigate command | the same numbers, ahead by NAV_LEAD |

The recording lags the operator's input: a frame shows the wrist targets sent
that step, but the hands and vyaw sent one step and vx, vy and the target yaw
sent two steps before (flywheel_simple.tray.s2.parents.NAV_LEAD). The pipeline
maps controller poses back with the same calibration, so the wrist targets
reach the IK unchanged whatever the calibration was. Frame 0 is the activation
step (recording starts when the operator activates on a stable robot), so the
replay activates on its first step and then plays the parent's frames one per
step. After the last frame the hands hold still and the sticks are let go; the
operator gives up `done_wait_s` later, as the virtual operator does when its
planner is done without success.

Pure numpy: runs in the workspace. `flywheel_simple.tray.s2.streamer` plugs it
into the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.pico.operator import Calibration, PicoSignal
from flywheel_simple.tray.pico.virtual import robot_to_teleop
from flywheel_simple.tray.predicates import quat_to_mat
from flywheel_simple.tray.s2.parents import HAND_LEAD, NAV_LEAD, ParentDemo
from flywheel_simple.tray.s2.segments import Segmentation

Array = NDArray[np.float64]
CONTROL_DT = 1.0 / 50


def eef_matrices(row: Array) -> tuple[Array, Array]:
    """A 14-wide `action.eef` row (left pos, quat wxyz, right pos, quat wxyz) as two 4 x 4."""
    out = []
    for k in (0, 7):
        pose = np.eye(4)
        pose[:3, :3] = quat_to_mat(row[k + 3 : k + 7])
        pose[:3, 3] = row[k : k + 3]
        out.append(pose)
    return out[0], out[1]


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

    def __init__(self, ctrl0: tuple[Array, Array], done_wait_s: float, dt: float = CONTROL_DT):
        self.ctrl0 = ctrl0
        self.done_wait_s = done_wait_s
        self.dt = dt
        self.plan: ReplayPlan | None = None
        self.tau = -1  # steps since activation; -1 before it
        self.ref = 0  # parent frame played
        self._stage = "activate"
        self._t_end: float | None = None
        self.timeline: list[tuple[str, float]] = []

    def reset(self, plan: ReplayPlan) -> None:
        self.plan = plan
        self.tau, self.ref = -1, 0
        self._stage = "activate"
        self._t_end = None
        self.timeline = []

    def step(self, t: float, calibration: Calibration | None) -> PicoSignal:
        plan = self.plan
        assert plan is not None, "reset with a plan first"
        self.tau += 1
        if self.tau == 0:
            self._enter("activate", t)
            return self._idle(activate=True, stage="activate")
        self.ref = self.tau
        ref = min(self.ref, plan.frames - 1)
        ended = self.ref >= plan.frames
        stage = "end" if ended else plan.cut.segment_of(ref)
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
            ee0, scale = calibration.ee0, calibration.scale
            controllers = (
                robot_to_teleop(targets[0], ee0[0], self.ctrl0[0], scale),
                robot_to_teleop(targets[1], ee0[1], self.ctrl0[1], scale),
            )
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
    def _lead(plan: ReplayPlan, ref: int) -> Array:
        """The sticks the parent's operator sent at frame `ref` (see NAV_LEAD)."""
        last = plan.frames - 1
        nav = plan.parent.navigate
        return np.array([nav[min(ref + d, last), k] for k, d in enumerate(NAV_LEAD)])

    def _enter(self, stage: str, t: float) -> None:
        if stage != self._stage or not self.timeline:
            self._stage = stage
            self.timeline.append((stage, round(t, 2)))

    def _idle(self, activate: bool = False, reset: bool = False, stage: str = "") -> PicoSignal:
        return PicoSignal(
            controllers=self.ctrl0,
            closed=(False, False),
            navigate_cmd=(0.0, 0.0, 0.0, 0.0),
            activate=activate,
            reset=reset,
            stage=stage,
        )
