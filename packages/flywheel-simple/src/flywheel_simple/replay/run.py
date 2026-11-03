"""SIMPLE's replay-decoupled-wbc on one shard, with the joints of every step kept (DA-17).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.replay.run --data-dir <dataset> --env-id <env> \
        --outcomes <file> --episode-start 0 --num-episodes 99 --save-dir <dir>

SIMPLE's command is called as is (`simple.cli.replay_decoupled_wbc.main`, no
recording); it already replays psi0 post-processed data (36-D action: upper
body from 0-30, base height and navigate command from 31-35). Two things are
added around it:

- the env that `gymnasium.make` returns is wrapped in OutcomeRecorder, which
  keeps the 31 state joints (`mujoco.get_robot_qpos()`, by name) after every
  recorded action and, when the next episode starts or the env closes, appends
  the episode's outcome (`compare.outcome`) to the --outcomes file. The
  stabilisation steps go to the unwrapped env and are not kept, as SIMPLE does
  not record them either;
- the replay runs on sim time, as the tray replay does (D-24): the agent's and
  the loop's `time` read `mjData.time` and never sleep, so a loaded machine
  replays the same as an idle one.

SIMPLE writes `meta/replay.txt` into --data-dir; `outcomes.replay_lerobot`
points it at a staged copy, never at the source dataset.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.replay.compare import joint_order, outcome

SIM_TIME_MODULES = ("simple.agents.replay_decoupled_agent", "simple.cli.replay_decoupled_wbc")
_live: Any = None  # the OutcomeRecorder of this process (one env per process)


class SimTime:
    """Stand-in for the `time` module: monotonic() is sim time, sleep() does not wait."""

    def monotonic(self) -> float:
        if _live is None:
            return time.monotonic()
        data = getattr(_live.unwrapped, "mjData", None)  # set on the first reset
        return float(data.time) if data is not None else 0.0

    def sleep(self, seconds: float) -> None:
        del seconds

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


def read_states(root: Path, episode: int) -> Any:
    """The recorded `states` of one episode, (T, 32)."""
    pq = importlib.import_module("pyarrow.parquet")
    info = json.loads((root / "meta" / "info.json").read_text())
    chunk = episode // int(info.get("chunks_size", 1000))
    path = root / info["data_path"].format(episode_chunk=chunk, episode_index=episode)
    return np.asarray(pq.read_table(path, columns=["states"]).column("states").to_pylist())


def recorder_class() -> type:
    gym = importlib.import_module("gymnasium")

    class OutcomeRecorder(gym.Wrapper):  # type: ignore[misc, name-defined]
        """Keeps the state joints after each data step and writes one outcome per episode."""

        def __init__(self, env: Any, data_dir: Path, out: Path, state_names: list[str]) -> None:
            global _live
            super().__init__(env)
            self.data_dir, self.out, self.state_names = data_dir, out, state_names
            self.episode: int | None = None
            self.rows: list[Any] = []
            self.order: list[int] | None = None
            _live = self

        def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> Any:
            self.flush()
            task_id = str((options or {}).get("task_id", ""))
            self.episode = int(task_id[8:]) if task_id.startswith("episode_") else None
            return self.env.reset(seed=seed, options=options)

        def step(self, action: Any) -> Any:
            result = self.env.step(action)
            qpos = self.env.unwrapped.mujoco.get_robot_qpos()
            if self.order is None:
                self.order = joint_order(list(qpos), self.state_names)
            values = np.asarray(list(qpos.values()), dtype=np.float64)
            self.rows.append(values[self.order])
            return result

        def close(self) -> Any:
            self.flush()
            return self.env.close()

        def flush(self) -> None:
            if self.episode is not None and self.rows:
                success = bool(getattr(self.env.unwrapped, "_success", False))
                line = outcome(
                    self.episode, read_states(self.data_dir, self.episode),
                    np.stack(self.rows), success,
                )
                with self.out.open("a") as f:
                    f.write(json.dumps(line) + "\n")
            self.episode, self.rows = None, []

    return OutcomeRecorder


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="flywheel_simple.replay.run")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--env-id", required=True)
    ap.add_argument("--outcomes", type=Path, required=True)
    ap.add_argument("--episode-start", type=int, required=True)
    ap.add_argument("--num-episodes", type=int, required=True)
    ap.add_argument("--save-dir", type=Path, required=True)
    args = ap.parse_args(argv)

    from flywheel_simple.tray.export import state_names
    from flywheel_simple.tray.replay_qa import ENV_ID as TRAY_ENV_ID

    if args.env_id == TRAY_ENV_ID:
        importlib.import_module("flywheel_simple.tray.run").prepare()  # registers the env id
    joints = importlib.import_module("simple.robots.g1_sonic").WHOLE_BODY_JOINTS
    names = state_names(joints)
    for name in SIM_TIME_MODULES:
        importlib.import_module(name).time = SimTime()  # type: ignore[attr-defined]
    gym = importlib.import_module("gymnasium")
    make, recorder = gym.make, recorder_class()

    def wrapped_make(*a: Any, **kw: Any) -> Any:
        return recorder(make(*a, **kw), args.data_dir, args.outcomes, names)

    setattr(gym, "make", wrapped_make)  # the CLI looks gym.make up when it calls it
    cli = importlib.import_module("simple.cli.replay_decoupled_wbc")
    cli.main(
        env_id=args.env_id,
        data_dir=str(args.data_dir),
        sim_mode="mujoco",
        headless=True,
        webrtc=False,
        render_hz=50,
        num_episodes=args.num_episodes,
        episode_start=args.episode_start,
        record=False,
        save_dir=str(args.save_dir),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
