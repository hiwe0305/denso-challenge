"""Trials of fixes for the tray S1 arm jumps: cap the arm goal's step (DA-33).

Runs tray episodes (no recording) with the planner and WBC of the batch:

- `baseline`: as they are;
- `rate_limit`: the IK's upper-body goal moves at most `--max-step` rad per control
  step towards the IK solution; the IK keeps its own warm-started solution, only the
  goal sent to the WBC (what the dataset records as `action`) is capped;
- `ik_velocity`: the IK's own QP gets a velocity limit (pink `VelocityLimit` on its
  model) such that its `num_step_per_frame` steps of `dt` move a joint at most
  `--max-step` rad per control step; the goal is the IK solution as before.

One JSON line per episode: success, failure, phases, and the largest per-step move
of the recorded arm goal.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/wrist_jump_fix_trial.py --variant rate_limit --seeds 300000 300001 \
        --out fwdata/analysis/wrist_jump_trial/rate_limit-0.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

# Arm slots of decoupled_wbc's upper_body group (waist 0-2, left arm 3-9, left hand
# 10-16, right arm 17-23, right hand 24-30).
ARM_SLOTS = list(range(3, 10)) + list(range(17, 24))


def install_rate_limit(max_step: float) -> None:
    from flywheel_simple.wbc import upper_body

    solve, reset = upper_body.UpperBodyIK.solve, upper_body.UpperBodyIK.reset

    def capped_solve(self: Any, left: Any, right: Any) -> Any:
        goal = solve(self, left, right)
        prev = getattr(self, "_capped_prev", None)
        if prev is not None:
            goal[ARM_SLOTS] = prev[ARM_SLOTS] + np.clip(
                goal[ARM_SLOTS] - prev[ARM_SLOTS], -max_step, max_step)
        self._capped_prev = goal.copy()
        return goal

    def fresh_reset(self: Any, sim_obs: Any) -> None:
        reset(self, sim_obs)
        self._capped_prev = None

    upper_body.UpperBodyIK.solve = capped_solve  # type: ignore[method-assign]
    upper_body.UpperBodyIK.reset = fresh_reset  # type: ignore[method-assign]


def install_ik_velocity_limit(max_step: float) -> None:
    from flywheel_simple.wbc import upper_body
    from pink.limits import VelocityLimit

    init = upper_body.UpperBodyIK.__init__

    def limited_init(self: Any, robot_model: Any) -> None:
        init(self, robot_model)
        solver = self._ik.body_ik_solver
        model = solver.configuration.model
        per_frame = solver.num_step_per_frame * solver.dt * solver.amplify_factor
        speed = np.minimum(np.asarray(model.velocityLimit, float), max_step / per_frame)
        model.velocity_limit = VelocityLimit(model, velocity_limit=speed)

    upper_body.UpperBodyIK.__init__ = limited_init  # type: ignore[method-assign]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", required=True,
                        choices=("baseline", "rate_limit", "ik_velocity"))
    parser.add_argument("--max-step", type=float, default=0.08)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.variant == "rate_limit":
        install_rate_limit(args.max_step)
    if args.variant == "ik_velocity":
        install_ik_velocity_limit(args.max_step)

    from flywheel_simple.tray.agent import TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig
    from flywheel_simple.tray.simple_task import make_env

    done = set()
    if args.out.exists():
        done = {json.loads(line)["seed"] for line in args.out.read_text().splitlines() if line}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    env = make_env(seed=args.seeds[0], level=args.level)
    agent = TrayAgent(env, PlannerConfig.load())
    for seed in args.seeds:
        if seed in done:
            continue
        goals: list[np.ndarray] = []

        def on_frame(obs: dict[str, Any], info: dict[str, Any], record: dict[str, Any]) -> None:
            goals.append(np.asarray(record["goal_upper_body"], float)[ARM_SLOTS])

        result = run_episode(env, agent, seed=seed, level=args.level, on_frame=on_frame)
        jumps = np.abs(np.diff(np.array(goals), axis=0)).max(axis=1)
        row = {"variant": args.variant, "max_step": args.max_step, "seed": seed,
               "level": args.level, "success": result.success, "failure": result.failure,
               "abort_reason": result.abort_reason, "phases": result.phases,
               "steps": result.steps, "wall_s": result.wall_s,
               "arm_jump_max": float(jumps.max()),
               "arm_jump_p999": float(np.quantile(jumps, 0.999)),
               "steps_over_0.0869": int((jumps > 0.0869346).sum())}
        with args.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)
    env.close()


if __name__ == "__main__":
    main()
