"""Record the tray scene: G1 under decoupled WBC stands, optionally walks, then stands again.

Writes the head-camera video (what the policy sees), a fixed overview video and a
report.json with the step report, into --out (default fwdata/simple/tray/view).
The robot is driven only by the stand-and-walk controller; nothing grasps the
tray, so the report shows no step reached unless the scene is broken.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/view_scene.py --seed 1000000 --level 2 --seconds 6 --walk 0.2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import imageio.v2 as iio
import mujoco
import numpy as np
from flywheel_simple.tray.simple_task import make_env
from flywheel_simple.wbc import StandWalkController, release_band

FPS = 50  # env steps per second (render_hz)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=1_000_000)
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--walk", type=float, default=0.0, help="vx for the middle third (m/s)")
    parser.add_argument("--out", type=Path, default=Path("fwdata/simple/tray/view"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    env = make_env(seed=args.seed, level=args.level)
    sim = env.unwrapped
    obs, _ = env.reset(seed=args.seed, options={"level": args.level})
    t_reset = time.perf_counter() - t0
    ctrl = StandWalkController(sim.task.robot)
    ctrl.reset()
    released = release_band(env, ctrl)

    model = sim.mjModel
    model.vis.global_.offwidth, model.vis.global_.offheight = 1280, 720
    overview = mujoco.Renderer(model, 720, 1280)
    cam = mujoco.MjvCamera()
    cam.lookat[:], cam.distance, cam.elevation, cam.azimuth = [0.3, 0, 0.7], 3.4, -22, 215
    head_writer = iio.get_writer(args.out / "head.mp4", fps=FPS // 2, codec="libx264", quality=8)
    over_writer = iio.get_writer(
        args.out / "overview.mp4", fps=FPS // 2, codec="libx264", quality=8
    )
    steps = int(args.seconds * FPS)
    info: dict = {}
    step_s = []
    for i in range(steps):
        walking = args.walk and steps // 3 <= i < 2 * steps // 3
        cmd = (args.walk, 0.0, 0.0, 0.0) if walking else (0.0, 0.0, 0.0, 0.0)
        t = time.perf_counter()
        obs, _, _, _, info = env.step(ctrl.action(sim.task.robot.prepare_obs(), navigate_cmd=cmd))
        step_s.append(time.perf_counter() - t)
        if i % 2 == 0:
            head_writer.append_data(obs["head_stereo_left"])
            overview.update_scene(sim.mjData, cam)
            over_writer.append_data(overview.render())
    head_writer.close()
    over_writer.close()

    pelvis = sim.mjData.body("pelvis").xpos
    report = {
        "seed": args.seed,
        "level": args.level,
        "sample": asdict(sim.task.sample),
        "first_reset_s": round(t_reset, 1),
        "band_released_at_step": released,
        "env_step_ms_median": round(1000 * float(np.median(step_s)), 1),
        "pelvis_end": [round(float(v), 3) for v in pelvis],
        "tray_report": asdict(info["tray_report"]),
        "videos": [str(args.out / "head.mp4"), str(args.out / "overview.mp4")],
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
