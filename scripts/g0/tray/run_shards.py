"""Run the shards of one or more generate.py batches with at most --max-live workers alive.

generate.py starts every shard of a batch at once. To regenerate a batch with its
old seed-to-shard split (so release order and seeds line up with the old release)
on a shared box that cannot hold that many workers, this runs the same per-shard
command (`generate.py --shard k --workers W`) from a queue:

- a batch is `{"out": ..., "workers": W, "n": N, "level": L, "seed_start": S}`, or
  `{"out": ..., "workers": W, "targeted": true}` with targets.jsonl already in `out`
  (copy the old batch's, so the seeds are the same);
- a shard starts only when fewer than --max-live run and the GPU has --min-free-mib;
- a shard that exits with attempts left is started again (generate.py resumes from
  its log), at most --max-starts times; one whose gen_log has not changed for
  --stale seconds is killed and started again (video writer deadlock, D-28);
- at the end each batch gets summary.json as generate.py writes it.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/run_shards.py --batches batches.json --max-live 10
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flywheel_simple.tray.generate import (
    LOG_NAME,
    check_planner_version,
    check_visuals_revision,
    read_log,
    shard_dir,
    split_attempts,
    summarize,
)
from flywheel_simple.tray.planner import PlannerConfig
from flywheel_simple.tray.recorder import planner_version, visuals_revision
from flywheel_simple.tray.targets import read_targets
from flywheel_simple.tray.visuals import default_manifest_path

GENERATE = Path(__file__).with_name("generate.py")


@dataclass
class Shard:
    batch: dict[str, Any]
    k: int
    share: int
    starts: int = 0
    proc: subprocess.Popen[bytes] | None = None
    started_at: float = 0.0
    exits: list[int] = field(default_factory=list)

    @property
    def out(self) -> Path:
        return Path(self.batch["out"])

    @property
    def log(self) -> Path:
        return shard_dir(self.out, self.k) / LOG_NAME

    def left(self) -> int:
        return self.share - (len(read_log(self.log)) if self.log.exists() else 0)

    def command(self) -> list[str]:
        b = self.batch
        cmd = [sys.executable, str(GENERATE), "--out", str(self.out), "--n", str(self.left())]
        cmd += ["--workers", str(b["workers"]), "--shard", str(self.k)]
        if b.get("targeted"):
            return cmd + ["--targeted"]
        return cmd + ["--level", str(b["level"]), "--seed-start", str(b["seed_start"])]


def shares(batch: dict[str, Any]) -> list[int]:
    w = int(batch["workers"])
    if batch.get("targeted"):
        plan = read_targets(Path(batch["out"]))
        return [len(plan[k::w]) for k in range(w)]
    return split_attempts(int(batch["n"]), w)


def gpu_free_mib() -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=True,
        )
        return int(out.stdout.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def say(log: Path, text: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {text}"
    print(line, flush=True)
    with log.open("a") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batches", type=Path, required=True)
    ap.add_argument("--max-live", type=int, default=10)
    ap.add_argument("--min-free-mib", type=int, default=700)
    ap.add_argument("--max-starts", type=int, default=6)
    ap.add_argument("--stale", type=float, default=900.0)
    ap.add_argument("--stagger", type=float, default=8.0)
    ap.add_argument("--poll", type=float, default=30.0)
    args = ap.parse_args()
    batches = json.loads(args.batches.read_text())
    log = args.batches.with_suffix(".log")
    version = planner_version(PlannerConfig.load())
    revision = visuals_revision(default_manifest_path())
    queue: list[Shard] = []
    for b in batches:
        out = Path(b["out"])
        out.mkdir(parents=True, exist_ok=True)
        check_planner_version(out, version)
        check_visuals_revision(out, revision)
        queue += [Shard(b, k, n) for k, n in enumerate(shares(b)) if n > 0]
    say(log, f"start {len(queue)} shards, planner {version}, visuals {revision}, "
             f"max_live {args.max_live}")
    env = dict(os.environ)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env.setdefault(var, "1")
    live: list[Shard] = []
    done: list[Shard] = []
    while queue or live:
        for s in list(live):
            assert s.proc is not None
            rc = s.proc.poll()
            now = time.time()
            if rc is None:
                age = now - (s.log.stat().st_mtime if s.log.exists() else s.started_at)
                if age > args.stale and now - s.started_at > args.stale:
                    say(log, f"{s.out.name} shard {s.k} stale {age:.0f}s: kill")
                    s.proc.kill()
                    s.proc.wait()
                    rc = -9
                else:
                    continue
            s.exits.append(rc)
            live.remove(s)
            left = s.left()
            say(log, f"{s.out.name} shard {s.k} exit {rc}, {left} left")
            if left > 0 and s.starts < args.max_starts:
                queue.append(s)
            else:
                done.append(s)
        while queue and len(live) < args.max_live:
            free = gpu_free_mib()
            if free < args.min_free_mib:
                say(log, f"GPU free {free} MiB < {args.min_free_mib}: wait")
                break
            s = queue.pop(0)
            if s.left() <= 0:
                done.append(s)
                continue
            work = shard_dir(s.out, s.k)
            work.mkdir(parents=True, exist_ok=True)
            with (work / "worker.log").open("a") as wlog:
                cmd = s.command()
                s.proc = subprocess.Popen(cmd, stdout=wlog, stderr=subprocess.STDOUT, env=env)
            s.starts += 1
            s.started_at = time.time()
            live.append(s)
            say(log, f"{s.out.name} shard {s.k} start #{s.starts} pid {s.proc.pid} "
                     f"left {s.left()} (GPU free {free} MiB)")
            time.sleep(args.stagger)
        time.sleep(args.poll)
    failed = []
    for b in batches:
        out = Path(b["out"])
        mine = [s for s in done if s.out == out]
        restarted = [s.k for s in mine if s.starts > 1]
        short = [s.k for s in mine if s.left() > 0]
        failed += short
        summary = {**summarize(out), "retried_shards": restarted, "failed_shards": short}
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        say(log, f"{out.name} DONE {json.dumps(summary)[:500]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
