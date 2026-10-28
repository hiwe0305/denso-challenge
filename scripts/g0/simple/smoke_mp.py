"""Smoke-test a SIMPLE env in sim_mode=mujoco: reset, step, save camera frames, time it.

Run with the SIMPLE venv from setup_simple_mujoco.sh, for example:

    MUJOCO_GL=egl fwdata/simple/.venv/bin/python scripts/g0/simple/smoke_mp.py \
        --env-id simple/G1WholebodyBendPickMP-v0 --steps 100 --out fwdata/simple/smoke_mp
"""

import argparse
import json
import sys
import time
from pathlib import Path

import gymnasium as gym
import imageio.v3 as iio
import numpy as np


def find_images(obs, prefix=""):
    """Yield (name, HxWx3 uint8 array) for every RGB image in a nested observation."""
    if isinstance(obs, dict):
        for key, value in obs.items():
            yield from find_images(value, f"{prefix}{key}/")
    elif isinstance(obs, np.ndarray) and obs.ndim == 3 and obs.shape[2] == 3:
        yield prefix.rstrip("/"), obs.astype(np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-id", default="simple/G1WholebodyBendPickMP-v0")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--render-hz", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path("fwdata/simple/smoke_mp"))
    args = parser.parse_args()

    import simple.envs  # noqa: F401  registers SIMPLE's env ids

    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    env = gym.make(args.env_id, sim_mode="mujoco", headless=True, render_hz=args.render_hz)
    obs, info = env.reset(seed=args.seed)
    t_reset = time.perf_counter() - t0

    robot = env.unwrapped.task.robot
    step_times = []
    for _ in range(args.steps):
        t = time.perf_counter()
        obs, reward, terminated, truncated, info = env.step(robot.random_action())
        step_times.append(time.perf_counter() - t)
        if terminated or truncated:
            break

    images = dict(find_images(obs))
    for name, image in images.items():
        iio.imwrite(args.out / f"{name.replace('/', '_')}.png", image)
    env.close()

    report = {
        "env_id": args.env_id,
        "steps": len(step_times),
        "reset_s": round(t_reset, 2),
        "step_ms_median": round(1000 * float(np.median(step_times)), 1),
        "images": {name: list(image.shape) for name, image in images.items()},
        "isaacsim_imported": "isaacsim" in sys.modules,
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if images and not report["isaacsim_imported"] else 1


if __name__ == "__main__":
    sys.exit(main())
