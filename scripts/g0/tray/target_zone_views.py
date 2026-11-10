"""Head-camera views of planner episodes with and without the target zone, and their physics.

For each (level, seed) the scripted planner runs the episode twice in one env:
once on the scene as built now (target zone drawn, visuals_revision `...+zone1`),
once with `mjcf.add_target_zone` switched off (the scene before). It saves what
the policy sees (`head_stereo_left`, 320x180) at the start of TURN, CARRY, 1 s
and 2 s into CARRY, ARRIVE_B and LOWER as one PNG per episode (top row before,
bottom row after), and compares the two runs' qpos, qvel and action at every step.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/target_zone_views.py --out fwdata/simple/tray/target-zone \
        --cases 0:0 1:1279 2:125195
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import imageio.v2 as iio
import numpy as np
from flywheel_simple.tray import mjcf
from flywheel_simple.tray.agent import TrayAgent, run_episode
from flywheel_simple.tray.planner import PlannerConfig
from flywheel_simple.tray.recorder import visuals_revision
from flywheel_simple.tray.simple_task import make_env
from flywheel_simple.tray.visuals import default_manifest_path

CAMERA = "head_stereo_left"
FPS = 50
# (label, phase, seconds after the phase starts)
MOMENTS = [
    ("TURN", "TURN", 0.0),
    ("CARRY", "CARRY", 0.0),
    ("CARRY+1s", "CARRY", 1.0),
    ("CARRY+2s", "CARRY", 2.0),
    ("ARRIVE_B", "ARRIVE_B", 0.0),
    ("LOWER", "LOWER", 0.0),
]


def run(env: Any, level: int, seed: int, zone: bool) -> dict[str, Any]:
    original = mjcf.add_target_zone
    if not zone:
        mjcf.add_target_zone = lambda *a, **k: None
    sim = env.unwrapped
    agent = TrayAgent(env, PlannerConfig.load())
    frames: dict[str, np.ndarray] = {}
    starts: dict[str, int] = {}
    states: list[np.ndarray] = []
    step = 0

    def on_frame(obs: Any, info: Any, record: Any) -> None:
        nonlocal step
        cmd = agent.last_command
        phase = cmd.phase.name if cmd is not None else "?"
        starts.setdefault(phase, step)
        for label, name, after in MOMENTS:
            if name in starts and step == starts[name] + round(after * FPS):
                frames[label] = np.asarray(obs[CAMERA]).copy()
        step += 1

    def on_step(obs: Any, info: Any, action: Any) -> None:
        states.append(np.concatenate([sim.mjData.qpos, sim.mjData.qvel, np.asarray(action)]))

    try:
        result = run_episode(env, agent, seed, level, on_step=on_step, on_frame=on_frame)
    finally:
        mjcf.add_target_zone = original
    has_zone = any(sim.mjModel.body(i).name == "target_zone" for i in range(sim.mjModel.nbody))
    return {
        "result": result,
        "frames": frames,
        "states": np.array(states),
        "has_zone": has_zone,
        "target_pose": sim.task.target_pose,
    }


def grid(before: dict[str, np.ndarray], after: dict[str, np.ndarray]) -> np.ndarray:
    labels = [m[0] for m in MOMENTS if m[0] in before or m[0] in after]
    shape = next(iter({**before, **after}.values())).shape
    blank = np.zeros(shape, np.uint8)
    rows = [
        np.concatenate([np.pad(row.get(lb, blank), ((2, 2), (2, 2), (0, 0))) for lb in labels], 1)
        for row in (before, after)
    ]
    return np.concatenate(rows, 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="+", default=["0:0", "1:1279", "2:125195"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "visuals_revision": visuals_revision(default_manifest_path()),
        "moments": [m[0] for m in MOMENTS],
        "camera": CAMERA,
        "episodes": [],
    }
    env = make_env(seed=0)
    try:
        for case in args.cases:
            level, seed = (int(v) for v in case.split(":"))
            after = run(env, level, seed, zone=True)
            before = run(env, level, seed, zone=False)
            a, b = after["states"], before["states"]
            same = a.shape == b.shape and bool(np.array_equal(a, b))
            diff = float(np.max(np.abs(a - b))) if a.shape == b.shape else None
            name = f"L{level}-s{seed}"
            iio.imwrite(args.out / f"{name}.png", grid(before["frames"], after["frames"]))
            for label, img in after["frames"].items():
                iio.imwrite(args.out / f"{name}-after-{label}.png", img)
            t = after["target_pose"]
            report["episodes"].append({
                "level": level,
                "seed": seed,
                "target_pose": [t.x, t.y, t.yaw],
                "zone_in_scene": {"after": after["has_zone"], "before": before["has_zone"]},
                "success": {"after": after["result"].success, "before": before["result"].success},
                "phases_after": after["result"].phases,
                "phases_same": after["result"].phases == before["result"].phases,
                "steps": [len(a), len(b)],
                "state_identical": same,
                "state_max_abs_diff": diff,
                "image_shape": list(next(iter(after["frames"].values())).shape),
                "moments_found": sorted(after["frames"]),
            })
            print(json.dumps(report["episodes"][-1]), flush=True)
    finally:
        env.close()
    (args.out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    return 0 if all(e["state_identical"] for e in report["episodes"]) else 1


if __name__ == "__main__":
    sys.exit(main())
