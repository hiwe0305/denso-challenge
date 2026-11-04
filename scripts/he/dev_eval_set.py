"""Build HE-1's eval set of the two-table task from the team's dev seeds (DA-26 AC 1).

SIMPLE's `dr-decoupled-wbc` built the authors' simple-eval from train episodes:
level k of condition i is train episode i re-randomised the way
`DRManager.load_state_dict(dr_level=k)` says (0: distractors and material redrawn;
1: lighting too; 2: object poses too, robot pose kept). So levels 0 and 1 of
simple-eval are train scenes (S1-07 section 4). This does the same with a reference
scene drawn fresh from a seed of the team's dev split instead of a train episode, so
every condition is new and the levels keep the authors' meaning.

SIMPLE's randomizers draw from numpy's and Python's global RNG; `DRManager.reset`
ignores the seed given to `env.reset`. Both RNGs are therefore seeded before each
reset: with the condition seed for the reference scene, and with a hash of
(salt, seed, level) for the level's redraw. Probe of 4/11/2026: the same seed gave the
same `dr_state_dict` twice, two seeds gave two scenes.

Writes `<out>/<env id>/dr-level-<k>/` (LeRobot, one frame per episode, as
simple-eval; `eval-decoupled-wbc --data-format lerobot` reads it and resets from the
full `environment_config`, so the scene is fixed by the file) and
`<out>/conditions.jsonl`, one row (level, seed, environment_config) per condition.
The RunPlan pins `conditions_sha256`, the sha256 of those rows as compact JSON in
insertion order (see `config_sha256`); the encoded frames are not pinned. Runs in the
SIMPLE venv (scripts/g0/setup_simple.sh):

    MUJOCO_GL=egl PYTHONPATH=scripts/g0/simple/curobo_stub fwdata/simple/.venv/bin/python \
        scripts/he/dev_eval_set.py --start 1000100 --stop 1000130 --out fwdata/he/dev-eval
    ... scripts/he/dev_eval_set.py --start 1000100 --stop 1000130 --check <sha256>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

ENV_ID = "simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0"
SALT = "DA-26/he-1/dev-eval/v1"
DEV = (1_000_000, 1_001_000)  # configs/splits/default.yaml seed_ranges.dev


def config_sha256(value: Any) -> str:
    """sha256 of compact JSON in insertion order. Not sorted: SIMPLE gives the stored
    distractors to `distractor_0, 1, ...` in dict order, so the order is part of the
    scene (sorting the keys moved the distractors in the probe of 4/11/2026)."""
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def level_seed(seed: int, level: int) -> int:
    digest = hashlib.sha256(f"{SALT}|{seed}|{level}".encode()).hexdigest()
    return int(digest[:8], 16)


def seed_all(seed: int) -> None:
    np.random.seed(seed)
    random.seed(seed)


def plain(env_config: dict[str, Any]) -> Any:
    """The env config as plain JSON, the way SIMPLE writes it to episodes.jsonl."""
    from simple.utils import NumpyArrayEncoder

    return json.loads(json.dumps(env_config, cls=NumpyArrayEncoder))


def make_env() -> Any:
    import gymnasium as gym
    import simple.envs  # noqa: F401  registers SIMPLE's env ids
    from simple.cli.dr_decoupled_wbc import _make_sonic_config

    sonic_config = _make_sonic_config()
    return gym.make(
        ENV_ID,
        sim_mode="mujoco",
        headless=True,
        render_hz=50,
        physics_dt=float(sonic_config["SIMULATE_DT"]),
        webrtc=False,
        sonic_config=sonic_config,
    )


def condition(env: Any, seed: int, level: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """(observation, environment_config) of condition (level, seed)."""
    task = env.unwrapped.task
    seed_all(seed)
    env.reset(seed=seed)
    reference = task.state_dict()
    seed_all(level_seed(seed, level))
    observation, _ = env.reset(options={"state_dict": reference, "dr_level": level})
    return observation, task.state_dict()


def robot_model(robot: Any) -> Any:
    """The WBC robot model SIMPLE's PicoDecoupledAgent builds, without its teleop stack."""
    from decoupled_wbc.control.robot_model.instantiation.g1 import instantiate_g1_robot_model

    cfg = robot.sonic_config
    waist = "lower_and_upper_body" if cfg.get("enable_waist", False) else "lower_body"
    return instantiate_g1_robot_model(
        waist_location=waist, high_elbow_pose=cfg.get("high_elbow_pose", False)
    )


def frame(observation: dict[str, Any], num_objects: int) -> dict[str, Any]:
    """First-frame row as SIMPLE's dr-decoupled-wbc writes it (no action in an eval set)."""
    lin = observation.get("base_lin_vel", np.zeros(3))
    ang = observation.get("base_ang_vel", np.zeros(3))
    pose = observation.get("base_pose_quat", observation.get("floating_base_pose", np.zeros(7)))
    row = {
        "observation.images.ego_view": observation["head_stereo_left"],
        "observation.state": np.asarray(observation["joint_qpos"], dtype=np.float64),
        "observation.base_pose": np.asarray(pose, dtype=np.float64),
        "observation.base_vel": np.asarray(
            np.concatenate([lin, ang]) if len(lin) == 3 else lin, dtype=np.float64
        ),
        "observation.eef_state": np.zeros(14, dtype=np.float64),
        "observation.img_state_delta": np.zeros(1, dtype=np.float32),
        "teleop.navigate_command": np.zeros(4, dtype=np.float64),
        "teleop.base_height_command": np.zeros(1, dtype=np.float64),
        "action": np.zeros(43, dtype=np.float64),
        "action.eef": np.zeros(14, dtype=np.float64),
    }
    if "object_poses" in observation:
        row["observation.object_poses"] = np.asarray(observation["object_poses"], np.float64)
    elif num_objects > 0:
        row["observation.object_poses"] = np.zeros(num_objects * 7, dtype=np.float64)
    return row


def build(seeds: range, levels: list[int], out: Path | None) -> str:
    """Generate every condition; write the datasets when `out` is set. Returns the sha256."""
    env = make_env()
    task = env.unwrapped.task
    rows: list[dict[str, Any]] = []
    try:
        for level in levels:
            exporter = None
            obj_names: list[str] = []
            for index, seed in enumerate(seeds):
                observation, env_config = condition(env, seed, level)
                config = plain(env_config)
                rows.append({"level": level, "seed": seed, "environment_config": config})
                print(f"level {level} seed {seed}: {config_sha256(config)[:12]}", flush=True)
                if out is None:
                    continue
                if exporter is None:
                    from simple.cli.dr_decoupled_wbc import _init_exporter

                    obj_names = list(env.unwrapped.mujoco.mj_objects.keys())
                    exporter = _init_exporter(
                        str(out / ENV_ID / f"dr-level-{level}"),
                        task.instruction,
                        robot_model(task.robot),
                        obj_names,
                        task.robot.joint_names,
                        observation["head_stereo_left"].shape,
                    )
                exporter.add_frame(frame(observation, len(obj_names)))
                exporter.save_episode()
                _write_env_config(exporter, config, index)
            if exporter is not None:
                exporter.stop_video_writers()
    finally:
        env.close()
    digest = config_sha256(rows)
    if out is not None:
        with open(out / "conditions.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        (out / "conditions.sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def _write_env_config(exporter: Any, config: Any, episode_index: int) -> None:
    """SIMPLE's `_save_episode_env_config`, given the already-plain config."""
    meta = Path(exporter.root) / "meta" / "episodes.jsonl"
    lines = [json.loads(line) for line in meta.read_text(encoding="utf-8").splitlines()]
    lines[episode_index]["environment_config"] = json.dumps(config)
    meta.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--stop", type=int, required=True)
    parser.add_argument("--levels", type=int, nargs="+", default=[0, 1, 2])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--check", help="conditions_sha256 the RunPlan pins")
    args = parser.parse_args(argv)
    if not DEV[0] <= args.start < args.stop <= DEV[1]:
        print(f"seeds [{args.start}, {args.stop}) leave the dev range {DEV}", file=sys.stderr)
        return 2
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=False)
    digest = build(range(args.start, args.stop), args.levels, args.out)
    print(f"conditions_sha256 {digest}")
    if args.check is not None and digest != args.check:
        print(f"differs from {args.check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
