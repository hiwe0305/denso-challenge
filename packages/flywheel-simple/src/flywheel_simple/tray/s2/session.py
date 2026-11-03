"""Run S2 jobs through SIMPLE's PICO pipeline and record the successful ones (DA-35 tasks 9-11).

One worker: one env, one LeRobot dataset under `--save-dir`, the jobs of a
JSON-lines file (`parent_id`, `level`, `seed`, `gen_seed` per line), one attempt
each. The loop is the PICO session's (flywheel_simple.tray.pico.session): sim
clock, only successes saved, every attempt logged to `attempts.jsonl` with its
job, outcome, failure label and times.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \\
        -m flywheel_simple.tray.s2.session --parents fwdata/simple/tray/virtual/parents-1103b \\
        --jobs jobs.jsonl --save-dir fwdata/simple/tray/s2/<run>/shard-00
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from flywheel_simple.tray.pico.conditions import ConditionQueue
from flywheel_simple.tray.s2.jobs import read_jobs

OPERATOR = "op-s2"
SOURCE_DETAIL = "s2"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--parents", type=Path, required=True, help="parent batch directory")
    parser.add_argument("--jobs", type=Path, required=True, help="JSON lines of S2 jobs")
    parser.add_argument("--save-dir", type=Path, required=True)
    parser.add_argument("--session", default=datetime.now().strftime("s2-%Y%m%d-%H%M%S"))
    parser.add_argument("--config", type=Path, default=None, help="tray_s2.yaml")
    parser.add_argument("--operator-config", type=Path, default=None)
    parser.add_argument("--keep-failed", action="store_true", help="also save failed attempts")
    parser.add_argument(
        "--mode", choices=["exact", "variant"], default="variant", help="exact: parent as recorded"
    )
    args = parser.parse_args(argv)

    from flywheel_simple.tray.pico import agent as pico_agent
    from flywheel_simple.tray.pico.clock import SimClock
    from flywheel_simple.tray.pico.operator import OperatorConfig
    from flywheel_simple.tray.pico.session import make_teleop_env, run_session
    from flywheel_simple.tray.s2.config import S2Config
    from flywheel_simple.tray.s2.streamer import ParentStore, S2Streamer

    jobs = read_jobs(args.jobs)
    s2_cfg = S2Config.load(args.config)
    env = make_teleop_env(jobs[0].level if jobs else 0, headless=True)
    streamer = S2Streamer(
        env,
        ParentStore(args.parents, s2_cfg),
        OperatorConfig.load(args.operator_config),
        s2_cfg,
        mode=args.mode,
    )
    agent = pico_agent.StreamerDecoupledAgent(env.unwrapped.task.robot, streamer, clock=SimClock())
    agent.num_episodes = len(jobs)
    try:
        summary = run_session(
            env,
            agent,
            ConditionQueue(jobs, max_attempts=1),
            save_dir=args.save_dir,
            operator=OPERATOR,
            session=args.session,
            source_detail=SOURCE_DETAIL,
            keep_failed=args.keep_failed,
        )
    finally:
        env.close()
        agent.close()
    print(json.dumps(asdict(summary)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
