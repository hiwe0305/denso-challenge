"""SIMPLE's replay-decoupled-wbc on one shard, with the joints of every step kept (DA-17).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.replay.run --data-dir <dataset> --env-id <env> \
        --outcomes <file> --episode-start 0 --num-episodes 99 --save-dir <dir> --clock wall

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
- with `--clock sim` (the default of `outcomes.replay_lerobot`) the replay runs
  on sim time, as the tray replay does (D-24): the agent's and the loop's `time`
  read `mjData.time` and never sleep, so a loaded machine replays the same as an
  idle one. `--clock wall` leaves SIMPLE's clock alone. The agent reads
  `time.monotonic()` once to time a goal and once to sample the WBC's
  interpolation; on sim time the two are equal, on the wall clock their gap is
  whatever the machine took in between. On psi-data e78fb93 neither clock
  replays the task more often (docs/g0/replay.md section 3), so the
  reproducible one is the default.

With `--trace <file.jsonl>` (DA-17 task 6) the recorder also writes, per
episode, a row right after `reset` (step -1) and one after every recorded
action; `trace_row` says what each row holds. Without it nothing else changes.

With `--hold-steps N` (default 0) the replay keeps the last recorded command N
steps longer before `_success` is read: SIMPLE's agent already pads 10 frames
past the data with the last row as the WBC goal (`ReplayDecoupledAgent`
`num_pad_frames`), and `hold_agent_class` makes that 10 + N. The WBC keeps
balancing on that goal; the joint targets are not frozen. The outcome line then
also holds `hold_steps` and `success_at_step` (index of the step at which
`_success` first read true, as the trace counts steps, or null); with N = 0 it
is the line of today's replay, which `replay_check` reads.

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

from flywheel_simple.replay.compare import base_yaw, joint_order, outcome

CLOCKS = ("sim", "wall")
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


def dataset_uids(root: Path) -> dict[int, str | None]:
    """episode_index -> `uid` of its environment_config, before the CLI overrides it."""
    uids: dict[int, str | None] = {}
    for line in (root / "meta" / "episodes.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            conf = row.get("environment_config")
            conf = json.loads(conf) if isinstance(conf, str) else conf or {}
            uids[int(row["episode_index"])] = conf.get("uid")
    return uids


def _xyz(values: Any) -> list[float]:
    return [round(float(v), 5) for v in np.asarray(values, dtype=np.float64)[:3]]


def trace_row(sim: Any, episode: int, step: int) -> dict[str, Any]:
    """Base, object and grasp of SIMPLE's two-table task, read from the live env.

    Names as in SIMPLE b75c678 `tasks/g1_wholebody_locomotion_pick_between_tables_
    teleop.py` and `engines/mujoco.py`: the base is MuJoCo body `pelvis`; the
    object and the container are `mujoco.mj_objects["target"]` and `["container"]`
    (bodies named after `task.target.asset.label`, `task.container.asset.label`).
    The contacts are read the way the task's `check_hand_object_contact` and
    `check_object_in_container` read them: a body name holding the target's label
    against one holding `left_hand` / `right_hand` (the task only asks for "hand"),
    the container's label, or `table2`. `reward` is `task.reward`, which the task
    raises by 0.02 per call while the object is on the container and no hand
    touches it; SIMPLE's env calls it twice per step and succeeds at 0.4.
    """
    data, model, task = sim.mjData, sim.mjModel, sim.task
    pelvis = data.body("pelvis")
    target = str(task.target.asset.label)
    container = str(task.container.asset.label)
    touching: list[str] = []
    for k in range(int(data.ncon)):
        contact = data.contact[k]
        names = [str(model.body(model.geom(g).bodyid).name) for g in (contact.geom1, contact.geom2)]
        if target in names[0]:
            touching.append(names[1])
        elif target in names[1]:
            touching.append(names[0])
    objects = sim.mujoco.mj_objects
    return {
        "episode": episode,
        "step": step,
        "base_xyz": _xyz(pelvis.xpos),
        "base_yaw": round(base_yaw(pelvis.xquat), 5),
        "object_xyz": _xyz(objects["target"].xpos),
        "container_xyz": _xyz(objects["container"].xpos),
        "grasp": {side: any(f"{side}_hand" in n for n in touching) for side in ("left", "right")},
        "on_container": any(container in n for n in touching),
        "on_table2": any("table2" in n for n in touching),
        "reward": round(float(getattr(task, "reward", 0.0)), 5),
        "success": bool(getattr(sim, "_success", False)),
    }


def reset_row(
    sim: Any, episode: int, options: dict[str, Any], dataset_uid: str | None
) -> dict[str, Any]:
    """trace_row at step -1, plus the object pose and DR level the reset was asked for.

    `env_conf_object_xyz` is `dr_state_dict.spatial[<target uid>]` of the episode's
    environment_config: with `dr_level` None (the CLI's default) SIMPLE's
    `DRManager.load_state_dict` restores every randomizer from it, spatial poses
    included. (The config's `layout` holds the poses at the end of the recording.)
    """
    row = trace_row(sim, episode, -1)
    conf = options.get("state_dict") or {}
    dr = conf.get("dr_state_dict") or {}
    pose = (dr.get("spatial") or {}).get(str((dr.get("target") or {}).get("uid"))) or {}
    row["env_conf_object_xyz"] = _xyz(pose["position"]) if "position" in pose else None
    row["dr_level"] = options.get("dr_level")
    row["uid_overridden"] = dataset_uid != sim.task.uid
    return row


def hold_agent_class(base: type, steps: int) -> type:
    """`base` (SIMPLE's ReplayDecoupledAgent) padding `steps` more frames, or base itself."""
    if steps <= 0:
        return base

    class HoldLastCommand(base):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._num_pad_frames += steps

    return HoldLastCommand


def recorder_class(base: type | None = None) -> type:
    """OutcomeRecorder on top of `base` (gymnasium.Wrapper unless a test passes one)."""
    wrapper = base or importlib.import_module("gymnasium").Wrapper

    class OutcomeRecorder(wrapper):  # type: ignore[misc, valid-type]
        """Keeps the state joints after each data step and writes one outcome per episode."""

        def __init__(
            self, env: Any, data_dir: Path, out: Path, state_names: list[str],
            trace: Path | None = None, hold_steps: int = 0,
        ) -> None:  # fmt: skip
            global _live
            super().__init__(env)
            self.data_dir, self.out, self.state_names = data_dir, out, state_names
            self.trace, self.hold_steps = trace, hold_steps
            self.success_at: int | None = None
            self.uids = dataset_uids(data_dir) if trace is not None else {}
            self.episode: int | None = None
            self.rows: list[Any] = []
            self.trace_rows: list[dict[str, Any]] = []
            self.order: list[int] | None = None
            _live = self

        def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> Any:
            self.flush()
            task_id = str((options or {}).get("task_id", ""))
            self.episode = int(task_id[8:]) if task_id.startswith("episode_") else None
            result = self.env.reset(seed=seed, options=options)
            if self.trace is not None and self.episode is not None:
                row = reset_row(
                    self.env.unwrapped, self.episode, options or {}, self.uids.get(self.episode)
                )
                self.trace_rows.append(row)
            return result

        def step(self, action: Any) -> Any:
            result = self.env.step(action)
            qpos = self.env.unwrapped.mujoco.get_robot_qpos()
            if self.order is None:
                self.order = joint_order(list(qpos), self.state_names)
            values = np.asarray(list(qpos.values()), dtype=np.float64)
            self.rows.append(values[self.order])
            if self.success_at is None and getattr(self.env.unwrapped, "_success", False):
                self.success_at = len(self.rows) - 1
            if self.trace is not None and self.episode is not None:
                self.trace_rows.append(
                    trace_row(self.env.unwrapped, self.episode, len(self.rows) - 1)
                )
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
                if self.hold_steps > 0:
                    line.update(hold_steps=self.hold_steps, success_at_step=self.success_at)
                with self.out.open("a") as f:
                    f.write(json.dumps(line) + "\n")
            if self.trace is not None and self.trace_rows:
                with self.trace.open("a") as f:
                    f.writelines(json.dumps(r) + "\n" for r in self.trace_rows)
            self.episode, self.rows, self.trace_rows, self.success_at = None, [], [], None

    return OutcomeRecorder


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="flywheel_simple.replay.run")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--env-id", required=True)
    ap.add_argument("--outcomes", type=Path, required=True)
    ap.add_argument("--episode-start", type=int, required=True)
    ap.add_argument("--num-episodes", type=int, required=True)
    ap.add_argument("--save-dir", type=Path, required=True)
    ap.add_argument("--clock", choices=CLOCKS, required=True)
    ap.add_argument("--trace", type=Path, help="per-step trace, one JSON row per step")
    ap.add_argument("--hold-steps", type=int, default=0, help="extra steps on the last command")
    args = ap.parse_args(argv)

    from flywheel_simple.tray.export import state_names
    from flywheel_simple.tray.replay_qa import ENV_ID as TRAY_ENV_ID

    if args.env_id == TRAY_ENV_ID:
        importlib.import_module("flywheel_simple.tray.run").prepare()  # registers the env id
    joints = importlib.import_module("simple.robots.g1_sonic").WHOLE_BODY_JOINTS
    names = state_names(joints)
    for name in SIM_TIME_MODULES if args.clock == "sim" else ():
        importlib.import_module(name).time = SimTime()  # type: ignore[attr-defined]
    gym = importlib.import_module("gymnasium")
    make, recorder = gym.make, recorder_class()

    def wrapped_make(*a: Any, **kw: Any) -> Any:
        env = make(*a, **kw)
        return recorder(env, args.data_dir, args.outcomes, names, args.trace, args.hold_steps)

    setattr(gym, "make", wrapped_make)  # the CLI looks gym.make up when it calls it
    cli = importlib.import_module("simple.cli.replay_decoupled_wbc")
    agent = hold_agent_class(getattr(cli, "ReplayDecoupledAgent"), args.hold_steps)
    setattr(cli, "ReplayDecoupledAgent", agent)  # the CLI builds its agent from this name
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
