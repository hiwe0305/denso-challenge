"""The replay's per-step trace and its last-command hold, on a fake sim (DA-17 task 6)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from flywheel_simple.replay.run import hold_agent_class, recorder_class

UID = "g1_wholebody_locomotion_pick_between_tables_teleop"
NAMES = [f"j{i}" for i in range(32)]
STEPS = 6


class Wrapper:
    """The part of gymnasium.Wrapper that OutcomeRecorder uses."""

    def __init__(self, env: Any) -> None:
        self.env = env

    @property
    def unwrapped(self) -> Any:
        return self.env.unwrapped


class Body:
    def __init__(self, xyz: list[float], quat: list[float] | None = None) -> None:
        self.xpos = np.asarray(xyz, dtype=float)
        self.xquat = np.asarray(quat or [1.0, 0.0, 0.0, 0.0], dtype=float)


class FakeSim:
    """SonicLocoManipEnv as the trace reads it: bodies, contacts, task, _success.

    Body ids: 0 pelvis, 1 the target `cracker_box`, 2 `right_hand_palm_link`, 3 the
    container `brasket`, 4 `table2`. Geom i belongs to body i. Each step the base
    walks 0.1 m along -x; the hand holds the box on steps 1-2; the box sits on the
    container from step 4 on, and `_success` turns true at `success_at`.
    """

    BODIES = ["pelvis", "cracker_box", "right_hand_palm_link", "brasket", "table2"]

    def __init__(self, success_at: int | None = None) -> None:
        self.success_at = success_at
        self.unwrapped = self
        self.steps = 0
        self._success = False
        self.task = SimpleNamespace(
            uid=UID, reward=0.0,
            target=SimpleNamespace(asset=SimpleNamespace(label="cracker_box")),
            container=SimpleNamespace(asset=SimpleNamespace(label="brasket")),
        )  # fmt: skip
        self.mjModel = SimpleNamespace(
            geom=lambda g: SimpleNamespace(bodyid=g),
            body=lambda b: SimpleNamespace(name=self.BODIES[b]),
        )
        self.mujoco = SimpleNamespace(get_robot_qpos=self.qpos, mj_objects={})
        self._place()

    def _place(self) -> None:
        k = self.steps
        yaw = np.pi / 2  # quaternion of a quarter turn about z
        bodies = {
            "pelvis": Body([-0.64 - 0.1 * k, 0.0, 0.78], [np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)]),
            "cracker_box": Body([-0.31 - 0.2 * k, -0.02, 0.76]),
            "brasket": Body([-2.47, 0.16, 0.66]),
        }
        pairs = [(1, 2)] if k in (1, 2) else []
        pairs += [(1, 3)] if k >= 4 else []
        contacts = [SimpleNamespace(geom1=a, geom2=b) for a, b in pairs]
        self.mjData = SimpleNamespace(
            body=lambda name: bodies[name], ncon=len(contacts), contact=contacts, time=0.02 * k
        )
        self.mujoco.mj_objects = {"target": bodies["cracker_box"], "container": bodies["brasket"]}

    def qpos(self) -> dict[str, float]:
        return {n: 0.01 * self.steps for n in NAMES[:31]}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> Any:
        self.steps, self._success = 0, False
        self._place()
        return {}, {}

    def step(self, action: Any) -> Any:
        self.steps += 1
        self._place()
        self._success = self.success_at is not None and self.steps >= self.success_at
        self.task.reward = 0.04 * max(0, self.steps - 3)
        return {}, 0.0, self._success, False, {}

    def close(self) -> None:
        pass


def env_conf(uid: str = UID) -> dict[str, Any]:
    spatial = {"g1_sonic": {"position": [-0.644, 0.0, 0.0]},
               "container_0": {"position": [-2.472, 0.159, 0.662]},
               "0": {"position": [-0.312, -0.02, 0.763]}}
    return {"uid": uid, "dr_state_dict": {"target": {"uid": "0"}, "spatial": spatial}}


def dataset(root: Path, uid: str = UID) -> Path:
    """One episode of STEPS + 1 recorded 32-D states, and its environment_config."""
    (root / "meta").mkdir(parents=True)
    info = {"chunks_size": 1000,
            "data_path": "data/chunk-000/episode_{episode_index:06d}.parquet"}
    (root / "meta" / "info.json").write_text(json.dumps(info))
    row = {"episode_index": 0, "length": STEPS + 1, "environment_config": json.dumps(env_conf(uid))}
    (root / "meta" / "episodes.jsonl").write_text(json.dumps(row) + "\n")
    states = [[0.01 * k] * 32 for k in range(STEPS + 1)]
    path = root / "data" / "chunk-000" / "episode_000000.parquet"
    path.parent.mkdir(parents=True)
    pq.write_table(pa.table({"states": states}), path)
    return root


def replay(
    tmp_path: Path, trace: Path | None, *, uid: str = UID, success_at: int | None = 4,
    hold_steps: int = 0, steps: int = STEPS,
) -> tuple[dict[str, Any], FakeSim]:
    """What SIMPLE's CLI does with the env: the uid override, reset, `steps` steps, close."""
    data = dataset(tmp_path / "data", uid)
    out = tmp_path / "outcomes.jsonl"
    sim = FakeSim(success_at)
    env = recorder_class(Wrapper)(sim, data, out, NAMES, trace=trace, hold_steps=hold_steps)
    conf = env_conf(uid)
    conf["uid"] = UID  # the CLI overrides a mismatched uid before reset
    env.reset(options={"state_dict": conf, "task_id": "episode_0", "dr_level": None})
    for _ in range(steps):
        _, _, terminated, _, _ = env.step(None)
        if terminated:
            break
    env.close()
    return json.loads(out.read_text()), sim


def test_trace_off_by_default_keeps_outcomes_unchanged(tmp_path: Path) -> None:
    line, _ = replay(tmp_path, None)
    assert sorted(line) == sorted([
        "episode_index", "success", "state_error_by_group", "hand_event_offset_steps",
        "state_error_peak_frame_by_group", "replayed_frames", "recorded_frames",
    ])  # fmt: skip
    assert line["success"] is True and line["replayed_frames"] == 4
    assert not list(tmp_path.glob("*.trace.jsonl"))


def test_trace_writes_reset_row_then_one_row_per_step(tmp_path: Path) -> None:
    trace = tmp_path / "t.trace.jsonl"
    line, _ = replay(tmp_path, trace, success_at=None)
    rows = [json.loads(r) for r in trace.read_text().splitlines()]
    assert [r["step"] for r in rows] == list(range(-1, STEPS))
    assert {r["episode"] for r in rows} == {0}
    reset = rows[0]
    assert reset["env_conf_object_xyz"] == [-0.312, -0.02, 0.763]
    assert reset["dr_level"] is None and reset["uid_overridden"] is False
    assert reset["object_xyz"] == pytest.approx([-0.31, -0.02, 0.76])
    step = rows[1]
    keys = {"episode", "step", "base_xyz", "base_yaw", "object_xyz", "container_xyz", "grasp",
            "on_container", "on_table2", "reward", "success"}
    assert set(step) == keys
    assert step["base_xyz"] == pytest.approx([-0.74, 0.0, 0.78])
    assert step["base_yaw"] == pytest.approx(np.pi / 2, abs=1e-5)  # rounded to 5 places
    assert [r["grasp"] for r in rows[1:4]] == [{"left": False, "right": True}] * 2 + [
        {"left": False, "right": False}
    ]
    assert [r["on_container"] for r in rows[1:]] == [False, False, False, True, True, True]
    assert rows[-1]["reward"] == pytest.approx(0.12) and rows[-1]["success"] is False
    assert line["success"] is False


def test_trace_flags_a_dataset_uid_the_cli_overrode(tmp_path: Path) -> None:
    trace = tmp_path / "t.trace.jsonl"
    replay(tmp_path, trace, uid="g1_wholebody_old_uid")
    assert json.loads(trace.read_text().splitlines()[0])["uid_overridden"] is True


class FakeAgent:
    """ReplayDecoupledAgent's padding: past the data it keeps the last row's goal."""

    def __init__(self, robot: Any, sonic_config: dict[str, Any], num_pad_frames: int = 10) -> None:
        self._num_pad_frames = num_pad_frames
        self.rows: list[int] = []
        self.index = 0

    def get_action(self, observation: Any) -> int:
        if self.index >= len(self.rows) + self._num_pad_frames:
            raise StopIteration("Episode data exhausted")
        action = self.rows[min(self.index, len(self.rows) - 1)]
        self.index += 1
        return action


def test_hold_steps_zero_is_the_current_replay(tmp_path: Path) -> None:
    assert hold_agent_class(FakeAgent, 0) is FakeAgent
    line, _ = replay(tmp_path, None, hold_steps=0)
    assert "hold_steps" not in line and "success_at_step" not in line


def test_hold_steps_repeats_the_last_action_then_reads_success(tmp_path: Path) -> None:
    agent = hold_agent_class(FakeAgent, 5)(None, {})
    agent.rows = [7, 8, 9]
    actions = []
    while True:
        try:
            actions.append(agent.get_action(None))
        except StopIteration:
            break
    assert actions == [7, 8, 9] + [9] * 15  # SIMPLE's 10 pad frames, then 5 more

    line, _ = replay(tmp_path, None, success_at=STEPS + 3, hold_steps=5, steps=STEPS + 5)
    assert line["success"] is True
    assert line["hold_steps"] == 5 and line["success_at_step"] == STEPS + 2  # 0-based, as the trace
    line, _ = replay(tmp_path / "never", None, success_at=None, hold_steps=5, steps=STEPS + 5)
    assert line["success"] is False and line["success_at_step"] is None
