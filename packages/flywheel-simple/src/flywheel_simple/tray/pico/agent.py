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

from flywheel_simple.tray.pico.clock import ClockedTime, SimClock

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

    def _poll_pico_buttons(self) -> None:
        pass  # resets come from the session, not from controller buttons
