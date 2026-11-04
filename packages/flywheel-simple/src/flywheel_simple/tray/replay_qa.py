"""Replay recorded episodes through SIMPLE's replay-decoupled-wbc as QA (DA-33 Task 7, AC 4).

The replay starts each episode as SIMPLE's eval does (scene rebuilt from the
recorded environment_config, `robot.stabilized` wait under the WBC default pose)
and feeds only the recorded `action` upper-body joints and
`teleop.navigate_command` to the decoupled WBC: what a policy trained on this
data would command. An episode passes when the replay succeeds by
`check_success` and the replayed tray comes to rest within TRAY_TOL_M and
YAW_TOL_DEG (mod 180 deg, D-14) of the recorded final pose.

The CLI runs in a subprocess on sim time (`flywheel_simple.tray.run`, D-24),
without recording a new dataset: the release exports the raw episodes that pass
(D-24). The tray env appends each replayed episode's outcome to the file named
by OUTCOMES_ENV; SIMPLE's own `meta/replay.txt` only has success per episode.

SIMPLE's replay CLI catches every exception, prints "An error occurred" and exits
0 (an EGL or offscreen framebuffer failure when the GPU is full), so a crashed
replay leaves recorded episodes without an outcome. Those are not QA verdicts:
`replay_qa` then raises ReplayIncomplete and writes no replay_qa.jsonl, so the
export refuses the shard until its replay runs again.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.tray.generate import read_log

ENV_ID = "simple/G1WholebodyTrayTransferTeleop-v0"
OUTCOMES_ENV = "FLYWHEEL_TRAY_OUTCOMES"  # = simple_task.OUTCOMES_ENV (that module needs SIMPLE)
TRAY_TOL_M = 0.02
YAW_TOL_DEG = 3.0


class ReplayIncomplete(RuntimeError):
    """The replay produced no outcome for some recorded episodes: a harness failure."""


@dataclass(frozen=True)
class ReplayVerdict:
    episode: int
    seed: int
    success: bool
    tray_error_m: float | None
    yaw_error_deg: float | None
    passed: bool
    reason: str  # "pass", "not_replayed", "not_success", "tray_moved"


def yaw_of(quat_wxyz: Sequence[float]) -> float:
    w, x, y, z = quat_wxyz
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def yaw_gap_deg(a: float, b: float) -> float:
    """Smallest |a - b| modulo pi (the tray is symmetric under a half turn, D-14), degrees."""
    gap = (a - b) % math.pi
    return math.degrees(min(gap, math.pi - gap))


def verdict(
    episode: int,
    seed: int,
    recorded_pose: Sequence[float],
    outcome: Mapping[str, Any] | None,
) -> ReplayVerdict:
    """Compare a replay outcome with the recorded final tray pose (pos xyz, quat wxyz)."""
    if outcome is None:
        return ReplayVerdict(episode, seed, False, None, None, False, "not_replayed")
    error = float(np.linalg.norm(np.asarray(outcome["tray_pos"]) - np.asarray(recorded_pose[:3])))
    yaw = yaw_gap_deg(yaw_of(outcome["tray_quat"]), yaw_of(recorded_pose[3:7]))
    success = bool(outcome["success"])
    if not success:
        reason = "not_success"
    elif error > TRAY_TOL_M or yaw > YAW_TOL_DEG:
        reason = "tray_moved"
    else:
        reason = "pass"
    return ReplayVerdict(
        episode, seed, success, round(error, 4), round(yaw, 2), reason == "pass", reason
    )


def recorded_finals(raw_root: Path) -> dict[int, tuple[int, list[float]]]:
    """Episode index -> (seed, last observation.tray_pose) of a recorded dataset."""
    pq = importlib.import_module("pyarrow.parquet")
    out: dict[int, tuple[int, list[float]]] = {}
    for entry in read_log(raw_root / "meta" / "episodes.jsonl"):
        index = int(entry["episode_index"])
        seed = int(json.loads(entry["environment_config"])["tray"]["sample"]["seed"])
        chunk = f"chunk-{index // 1000:03d}"
        table = pq.read_table(raw_root / "data" / chunk / f"episode_{index:06d}.parquet")
        out[index] = (seed, list(table.column("observation.tray_pose")[-1].as_py()))
    return out


def run_replay(raw_root: Path, work: Path, python: str = sys.executable) -> Path:
    """Replay every episode of raw_root (no new dataset); returns the outcomes file."""
    work.mkdir(parents=True, exist_ok=True)
    outcomes = work / "replay_outcomes.jsonl"
    outcomes.unlink(missing_ok=True)
    cmd = [python, "-m", "flywheel_simple.tray.run", "replay-decoupled-wbc", ENV_ID]
    cmd += ["--data-dir", str(raw_root), "--sim-mode", "mujoco", "--headless", "--no-webrtc"]
    cmd += ["--render-hz", "50", "--no-record", "--save-dir", str(work / "unused")]
    env = {**os.environ, OUTCOMES_ENV: str(outcomes)}
    with (work / "replay.log").open("w") as log:
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    return outcomes


def replay_qa(raw_root: Path, work: Path) -> list[ReplayVerdict]:
    """Replay raw_root and judge each recorded episode; writes work/replay_qa.jsonl."""
    (work / "replay_qa.jsonl").unlink(missing_ok=True)
    outcomes = {int(o["seed"]): o for o in read_log(run_replay(raw_root, work))}
    verdicts = [
        verdict(index, seed, pose, outcomes.get(seed))
        for index, (seed, pose) in sorted(recorded_finals(raw_root).items())
    ]
    missing = [v.episode for v in verdicts if v.reason == "not_replayed"]
    if missing:
        log = work / "replay.log"
        errors = [line for line in log.read_text().splitlines() if "An error occurred" in line]
        raise ReplayIncomplete(
            f"no replay outcome for {len(missing)}/{len(verdicts)} episodes {missing[:10]}"
            f" of {raw_root}: {errors[-1] if errors else 'see ' + str(log)}; replay the shard again"
        )
    (work / "replay_qa.jsonl").write_text("".join(json.dumps(v.__dict__) + "\n" for v in verdicts))
    return verdicts
