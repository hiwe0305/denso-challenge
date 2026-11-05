"""SIMPLE's PICO teleop agent with the headset swapped for any streamer.

`PicoDecoupledAgent` runs PicoStreamer -> TeleopPolicy (wrist pre-processor,
TeleopRetargetingIK with the waist) -> G1DecoupledWholeBodyPolicy. Here the
same pipeline reads a streamer we pass in: the scripted one below for tests
without a headset, the virtual operator, and the S2 replay streamer
(flywheel_simple.tray.s2.streamer). No VR video server, no XRoboToolkit, no
controller buttons.

decoupled_wbc's own DummyStreamer cannot be used: it imports ROS for a keyboard
listener. Only runs in the SIMPLE venv, with PyAV installed (SIMPLE's PICO
agent module imports its video sender at import time).
"""

from __future__ import annotations

import dataclasses
import functools
import importlib
import importlib.util
import sys
import types
from typing import Any
from unittest import mock

import numpy as np
from simple.agents import pico_decoupled_agent  # type: ignore[import-not-found]
from simple.agents.pico_decoupled_agent import (  # type: ignore[import-not-found]
    PicoDecoupledAgent,
)

from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.pico.clock import ClockedTime, SimClock
from flywheel_simple.tray.pico.conditions import Condition
from flywheel_simple.tray.pico.ik_limit import arms_only, limit_joint_step
from flywheel_simple.tray.pico.operator import (
    Calibration,
    PicoSignal,
    VirtualOperator,
    operator_version,
)
from flywheel_simple.tray.pico.virtual import Style, pico_fingers, sample_style, style_seed_for
from flywheel_simple.tray.planner import PlannerConfig, TrayPlanner

STANDING_HEIGHT = 0.74  # PicoStreamer's initial base height command


def _stub_ik_visualizer() -> None:
    # TeleopRetargetingIK imports its visualizer at module level, which needs
    # meshcat-shapes (decoupled_wbc[full]). Visualisation stays off, so a
    # placeholder stands in when it is absent. Same workaround as DA-33's
    # flywheel_simple.wbc.upper_body (unmerged); keep one copy once it merges.
    name = "decoupled_wbc.control.visualization.humanoid_visualizer"
    if name not in sys.modules and importlib.util.find_spec("meshcat_shapes") is None:
        placeholder = types.ModuleType(name)
        placeholder.RobotVisualizer = None  # type: ignore[attr-defined]
        sys.modules[name] = placeholder


def _streamer_output(**fields: Any) -> Any:
    base = importlib.import_module("decoupled_wbc.control.teleop.streamers.base_streamer")
    return base.StreamerOutput(**fields)


def open_fingers() -> dict[str, Any]:
    """Finger input with the thumb open and no finger closed, as PicoStreamer sends it."""
    tips = np.zeros((25, 4, 4))
    tips[4, 0, 3] = 1.0
    return {"position": tips}


class ScriptedStreamer:
    """Activates teleop once, then holds both wrists at the calibration pose.

    `navigate_cmd` is [vx, vy, yaw rate, target yaw], as PicoStreamer builds it.
    """

    def __init__(self, navigate_cmd: tuple[float, float, float, float] = (0, 0, 0, 0)) -> None:
        self.navigate_cmd = list(navigate_cmd)
        self.reset_status()

    def reset_status(self) -> None:
        self._activation_sent = False

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    def get(self) -> Any:
        activate, self._activation_sent = not self._activation_sent, True
        return _streamer_output(
            ik_data={
                "left_wrist": np.eye(4),
                "right_wrist": np.eye(4),
                "left_fingers": open_fingers(),
                "right_fingers": open_fingers(),
            },
            control_data={
                "base_height_command": STANDING_HEIGHT,
                "navigate_cmd": list(self.navigate_cmd),
                "toggle_policy_action": False,
            },
            teleop_data={"toggle_activation": activate},
            data_collection_data={"toggle_data_collection": False, "toggle_data_abort": False},
            source="scripted",
        )


class VirtualPicoStreamer:
    """The virtual operator (flywheel_simple.tray.pico.operator) as a PICO streamer.

    Sees the scene as the operator would through the headset: tray, palms and
    base from MuJoCo, the scorer's report from the task. Reads the calibration
    the pipeline made at activation from its WristsPreProcessor (`bind`).

    With `style_base`, every attempt gets its own style, drawn from
    `style_seed_for(style_base, level, seed, attempt)` (`begin_attempt`); None
    plays the planner's targets as they are.
    """

    def __init__(
        self,
        env: Any,
        operator: VirtualOperator,
        planner_cfg: PlannerConfig,
        style_base: int | None = 0,
    ) -> None:
        self.env = env
        self.operator = operator
        self.planner_cfg = planner_cfg
        self.style_base = style_base
        self.version = operator_version(operator.cfg, planner_cfg)
        self._attempt: tuple[Condition, int] | None = None
        self._pre: Any = None
        self._last: tuple[float, PicoSignal] | None = None
        self.reset_status()

    def bind(self, pre_processor: Any) -> None:
        self._pre = pre_processor

    def begin_attempt(self, condition: Condition, attempt: int) -> None:
        """The session's next attempt; its style applies from the following reset."""
        self._attempt = (condition, attempt)

    def _style(self) -> tuple[Style | None, int | None]:
        if self.style_base is None or self._attempt is None:
            return None, None
        condition, attempt = self._attempt
        seed = style_seed_for(self.style_base, condition.level, condition.seed, attempt)
        return sample_style(seed), seed

    def reset_status(self) -> None:
        """New episode (SIMPLE's teleop reset): a planner for the task's current sample."""
        task = self.env.unwrapped.task
        if getattr(task, "sample", None) is not None:  # none before the env's first reset
            style, seed = self._style()
            planner = TrayPlanner(self.planner_cfg, task.cfg, task.sample)
            self.operator.reset(planner, style=style, style_seed=seed or 0)
        self._last = None

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    def episode_meta(self) -> dict[str, Any]:
        """The flywheel block's source fields for this episode (DA-35 AC 3)."""
        style, seed = self._style()
        return {
            "source_kind": "synthetic",
            "synthetic_tier": "S1",
            "action_quality": "planned",
            "operator_version": self.version,
            "style_base": self.style_base,
            "style_seed": seed,
            "style": None if style is None else dataclasses.asdict(style),
            "condition_attempt": None if self._attempt is None else self._attempt[1],
        }

    def attempt_notes(self) -> dict[str, Any]:
        """Operator stages and planner phases of this attempt, for attempts.jsonl."""
        return {
            "style_seed": self._style()[1],
            "timeline": [list(entry) for entry in self.operator.timeline],
            "abort_reason": self.operator.abort_reason,
        }

    @property
    def wants_reset(self) -> bool:
        return self._last is not None and self._last[1].reset

    def _calibration(self) -> Calibration | None:
        return calibration_of(self._pre)

    def signal(self) -> PicoSignal:
        """This step's signal. TeleopPolicy reads the streamer twice in the activation step
        (the second read calibrates); a second read at the same sim time repeats the
        first without the activation edge, as PicoStreamer's edge detection does."""
        from flywheel_simple.tray.simple_task import tray_state
        from flywheel_simple.wbc.drive import pelvis_pose

        sim = self.env.unwrapped
        t = float(sim.mjData.time)
        if self._last is not None and self._last[0] == t:
            return dataclasses.replace(self._last[1], activate=False)
        xy, yaw = pelvis_pose(self.env)
        signal = self.operator.step(
            tray_state(sim.mjModel, sim.mjData),
            Pose2D(float(xy[0]), float(xy[1]), yaw),
            sim.task.report,
            # Calibration happens on the activation step: read it from the next step on.
            None if self._last is None else self._calibration(),
        )
        self._last = (t, signal)
        return signal

    def get(self) -> Any:
        return pico_output(self.signal(), self.operator.cfg.grasp_name, source="virtual")


def calibration_of(pre_processor: Any) -> Calibration | None:
    """What WristsPreProcessor fixed at activation, or None before it calibrated."""
    pre = pre_processor
    if pre is None or not pre.robot_world_T_init_ee:
        return None
    frames = pre.robot.supplemental_info.hand_frame_names
    ee0 = tuple(np.array(pre.robot_world_T_init_ee[frames[s]]) for s in ("left", "right"))
    return Calibration(ee0=(ee0[0], ee0[1]), scale=float(pre.motion_scale))


def pico_output(s: PicoSignal, grasp: str, source: str) -> Any:
    """One step of controller input packed as PicoStreamer's StreamerOutput."""
    return _streamer_output(
        ik_data={
            "left_wrist": s.controllers[0],
            "right_wrist": s.controllers[1],
            "left_fingers": {"position": pico_fingers(s.closed[0], grasp)},
            "right_fingers": {"position": pico_fingers(s.closed[1], grasp)},
        },
        control_data={
            "base_height_command": STANDING_HEIGHT,
            "navigate_cmd": list(s.navigate_cmd),
            "toggle_policy_action": False,
        },
        teleop_data={"toggle_activation": s.activate},
        data_collection_data={"toggle_data_collection": False, "toggle_data_abort": False},
        source=source,
    )


def _install_clock(clock: SimClock) -> None:
    """Make SIMPLE's PICO agent module read `clock` wherever it calls `time.monotonic()`.

    The module's `time` is swapped process-wide, so only one clocked agent may
    live in a process (one env per worker anyway); a second, different clock is
    refused.
    """
    current = pico_decoupled_agent.time
    if isinstance(current, ClockedTime) and current.clock is not clock:
        raise RuntimeError("another SimClock already drives this process's PICO agent")
    pico_decoupled_agent.time = ClockedTime(clock)


class StreamerDecoupledAgent(PicoDecoupledAgent):  # type: ignore[misc]
    """PicoDecoupledAgent reading `streamer` instead of the PICO headset.

    With `clock`, the pipeline runs on simulated time (see flywheel_simple.tray.pico.clock);
    the session ticks it once per env step. Without, it keeps the wall clock. With
    `max_joint_step` (rad per control step), the retargeting IK moves no joint further
    than that per step (`limit_joint_step`); without, it keeps the URDF limits. With
    `lock_waist`, the retargeting IK solves the arms alone and the waist command stays
    at zero (`arms_only`); without, it moves the waist as SIMPLE's PICO agent does.
    """

    def __init__(
        self,
        robot: Any,
        streamer: Any,
        clock: SimClock | None = None,
        max_joint_step: float | None = None,
        lock_waist: bool = False,
    ) -> None:
        self._external_streamer = streamer
        self._lock_waist = lock_waist
        self.clock = clock
        if clock is not None:
            _install_clock(clock)
        super().__init__(robot)
        if max_joint_step is not None:
            limit_joint_step(self._teleop_policy.retargeting_ik.body_ik_solver, max_joint_step)

    def _init_pico_streamer(self) -> None:
        # No TCP server for the headset's video stream.
        self._streaming = None
        self._frame_buffer = None

    def _init_decoupled_policy(self) -> None:
        # Build SIMPLE's pipeline with no real device, which still creates the
        # wrist and finger pre-processors for body_control_device "pico", then
        # plug our streamer in where PicoStreamer would be.
        _stub_ik_visualizer()
        teleop_policy = importlib.import_module("decoupled_wbc.control.policy.teleop_policy")
        offline = functools.partial(teleop_policy.TeleopPolicy, enable_real_device=False)
        ik_module = importlib.import_module("decoupled_wbc.control.teleop.teleop_retargeting_ik")
        ik_class = ik_module.TeleopRetargetingIK
        ik = arms_only(ik_class) if self._lock_waist else ik_class
        with (
            mock.patch.object(teleop_policy, "TeleopPolicy", offline),
            mock.patch.object(ik_module, "TeleopRetargetingIK", ik),
        ):
            super()._init_decoupled_policy()
        streamer = self._teleop_policy.teleop_streamer
        if streamer.body_pre_processor is None:
            raise RuntimeError("teleop pipeline built without the wrist pre-processor")
        streamer.enable_real_device = True
        streamer.body_streamer = self._external_streamer
        self._pico_streamer = self._external_streamer
        bind = getattr(self._external_streamer, "bind", None)
        if bind is not None:
            bind(streamer.body_pre_processor)

    def reset_policy(self) -> None:
        """SIMPLE's reset, plus the calibration decoupled_wbc keeps across episodes.

        TeleopStreamer stays `is_calibrated` after the first activation, so in every
        later episode of a process the activation step already maps the controllers
        with the old calibration, and WristsPreProcessor appends its hands to
        `ee_name_list` again at every calibration. An episode then differed from
        the same episode run first in a fresh process from the activation step on
        (DA-35 task 10: identical up to step 165, apart after). Reset both to how a
        new pipeline starts.
        """
        super().reset_policy()
        streamer = self._teleop_policy.teleop_streamer
        streamer.is_calibrated = False
        pre = streamer.body_pre_processor
        if pre is not None:
            pre.calibration_ee_pose = {}
            pre.ee_name_list = []
            pre.robot_world_T_init_ee = {}
            pre.init_teleop_T_teleop_world = {}
            pre.init_teleop_T_init_ee = {}
            pre.latest_data = None

    def _poll_pico_buttons(self) -> None:
        # No controller buttons; a streamer that gives up (the virtual operator) asks
        # for the reset that holding both grips would.
        if getattr(self._external_streamer, "wants_reset", False):
            self._reset_requested = True
