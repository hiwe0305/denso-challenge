"""The tray task on the jig scene, through SIMPLE (DA-41 AC 1, 5).

The jig env resets with the target fixed on table B and the jig in the scene; the
scripted planner carries the tray into the jig. Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_jig_task_sim.py -m sim -v
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.sim


@pytest.fixture(scope="module")
def env() -> Iterator[Any]:
    from flywheel_simple.tray.jig_task import make_env

    e = make_env(seed=0)
    yield e
    e.close()


def run(env: Any, seed: int, level: int) -> Any:
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    return run_episode(env, TrayAgent(env, PlannerConfig.load()), seed=seed, level=level)


@pytest.mark.parametrize(("level", "seed"), [(0, 0), (1, 1279), (2, 125195)])
def test_reset_puts_the_target_on_the_jig_and_keeps_the_rest_of_the_episode(
    env: Any, level: int, seed: int
) -> None:
    from flywheel_simple.tray import TrayConfig
    from flywheel_simple.tray.jig import JigConfig, guide_boxes, sample_jig_episode
    from flywheel_simple.tray.randomize import sample_episode

    env.reset(seed=seed, options={"level": level})
    task, sim = env.unwrapped.task, env.unwrapped.mujoco
    cfg, jig = TrayConfig.load(), JigConfig.load()
    assert task.sample == sample_jig_episode(cfg, jig, level, seed)
    old = sample_episode(cfg, level, seed)
    assert (task.sample.tray_pose, task.sample.robot_spawn) == (old.tray_pose, old.robot_spawn)
    t = task.target_pose
    assert task.tracker.sample.target_pose == t
    privileged = task.privileged_state(sim)["target_pose"]
    assert privileged == pytest.approx([t.x, t.y, t.yaw])
    model = sim.mjModel
    names = {model.geom(g).name for g in range(model.ngeom)}
    assert {b.name for b in guide_boxes(cfg, jig)} | {"jig_pad"} <= names
    # The zone is drawn at the jig target, as the policy sees it (MJCF keeps 6 digits).
    zone = sim.mjData.body("target_zone").xpos
    assert zone[:2] == pytest.approx([t.x, t.y], abs=1e-5)
    assert task.state_dict()["tray"]["jig"]["height"] == jig.height


def test_planner_lowers_the_tray_into_the_jig_at_level0_seed0(env: Any) -> None:
    from flywheel_simple.tray import TrayConfig

    result = run(env, seed=0, level=0)
    # The env terminates on success, which may come before the planner reaches DONE.
    assert result.success and result.failure is None, result
    assert "LOWER" in [p for p, _ in result.phases]
    data, t = env.unwrapped.mujoco.mjData, env.unwrapped.task.target_pose
    tray = data.body("tray")
    err = math.hypot(tray.xpos[0] - t.x, tray.xpos[1] - t.y)
    assert err <= TrayConfig.load().target_pos_tol


def test_planner_succeeds_on_most_level1_seeds_on_the_jig_scene(env: Any) -> None:
    # Measured on the laptop (docs/g0/tray/jig.md 4.3): seeds 1-6 give 4 of 6 (seed 3
    # times out in RELEASE, seed 5 ends 6 cm towards the open robot side), as on the
    # scene without the jig (test_agent.py: 5 of 6, require 4). Require 4: a large
    # regression fails, a seed swapping outcome with another does not.
    results = {seed: run(env, seed=seed, level=1) for seed in range(1, 7)}
    assert sum(r.success for r in results.values()) >= 4, results
