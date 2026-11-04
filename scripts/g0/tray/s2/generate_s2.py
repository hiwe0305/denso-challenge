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

The launcher supervises its workers (task 12, faults of `measure-1104`). Each
worker runs in its own process group, so a kill reaches its children. A worker
that ends while its shard still has jobs not logged (any exit code, 0 included:
an interrupted session exits 0), or logs no attempt for `--stall-s` (the video
writer's hang), is killed and started again on those jobs, at most
`--max-restarts` times per shard; every restart is a line of
`<out>/supervisor.jsonl`. A worker that stalls after logging all its jobs ends
`stalled-done`, which counts as done. A shard whose saved episodes do not match
its attempts log (`shard_mismatches`: a worker died between saving an episode
and logging it) is never resumed: the launcher refuses to start on it and stops
supervising it, and summary.json lists it under `shard_mismatches`.

The launcher exits 1 if a shard's last worker failed, a shard mismatches, or any
job of the list is still not logged. Before a worker starts, a dataset of its
shard that never saved an episode is renamed `<name>.empty-<stamp>` (kept, not
deleted): LeRobot cannot resume a dataset with no `meta/episodes.jsonl`, so the
worker opens a fresh one.

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
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from flywheel_simple.tray.pico.recording import shard_mismatches
from flywheel_simple.tray.s2.config import S2Config
from flywheel_simple.tray.s2.jobs import sample_jobs

JOB_KEYS = ("parent_id", "level", "seed", "gen_seed")
DONE = (0, "stalled-done")  # how a shard's last worker may end


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


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def attempts_of(shard: Path) -> list[dict[str, Any]]:
    return jsonl_rows(shard / "attempts.jsonl")


def logged_key(attempt: dict[str, Any]) -> tuple[Any, ...]:
    return (attempt["parent_episode"], attempt["level"], attempt["seed"], attempt["gen_seed"])


def pending(args: argparse.Namespace, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The jobs of the list that no shard has logged yet."""
    done = {logged_key(a) for shard in args.out.glob("shard-*") for a in attempts_of(shard)}
    return [j for j in jobs if job_key(j) not in done]


def set_aside_empty_datasets(shard: Path, stamp: str) -> list[Path]:
    """Rename the shard's datasets that saved no episode, so the worker opens a fresh one."""
    moved = []
    for info in sorted(shard.rglob("meta/info.json")):
        root = info.parent.parent
        if ".empty-" in root.name or (root / "meta" / "episodes.jsonl").exists():
            continue
        target = root.with_name(f"{root.name}.empty-{stamp}")
        root.rename(target)
        moved.append(target)
    return moved


def pending_jobs(shard: Path) -> list[dict[str, Any]]:
    """The shard's jobs that its attempts log does not have yet."""
    path = shard / "jobs.jsonl"
    if not path.exists():
        return []
    logged = {logged_key(a) for a in attempts_of(shard)}
    jobs = [json.loads(line) for line in path.read_text().splitlines() if line]
    return [j for j in jobs if job_key(j) not in logged]


class Worker(Protocol):
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...
    def wait(self) -> int: ...


class GroupWorker:
    """A worker in its own session: a kill reaches the whole group (the video writer too)."""

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self.proc = proc

    def poll(self) -> int | None:
        return self.proc.poll()

    def kill(self) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, signal.SIGKILL)

    def wait(self) -> int:
        return self.proc.wait()


def start_worker(args: argparse.Namespace, k: int, jobs: list[dict[str, Any]]) -> Worker:
    """One `tray.s2.session` process on shard k with these jobs."""
    shard = args.out / f"shard-{k:02d}"
    shard.mkdir(parents=True, exist_ok=True)
    set_aside_empty_datasets(shard, datetime.now().strftime("%m%dT%H%M%S"))
    jobs_file = shard / "jobs.jsonl"
    jobs_file.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    cmd = [
        args.worker_python, "-m", "flywheel_simple.tray.s2.session",
        "--parents", str(args.parents), "--jobs", str(jobs_file),
        "--session", f"{args.out.name}-{k:02d}", "--save-dir", str(shard),
        "--mode", args.mode,
        *(["--config", str(args.config)] if args.config else []),
    ]  # fmt: skip
    with (shard / "worker.log").open("ab") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return GroupWorker(proc)


def launch(
    args: argparse.Namespace,
    jobs: list[dict[str, Any]],
    start: Callable[[argparse.Namespace, int, list[dict[str, Any]]], Worker] = start_worker,
) -> dict[int, Worker]:
    """One worker per shard; jobs any shard has logged are not run again."""
    todo = pending(args, jobs)
    shares = {k: todo[k :: args.workers] for k in range(args.workers)}
    return {k: start(args, k, mine) for k, mine in shares.items() if mine}


def last_progress(shard: Path, since: float) -> float:
    """Wall time of the shard's latest logged attempt, not before `since`.

    The attempts log only: a hung worker can keep writing its log (warnings).
    """
    log = shard / "attempts.jsonl"
    return max(since, log.stat().st_mtime) if log.exists() else since


def mismatched_shards(out: Path) -> dict[str, list[str]]:
    return {s.name: p for s in sorted(out.glob("shard-*")) if (p := shard_mismatches(s))}


def supervise(
    args: argparse.Namespace,
    procs: dict[int, Worker],
    start: Callable[[argparse.Namespace, int, list[dict[str, Any]]], Worker] = start_worker,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[int, list[int | str]]:
    """Wait for the workers; restart one that ends or stalls with jobs not logged.

    A shard's ends list each worker's exit code or "stalled"; "stalled-done" when it
    hung after logging all its jobs, and a last "mismatch" when its dataset and
    attempts log disagree (it is not restarted).
    """
    ends: dict[int, list[int | str]] = {k: [] for k in procs}
    started = {k: now() for k in procs}
    restarts: Counter[int] = Counter()
    try:
        while procs:
            sleep(args.poll_s)
            for k, proc in list(procs.items()):
                shard = args.out / f"shard-{k:02d}"
                end: int | str | None = proc.poll()
                if end is None:
                    if now() - last_progress(shard, started[k]) <= args.stall_s:
                        continue
                    proc.kill()
                    proc.wait()
                    end = "stalled"
                left = pending_jobs(shard)
                ends[k].append("stalled-done" if end == "stalled" and not left else end)
                if problems := shard_mismatches(shard):
                    ends[k].append("mismatch")
                    print(f"shard {k:02d} mismatch, not resumed: {'; '.join(problems)}", flush=True)
                if not left or ends[k][-1] == "mismatch" or restarts[k] >= args.max_restarts:
                    del procs[k]
                    continue
                restarts[k] += 1
                event = {"at": datetime.now().isoformat(timespec="seconds"), "shard": k,
                         "end": end, "restart": restarts[k], "pending": len(left)}  # fmt: skip
                with (args.out / "supervisor.jsonl").open("a") as log:
                    log.write(json.dumps(event) + "\n")
                print(f"shard {k:02d} ended {end}; restart {restarts[k]}, {len(left)} jobs", flush=True)
                procs[k] = start(args, k, left)
                started[k] = now()
    except BaseException:  # interrupted launcher: its workers sit in their own sessions
        for proc in procs.values():
            proc.kill()
        raise
    return ends


def exit_status(codes: list[int | str]) -> int:
    """1 if any shard's last worker failed (after its restarts) or the shard mismatches."""
    return 1 if any(code not in DONE for code in codes) else 0


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
        "worker_restarts": len(jsonl_rows(out / "supervisor.jsonl")),
        "shard_mismatches": mismatched_shards(out),
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
    parser.add_argument("--poll-s", type=float, default=30.0, help="supervisor: poll period")
    parser.add_argument(
        "--stall-s", type=float, default=1800.0,
        help="supervisor: kill a worker that logs nothing this long (attempts take ~100-500 s)",
    )  # fmt: skip
    parser.add_argument("--max-restarts", type=int, default=3, help="supervisor: per shard")
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

        if mismatched := mismatched_shards(args.out):
            print(f"refused: shards do not reconcile, set them aside first: {mismatched}")
            return 1
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
            ends = supervise(args, procs)
            codes = [e for shard_ends in ends.values() for e in shard_ends]
            last = [shard_ends[-1] for shard_ends in ends.values() if shard_ends]
            print(f"workers done, ends {Counter(codes)}", flush=True)
            summary = summarize(args.out, time.monotonic() - t0)
            missing = len(pending(args, jobs))
            job.notes.append(
                f"{summary['attempts']} attempts, {summary['successes']} successes, "
                f"{summary['worker_s']} worker-s, worker ends {dict(Counter(codes))}, "
                f"{summary['worker_restarts']} restarts, {missing} jobs not logged, "
                f"{len(summary['shard_mismatches'])} shards mismatched"
            )
        print(f"ledger: run plan {job.run_plan_id}, job {job.job_id}", flush=True)
    else:
        last, missing, summary = [], 0, summarize(args.out, None)
    print(json.dumps(summary, indent=1))
    failed = sum(c not in DONE for c in last)
    if summary["shard_mismatches"]:
        print(f"shards {sorted(summary['shard_mismatches'])} mismatch: set them aside, then rerun")
    if failed or missing:
        print(f"{failed} shards failed, {missing} jobs not logged: rerun to finish the batch")
    return 1 if exit_status(last) or missing or summary["shard_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
