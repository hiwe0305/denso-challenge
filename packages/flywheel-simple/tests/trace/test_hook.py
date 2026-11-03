"""Trace hook around SIMPLE's eval loop, on fakes of SIMPLE (DA-38 AC 1, 4, 5).

The fakes copy the parts of SIMPLE 6d10628 the hook relies on:
`SonicDecoupledWbcAgent.get_action` pops one queued command per call and the psi0
agent queries the server when the queue is empty, queuing each row `upsample_factor`
times; the eval loop resets the env, then the agent, steps until the episode ends and
writes `episode_<i>: <success>` through `_append_eval_stats_line`.
"""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from flywheel_simple.trace.camera import CameraValues
from flywheel_simple.trace.hook import (
    ChunkMirror,
    EpisodeTrace,
    TraceRecorder,
    camera_values,
    install,
    parse_stats_line,
    traced_agent_class,
    traced_env_class,
)


class ListSink:
    def __init__(self) -> None:
        self.episodes: list[EpisodeTrace] = []

    def write(self, episode: EpisodeTrace) -> None:
        self.episodes.append(episode)


def zeros_state() -> dict[str, np.ndarray]:
    return dict(joint_qpos=np.zeros(43), base_qpos=np.array([0, 0, 0.74, 1, 0, 0, 0.0]))


# --- ChunkMirror ---------------------------------------------------------------------------


def test_mirror_repeats_each_row_upsample_times_in_order() -> None:
    m = ChunkMirror()
    m.push_chunk(np.array([[1.0] * 36, [2.0] * 36]), upsample=2)
    assert [m.pop()[0] for _ in range(4)] == [1.0, 1.0, 2.0, 2.0]
    assert len(m) == 0


def test_mirror_pop_on_empty_raises() -> None:
    with pytest.raises(IndexError):
        ChunkMirror().pop()


# --- parse_stats_line ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("episode_3: True \n", ("episode_3", True)),
        ("episode_12: False \n", ("episode_12", False)),
        ("success rate: 0.50 \n", None),
        ("================\n", None),
        ("run: simple/X-v0 - psi0_decoupled_wbc\n", None),
    ],
)
def test_parse_stats_line(line: str, expected: tuple[str, bool] | None) -> None:
    assert parse_stats_line(line) == expected


# --- TraceRecorder -------------------------------------------------------------------------


def cycle(rec: TraceRecorder, t: float, *, sent: bool) -> None:
    rec.record_cycle(
        t_state=t,
        joint_qpos=np.zeros(43),
        base_qpos=np.array([0, 0, 0.74, 1, 0, 0, 0.0]),
        base_qvel=np.zeros(6),
        action_row=np.full(36, t),
        frame_sent=sent,
    )


def test_recorder_numbers_cycles_and_keeps_t_image_only_when_a_frame_was_sent() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="g0-DA-38-test")
    rec.start_episode(cameras=[])
    cycle(rec, 1.00, sent=True)
    cycle(rec, 1.02, sent=False)
    rec.end_episode("episode_7", success=True)
    (ep,) = sink.episodes
    assert ep.episode_id == "episode_7" and ep.sim_success is True
    assert ep.run_plan_id == "g0-DA-38-test"
    assert [c.step for c in ep.cycles] == [0, 1]
    assert [c.t_image for c in ep.cycles] == [1.00, None]
    assert ep.cycles[1].cmd_upper[0] == pytest.approx(1.02)


def test_recorder_flushes_an_unfinished_episode_without_a_success_flag() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="rp")
    rec.start_episode(cameras=[])
    cycle(rec, 0.0, sent=True)
    rec.start_episode(cameras=[])  # next reset before any stats line
    rec.close()
    assert [e.sim_success for e in sink.episodes] == [None, None]
    assert sink.episodes[0].episode_id != sink.episodes[1].episode_id
    assert sink.episodes[0].episode_id.startswith("unfinished-")


def test_recorder_rejects_a_cycle_outside_an_episode() -> None:
    with pytest.raises(RuntimeError, match="episode"):
        cycle(TraceRecorder(ListSink(), run_plan_id="rp"), 0.0, sent=True)


def test_recorder_ignores_a_stats_line_without_an_open_episode() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="rp")
    rec.end_episode("episode_0", success=False)
    assert sink.episodes == []


# --- agent subclass ------------------------------------------------------------------------


class FakeClient:
    def __init__(self, chunks: list[np.ndarray]) -> None:
        self.chunks = deque(chunks)
        self.calls = 0

    def query_action(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        self.calls += 1
        return self.chunks.popleft(), {}


class FakePsi0Agent:
    """Queue and query logic of SIMPLE's psi0_decoupled_wbc agent, nothing else."""

    def __init__(self, robot: Any, host: str, port: int, upsample_factor: int = 1, **kw: Any):
        self.robot = robot
        self.upsample_factor = upsample_factor
        self._action_queue: deque[Any] = deque()
        self.client = FakeClient(kw.pop("chunks"))

    def reset(self, **kwargs: Any) -> None:
        self._action_queue = deque()

    def get_action(self, observation: Any, instruction: Any = None, **kwargs: Any) -> Any:
        if len(self._action_queue) == 0:
            pred, *_ = self.client.query_action({}, instruction, {})
            for row in pred:
                for _ in range(self.upsample_factor):
                    self._action_queue.append(("vla_cmd", row))
        try:
            return self._action_queue.popleft()
        except IndexError:
            raise StopIteration from None


def fake_robot(t: float = 0.5) -> Any:
    data = SimpleNamespace(
        time=t,
        qpos=np.concatenate([[0.1, 0.2, 0.73, 1, 0, 0, 0], np.arange(43) * 0.01]),
        qvel=np.zeros(6 + 43),
    )
    return SimpleNamespace(mjData=data)


def test_traced_agent_records_one_cycle_per_get_action_with_the_consumed_row() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="rp")
    chunk = np.stack([np.full(36, 1.0), np.full(36, 2.0)])
    cls = traced_agent_class(FakePsi0Agent, rec)
    robot = fake_robot()
    agent = cls(robot, "h", 1, upsample_factor=2, chunks=[chunk, chunk * 10])
    rec.start_episode(cameras=[])
    obs = {"joint_qpos": np.arange(43, dtype=np.float32)}
    for i in range(5):
        robot.mjData.time = 0.5 + 0.02 * i
        agent.get_action(obs, instruction="go")
    rec.end_episode("episode_0", success=False)
    cycles = sink.episodes[0].cycles
    assert [c.cmd_upper[0] for c in cycles] == [1.0, 1.0, 2.0, 2.0, 10.0]
    assert [c.t_image is not None for c in cycles] == [True, False, False, False, True]
    assert [c.t_state for c in cycles] == pytest.approx([0.5, 0.52, 0.54, 0.56, 0.58])
    assert cycles[0].meas_lower[3] == pytest.approx(0.73)  # base height from mjData.qpos[2]
    assert cycles[0].meas_upper[0] == pytest.approx(29.0)  # left thumb from observation joint_qpos


def test_traced_agent_reset_drops_the_mirrored_rows() -> None:
    rec = TraceRecorder(ListSink(), run_plan_id="rp")
    cls = traced_agent_class(FakePsi0Agent, rec)
    chunk = np.stack([np.full(36, 1.0), np.full(36, 2.0)])
    agent = cls(fake_robot(), "h", 1, chunks=[chunk, chunk * 3])
    rec.start_episode(cameras=[])
    agent.get_action({"joint_qpos": np.zeros(43)})
    agent.reset()
    rec.start_episode(cameras=[])
    agent.get_action({"joint_qpos": np.zeros(43)})
    assert agent.client.calls == 2


# --- env wrapper ---------------------------------------------------------------------------


class FakeWrapper:
    def __init__(self, env: Any) -> None:
        self.env = env

    def reset(self, **kwargs: Any) -> Any:
        return self.env.reset(**kwargs)

    def close(self) -> None:
        self.env.close()

    @property
    def unwrapped(self) -> Any:
        return self.env


def fake_model() -> Any:
    names = ["head_stereo_left", "head_stereo_right"]
    return SimpleNamespace(
        ncam=2,
        camera=lambda i: SimpleNamespace(name=names[i]),
        body=lambda i: SimpleNamespace(name="torso_link"),
        cam_bodyid=np.array([7, 7]),
        cam_fovy=np.array([58.0, 58.0]),
        cam_sensorsize=np.zeros((2, 2)),
        cam_intrinsic=np.zeros((2, 4)),
        cam_pos=np.array([[0.05, 0.02, 0.43], [0.05, -0.03, 0.43]]),
        cam_quat=np.array([[0.5, -0.5, 0.5, -0.5], [0.5, -0.5, 0.5, -0.5]]),
    )


class FakeEnv:
    def __init__(self) -> None:
        self.resets = 0
        self.closed = False
        cfg = SimpleNamespace(mount="eye_in_head")
        self.task = SimpleNamespace(
            layout=SimpleNamespace(cameras={"head_stereo_left": cfg, "head_stereo_right": cfg})
        )
        self.mujoco = SimpleNamespace(mjModel=fake_model())
        self.isaac = None

    def reset(self, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        self.resets += 1
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        return {"joint_qpos": np.zeros(43), "head_stereo_left": img, "head_stereo_right": img}, {}

    def close(self) -> None:
        self.closed = True


def test_camera_values_read_the_compiled_model_at_the_render_size() -> None:
    env = FakeEnv()
    obs, _ = env.reset()
    cams = camera_values(env, obs)
    assert [c.uid for c in cams] == ["head_stereo_left", "head_stereo_right"]
    left = cams[0]
    assert (left.width, left.height, left.mount) == (640, 360, "eye_in_head")
    assert left.fx == pytest.approx(180 / np.tan(np.radians(29.0)))
    assert left.pose == pytest.approx((0.05, 0.02, 0.43, 0.5, -0.5, 0.5, -0.5))


def test_camera_values_are_empty_when_isaac_renders() -> None:
    env = FakeEnv()
    env.isaac = object()
    obs, _ = env.reset()
    assert camera_values(env, obs) == []


def test_traced_env_starts_an_episode_with_cameras_on_reset_and_flushes_on_close() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="rp")
    env = traced_env_class(FakeWrapper, rec)(FakeEnv())
    env.reset(options={"state_dict": {}})
    cycle(rec, 0.0, sent=True)
    env.close()
    (ep,) = sink.episodes
    assert ep.sim_success is None
    assert [c.uid for c in ep.cameras] == ["head_stereo_left", "head_stereo_right"]
    assert isinstance(ep.cameras[0], CameraValues)


# --- install -------------------------------------------------------------------------------


def fake_modules() -> tuple[Any, Any, list[str]]:
    lines: list[str] = []
    gym = SimpleNamespace(make=lambda env_id, **kw: FakeEnv(), Wrapper=FakeWrapper, registry={})
    eval_module = SimpleNamespace(
        gym=gym, _append_eval_stats_line=lambda eval_dir, line: lines.append(line)
    )
    agent_module = SimpleNamespace(Psi0DecoupledWbcAgent=FakePsi0Agent)
    return eval_module, agent_module, lines


def test_install_patches_env_agent_and_stats_line_once() -> None:
    sink = ListSink()
    rec = TraceRecorder(sink, run_plan_id="rp")
    ev, ag, lines = fake_modules()
    install(ev, ag, rec)
    install(ev, ag, rec)  # idempotent: a second call must not wrap twice
    env = ev.gym.make("simple/X-v0")
    agent = ag.Psi0DecoupledWbcAgent(fake_robot(), "h", 1, chunks=[np.ones((2, 36))])
    env.reset()
    agent.reset()
    agent.get_action({"joint_qpos": np.zeros(43)})
    ev._append_eval_stats_line("/tmp/x", "episode_4: True \n")
    assert lines == ["episode_4: True \n"]  # SIMPLE's own line still written
    (ep,) = sink.episodes
    assert (ep.episode_id, ep.sim_success, len(ep.cycles)) == ("episode_4", True, 1)
    assert ag.Psi0DecoupledWbcAgent.__mro__[1] is FakePsi0Agent
    assert ev.gym.Wrapper is FakeWrapper  # only make is replaced
