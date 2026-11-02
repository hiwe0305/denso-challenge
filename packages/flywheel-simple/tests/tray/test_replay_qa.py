"""Recorded planner episodes replay through SIMPLE's replay-decoupled-wbc (DA-33 AC 4, Task 7).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m pytest packages/flywheel-simple/tests/tray/test_replay_qa.py -m sim -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.sim


def test_reset_from_a_recorded_state_dict_rebuilds_its_episode() -> None:
    from flywheel_simple.tray.simple_task import make_env

    env = make_env(seed=0, level=0)
    try:
        env.reset(seed=5, options={"level": 1})
        recorded = json.loads(json.dumps(env.unwrapped.task.state_dict(), default=float))
        env.reset(seed=None, options={"state_dict": recorded, "dr_level": 0})
        sample = env.unwrapped.task.sample
        assert (sample.seed, sample.level) == (5, 1)
    finally:
        env.close()


def test_two_recorded_episodes_replay_with_the_same_outcome(tmp_path: Path) -> None:
    from flywheel_simple.tray.generate import generate, read_log, shard_dir
    from flywheel_simple.tray.replay_qa import replay_qa

    summary = generate(tmp_path / "gen", n_attempts=2, level=1, seed_start=1)
    assert summary.recorded == 2, read_log(shard_dir(tmp_path / "gen", 0) / "gen_log.jsonl")
    verdicts = replay_qa(shard_dir(tmp_path / "gen", 0) / "raw", tmp_path / "replay")
    assert [v.seed for v in verdicts] == [1, 2]
    assert all(v.passed for v in verdicts), verdicts
    assert all(v.tray_error_m is not None and v.tray_error_m < 0.02 for v in verdicts)
