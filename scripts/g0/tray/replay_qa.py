"""Replay every shard of a generated batch through replay-decoupled-wbc as QA (DA-33 Task 7).

One process per shard (one live env per process), started --stagger seconds
apart with one BLAS/OpenMP thread each, as scripts/g0/tray/generate.py runs them.
Each shard gets shard-NN/replay/replay_qa.jsonl (one verdict per recorded
episode); <out>/replay_summary.json has the pass rate and the error spread.

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/replay_qa.py --out fwdata/simple/tray/gen/<run> --workers 14
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def summarize(out: Path) -> dict[str, object]:
    rows = [
        json.loads(line)
        for path in sorted(out.glob("shard-*/replay/replay_qa.jsonl"))
        for line in path.read_text().splitlines()
        if line
    ]
    errors = sorted(r["tray_error_m"] for r in rows if r["tray_error_m"] is not None)
    reasons: dict[str, int] = {}
    for r in rows:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    return {
        "episodes": len(rows),
        "passed": sum(bool(r["passed"]) for r in rows),
        "replay_success": sum(bool(r["success"]) for r in rows),
        "reasons": dict(sorted(reasons.items())),
        "tray_error_m": {
            "median": errors[len(errors) // 2] if errors else None,
            "max": errors[-1] if errors else None,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="batch directory of generate.py")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--shard", type=Path, help="replay this shard in this process")
    ap.add_argument("--stagger", type=float, default=5.0)
    args = ap.parse_args()

    if args.shard is not None:
        from flywheel_simple.tray.replay_qa import replay_qa

        verdicts = replay_qa(args.shard / "raw", args.shard / "replay")
        print(json.dumps({"shard": args.shard.name, "passed": sum(v.passed for v in verdicts)}))
        return 0

    # A shard whose worker recorded nothing has no data/ to replay.
    shards = [
        s for s in sorted(args.out.glob("shard-*")) if any((s / "raw").glob("data/*/*.parquet"))
    ]
    env = dict(os.environ)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env.setdefault(var, "1")
    running: list[subprocess.Popen[bytes]] = []
    failed = []
    for shard in shards:
        while len(running) >= args.workers:
            time.sleep(2.0)
            failed += [p.args for p in running if p.poll() not in (None, 0)]
            running = [p for p in running if p.poll() is None]
        if running:
            time.sleep(args.stagger)
        (shard / "replay").mkdir(exist_ok=True)
        with (shard / "replay" / "worker.log").open("w") as log:
            cmd = [sys.executable, __file__, "--out", str(args.out), "--shard", str(shard)]
            running.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env))
    failed += [p.args for p in running if p.wait() != 0]
    summary = {**summarize(args.out), "failed_shards": len(failed)}
    (args.out / "replay_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
