"""Re-run tray seeds in sim and log the planner phase and segment at every step (DA-33).

Companion of wrist_jump.py: the release does not record the planner's phase, so this
runs the same planner on the same (level, seed) and writes, per step, the phase, the
smoothing segment key, the number of decaying wrist blends, the IK's upper-body goal and
the measured joints, and the wrist targets. Nothing is recorded as data; the scene, planner and
WBC are those of the batch (same code and tray_planner.yaml).

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/wrist_jump_sim.py --seeds 1000 1022 --out fwdata/analysis/wrist_jump_sim
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit-s", type=float, default=90.0)
    args = parser.parse_args()

    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig
    from flywheel_simple.tray.simple_task import make_env

    args.out.mkdir(parents=True, exist_ok=True)
    env = make_env(seed=args.seeds[0], level=args.level)
    agent = TrayAgent(env, PlannerConfig.load())
    for seed in args.seeds:
        rows: list[dict[str, Any]] = []

        def on_frame(obs: dict[str, Any], info: dict[str, Any], record: dict[str, Any]) -> None:
            planner = agent.planner
            cmd = agent.last_command
            assert planner is not None and cmd is not None
            key = planner._nominal[0] if planner._nominal is not None else None
            rows.append({
                "step": len(rows),
                "phase": cmd.phase.name,
                "segment": None if key is None else [key[0].name, key[1]],
                "blends": len(planner._wrist_blends),
                "raised": planner._raised,
                "nav": list(cmd.nav),
                "left_wrist": np.asarray(cmd.left_wrist).round(6).tolist(),
                "right_wrist": np.asarray(cmd.right_wrist).round(6).tolist(),
                "upper_goal": np.asarray(record["goal_upper_body"], float).round(6).tolist(),
                "joint_qpos": np.asarray(obs["joint_qpos"], float).round(6).tolist(),
            })

        result = run_episode(env, agent, seed=seed, level=args.level, on_frame=on_frame,
                             limit_s=args.limit_s)
        path = args.out / f"seed_{seed}.jsonl"
        with path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(json.dumps({"seed": seed, "success": result.success, "steps": result.steps,
                          "phases": result.phases, "rows": str(path)}))
    env.close()


if __name__ == "__main__":
    main()
