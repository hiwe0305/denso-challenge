"""S2 replays in SIMPLE's teleop pipeline on the tray env (DA-35 tasks 9-11).

Needs the parent batch parents-1103b (fwdata/simple/tray/virtual/, or
$S2_PARENTS); skips without it. Runs in the SIMPLE venv, about 4 min on rtx3060:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/s2 -m sim -v
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim

PARENTS = Path(os.environ.get("S2_PARENTS", "fwdata/simple/tray/virtual/parents-1103b"))
SHORT_STEPS = 700  # 14 s: activation, the walk to table A and the reach
# Two parents of parents-1103b and level-1 conditions drawn by sample_jobs (gen base 900).
X = {"parent_id": "parents-1103b/shard-10/0", "level": 1, "seed": 204275, "gen_seed": 129588076}
Y = {"parent_id": "parents-1103b/shard-07/4", "level": 1, "seed": 423796, "gen_seed": 550757015}


class MemoryExporter:
    """Gr00tDataExporter's methods the session uses, frames kept in memory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.saved: list[list[dict[str, Any]]] = []
        self._frames: list[dict[str, Any]] = []
        (root / "meta").mkdir(parents=True, exist_ok=True)
        (root / "meta" / "episodes.jsonl").write_text("")
        self._new()

    def _new(self) -> None:
        self._frames = []
        self.episode_buffer = {"episode_index": len(self.saved), "size": 0}

    def add_frame(self, frame: dict[str, Any]) -> None:
        self._frames.append(frame)
        self.episode_buffer["size"] += 1

    def save_episode(self) -> None:
        with (self.root / "meta" / "episodes.jsonl").open("a") as f:
            f.write(json.dumps({"episode_index": len(self.saved), "length": len(self._frames)}))
            f.write("\n")
        self.saved.append(self._frames)
        self._new()

    def skip_and_start_new_episode(self) -> None:
        self._new()

    def stop_video_writers(self) -> None:
        pass


@pytest.fixture(scope="module")
def pipeline() -> Iterator[tuple[Any, Any, Any]]:
    if not (PARENTS / "summary.json").exists():
        pytest.skip(f"parent batch {PARENTS} not here")
    from flywheel_simple.tray.pico.agent import StreamerDecoupledAgent
    from flywheel_simple.tray.pico.clock import ClockedTime, SimClock
    from flywheel_simple.tray.pico.operator import OperatorConfig
    from flywheel_simple.tray.pico.session import make_teleop_env
    from flywheel_simple.tray.s2.config import S2Config
    from flywheel_simple.tray.s2.streamer import ParentStore, S2Streamer
    from simple.agents import pico_decoupled_agent

    current = pico_decoupled_agent.time
    clock = current.clock if isinstance(current, ClockedTime) else SimClock()
    cfg = S2Config.load()
    env = make_teleop_env(level=1, headless=True)
    streamer = S2Streamer(env, ParentStore(PARENTS, cfg), OperatorConfig.load(), cfg)
    agent = StreamerDecoupledAgent(env.unwrapped.task.robot, streamer, clock=clock)
    yield env, agent, streamer
    agent.close()
    env.close()


def run(
    pipeline: tuple[Any, Any, Any],
    save_dir: Path,
    jobs: list[dict[str, Any]],
    mode: str = "variant",
    max_steps: int | None = None,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """Attempts, saved frames and flywheel blocks of one S2 session over `jobs`."""
    from flywheel_simple.tray.pico.conditions import ConditionQueue
    from flywheel_simple.tray.pico.session import run_session
    from flywheel_simple.tray.s2.jobs import S2Job
    from gymnasium.wrappers import TimeLimit

    env, agent, streamer = pipeline
    streamer.mode = mode
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

    queue = [S2Job(j["level"], j["seed"], j["parent_id"], j["gen_seed"]) for j in jobs]
    try:
        run_session(
            env, agent, ConditionQueue(queue, max_attempts=1), save_dir=save_dir,
            operator="op-s2", session="s-test", source_detail="s2", keep_failed=True,
            make_exporter=make,
        )  # fmt: skip
    finally:
        time_limit._max_episode_steps = limit
    attempts = [json.loads(x) for x in (save_dir / "attempts.jsonl").read_text().splitlines()]
    lines = (exporters[0].root / "meta" / "episodes.jsonl").read_text().splitlines()
    blocks = [json.loads(json.loads(x)["environment_config"])["flywheel"] for x in lines]
    return attempts, exporters[0].saved, blocks


def test_exact_replay_of_a_parent_reaches_check_success(
    pipeline: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    # Reproduced in the task-9 batch (replay-1103).
    job = {"parent_id": "parents-1103b/shard-00/2", "level": 0, "seed": 116, "gen_seed": 0}
    (attempt,), _, (block,) = run(pipeline, tmp_path, [job], mode="exact")
    assert attempt["outcome"] == "success", attempt
    assert (block["source_kind"], block["synthetic_tier"]) == ("synthetic", "S2")
    assert block["parent_episode"] == job["parent_id"] and block["s2_mode"] == "exact"


def test_same_job_gives_the_same_variant_wherever_it_runs(
    pipeline: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    alone = run(pipeline, tmp_path / "a", [X], max_steps=SHORT_STEPS)[1][-1]
    after = run(pipeline, tmp_path / "b", [Y, X], max_steps=SHORT_STEPS)[1][-1]
    assert len(alone) == len(after) > 0
    for key in ("action", "action.eef", "observation.state", "teleop.navigate_command"):
        np.testing.assert_array_equal(
            np.stack([f[key] for f in alone]), np.stack([f[key] for f in after]), err_msg=key
        )
