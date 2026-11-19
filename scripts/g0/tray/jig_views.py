"""Head-camera views of planner episodes on the jig scene, and how much of the jig they show.

For each (level, seed) the scripted planner runs the episode on the jig env
(`flywheel_simple.tray.jig_task`). It saves what the policy sees (`head_stereo_left`)
at the start of TURN, CARRY, 1 s and 2 s into CARRY, ARRIVE_B and LOWER as one PNG per
episode, and counts at each moment the pixels in the jig's blue and in the target zone's
orange: the zone lies flat under the carried tray, the guides stand around it. Writes
`report.json` with the counts, the outcome and the phases.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/jig_views.py --out fwdata/simple/tray/jig-views \
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
from flywheel_simple.tray.agent import TrayAgent, run_episode
from flywheel_simple.tray.jig_task import make_env
from flywheel_simple.tray.planner import PlannerConfig
from flywheel_simple.tray.recorder import visuals_revision
from flywheel_simple.tray.visuals import default_manifest_path
from numpy.typing import NDArray

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


def blue_mask(img: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Pixels in the jig's blue (JIG_RGBA, shaded): almost no red, green under 0.7 blue.

    The floor checker is blue-grey too (about 41, 81, 120): its red is a third of its
    blue, the jig's under a fifth, so the red ratio tells them apart.
    """
    r, g, b = (img[..., k].astype(np.int32) for k in range(3))
    return (b > 80) & (r * 5 < b) & (g * 10 < b * 7)


def orange_mask(img: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Pixels in the target zone's orange (TARGET_ZONE_RGBA, shaded)."""
    r, g, b = (img[..., k].astype(np.int16) for k in range(3))
    return (r > 120) & (r - g > 50) & (g - b > 15) & (b < 90)


def run(env: Any, level: int, seed: int) -> dict[str, Any]:
    agent = TrayAgent(env, PlannerConfig.load())
    frames: dict[str, NDArray[np.uint8]] = {}
    starts: dict[str, int] = {}
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

    result = run_episode(env, agent, seed, level, on_frame=on_frame)
    t = env.unwrapped.task.target_pose
    return {"result": result, "frames": frames, "target_pose": [t.x, t.y, t.yaw]}


def grid(frames: dict[str, NDArray[np.uint8]]) -> NDArray[np.uint8]:
    labels = [m[0] for m in MOMENTS if m[0] in frames]
    return np.concatenate([np.pad(frames[lb], ((2, 2), (2, 2), (0, 0))) for lb in labels], 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="+", default=["0:0", "1:1279", "2:125195"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "visuals_revision": visuals_revision(default_manifest_path(), jig=True),
        "moments": [m[0] for m in MOMENTS],
        "camera": CAMERA,
        "episodes": [],
    }
    env = make_env(seed=0)
    try:
        for case in args.cases:
            level, seed = (int(v) for v in case.split(":"))
            ep = run(env, level, seed)
            name = f"L{level}-s{seed}"
            if ep["frames"]:
                iio.imwrite(args.out / f"{name}.png", grid(ep["frames"]))
            pixels = {
                label: {
                    "jig_blue": int(blue_mask(img).sum()),
                    "zone_orange": int(orange_mask(img).sum()),
                }
                for label, img in ep["frames"].items()
            }
            res = ep["result"]
            report["episodes"].append({
                "level": level,
                "seed": seed,
                "target_pose": ep["target_pose"],
                "success": res.success,
                "failure": res.failure,
                "abort_reason": res.abort_reason,
                "phases": res.phases,
                "pixels": pixels,
                "image_shape": list(next(iter(ep["frames"].values())).shape)
                if ep["frames"] else None,
            })
            print(json.dumps(report["episodes"][-1]), flush=True)
    finally:
        env.close()
    (args.out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
