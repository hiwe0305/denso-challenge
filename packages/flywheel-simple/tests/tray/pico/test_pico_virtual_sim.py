"""The virtual PICO operator in SIMPLE's teleop pipeline on the tray env (DA-35 tasks 5, 6).

Runs in the SIMPLE venv, about 5 min on rtx3060:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/pico -m sim -v
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_pico_session_sim import MemoryExporter

pytestmark = pytest.mark.sim

SHORT_STEPS = 700  # 14 s: stabilise, activate, walk to table A and start reaching
# Arm joints in SIMPLE's 43-d action (left then right arm, 7 each).
ACTION_ARMS = [*range(15, 22), *range(29, 36)]


@pytest.fixture(scope="module")
def env_agent_streamer() -> Iterator[tuple[Any, Any, Any]]:
    from flywheel_simple.tray.pico.agent import StreamerDecoupledAgent, VirtualPicoStreamer
    from flywheel_simple.tray.pico.clock import ClockedTime, SimClock
    from flywheel_simple.tray.pico.operator import OperatorConfig, VirtualOperator
    from flywheel_simple.tray.pico.session import make_teleop_env
    from flywheel_simple.tray.planner import PlannerConfig
    from simple.agents import pico_decoupled_agent

    # One clock drives SIMPLE's PICO agent module per process; reuse it if another
    # test module installed one.
    current = pico_decoupled_agent.time
    clock = current.clock if isinstance(current, ClockedTime) else SimClock()
    env = make_teleop_env(level=0, headless=True)
    cfg = OperatorConfig.load()
    streamer = VirtualPicoStreamer(env, VirtualOperator(cfg), PlannerConfig.load())
    agent = StreamerDecoupledAgent(
        env.unwrapped.task.robot, streamer, clock=clock, max_joint_step=cfg.arm_step_max
    )
    yield env, agent, streamer
    agent.close()
    env.close()


def run(
    env_agent_streamer: tuple[Any, Any, Any],
    save_dir: Path,
    conditions: str,
    style_base: int | None,
    max_steps: int | None = None,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """Attempts, saved frames and saved flywheel blocks of one session."""
    from flywheel_simple.tray.pico.conditions import ConditionQueue, parse_conditions
    from flywheel_simple.tray.pico.session import run_session
    from gymnasium.wrappers import TimeLimit

    env, agent, streamer = env_agent_streamer
    streamer.style_base = style_base
    time_limit = env
    while not isinstance(time_limit, TimeLimit):
        time_limit = time_limit.env
    limit = time_limit._max_episode_steps
    if max_steps is not None:
        time_limit._max_episode_steps = max_steps
    exporters: list[MemoryExporter] = []

    def make(root: Path, *_: Any) -> MemoryExporter:
        exporters.append(MemoryExporter(root))
        return exporters[-1]

    try:
        run_session(
            env,
            agent,
            ConditionQueue(parse_conditions(conditions), max_attempts=1),
            save_dir=save_dir,
            operator="op-virtual",
            session="s-test",
            source_detail="virtual_teleop",
            keep_failed=True,
            make_exporter=make,
        )
    finally:
        time_limit._max_episode_steps = limit
    attempts = [json.loads(x) for x in (save_dir / "attempts.jsonl").read_text().splitlines()]
    lines = (exporters[0].root / "meta" / "episodes.jsonl").read_text().splitlines()
    blocks = [json.loads(json.loads(x)["environment_config"])["flywheel"] for x in lines]
    return attempts, exporters[0].saved, blocks


def test_virtual_operator_episode_reaches_check_success(
    env_agent_streamer: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    # A condition that passed in the parent batch parents-1103b (episodes are
    # deterministic); about one in five conditions fails with the D-25 hold.
    (attempt,), (frames,), (block,) = run(env_agent_streamer, tmp_path, "0:100", style_base=0)
    assert attempt["outcome"] == "success", attempt
    assert attempt["steps_reached"] == 7
    phases = [name for name, _ in attempt["timeline"]]
    assert phases[0] == "engage" and "CARRY" in phases and "RELEASE" in phases
    # A frame holds the observation before its step, so the last one can still
    # miss the seventh flag that the final step raised.
    assert frames[-1]["observation.tray_steps"][:6].tolist() == [1.0] * 6
    assert (block["source_kind"], block["synthetic_tier"]) == ("synthetic", "S1")
    assert (block["source_detail"], block["action_quality"]) == ("virtual_teleop", "planned")
    assert block["style_seed"] == attempt["style_seed"] and block["style"]["omega"] > 0
    assert block["operator_version"].startswith("da35-virtual-")
    # The retargeting IK's step limit (arm_step_max 0.08) holds over the whole episode,
    # activation included: DA-03 QA flags an arm step over 0.0869 (action_jump.arm).
    arms = np.stack([f["action"] for f in frames])[:, ACTION_ARMS]
    steps = np.abs(np.diff(arms, axis=0))
    assert steps.max() <= 0.08 + 1e-6, (steps.max(), np.unravel_index(steps.argmax(), steps.shape))


def test_same_condition_and_style_seed_give_the_same_episode(
    env_agent_streamer: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    runs = [
        run(env_agent_streamer, tmp_path / str(k), "1:7", style_base=base, max_steps=SHORT_STEPS)
        for k, base in enumerate((0, 0, 1))
    ]
    (first, second, other) = [frames for _, (frames,), _ in runs]
    assert len(first) == len(second) > 0
    for key in ("action", "action.eef", "observation.state", "teleop.navigate_command"):
        np.testing.assert_array_equal(
            np.stack([f[key] for f in first]), np.stack([f[key] for f in second]), err_msg=key
        )
    # another style seed: another wrist path
    n = min(len(first), len(other))
    eef = [np.stack([f["action.eef"] for f in frames[:n]])[:, :3] for frames in (first, other)]
    assert np.abs(eef[0] - eef[1]).max() > 0.005
