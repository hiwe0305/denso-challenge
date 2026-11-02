"""Generate tray planner episodes in parallel shards (DA-33 Task 6).

With --workers W > 1, starts W processes of this script, one per shard (one live
env per process), splits --n attempts over them and waits; each shard writes its
LeRobot dataset under <out>/shard-NN/raw and its attempt log
<out>/shard-NN/gen_log.jsonl. Running the same command again resumes: seeds
already logged in any shard are skipped. At the end, writes <out>/summary.json
(counts, failure labels, seconds per attempt over every shard).

Workers run with one BLAS/OpenMP thread each and start --stagger seconds apart:
on rtx3060 (64 CPU), 22 workers with default threads took 300-2000 s per 30 s
episode, and 5 of 22 started at once failed in eglMakeCurrent (EGL_NOT_INITIALIZED).

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/generate.py --out fwdata/simple/tray/gen/<run> --n 130 --level 1 \
        --seed-start 100 --workers 22
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from flywheel_simple.tray.generate import generate, shard_dir, split_attempts, summarize


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, required=True, help="new attempts over all shards")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--seed-start", type=int, default=100)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--shard", type=int, help="run one shard in this process (set by --workers)")
    ap.add_argument("--allow-plain", action="store_true", help="record without SimReady visuals")
    ap.add_argument("--stagger", type=float, default=5.0, help="seconds between worker starts")
    args = ap.parse_args()

    if args.shard is not None:
        summary = generate(
            args.out,
            n_attempts=args.n,
            level=args.level,
            seed_start=args.seed_start,
            allow_plain=args.allow_plain,
            shard=args.shard,
            workers=args.workers,
        )
        print(json.dumps({"shard": args.shard, **summary.__dict__}))
        return 0

    env = dict(os.environ)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env.setdefault(var, "1")
    procs = []
    for shard, n in enumerate(split_attempts(args.n, args.workers)):
        if n == 0:
            continue
        if procs:
            time.sleep(args.stagger)
        work = shard_dir(args.out, shard)
        work.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, __file__, "--out", str(args.out), "--n", str(n)]
        cmd += ["--level", str(args.level), "--seed-start", str(args.seed_start)]
        cmd += ["--workers", str(args.workers), "--shard", str(shard)]
        cmd += ["--allow-plain"] if args.allow_plain else []
        with (work / "worker.log").open("a") as log:
            procs.append(
                (shard, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env))
            )
    failed = [shard for shard, p in procs if p.wait() != 0]
    summary = {**summarize(args.out), "failed_shards": failed}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
