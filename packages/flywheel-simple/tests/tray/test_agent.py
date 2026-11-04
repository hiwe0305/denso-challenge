"""The scripted planner carries the tray in sim (DA-33 AC 3, target 6/11).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_agent.py -m sim -v
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim


@pytest.fixture(scope="module")
def env() -> Iterator[Any]:
    from flywheel_simple.tray.simple_task import make_env

    e = make_env(seed=0)
    yield e
    e.close()


def run(env: Any, seed: int, level: int) -> Any:
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    return run_episode(env, TrayAgent(env, PlannerConfig.load()), seed=seed, level=level)


def test_planner_carries_the_tray_at_level0_seed0(env: Any) -> None:
    result = run(env, seed=0, level=0)
    assert result.success and result.failure is None, result
    assert result.sim_s < 90


def test_planner_succeeds_on_most_level1_train_seeds(env: Any) -> None:
    # The planner succeeds on ~84 % of level 1 seeds (80/95 on rtx3060, D-24); seeds 1-6
    # give 5 of 6 (seed 3 tilts the tray as it drops). Require 4: a large regression
    # fails, a seed swapping outcome with another does not.
    results = {seed: run(env, seed=seed, level=1) for seed in range(1, 7)}
    assert sum(r.success for r in results.values()) >= 4, results


def test_arm_commands_move_at_most_arm_step_max_per_step(env: Any) -> None:
    # Without the IK's velocity limit the palm-up hold (D-25) made the arm action jump up
    # to 0.28 rad in one step at REACH (docs/g0/tray/wrist-jump.md); a whole episode,
    # anchoring the IK included, must now stay within arm_step_max.
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    cfg = PlannerConfig.load()
    agent = TrayAgent(env, cfg)
    model = agent.ctrl.model
    upper = list(model.get_joint_group_indices("upper_body"))
    arms = [upper.index(i) for i in model.get_joint_group_indices("arms")]
    goals: list[Any] = []

    def on_frame(obs: Any, info: Any, record: dict[str, Any]) -> None:
        goals.append(np.asarray(record["goal_upper_body"], float)[arms])

    run_episode(env, agent, seed=1, level=1, on_frame=on_frame)
    steps = np.abs(np.diff(np.array(goals), axis=0))
    assert len(arms) == 14 and len(goals) > 500
    assert steps.max() <= cfg.arm_step_max + 1e-6, (steps.max(), np.argmax(steps.max(axis=1)))


def test_posture_changes_go_through_joint_transits(env: Any) -> None:
    # Planner-6 (D-29): the raise and the turn to the palm-up pose each solve one IK goal
    # and follow a quintic to it; the goal's wrists are on the commanded targets.
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    agent = TrayAgent(env, PlannerConfig.load())
    result = run_episode(env, agent, seed=1, level=1)
    assert [t["transit"] for t in agent.transits] == ["APPROACH_A.1", "REACH.0"], agent.transits
    for t in agent.transits:
        assert t["steps"] >= 30  # smooth_min_s at 50 Hz
        for side in ("left", "right"):
            assert t[side]["error"] < 0.01, t  # m + 0.1 m/rad
    assert result.success, result
