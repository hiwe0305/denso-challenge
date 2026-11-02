"""A teleop session on the tray env with a scripted streamer instead of PICO (DA-35 AC 1).

The scripted streamer activates teleop and holds the hands at the calibration
pose, so no attempt succeeds: each one times out. Runs in the SIMPLE venv with
PyAV importable (SIMPLE's PICO agent imports it):

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/pico -m sim -v

The LeRobot test also needs SIMPLE's `lerobot` extra (lerobot, datasets,
pyarrow) and is skipped without it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytestmark = pytest.mark.sim

MAX_STEPS = 250  # 5 s: release, stabilise, a short recording, time out
TABLE_HEIGHT = 0.85


class MemoryExporter:
    """Gr00tDataExporter's methods the session uses, keeping frames in memory."""

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
def env_and_agent() -> Iterator[tuple[Any, Any]]:
    from flywheel_simple.tray.pico.agent import ScriptedStreamer, StreamerDecoupledAgent
    from flywheel_simple.tray.pico.clock import SimClock
    from flywheel_simple.tray.pico.session import make_teleop_env

    env = make_teleop_env(level=0, headless=True, max_episode_steps=MAX_STEPS)
    # The clock replaces `time` in SIMPLE's agent module for the whole process,
    # so every test here shares this one clocked agent.
    agent = StreamerDecoupledAgent(env.unwrapped.task.robot, ScriptedStreamer(), clock=SimClock())
    yield env, agent
    agent.close()
    env.close()


def run(
    env_and_agent: tuple[Any, Any], save_dir: Path, conditions: str, keep: bool, **kwargs: Any
) -> Any:
    from flywheel_simple.tray.pico.conditions import ConditionQueue, parse_conditions
    from flywheel_simple.tray.pico.session import run_session

    env, agent = env_and_agent
    return run_session(
        env,
        agent,
        ConditionQueue(parse_conditions(conditions), max_attempts=1),
        save_dir=save_dir,
        operator="op-test",
        session="s-test",
        source_detail="teleop_scripted",
        keep_failed=keep,
        **kwargs,
    )


def attempts(save_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (save_dir / "attempts.jsonl").read_text().splitlines()]


def configs(root: Path) -> list[dict[str, Any]]:
    lines = (root / "meta" / "episodes.jsonl").read_text().splitlines()
    return [json.loads(json.loads(x)["environment_config"]) for x in lines]


def test_attempts_follow_the_conditions_and_failed_ones_are_kept_on_request(
    env_and_agent: tuple[Any, Any], tmp_path: Path
) -> None:
    exporters: list[MemoryExporter] = []

    def make(root: Path, *_: Any) -> MemoryExporter:
        exporters.append(MemoryExporter(root))
        return exporters[-1]

    summary = run(env_and_agent, tmp_path, "0:3,1:5", keep=True, make_exporter=make)

    log = attempts(tmp_path)
    assert [(a["level"], a["seed"]) for a in log] == [(0, 3), (1, 5)]
    assert [a["outcome"] for a in log] == ["timeout", "timeout"]
    assert [a["episode_index"] for a in log] == [0, 1]
    assert all(a["recorded_frames"] > 0 for a in log)
    assert (summary.attempts, summary.successes, summary.saved) == (2, 0, 2)
    assert json.loads((tmp_path / "sessions.jsonl").read_text())["attempts"] == 2

    (exporter,) = exporters
    for config, (level, seed) in zip(configs(exporter.root), [(0, 3), (1, 5)]):
        assert (config["flywheel"]["level"], config["flywheel"]["seed"]) == (level, seed)
        assert config["flywheel"]["outcome"] == "timeout"
        assert config["flywheel"]["source_detail"] == "teleop_scripted"
        # the env really reset to this condition
        assert (config["tray"]["sample"]["level"], config["tray"]["sample"]["seed"]) == (
            level,
            seed,
        )

    frames = exporter.saved[0]
    assert len(frames) == log[0]["recorded_frames"]
    tray = np.stack([f["observation.tray_pose"] for f in frames])
    assert np.all(np.abs(tray[:, 2] - TABLE_HEIGHT) < 0.02)  # still on table A
    assert np.stack([f["observation.part_pos"] for f in frames]).shape == (len(frames), 18)
    assert np.stack([f["observation.tray_steps"] for f in frames]).shape == (len(frames), 7)
    for key in ("action", "action.eef", "teleop.navigate_command", "observation.images.ego_view"):
        assert key in frames[0]
    assert frames[0]["action"].shape == (43,)
    assert frames[0]["action.eef"].shape == (14,)


def test_failed_attempts_are_logged_but_not_saved_by_default(
    env_and_agent: tuple[Any, Any], tmp_path: Path
) -> None:
    exporters: list[MemoryExporter] = []

    def make(root: Path, *_: Any) -> MemoryExporter:
        exporters.append(MemoryExporter(root))
        return exporters[-1]

    run(env_and_agent, tmp_path, "0:4", keep=False, make_exporter=make)

    log = attempts(tmp_path)
    assert [(a["seed"], a["outcome"], a["episode_index"]) for a in log] == [(4, "timeout", None)]
    assert log[0]["recorded_frames"] > 0
    assert exporters[0].saved == []


def test_lerobot_dataset_has_the_tray_columns(
    env_and_agent: tuple[Any, Any], tmp_path: Path
) -> None:
    pytest.importorskip("datasets", reason="SIMPLE's lerobot extra is not installed")
    pq = pytest.importorskip("pyarrow.parquet")

    run(env_and_agent, tmp_path, "0:6", keep=True)

    root = next(p.parents[1] for p in tmp_path.glob("**/meta/episodes.jsonl"))
    assert configs(root)[0]["flywheel"]["seed"] == 6
    table = pq.read_table(next(root.glob("data/**/episode_000000.parquet")))
    for key in ("observation.tray_pose", "observation.part_pos", "observation.tray_steps"):
        assert key in table.column_names


def test_clocked_runs_are_identical_and_faster_than_real_time(
    env_and_agent: tuple[Any, Any], tmp_path: Path
) -> None:
    runs: list[list[dict[str, Any]]] = []
    for k in range(2):
        exporters: list[MemoryExporter] = []

        def make(root: Path, *_: Any) -> MemoryExporter:
            exporters.append(MemoryExporter(root))
            return exporters[-1]

        run(env_and_agent, tmp_path / str(k), "1:7", keep=True, make_exporter=make)
        runs.append(exporters[0].saved[0])
        (attempt,) = attempts(tmp_path / str(k))
        # MAX_STEPS steps of 0.02 s sim time in less wall time
        assert attempt["wall_s"] < MAX_STEPS * 0.02

    first, second = runs
    assert len(first) == len(second) > 0
    for key in ("action", "action.eef", "observation.state", "observation.tray_pose"):
        np.testing.assert_array_equal(
            np.stack([f[key] for f in first]), np.stack([f[key] for f in second]), err_msg=key
        )
