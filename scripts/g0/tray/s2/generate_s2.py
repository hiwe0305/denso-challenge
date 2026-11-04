"""Run S2 jobs over parallel workers and summarise them (DA-35 tasks 9-12).

Job lists:

- `--replay`: every parent of `<parents>/s2_segments.jsonl` on its own condition,
  played as recorded (task 9: how well the pipeline reproduces a demo);
- `--tracked`: the same jobs replayed closed loop as identity variants (task 10);
- `--variants N`: N variants drawn from `--gen-base` (flywheel_simple.tray.s2.jobs
  .sample_jobs): parents uniformly, conditions in the train domain (tasks 10-12).

The jobs go round-robin to `--workers` processes; each worker is one
`flywheel_simple.tray.s2.session` with its own env and LeRobot dataset under
`<out>/shard-NN/`. A rerun skips the jobs any shard has already logged, so the
jobs of a killed worker run again (with any number of workers). At the end (or
with --summarize) it writes `<out>/summary.json`: attempts, outcomes, failure
labels, sim and machine time.

Every batch writes its two ledger rows through `flywheel.data.ledger.job_ledger`
(estimate before the workers start: jobs x `--est-attempt-s` over the workers;
measured wall seconds after), under `$FW_ROOT/runs/g0-DA-35-<date>/`. The launcher
needs the workspace venv for that (pydantic); the workers run in the SIMPLE venv
(`--worker-python`). Run on the sim machine, detached:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid \\
        .venv/bin/python scripts/g0/tray/s2/generate_s2.py \\
        --worker-python fwdata/simple/.venv/bin/python \\
        --parents fwdata/simple/tray/virtual/parents-1103b \\
        --out fwdata/simple/tray/s2/replay-1104 \\
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

from flywheel_simple.tray.s2.config import S2Config
from flywheel_simple.tray.s2.jobs import sample_jobs

JOB_KEYS = ("parent_id", "level", "seed", "gen_seed")


def segments_of(parents: Path) -> list[dict[str, Any]]:
    path = parents / "s2_segments.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def replay_jobs(parents: Path) -> list[dict[str, Any]]:
    return [
        {"parent_id": p["parent_id"], "level": p["level"], "seed": p["seed"], "gen_seed": 0}
        for p in segments_of(parents)
    ]


def variant_jobs(parents: Path, count: int, gen_base: int, cfg: S2Config) -> list[dict[str, Any]]:
    seeds = (cfg.cond_seed_min, cfg.cond_seed_max)
    jobs = sample_jobs(segments_of(parents), count, gen_base, cfg.level1_share, seeds)
    return [
        {"parent_id": j.parent_id, "level": j.level, "seed": j.seed, "gen_seed": j.gen_seed}
        for j in jobs
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


def pending(args: argparse.Namespace, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The jobs of the list that no shard has logged yet."""
    done = {logged_key(a) for shard in args.out.glob("shard-*") for a in attempts_of(shard)}
    return [j for j in jobs if job_key(j) not in done]


def launch(args: argparse.Namespace, jobs: list[dict[str, Any]]) -> list[subprocess.Popen[bytes]]:
    """One worker per shard; jobs any shard has logged are not run again."""
    todo = pending(args, jobs)
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
            args.worker_python, "-m", "flywheel_simple.tray.s2.session",
            "--parents", str(args.parents), "--jobs", str(jobs_file),
            "--session", f"{args.out.name}-{k:02d}", "--save-dir", str(shard),
            "--mode", args.mode,
            *(["--config", str(args.config)] if args.config else []),
        ]  # fmt: skip
        log = (shard / "worker.log").open("ab")
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT))
    return procs


def exit_status(codes: list[int]) -> int:
    """1 if any worker failed: its jobs are missing from the batch until a rerun."""
    return 1 if any(code != 0 for code in codes) else 0


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
                "successes": sum(
                    a["level"] == level and a["outcome"] == "success" for a in attempts
                ),
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
    jobs_from = parser.add_mutually_exclusive_group()
    jobs_from.add_argument("--replay", action="store_true", help="parents as recorded")
    jobs_from.add_argument("--tracked", action="store_true", help="parents closed loop")
    jobs_from.add_argument("--variants", type=int, default=None, help="N drawn variants")
    parser.add_argument("--gen-base", type=int, default=0, help="--variants: base of the draw")
    parser.add_argument("--config", type=Path, default=None, help="tray_s2.yaml for the workers")
    parser.add_argument("--worker-python", default=sys.executable, help="the SIMPLE venv's python")
    parser.add_argument(
        "--est-attempt-s", type=float, default=70.0,
        help="ledger estimate: worker wall seconds per attempt (replay-1103: 68.7 per success)",
    )  # fmt: skip
    parser.add_argument("--limit", type=int, default=None, help="first N jobs only")
    parser.add_argument("--workers", type=int, default=12, help="team cap: <= 14 on rtx3060")
    parser.add_argument("--summarize", action="store_true", help="only rewrite summary.json")
    args = parser.parse_args(argv)
    if not args.summarize:
        if args.variants is not None:
            cfg = S2Config.load(args.config)
            jobs = variant_jobs(args.parents, args.variants, args.gen_base, cfg)
        elif args.replay or args.tracked:
            jobs = replay_jobs(args.parents)
        else:
            parser.error("choose a job list (--replay, --tracked or --variants)")
        jobs = jobs[: args.limit]
        args.mode = "exact" if args.replay else "variant"
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in jobs))
        from flywheel.data.ledger import job_ledger  # workspace venv only

        todo = len(pending(args, jobs))
        workers = max(1, min(args.workers, todo))
        estimate = max(todo, 0) * args.est_attempt_s / workers
        note = (
            f"Assumption: {todo} S2 {args.mode} attempts x {args.est_attempt_s:g} s worker wall "
            f"over {workers} workers on rtx3060; batch {args.out.name}"
        )
        activity = "replay" if args.replay else "data_generation"
        command = f"da35_s2_{args.out.name}"
        with job_ledger(activity, command, estimate, note=note, story="DA-35") as job:
            t0 = time.monotonic()
            procs = launch(args, jobs)
            print(f"{len(procs)} workers started, {len(jobs)} jobs in the list", flush=True)
            codes = [p.wait() for p in procs]
            print(f"workers done, exit codes {Counter(codes)}", flush=True)
            summary = summarize(args.out, time.monotonic() - t0)
            job.notes.append(
                f"{summary['attempts']} attempts, {summary['successes']} successes, "
                f"{summary['worker_s']} worker-s, exit codes {dict(Counter(codes))}"
            )
        print(f"ledger: run plan {job.run_plan_id}, job {job.job_id}", flush=True)
    else:
        codes, summary = [], summarize(args.out, None)
    print(json.dumps(summary, indent=1))
    if exit_status(codes):
        print(f"{sum(c != 0 for c in codes)} workers failed: rerun to finish the batch", flush=True)
    return exit_status(codes)


if __name__ == "__main__":
    sys.exit(main())
