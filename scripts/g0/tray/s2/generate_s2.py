"""Run S2 jobs over parallel workers and summarise them (DA-35 tasks 9-12).

Job lists:

- `--replay`: every parent of `<parents>/s2_segments.jsonl` on its own condition,
  untransformed (task 9: how well the pipeline reproduces a demo).

The jobs go round-robin to `--workers` processes; each worker is one
`flywheel_simple.tray.s2.session` with its own env and LeRobot dataset under
`<out>/shard-NN/`. A rerun skips the jobs any shard has already logged, so the
jobs of a killed worker run again (with any number of workers). At the end (or with --summarize) it writes
`<out>/summary.json`: attempts, outcomes, failure labels, sim and machine time.

Run on the sim machine in the SIMPLE venv, detached:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid \\
        fwdata/simple/.venv/bin/python scripts/g0/tray/s2/generate_s2.py \\
        --parents fwdata/simple/tray/virtual/parents-1103b --out fwdata/simple/tray/s2/replay-1104 \\
        --replay --workers 12 < /dev/null > replay.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

JOB_KEYS = ("parent_id", "level", "seed", "gen_seed")


def segments_of(parents: Path) -> list[dict[str, Any]]:
    path = parents / "s2_segments.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def replay_jobs(parents: Path) -> list[dict[str, Any]]:
    return [
        {"parent_id": p["parent_id"], "level": p["level"], "seed": p["seed"], "gen_seed": 0}
        for p in segments_of(parents)
    ]


def job_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[k] for k in JOB_KEYS)


def attempts_of(shard: Path) -> list[dict[str, Any]]:
    path = shard / "attempts.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def logged_key(attempt: dict[str, Any]) -> tuple[Any, ...]:
    return (attempt["parent_episode"], attempt["level"], attempt["seed"], attempt["gen_seed"])


def launch(args: argparse.Namespace, jobs: list[dict[str, Any]]) -> list[subprocess.Popen[bytes]]:
    """One worker per shard; jobs any shard has logged are not run again."""
    done = {logged_key(a) for shard in args.out.glob("shard-*") for a in attempts_of(shard)}
    todo = [j for j in jobs if job_key(j) not in done]
    procs = []
    for k in range(args.workers):
        shard = args.out / f"shard-{k:02d}"
        mine = todo[k :: args.workers]
        if not mine:
            continue
        shard.mkdir(parents=True, exist_ok=True)
        jobs_file = shard / "jobs.jsonl"
        jobs_file.write_text("".join(json.dumps(j) + "\n" for j in mine))
        cmd = [
            sys.executable, "-m", "flywheel_simple.tray.s2.session",
            "--parents", str(args.parents), "--jobs", str(jobs_file),
            "--session", f"{args.out.name}-{k:02d}", "--save-dir", str(shard),
        ]  # fmt: skip
        log = (shard / "worker.log").open("ab")
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT))
    return procs


def summarize(out: Path, wall_s: float | None) -> dict[str, Any]:
    attempts = [a for shard in sorted(out.glob("shard-*")) for a in attempts_of(shard)]
    outcomes = Counter(a["outcome"] for a in attempts)
    successes = outcomes.get("success", 0)
    worker_s = sum(a["wall_s"] for a in attempts)
    summary = {
        "out": str(out),
        "written_at": datetime.now().isoformat(timespec="seconds"),
        "attempts": len(attempts),
        "outcomes": dict(outcomes),
        "successes": successes,
        "success_rate": round(successes / len(attempts), 3) if attempts else None,
        "failures": dict(
            Counter(a["failure"] or a["outcome"] for a in attempts if a["outcome"] != "success")
        ),
        "by_level": {
            str(level): {
                "attempts": sum(a["level"] == level for a in attempts),
                "successes": sum(a["level"] == level and a["outcome"] == "success" for a in attempts),
            }
            for level in sorted({a["level"] for a in attempts})
        },  # fmt: skip
        "sim_s": round(sum(a["sim_s"] for a in attempts), 1),
        "worker_s": round(worker_s, 1),
        "worker_s_per_success": round(worker_s / successes, 1) if successes else None,
        "batch_wall_s": None if wall_s is None else round(wall_s, 1),
        "generator_versions": sorted({a.get("generator_version") or "" for a in attempts}),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--parents", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replay", action="store_true", help="each parent on its own condition")
    parser.add_argument("--limit", type=int, default=None, help="first N jobs only")
    parser.add_argument("--workers", type=int, default=12, help="team cap: <= 14 on rtx3060")
    parser.add_argument("--summarize", action="store_true", help="only rewrite summary.json")
    args = parser.parse_args(argv)
    if not args.summarize:
        if not args.replay:
            parser.error("choose a job list (--replay)")
        jobs = replay_jobs(args.parents)[: args.limit]
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in jobs))
        t0 = time.monotonic()
        procs = launch(args, jobs)
        print(f"{len(procs)} workers started, {len(jobs)} jobs in the list", flush=True)
        codes = [p.wait() for p in procs]
        print(f"workers done, exit codes {Counter(codes)}", flush=True)
        summary = summarize(args.out, time.monotonic() - t0)
    else:
        summary = summarize(args.out, None)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
