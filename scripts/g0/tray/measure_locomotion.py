"""Measure G1 walking and turning in the tray scene on decoupled WBC (DA-33 Task 1).

Each case starts from a fresh reset at seed 0, level 0, after band release, so
cases do not inherit each other's drift. Walk and turn cases run with the tables
--corridor apart (same floor, robot and physics): in the default 1.8 m corridor
G1's fingers reach table A's edge after a few centimetres. One case (`scene:
default`) walks towards table A in the default scene to keep that measured. Writes one
JSON row per case (and the per-step log of every case) into --out (default
fwdata/simple/tray/locomotion).

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/measure_locomotion.py
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from flywheel_simple.tray import TrayConfig
from flywheel_simple.tray.simple_task import make_env
from flywheel_simple.wbc import StandWalkController, release_band
from flywheel_simple.wbc.drive import Driver, turn, walk

WALK_SECONDS = 4.0


def standing(env: Any) -> Driver:
    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    release_band(env, ctrl)
    return Driver(env, ctrl)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("fwdata/simple/tray/locomotion"))
    parser.add_argument("--corridor", type=float, default=8.0, help="table gap for walk/turn (m)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    open_cfg = replace(TrayConfig.load(), corridor=args.corridor).write(args.out / "tray_open.yaml")

    cases: list[dict[str, Any]] = []
    for hold in (0.0, 0.1):
        for vx in (0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.25, -0.4):
            cases.append({"kind": "walk", "vx": vx, "hold_heading": hold})
    for vyaw in (0.3, 0.5, 1.0):
        cases.append({"kind": "turn", "vyaw": vyaw, "target": math.pi})

    cases.append({"kind": "walk", "vx": 0.3, "hold_heading": 0.0, "scene": "default"})

    configs = {"open": str(open_cfg), "default": None}
    env: Any = None
    scene_now = None
    rows = []
    try:
        for i, case in enumerate(cases):
            scene = case.setdefault("scene", "open")
            if scene != scene_now:  # make_env: one live env per process
                if env is not None:
                    env.close()
                env, scene_now = make_env(seed=0, tray_config=configs[scene]), scene
            driver = standing(env)
            t0 = time.perf_counter()
            if case["kind"] == "walk":
                along, lateral, up = walk(
                    driver, case["vx"], WALK_SECONDS, hold_heading=case["hold_heading"]
                )
                yaw_end = driver.log[-1]["yaw"]
                row = {
                    **case,
                    "seconds": WALK_SECONDS,
                    "along_m": round(along, 3),
                    "lateral_m": round(lateral, 3),
                    "speed_ms": round(along / WALK_SECONDS, 3),
                    "ratio": round(along / (case["vx"] * WALK_SECONDS), 2),
                    "yaw_end_deg": round(math.degrees(yaw_end), 1),
                }
            else:
                dyaw, moved, up = turn(driver, case["vyaw"], case["target"], max_seconds=15.0)
                turning = [r for r in driver.log if r["walk_policy"]]
                row = {
                    **case,
                    "dyaw_deg": round(math.degrees(dyaw), 1),
                    "turn_s": round(len(turning) * driver.nav.dt, 2),
                    "moved_m": round(moved, 3),
                }
            row["min_upright"] = round(up, 4)
            row["fell"] = up < 0.9
            row["wall_s"] = round(time.perf_counter() - t0, 1)
            rows.append(row)
            print(json.dumps(row), flush=True)
            (args.out / f"case_{i:02d}.json").write_text(json.dumps(driver.log))
    finally:
        if env is not None:
            env.close()
    (args.out / "summary.json").write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
