"""Measure how the arms hold the tray: elbow flare and height per episode (DA-33, D-25).

For each (variant, seed), runs one planner episode and, while both hands hold the
tray (GRASP to LOWER), averages over both arms, in the simulated pelvis frame:
- flare: |elbow y| - |shoulder y| (m); positive = elbow out beside the body.
- rise: elbow z - midpoint z of shoulder and wrist (m); positive = elbow above the arm line.
Also counts the steps of APPROACH_A in which a hand or wrist touches table A (`touch_a`).
Writes one JSON row per episode to --out and prints a table per variant.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/measure_arm_pose.py --seeds 100-121 --workers 22 \
        --variant base --variant elbow1:elbow_cost=1.0
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

HOLDING = {"GRASP", "LIFT", "BACK_OFF", "TURN", "CARRY", "ARRIVE_B", "LOWER"}


_ENV: Any = None


def _env() -> Any:
    """One env per process, kept for all its jobs (a second env failed to build its renderer)."""
    global _ENV
    if _ENV is None:
        from flywheel_simple.tray.simple_task import make_env

        _ENV = make_env(seed=100, level=1)
    return _ENV


def parse_variant(text: str) -> tuple[str, dict[str, float]]:
    name, _, sets = text.partition(":")
    pairs = (s.split("=") for s in sets.split(",") if s)
    return name, {k: float(v) for k, v in pairs}


def run_one(job: tuple[str, dict[str, float], int, int]) -> dict[str, Any]:
    import numpy as np
    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig

    name, sets, seed, level = job
    cfg = replace(PlannerConfig.load(), **sets)
    env = _env()
    agent = TrayAgent(env, cfg)
    flare: list[float] = []
    rise: list[float] = []
    touch_a = 0

    def in_pelvis(data: Any, body: str) -> Any:
        pelvis = data.body("pelvis")
        return pelvis.xmat.reshape(3, 3).T @ (data.body(body).xpos - pelvis.xpos)

    def hand_on_table_a(model: Any, data: Any) -> bool:
        for c in data.contact[: data.ncon]:
            names = {model.body(model.geom_bodyid[g]).name for g in (c.geom1, c.geom2)}
            if any(n.startswith("table_a") for n in names) and any(
                "hand" in n or "wrist" in n for n in names
            ):
                return True
        return False

    def on_step(obs: Any, info: Any, action: Any) -> None:
        nonlocal touch_a
        cmd = agent.last_command
        data = env.unwrapped.mjData
        if cmd is not None and cmd.phase.name == "APPROACH_A":
            touch_a += hand_on_table_a(env.unwrapped.mjModel, data)
        if cmd is None or cmd.phase.name not in HOLDING:
            return
        for side in ("left", "right"):
            shoulder = in_pelvis(data, f"{side}_shoulder_pitch_link")
            elbow = in_pelvis(data, f"{side}_elbow_link")
            wrist = in_pelvis(data, f"{side}_wrist_yaw_link")
            flare.append(abs(elbow[1]) - abs(shoulder[1]))
            rise.append(elbow[2] - (shoulder[2] + wrist[2]) / 2)

    result = run_episode(env, agent, seed=seed, level=level, on_step=on_step)
    return {
        "variant": name,
        "sets": sets,
        "seed": seed,
        "level": level,
        "success": result.success,
        "failure": result.failure or result.abort_reason,
        "flare_m": round(float(np.mean(flare)), 4) if flare else None,
        "rise_m": round(float(np.mean(rise)), 4) if rise else None,
        "touch_a": touch_a,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="100-121", help="first-last, inclusive")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--variant", action="append", default=[], help="name[:key=value,...]")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("fwdata/simple/tray/arm_pose.jsonl"))
    ap.add_argument("--jobs", type=Path, help="run these jobs in this process (set by --workers)")
    args = ap.parse_args()

    if args.jobs is not None:
        with args.out.open("w") as f:
            for job in json.loads(args.jobs.read_text()):
                f.write(json.dumps(run_one(tuple(job))) + "\n")
                f.flush()
        return 0

    first, last = (int(s) for s in args.seeds.split("-"))
    variants = [parse_variant(v) for v in args.variant or ["base"]]
    jobs = [(n, s, seed, args.level) for n, s in variants for seed in range(first, last + 1)]
    work = args.out.with_suffix(".parts")
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    procs = []
    # One process per worker, started 5 s apart: 22 workers opening EGL at once failed
    # in eglMakeCurrent, and a multiprocessing pool failed to build renderers (D-23).
    for k in range(args.workers):
        mine = jobs[k :: args.workers]
        if not mine:
            continue
        if procs:
            time.sleep(5.0)
        (work / f"jobs-{k:02d}.json").write_text(json.dumps(mine))
        cmd = [sys.executable, __file__, "--jobs", str(work / f"jobs-{k:02d}.json")]
        cmd += ["--out", str(work / f"rows-{k:02d}.jsonl")]
        with (work / f"worker-{k:02d}.log").open("w") as log:
            procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env))
    failed = [p.args for p in procs if p.wait() != 0]
    rows = [json.loads(line) for part in sorted(work.glob("rows-*.jsonl")) for line in part.open()]
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    for name, _ in variants:
        mine = [r for r in rows if r["variant"] == name]
        held = [r for r in mine if r["flare_m"] is not None]
        flare = sum(r["flare_m"] for r in held) / max(len(held), 1)
        rise = sum(r["rise_m"] for r in held) / max(len(held), 1)
        fails = sorted((r["seed"], r["failure"]) for r in mine if not r["success"])
        touched = sum(r.get("touch_a", 0) > 0 for r in mine)
        print(
            f"{name:10s} success {sum(r['success'] for r in mine)}/{len(mine)}  "
            f"flare {flare:+.3f} m  rise {rise:+.3f} m  touched A {touched}  failures {fails}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
