"""S2 replays in SIMPLE's teleop pipeline on the tray env (DA-35 tasks 9-11).

Needs a parent batch recorded by the current virtual operator (default the
da35-virtual-3 smoke batch parents-smoke-1104 in fwdata/simple/tray/virtual/, or
$S2_PARENTS); skips without it. Parents are taken from its summary.json. Runs in
the SIMPLE venv, about 4 min on rtx3060:

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

PARENTS = Path(os.environ.get("S2_PARENTS", "fwdata/simple/tray/virtual/parents-smoke-1104"))
SHORT_STEPS = 700  # 14 s: activation, the walk to table A and the reach
ACTION_ARMS = [*range(15, 22), *range(29, 36)]  # arm joints of the 43-d action
# Level-1 conditions and gen seeds once drawn by sample_jobs (gen base 900).
X_CONDITION = {"level": 1, "seed": 204275, "gen_seed": 129588076}
Y_CONDITION = {"level": 1, "seed": 423796, "gen_seed": 550757015}


def parents() -> list[dict[str, Any]]:
    """Parents of the batch as summary.json lists them, with their `parent_id`."""
    rows = json.loads((PARENTS / "summary.json").read_text())["parents"]
    return [{**p, "parent_id": f"{PARENTS.name}/{p['shard']}/{p['episode_index']}"} for p in rows]


def variant_jobs() -> tuple[dict[str, Any], dict[str, Any]]:
    """Two variant jobs on the batch's last two parents (any parent serves)."""
    *_, y, x = parents()
    x_job = {"parent_id": x["parent_id"], **X_CONDITION}
    return x_job, {"parent_id": y["parent_id"], **Y_CONDITION}


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
    from flywheel_simple.tray.pico.operator import LOCK_WAIST, OperatorConfig
    from flywheel_simple.tray.pico.session import make_teleop_env
    from flywheel_simple.tray.s2.config import S2Config
    from flywheel_simple.tray.s2.streamer import ParentStore, S2Streamer
    from simple.agents import pico_decoupled_agent

    current = pico_decoupled_agent.time
    clock = current.clock if isinstance(current, ClockedTime) else SimClock()
    cfg, op_cfg = S2Config.load(), OperatorConfig.load()
    env = make_teleop_env(level=1, headless=True)
    streamer = S2Streamer(env, ParentStore(PARENTS, cfg), op_cfg, cfg)
    agent = StreamerDecoupledAgent(
        env.unwrapped.task.robot,
        streamer,
        clock=clock,
        max_joint_step=op_cfg.arm_step_max,
        lock_waist=LOCK_WAIST,
    )
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
    # The batch's first parent; the smoke's exact replay reproduced all 16 (replay-smoke-1104).
    parent = parents()[0]
    job = {"parent_id": parent["parent_id"], "level": parent["level"], "seed": parent["seed"]}
    job["gen_seed"] = 0
    (attempt,), _, (block,) = run(pipeline, tmp_path, [job], mode="exact")
    assert attempt["outcome"] == "success", attempt
    assert (block["source_kind"], block["synthetic_tier"]) == ("synthetic", "S2")
    assert block["parent_episode"] == job["parent_id"] and block["s2_mode"] == "exact"


def test_same_job_gives_the_same_variant_wherever_it_runs(
    pipeline: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    X, Y = variant_jobs()
    alone = run(pipeline, tmp_path / "a", [X], max_steps=SHORT_STEPS)[1][-1]
    attempts, saved, blocks = run(pipeline, tmp_path / "b", [Y, X], max_steps=SHORT_STEPS)
    after = saved[-1]
    # Lineage and the transform on every attempt and in the saved episode's block (AC 6).
    assert [a["parent_episode"] for a in attempts] == [Y["parent_id"], X["parent_id"]]
    assert all(a["transform"]["t_k"] and a["condition_distance"] for a in attempts)
    block = blocks[-1]
    assert (block["source_kind"], block["synthetic_tier"], block["action_quality"]) == (
        "synthetic",
        "S2",
        "planned",
    )
    assert block["parent_episode"] == X["parent_id"] and block["gen_seed"] == X["gen_seed"]
    assert block["generator_version"].startswith("da35-s2-") and block["transform"]["t_p"]
    assert block["split"] == "train" and block["level"] == X["level"]
    assert len(alone) == len(after) > 0
    # The retargeting IK's joint step limit (arm_step_max) holds in the variant too.
    arms = np.stack([f["action"] for f in after])[:, ACTION_ARMS]
    assert np.abs(np.diff(arms, axis=0)).max() <= 0.08 + 1e-6
    for key in ("action", "action.eef", "observation.state", "teleop.navigate_command"):
        np.testing.assert_array_equal(
            np.stack([f[key] for f in alone]), np.stack([f[key] for f in after]), err_msg=key
        )
