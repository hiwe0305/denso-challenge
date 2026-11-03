"""Record a trace of every control cycle of SIMPLE's `eval-decoupled-wbc` (DA-38 AC 1, 4).

SIMPLE is not forked. `install` patches three module-level names that its eval
worker looks up at call time (SIMPLE 6d10628):

* `eval_module.gym` becomes a proxy whose `make` wraps the env: each `reset` opens
  an episode and reads its cameras from the compiled MuJoCo model;
* `agent_module.Psi0DecoupledWbcAgent` becomes a subclass: each `get_action` reads
  the state the policy acts on (`mjData` has not moved since the last step), mirrors
  the agent's action queue to know which 36-D Psi0 row it consumes, and records one
  cycle;
* `eval_module._append_eval_stats_line` also ends the episode: it receives
  `episode_<i>: <check_success>` after each episode.

Stabilization steps call the raw env, not the wrapped one, and are not recorded.
`install` must run at import time of the entry module (`trace.run`): SIMPLE's eval
workers are spawned processes that import that module but do not run its `main()`.
"""

from __future__ import annotations

import itertools
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray

from flywheel_simple.trace.camera import CameraValues, mujoco_intrinsics
from flywheel_simple.trace.signals import image_time, measured_signals, split_command

_STATS_LINE = re.compile(r"^(episode_\d+):\s*(True|False)\s*$")
_PATCHED = "_fw_trace_patched"


@dataclass(frozen=True)
class CycleRecord:
    step: int
    t_state: float
    t_image: float | None
    cmd_upper: list[float]
    meas_upper: list[float]
    cmd_lower: list[float]
    meas_lower: list[float]
    dropped_frames: int = 0  # renders are synchronous in sim: every cycle has a fresh frame


@dataclass
class EpisodeTrace:
    episode_id: str
    run_plan_id: str
    cameras: list[CameraValues]
    cycles: list[CycleRecord] = field(default_factory=list)
    sim_success: bool | None = None  # None: the eval loop never reported the episode


class TraceSink(Protocol):
    def write(self, episode: EpisodeTrace) -> None: ...


def parse_stats_line(line: str) -> tuple[str, bool] | None:
    """`("episode_3", True)` from SIMPLE's `episode_3: True` line; None for other lines."""
    m = _STATS_LINE.match(line.strip())
    return (m.group(1), m.group(2) == "True") if m else None


class TraceRecorder:
    """Collects the cycles of one episode at a time and hands each finished one to a sink."""

    def __init__(self, sink: TraceSink, *, run_plan_id: str) -> None:
        self.sink = sink
        self.run_plan_id = run_plan_id
        self._open: EpisodeTrace | None = None
        self._unfinished = itertools.count()

    def start_episode(self, *, cameras: list[CameraValues]) -> None:
        self._flush(None)
        self._open = EpisodeTrace(
            episode_id=f"unfinished-{next(self._unfinished)}",
            run_plan_id=self.run_plan_id,
            cameras=cameras,
        )

    def record_cycle(
        self,
        *,
        t_state: float,
        joint_qpos: ArrayLike,
        base_qpos: ArrayLike,
        base_qvel: ArrayLike,
        action_row: ArrayLike,
        frame_sent: bool,
    ) -> None:
        if self._open is None:
            raise RuntimeError("record_cycle outside an episode: the env was not reset")
        cmd_upper, cmd_lower = split_command(action_row)
        meas_upper, meas_lower = measured_signals(joint_qpos, base_qpos, base_qvel)
        self._open.cycles.append(
            CycleRecord(
                step=len(self._open.cycles),
                t_state=float(t_state),
                t_image=image_time(t_state, frame_sent=frame_sent),
                cmd_upper=cmd_upper,
                meas_upper=meas_upper,
                cmd_lower=cmd_lower,
                meas_lower=meas_lower,
            )
        )

    def end_episode(self, episode_id: str, *, success: bool) -> None:
        if self._open is None:
            return
        self._open.episode_id = episode_id
        self._flush(success)

    def close(self) -> None:
        self._flush(None)

    def _flush(self, success: bool | None) -> None:
        if self._open is None:
            return
        episode, self._open = self._open, None
        episode.sim_success = success
        self.sink.write(episode)


class ChunkMirror:
    """The agent's action queue as raw 36-D Psi0 rows, kept in step with it."""

    def __init__(self) -> None:
        self._rows: deque[NDArray[np.float64]] = deque()

    def push_chunk(self, rows: ArrayLike, *, upsample: int) -> None:
        for row in np.asarray(rows, dtype=np.float64).reshape(-1, 36):
            self._rows.extend(row.copy() for _ in range(upsample))

    def pop(self) -> NDArray[np.float64]:
        return self._rows.popleft()

    def clear(self) -> None:
        self._rows.clear()

    def __len__(self) -> int:
        return len(self._rows)


def traced_agent_class(base: type[Any], recorder: TraceRecorder) -> type[Any]:
    """Subclass of SIMPLE's psi0 agent that records a cycle per `get_action`."""

    class TracedAgent(base):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._fw_mirror = ChunkMirror()
            query = self.client.query_action

            def query_action(*a: Any, **kw: Any) -> Any:
                result = query(*a, **kw)
                self._fw_mirror.push_chunk(result[0], upsample=int(self.upsample_factor))
                return result

            self.client.query_action = query_action

        def reset(self, **kwargs: Any) -> Any:
            self._fw_mirror.clear()
            return super().reset(**kwargs)

        def get_action(self, observation: Any, *args: Any, **kwargs: Any) -> Any:
            frame_sent = len(self._action_queue) == 0
            data = self.robot.mjData
            t_state = float(data.time)
            base_qpos = np.array(data.qpos[:7], dtype=np.float64)
            base_qvel = np.array(data.qvel[:6], dtype=np.float64)
            action = super().get_action(observation, *args, **kwargs)
            row = self._fw_mirror.pop()
            if len(self._fw_mirror) != len(self._action_queue):
                raise RuntimeError(
                    f"trace mirror out of step with the agent queue "
                    f"({len(self._fw_mirror)} != {len(self._action_queue)})"
                )
            recorder.record_cycle(
                t_state=t_state,
                joint_qpos=observation["joint_qpos"],
                base_qpos=base_qpos,
                base_qvel=base_qvel,
                action_row=row,
                frame_sent=frame_sent,
            )
            return action

    TracedAgent.__name__ = TracedAgent.__qualname__ = base.__name__
    return TracedAgent


def camera_values(env: Any, observation: dict[str, Any]) -> list[CameraValues]:
    """Every camera rendered into `observation`, from the compiled MuJoCo model.

    Empty when Isaac renders the images: the MuJoCo camera is then not the one seen.
    """
    if getattr(env, "isaac", None) is not None:
        return []
    model = env.mujoco.mjModel
    configs = env.task.layout.cameras
    cams = []
    for i in range(int(model.ncam)):
        name = model.camera(i).name
        image = observation.get(name)
        if image is None or np.ndim(image) != 3:
            continue
        height, width = int(np.shape(image)[0]), int(np.shape(image)[1])
        fx, fy, cx, cy = mujoco_intrinsics(
            width,
            height,
            float(model.cam_fovy[i]),
            sensorsize=model.cam_sensorsize[i],
            intrinsic=model.cam_intrinsic[i],
        )
        cfg = configs.get(name) or configs.get(name.rsplit("_", 1)[0])
        mount = getattr(cfg, "mount", None) or model.body(int(model.cam_bodyid[i])).name
        pose = (*map(float, model.cam_pos[i]), *map(float, model.cam_quat[i]))
        cams.append(CameraValues(name, mount, width, height, fx, fy, cx, cy, pose))
    return cams


def traced_env_class(wrapper_base: type[Any], recorder: TraceRecorder) -> type[Any]:
    """gym wrapper that opens an episode, with its cameras, on every reset."""

    class TracedEnv(wrapper_base):  # type: ignore[misc]
        def reset(self, **kwargs: Any) -> Any:
            observation, info = super().reset(**kwargs)
            recorder.start_episode(cameras=camera_values(self.unwrapped, observation))
            return observation, info

        def close(self) -> Any:
            recorder.close()
            return super().close()

    return TracedEnv


class _GymProxy:
    """Stands in for the `gym` name of the eval module; only `make` differs."""

    def __init__(self, gym: Any, env_class: type[Any]) -> None:
        self._gym = gym
        self._env_class = env_class
        setattr(self, _PATCHED, True)

    def make(self, *args: Any, **kwargs: Any) -> Any:
        return self._env_class(self._gym.make(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._gym, name)


def install(eval_module: Any, agent_module: Any, recorder: TraceRecorder) -> None:
    """Patch SIMPLE's eval and psi0 agent modules once per process."""
    if getattr(eval_module, _PATCHED, False):
        return
    gym = eval_module.gym
    eval_module.gym = _GymProxy(gym, traced_env_class(gym.Wrapper, recorder))
    agent_module.Psi0DecoupledWbcAgent = traced_agent_class(
        agent_module.Psi0DecoupledWbcAgent, recorder
    )
    write_line = eval_module._append_eval_stats_line

    def append_eval_stats_line(eval_dir: str, line: str) -> None:
        write_line(eval_dir, line)
        parsed = parse_stats_line(line)
        if parsed is not None:
            recorder.end_episode(parsed[0], success=parsed[1])

    eval_module._append_eval_stats_line = append_eval_stats_line
    setattr(eval_module, _PATCHED, True)
