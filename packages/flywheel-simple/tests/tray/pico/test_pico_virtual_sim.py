"""The virtual PICO operator in SIMPLE's teleop pipeline on the tray env (DA-35 task 5).

One episode at level 0, seed 0 through `run_session`: the operator activates,
plays TrayPlanner as controller poses, buttons and sticks, and the attempt ends
on check_success. About 2.5 min on rtx3060. Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/pico -m sim -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_pico_session_sim import MemoryExporter

pytestmark = pytest.mark.sim


def test_virtual_operator_episode_reaches_check_success(tmp_path: Path) -> None:
    from flywheel_simple.tray.pico.agent import StreamerDecoupledAgent, VirtualPicoStreamer
    from flywheel_simple.tray.pico.clock import ClockedTime, SimClock
    from flywheel_simple.tray.pico.conditions import ConditionQueue, parse_conditions
    from flywheel_simple.tray.pico.operator import OperatorConfig, VirtualOperator
    from flywheel_simple.tray.pico.session import make_teleop_env, run_session
    from flywheel_simple.tray.planner import PlannerConfig
    from simple.agents import pico_decoupled_agent

    # One clock drives SIMPLE's PICO agent module per process; reuse it if another
    # test module installed one.
    current = pico_decoupled_agent.time
    clock = current.clock if isinstance(current, ClockedTime) else SimClock()
    env = make_teleop_env(level=0, headless=True)
    operator = VirtualOperator(OperatorConfig.load())
    streamer = VirtualPicoStreamer(env, operator, PlannerConfig.load())
    agent = StreamerDecoupledAgent(env.unwrapped.task.robot, streamer, clock=clock)
    exporters: list[MemoryExporter] = []

    def make(root: Path, *_: Any) -> MemoryExporter:
        exporters.append(MemoryExporter(root))
        return exporters[-1]

    try:
        summary = run_session(
            env,
            agent,
            ConditionQueue(parse_conditions("0:0"), max_attempts=1),
            save_dir=tmp_path,
            operator="op-virtual",
            session="s-test",
            source_detail="virtual_teleop",
            make_exporter=make,
        )
    finally:
        agent.close()
        env.close()

    (attempt,) = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert attempt["outcome"] == "success", attempt
    assert attempt["steps_reached"] == 7
    phases = [name for name, _ in attempt["timeline"]]
    assert phases[0] == "engage" and "CARRY" in phases and "RELEASE" in phases
    assert summary.saved == 1
    # A frame holds the observation before its step, so the last one can still
    # miss the seventh flag that the final step raised.
    frames = exporters[0].saved[0]
    assert frames[-1]["observation.tray_steps"][:6].tolist() == [1.0] * 6
