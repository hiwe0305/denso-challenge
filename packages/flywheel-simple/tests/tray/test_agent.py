"""The scripted planner carries the tray in sim (DA-33 AC 3, target 6/11).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_agent.py -m sim -v
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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
