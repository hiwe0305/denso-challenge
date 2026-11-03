"""Generate virtual-teleop parent demos of the tray task in parallel (DA-35 task 7).

Splits the (level, seed) conditions round-robin over worker processes; each
worker is one `flywheel_simple.tray.pico.session --streamer virtual` with its own
env and its own LeRobot dataset under `<out>/shard-NN/`. A rerun skips the
conditions a shard has already logged, so a killed worker resumes. At the end
(or with --summarize) it writes `<out>/summary.json`: attempts, successes,
successes with all seven step flags (the parents S2 can cut), failure labels,
sim and machine time, and the parent list.

Run on the sim machine in the SIMPLE venv, detached:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid \\
        fwdata/simple/.venv/bin/python scripts/g0/tray/pico/generate_parents.py \\
        --out fwdata/simple/tray/virtual/parents-1103 --levels 0,1 --seeds 100-179 \\
        --workers 16 < /dev/null > parents.log 2>&1 &
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

STEPS = 7


def conditions(levels: list[int], seeds: range) -> list[tuple[int, int]]:
    return [(level, seed) for seed in seeds for level in levels]


def attempts_of(shard: Path) -> list[dict[str, Any]]:
    path = shard / "attempts.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def launch(args: argparse.Namespace) -> list[subprocess.Popen[bytes]]:
    todo = conditions(args.levels, args.seeds)
    procs = []
    for k in range(args.workers):
        shard = args.out / f"shard-{k:02d}"
        done = {(a["level"], a["seed"]) for a in attempts_of(shard)}
        mine = [c for c in todo[k :: args.workers] if c not in done]
        if not mine:
            continue
        shard.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "flywheel_simple.tray.pico.session",
            "--conditions", ",".join(f"{level}:{seed}" for level, seed in mine),
            "--operator", "op-virtual", "--streamer", "virtual",
            "--max-attempts", str(args.max_attempts), "--style-base", str(args.style_base),
            "--session", f"{args.out.name}-{k:02d}", "--save-dir", str(shard),
        ]  # fmt: skip
        log = (shard / "worker.log").open("ab")
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT))
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
    args = parser.parse_args(argv)
    args.levels = [int(x) for x in args.levels.split(",")]
    if not args.summarize:
        t0 = time.monotonic()
        procs = launch(args)
        print(f"{len(procs)} workers started", flush=True)
        codes = [p.wait() for p in procs]
        print(f"workers done, exit codes {Counter(codes)}", flush=True)
        summary = summarize(args.out, time.monotonic() - t0)
    else:
        summary = summarize(args.out, None)
    print(json.dumps({k: v for k, v in summary.items() if k != "parents"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
