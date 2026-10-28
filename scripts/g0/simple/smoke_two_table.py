"""Smoke-test the SONIC two-table env in sim_mode=mujoco: reset, step, save frames, time it.

Builds the env the way simple.evals.sonic_wbc does (gear_sonic SimLoopConfig,
physics_dt 5 ms, render_hz 50). No whole-body controller runs: every step sends
the "elastic_band" action, so the robot hangs on the band while physics and
rendering advance. This checks the env, not the policy or WBC.

Run with the SIMPLE venv from scripts/g0/setup_simple.sh:

    MUJOCO_GL=egl fwdata/simple/.venv/bin/python scripts/g0/simple/smoke_two_table.py --out fwdata/simple/two_table/smoke
"""

import argparse
import json
import sys
import time
from pathlib import Path

import gymnasium as gym
import imageio.v3 as iio
import numpy as np
import tyro


def find_images(obs, prefix=""):
    if isinstance(obs, dict):
        for key, value in obs.items():
            yield from find_images(value, f"{prefix}{key}/")
    elif isinstance(obs, np.ndarray) and obs.ndim == 3 and obs.shape[2] == 3:
        yield prefix.rstrip("/"), obs.astype(np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-id", default="simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import simple.envs  # noqa: F401  registers SIMPLE's env ids
    from gear_sonic.utils.mujoco_sim.configs import SimLoopConfig
    from simple.core.action import ActionCmd

    sonic_config = tyro.cli(SimLoopConfig, config=(tyro.conf.ConsolidateSubcommandArgs,), args=[]).load_wbc_yaml()
    sonic_config["ENV_NAME"] = "simple"

    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    env = gym.make(
        args.env_id,
        sim_mode="mujoco",
        headless=True,
        render_hz=50,
        physics_dt=float(sonic_config["SIMULATE_DT"]),
        webrtc=False,
        sonic_config=sonic_config,
    )
    obs, info = env.reset(seed=args.seed)
    t_reset = time.perf_counter() - t0

    task = env.unwrapped.task
    action = ActionCmd("elastic_band", dropping=False, drop_rate=0.0)
    step_times = []
    for _ in range(args.steps):
        t = time.perf_counter()
        obs, reward, terminated, truncated, info = env.step(action)
        step_times.append(time.perf_counter() - t)
        if terminated or truncated:
            break

    images = dict(find_images(obs))
    for name, image in images.items():
        iio.imwrite(args.out / f"{name.replace('/', '_')}.png", image)
    pelvis_z = float(env.unwrapped.mjData.body("pelvis").xpos[2])
    env.close()

    report = {
        "env_id": args.env_id,
        "robot": type(task.robot).__name__,
        "instruction": task.instruction,
        "physics_dt": float(sonic_config["SIMULATE_DT"]),
        "steps": len(step_times),
        "reset_s": round(t_reset, 2),
        "step_ms_median": round(1000 * float(np.median(step_times)), 1),
        "pelvis_z_end": round(pelvis_z, 3),
        "images": {name: list(image.shape) for name, image in images.items()},
        "isaacsim_imported": "isaacsim" in sys.modules,
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if images and not report["isaacsim_imported"] else 1


if __name__ == "__main__":
    sys.exit(main())
