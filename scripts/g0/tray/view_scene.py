"""Record the tray scene: G1 stands and walks, or the scripted planner carries the tray.

Writes the head-camera video (what the policy sees), a fixed overview video and a
report.json into --out (default fwdata/simple/tray/view). With `--agent stand`
the robot is driven only by the stand-and-walk controller and nothing grasps the
tray, so the report shows no step reached unless the scene is broken. With
`--agent planner` one episode runs through flywheel_simple.tray.agent (DA-33)
and the report adds the episode result and its phase timeline.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/view_scene.py --seed 1000000 --level 2 --seconds 6 --walk 0.2
    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/view_scene.py --agent planner --seed 0 --level 0 \
        --out fwdata/simple/tray/planner
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import imageio.v2 as iio
import mujoco
import numpy as np
from flywheel_simple.tray.simple_task import make_env
from flywheel_simple.wbc import StandWalkController, release_band

FPS = 50  # env steps per second (render_hz)


class Videos:
    """Head camera and a fixed overview, every second env step."""

    def __init__(self, sim: Any, out: Path) -> None:
        model = sim.mjModel
        model.vis.global_.offwidth, model.vis.global_.offheight = 1280, 720
        self.sim = sim
        self.overview = mujoco.Renderer(model, 720, 1280)
        self.cam = mujoco.MjvCamera()
        self.cam.lookat[:], self.cam.distance = [0.0, 0, 0.7], 3.6
        self.cam.elevation, self.cam.azimuth = -22, 215
        self.paths = [out / "head.mp4", out / "overview.mp4"]
        self.writers = [
            iio.get_writer(p, fps=FPS // 2, codec="libx264", quality=8) for p in self.paths
        ]
        self.count = 0

    def add(self, obs: dict[str, Any]) -> None:
        if self.count % 2 == 0:
            self.writers[0].append_data(obs["head_stereo_left"])
            self.overview.update_scene(self.sim.mjData, self.cam)
            self.writers[1].append_data(self.overview.render())
        self.count += 1

    def close(self) -> None:
        for w in self.writers:
            w.close()


def run_stand(env: Any, args: argparse.Namespace, videos: Videos) -> dict[str, Any]:
    sim = env.unwrapped
    ctrl = StandWalkController(sim.task.robot)
    ctrl.reset()
    released = release_band(env, ctrl)
    steps = int(args.seconds * FPS)
    info: dict = {}
    step_s = []
    for i in range(steps):
        walking = args.walk and steps // 3 <= i < 2 * steps // 3
        cmd = (args.walk, 0.0, 0.0, 0.0) if walking else (0.0, 0.0, 0.0, 0.0)
        t = time.perf_counter()
        obs, _, _, _, info = env.step(ctrl.action(sim.task.robot.prepare_obs(), navigate_cmd=cmd))
        step_s.append(time.perf_counter() - t)
        videos.add(obs)
    return {
        "band_released_at_step": released,
        "env_step_ms_median": round(1000 * float(np.median(step_s)), 1),
        "tray_report": asdict(info["tray_report"]),
    }


def run_planner(env: Any, args: argparse.Namespace, videos: Videos) -> dict[str, Any]:
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    agent = TrayAgent(env, PlannerConfig.load(args.planner_config))
    last: dict[str, Any] = {}

    def on_step(obs: dict[str, Any], info: dict[str, Any], action: Any) -> None:
        videos.add(obs)
        last["info"] = info

    result = run_episode(env, agent, seed=args.seed, level=args.level, on_step=on_step)
    return {
        "result": asdict(result),
        "tray_report": asdict(last["info"]["tray_report"]) if last else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agent", choices=("stand", "planner"), default="stand")
    parser.add_argument("--seed", type=int, default=1_000_000)
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=5.0, help="stand agent only")
    parser.add_argument("--walk", type=float, default=0.0, help="vx for the middle third (m/s)")
    parser.add_argument("--planner-config", type=Path, default=None, help="tray_planner.yaml")
    parser.add_argument("--out", type=Path, default=Path("fwdata/simple/tray/view"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    env = make_env(seed=args.seed, level=args.level)
    sim = env.unwrapped
    env.reset(seed=args.seed, options={"level": args.level})
    t_reset = time.perf_counter() - t0
    videos = Videos(sim, args.out)
    try:
        run = run_planner if args.agent == "planner" else run_stand
        body = run(env, args, videos)
    finally:
        videos.close()
    pelvis = sim.mjData.body("pelvis").xpos
    report = {
        "agent": args.agent,
        "seed": args.seed,
        "level": args.level,
        "sample": asdict(sim.task.sample),
        "first_reset_s": round(t_reset, 1),
        "pelvis_end": [round(float(v), 3) for v in pelvis],
        **body,
        "videos": [str(p) for p in videos.paths],
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
