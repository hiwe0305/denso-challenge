"""SIMPLE's PICO teleop agent with the headset swapped for any streamer.

`PicoDecoupledAgent` runs PicoStreamer -> TeleopPolicy (wrist pre-processor,
TeleopRetargetingIK with the waist) -> G1DecoupledWholeBodyPolicy. Here the
same pipeline reads a streamer we pass in: the scripted one below for tests
without a headset, and later the S2 replay streamer (DA-35 task 6). No VR video
server, no XRoboToolkit, no controller buttons.

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
from flywheel_simple.tray.pico.operator import Calibration, PicoSignal, VirtualOperator
from flywheel_simple.tray.pico.virtual import pico_fingers
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
    """

    def __init__(self, env: Any, operator: VirtualOperator, planner_cfg: PlannerConfig) -> None:
        self.env = env
        self.operator = operator
        self.planner_cfg = planner_cfg
        self._pre: Any = None
        self._last: tuple[float, PicoSignal] | None = None
        self.reset_status()

    def bind(self, pre_processor: Any) -> None:
        self._pre = pre_processor

    def reset_status(self) -> None:
        """New episode (SIMPLE's teleop reset): a planner for the task's current sample."""
        task = self.env.unwrapped.task
        if getattr(task, "sample", None) is not None:  # none before the env's first reset
            self.operator.reset(TrayPlanner(self.planner_cfg, task.cfg, task.sample))
        self._last = None

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    def attempt_notes(self) -> dict[str, Any]:
        """Operator stages and planner phases of this attempt, for attempts.jsonl."""
        return {
            "timeline": [list(entry) for entry in self.operator.timeline],
            "abort_reason": self.operator.abort_reason,
        }

    @property
    def wants_reset(self) -> bool:
        return self._last is not None and self._last[1].reset

    def _calibration(self) -> Calibration | None:
        pre = self._pre
        if pre is None or not pre.robot_world_T_init_ee:
            return None
        frames = pre.robot.supplemental_info.hand_frame_names
        ee0 = tuple(np.array(pre.robot_world_T_init_ee[frames[s]]) for s in ("left", "right"))
        return Calibration(ee0=(ee0[0], ee0[1]), scale=float(pre.motion_scale))

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
        s = self.signal()
        grasp = self.operator.cfg.grasp_name
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
            source="virtual",
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
    the session ticks it once per env step. Without, it keeps the wall clock.
    """

    def __init__(self, robot: Any, streamer: Any, clock: SimClock | None = None) -> None:
        self._external_streamer = streamer
        self.clock = clock
        if clock is not None:
            _install_clock(clock)
        super().__init__(robot)

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
        with mock.patch.object(teleop_policy, "TeleopPolicy", offline):
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

    def _poll_pico_buttons(self) -> None:
        # No controller buttons; a streamer that gives up (the virtual operator) asks
        # for the reset that holding both grips would.
        if getattr(self._external_streamer, "wants_reset", False):
            self._reset_requested = True
