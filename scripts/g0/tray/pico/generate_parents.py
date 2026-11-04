"""Generate virtual-teleop parent demos of the tray task in parallel (DA-35 task 7).

Splits the (level, seed) conditions round-robin over worker processes; each
worker is one `flywheel_simple.tray.pico.session --streamer virtual` with its own
env and its own LeRobot dataset under `<out>/shard-NN/`. A rerun skips the
conditions a shard has already logged, so a killed worker resumes. At the end
(or with --summarize) it writes `<out>/summary.json`: attempts, successes,
successes with all seven step flags (the parents S2 can cut), failure labels,
sim and machine time, the parent list, and the shards whose saved episodes do not
match their attempts log (`shard_mismatches`; such a shard is never resumed).

Each worker runs in its own process group. An attempt logged as `interrupted`
(a SIGINT'd session, which exits 0) leaves its condition pending. The launcher
exits 1 if a worker exited non-zero (parents-1104 lost one to -9), a condition
is still not logged, or a shard mismatches; an interrupted launcher kills its
workers' groups.

Every batch writes its two ledger rows through `flywheel.data.ledger.job_ledger`
(estimate before the workers start, measured wall seconds after; DA-35 PO review
of #84). The launcher runs in the workspace venv for that; the workers in the
SIMPLE venv (`--worker-python`). Run on the sim machine, detached:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid \\
        .venv/bin/python scripts/g0/tray/pico/generate_parents.py \\
        --worker-python fwdata/simple/.venv/bin/python \\
        --out fwdata/simple/tray/virtual/parents-1103 --levels 0,1 --seeds 100-179 \\
        --workers 16 < /dev/null > parents.log 2>&1 &
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel_simple.tray.pico.recording import shard_mismatches

STEPS = 7
# A SIGINT'd session logs its attempt as interrupted and stops: the condition did not run.
NOT_RUN = ("interrupted",)


def conditions(levels: list[int], seeds: range) -> list[tuple[int, int]]:
    return [(level, seed) for seed in seeds for level in levels]


def attempts_of(shard: Path) -> list[dict[str, Any]]:
    path = shard / "attempts.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def pending(args: argparse.Namespace) -> list[tuple[int, int]]:
    """The conditions no shard has run yet."""
    done = {c for s in args.out.glob("shard-*") for c in done_conditions(s)}
    return [c for c in conditions(args.levels, args.seeds) if c not in done]


def mismatched_shards(out: Path) -> dict[str, list[str]]:
    return {s.name: p for s in sorted(out.glob("shard-*")) if (p := shard_mismatches(s))}


def kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def done_conditions(shard: Path) -> set[tuple[int, int]]:
    """The conditions the shard ran to an outcome (an interrupted attempt is not one)."""
    return {(a["level"], a["seed"]) for a in attempts_of(shard) if a["outcome"] not in NOT_RUN}


def launch(args: argparse.Namespace) -> list[subprocess.Popen[bytes]]:
    todo = conditions(args.levels, args.seeds)
    procs = []
    for k in range(args.workers):
        shard = args.out / f"shard-{k:02d}"
        done = done_conditions(shard)
        mine = [c for c in todo[k :: args.workers] if c not in done]
        if not mine:
            continue
        shard.mkdir(parents=True, exist_ok=True)
        cmd = [
            args.worker_python, "-m", "flywheel_simple.tray.pico.session",
            "--conditions", ",".join(f"{level}:{seed}" for level, seed in mine),
            "--operator", "op-virtual", "--streamer", "virtual",
            "--max-attempts", str(args.max_attempts), "--style-base", str(args.style_base),
            "--session", f"{args.out.name}-{k:02d}", "--save-dir", str(shard),
        ]  # fmt: skip
        with (shard / "worker.log").open("ab") as log:
            procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                          start_new_session=True))  # fmt: skip
    return procs


def summarize(out: Path, wall_s: float | None) -> dict[str, Any]:
    attempts, parents = [], []
    for shard in sorted(out.glob("shard-*")):
        for a in attempts_of(shard):
            attempts.append(a)
            if a["outcome"] == "success" and a["steps_reached"] == STEPS:
                parents.append(
                    {
                        "shard": shard.name,
                        "episode_index": a["episode_index"],
                        "level": a["level"],
                        "seed": a["seed"],
                        "style_seed": a.get("style_seed"),
                        "sim_s": a["sim_s"],
                    }
                )
    outcomes = Counter(a["outcome"] for a in attempts)
    summary = {
        "out": str(out),
        "written_at": datetime.now().isoformat(timespec="seconds"),
        "attempts": len(attempts),
        "outcomes": dict(outcomes),
        "successes": outcomes.get("success", 0),
        "parents_all_steps": len(parents),
        "failures": dict(
            Counter(
                a["failure"] or a.get("abort_reason") for a in attempts if a["outcome"] != "success"
            )
        ),  # fmt: skip
        "by_level": {
            str(level): {
                "attempts": sum(a["level"] == level for a in attempts),
                "parents": sum(p["level"] == level for p in parents),
            }
            for level in sorted({a["level"] for a in attempts})
        },
        "sim_s": round(sum(a["sim_s"] for a in attempts), 1),
        "worker_s": round(sum(a["wall_s"] for a in attempts), 1),
        "batch_wall_s": None if wall_s is None else round(wall_s, 1),
        "parents": parents,
        "shard_mismatches": mismatched_shards(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def seed_range(text: str) -> range:
    first, _, last = text.partition("-")
    return range(int(first), int(last or first) + 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--levels", default="0,1", help="comma list, 0 and 1 only")
    parser.add_argument("--seeds", type=seed_range, default=seed_range("100-179"))
    parser.add_argument("--workers", type=int, default=16, help="<= 22 on rtx3060")
    parser.add_argument("--max-attempts", type=int, default=1, help="per condition")
    parser.add_argument("--style-base", type=int, default=0)
    parser.add_argument("--summarize", action="store_true", help="only rewrite summary.json")
    parser.add_argument("--worker-python", default=sys.executable, help="the SIMPLE venv's python")
    parser.add_argument(
        "--est-attempt-s", type=float, default=110.0,
        help="ledger estimate: worker wall seconds per attempt (parents-1103: 110 per parent)",
    )  # fmt: skip
    args = parser.parse_args(argv)
    args.levels = [int(x) for x in args.levels.split(",")]
    if not args.summarize:
        from flywheel.data.ledger import job_ledger  # workspace venv only

        if mismatched := mismatched_shards(args.out):
            print(f"refused: shards do not reconcile, set them aside first: {mismatched}")
            return 1
        todo = pending(args)
        workers = max(1, min(args.workers, len(todo)))
        note = (
            f"Assumption: {len(todo)} virtual-teleop attempts x {args.est_attempt_s:g} s worker "
            f"wall over {workers} workers on rtx3060; batch {args.out.name}"
        )
        estimate = len(todo) * args.est_attempt_s / workers
        command = f"da35_parents_{args.out.name}"
        with job_ledger("teleop_session", command, estimate, note=note, story="DA-35") as job:
            t0 = time.monotonic()
            procs = launch(args)
            print(f"{len(procs)} workers started", flush=True)
            try:
                codes = [p.wait() for p in procs]
            except BaseException:  # the workers sit in their own sessions
                for p in procs:
                    kill_group(p)
                raise
            print(f"workers done, exit codes {Counter(codes)}", flush=True)
            summary = summarize(args.out, time.monotonic() - t0)
            left = len(pending(args))
            job.notes.append(
                f"{summary['attempts']} attempts, {summary['parents_all_steps']} parents with "
                f"seven flags, {summary['worker_s']} worker-s, exit codes {dict(Counter(codes))}, "
                f"{left} conditions not logged, {len(summary['shard_mismatches'])} shards mismatched"
            )
        print(f"ledger: run plan {job.run_plan_id}, job {job.job_id}", flush=True)
    else:
        codes, left, summary = [], 0, summarize(args.out, None)
    print(json.dumps({k: v for k, v in summary.items() if k != "parents"}, indent=1))
    failed = sum(c != 0 for c in codes)
    if summary["shard_mismatches"]:
        print(f"shards {sorted(summary['shard_mismatches'])} mismatch: set them aside, then rerun")
    if failed or left:
        print(f"{failed} workers failed, {left} conditions not logged: rerun to finish the batch")
    return 1 if failed or left or summary["shard_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
