"""Run a tray RunPlan's eval conditions in chunks, one client at a time (DA-34 task 3).

Reads `conditions.jsonl` of an eval set (`flywheel_psi0.tray.eval_set`) and refuses a
set whose conditions sha256 is not the expected one. Splits each level into chunks of
`--chunk` episodes and runs them in the order Hiếu set on 6/11/2026: levels 1 and 2
interleaved chunk by chunk, then level 0. Each chunk runs as one `eval_driver` client
behind one `act_log` proxy, in `<out>/<chunk>/attempt-<k>/`:

* `requests.jsonl` (every request), `outcomes.jsonl` (every episode, with step flags),
  `traces/` (DA-38 trace of every control cycle), `eval/` (SIMPLE's stats and logs),
  `data/evals/...` (videos), `client.log` and `proxy.log`;
* one row per attempt in `<out>/runs.jsonl`: chunk, attempt, first episode, count,
  exit code, wall time, finished and missing episodes.

An episode is finished when SIMPLE wrote its `episode_<i>:` stats line and the env its
outcome row. A chunk with episodes left (a crashed client or server) runs again from
its first missing episode, same conditions and seeds, in a new attempt directory, up to
`--attempts` times; then the batch stops with exit 1. Rerunning the command resumes:
finished episodes are not run again. Rollouts are not reproducible on EGL (tray.md 8.5),
so a rerun is a fresh rollout of the same condition and the attempt count is reported.

`--max-chunks N` runs the first N chunks of that order only, then exits: stage 1 of
branch B's two-stage eval (docs/he/tray.md 18.2) is `--max-chunks 6`. Rerunning without
it resumes with chunk N + 1; the order does not depend on the flag.

`--chunks a,b` runs only the named chunks of that (cut) order, still in plan order: one
serve lane each when stage 1 is split over several servers (C70_R1, docs/he/tray.md
20.15). Lanes may share `--out`: each chunk has its own directory, and `runs.jsonl` gets
one short appended line per attempt. An id twice, or one not in the order, is refused.

    python -m flywheel_psi0.tray.eval_batch --set <eval set> --conditions-sha256 <sha> \
        --out <dir> --server 127.0.0.1:22185 --simple-python <SIMPLE venv>/bin/python \
        --pythonpath <repo>/packages/*/src joined by ':'
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flywheel_psi0.tray.eval_set import conditions_sha256

ENV_ID = "simple/G1WholebodyTrayTransferTeleop-v0"
POLICY = "psi0_decoupled_wbc"
PHASES: tuple[tuple[int, ...], ...] = ((1, 2), (0,))  # Hiếu 6/11/2026
STATS_LINE = re.compile(r"^episode_(\d+):\s*(True|False)\s*$")
TIME_V = Path("/usr/bin/time")


@dataclass(frozen=True)
class Chunk:
    id: str
    level: int
    start: int  # episode index in dr-level-<level>
    seeds: tuple[int, ...]

    def seed_of(self, episode: int) -> int:
        return self.seeds[episode - self.start]


def phases_for(rows: Sequence[dict[str, Any]]) -> tuple[tuple[int, ...], ...]:
    """PHASES cut to the levels of the set (a smaller set of tray.md 14 has level 1 only)."""
    levels = {int(row["level"]) for row in rows}
    known = {level for phase in PHASES for level in phase}
    if not levels <= known:
        raise ValueError(f"set has levels {sorted(levels - known)} outside {PHASES}")
    cut = (tuple(level for level in phase if level in levels) for phase in PHASES)
    return tuple(phase for phase in cut if phase)


def chunk_plan(
    rows: Sequence[dict[str, Any]], size: int, phases: Sequence[Sequence[int]] = PHASES
) -> list[Chunk]:
    """Chunks of each level, in plan order within a level, interleaved within a phase."""
    by_level: dict[int, list[int]] = {}
    for row in rows:
        by_level.setdefault(int(row["level"]), []).append(int(row["seed"]))
    if sorted(by_level) != sorted(level for phase in phases for level in phase):
        raise ValueError(f"set has levels {sorted(by_level)}, phases name {phases}")
    plan = []
    for phase in phases:
        per_level = [
            [
                Chunk(f"l{level}-{start:03d}", level, start, tuple(seeds[start : start + size]))
                for start in range(0, len(seeds), size)
            ]
            for level, seeds in ((lv, by_level[lv]) for lv in phase)
        ]
        for i in range(max(len(chunks) for chunks in per_level)):
            plan += [chunks[i] for chunks in per_level if i < len(chunks)]
    return plan


def finished(chunk: Chunk, attempt: Path) -> dict[int, dict[str, Any]]:
    """Episode index -> outcome row of the chunk's episodes that this attempt finished."""
    stats = attempt / "eval/eval_stats.txt"
    reported = set()
    if stats.exists():
        for line in stats.read_text().splitlines():
            if m := STATS_LINE.match(line.strip()):
                reported.add(int(m.group(1)))
    rows = {}
    outcomes = attempt / "outcomes.jsonl"
    by_seed = {seed: chunk.start + i for i, seed in enumerate(chunk.seeds)}
    for line in outcomes.read_text().splitlines() if outcomes.exists() else []:
        row = json.loads(line)
        if row["level"] != chunk.level or row["seed"] not in by_seed:
            raise ValueError(f"{outcomes}: row for (level {row['level']}, seed {row['seed']})")
        rows[by_seed[row["seed"]]] = row
    return {i: row for i, row in rows.items() if i in reported}


def attempts(out: Path, chunk: Chunk) -> list[Path]:
    return sorted((out / chunk.id).glob("attempt-*"), key=lambda p: int(p.name.split("-")[1]))


def missing(out: Path, chunk: Chunk) -> list[int]:
    done: set[int] = set()
    for attempt in attempts(out, chunk):
        done |= finished(chunk, attempt).keys()
    return [chunk.start + i for i in range(len(chunk.seeds)) if chunk.start + i not in done]


@dataclass(frozen=True)
class Setup:
    set_dir: Path
    server: str  # host:port of the Psi0 server
    listen: int  # port of the act_log proxy the client talks to
    simple_python: Path
    proxy_python: Path
    pythonpath: str
    run_plan_id: str


Launch = Callable[[Chunk, int, int, Path], int]


def wait_for_port(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def launcher(setup: Setup) -> Launch:
    """Runs episodes [start, start + n) of a chunk: proxy, then client, then stops the proxy."""

    def launch(chunk: Chunk, start: int, n: int, attempt: Path) -> int:
        (attempt / "scene").mkdir(parents=True)
        env = {**os.environ, "PYTHONPATH": setup.pythonpath}
        with (attempt / "proxy.log").open("w") as proxy_log:
            proxy = subprocess.Popen(
                [
                    str(setup.proxy_python),
                    "-m",
                    "flywheel_psi0.tray.act_log",
                    "--listen",
                    str(setup.listen),
                    "--upstream",
                    setup.server,
                    "--log",
                    str(attempt / "requests.jsonl"),
                ],
                env=env,
                stdout=proxy_log,
                stderr=subprocess.STDOUT,
            )
        try:
            wait_for_port(setup.listen)
            client_env = {
                **env,
                "DEBUG": "1",  # no progress bar: SIMPLE's 1-worker teardown writes to a closed file
                "MUJOCO_GL": "egl",
                "OMP_NUM_THREADS": "1",
                "FLYWHEEL_TRAY_OUTCOMES": str(attempt / "outcomes.jsonl"),
                "FLYWHEEL_TRAY_DIR": str(attempt / "scene"),
                "FW_TRACE_JOB_DIR": str(attempt / "traces"),
                "FW_JOB_ID": f"job_da34_eval_{chunk.id}_{attempt.name}",
                "FW_RUN_PLAN_ID": setup.run_plan_id,
            }
            command = [
                *([str(TIME_V), "-v"] if TIME_V.exists() else []),
                str(setup.simple_python),
                "-m",
                "flywheel_psi0.tray.eval_driver",
                ENV_ID,
                POLICY,
                "--host",
                "127.0.0.1",
                "--port",
                str(setup.listen),
                "--data-format",
                "lerobot",
                "--data-dir",
                str(setup.set_dir / f"dr-level-{chunk.level}"),
                "--sim-mode",
                "mujoco",
                "--headless",
                "--num-episodes",
                str(n),
                "--episode-start",
                str(start),
                "--eval-dir",
                str(attempt / "eval"),
            ]
            with (attempt / "client.log").open("w") as client_log:
                return subprocess.run(
                    command,
                    cwd=attempt,  # SIMPLE writes videos under ./data/evals
                    env=client_env,
                    stdout=client_log,
                    stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
        finally:
            proxy.terminate()
            proxy.wait(timeout=30)

    return launch


def run_batch(
    out: Path,
    chunks: Sequence[Chunk],
    launch: Launch,
    max_attempts: int = 3,
    log: Callable[[str], None] = print,
) -> int:
    """Runs every chunk's missing episodes; 1 when a chunk still misses some after its attempts."""
    for chunk in chunks:
        while left := missing(out, chunk):
            k = len(attempts(out, chunk))
            if k >= max_attempts:
                log(f"{chunk.id}: episodes {left} still missing after {k} attempts; stopping")
                return 1
            start, n = left[0], chunk.start + len(chunk.seeds) - left[0]
            attempt = out / chunk.id / f"attempt-{k}"
            began, t0 = datetime.now(timezone.utc), time.monotonic()
            code = launch(chunk, start, n, attempt)
            done = sorted(finished(chunk, attempt))
            row = {
                "chunk": chunk.id,
                "level": chunk.level,
                "attempt": k,
                "start": start,
                "n": n,
                "seeds": [chunk.seed_of(i) for i in range(start, start + n)],
                "began": began.isoformat(timespec="seconds"),
                "wall_s": round(time.monotonic() - t0, 1),
                "exit": code,
                "finished": done,
                "missing": missing(out, chunk),
            }
            with (out / "runs.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
            log(json.dumps(row))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--conditions-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--server", default="127.0.0.1:22185")
    parser.add_argument("--listen", type=int, default=22186)
    parser.add_argument("--simple-python", type=Path, required=True)
    parser.add_argument("--proxy-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--pythonpath", required=True, help="packages/*/src of the repo, ':'")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="print the chunk order only")
    parser.add_argument(
        "--max-chunks", type=int, help="run the first N chunks of the order only, then stop"
    )
    parser.add_argument("--chunks", help="comma-separated chunk ids: run only these (one lane)")
    args = parser.parse_args(argv)
    if args.max_chunks is not None and args.max_chunks < 1:
        parser.error("--max-chunks must be at least 1")
    only = args.chunks.split(",") if args.chunks else None
    if only is not None and len(set(only)) != len(only):
        parser.error(f"--chunks names a chunk twice: {args.chunks}")

    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    digest = conditions_sha256(rows)
    if digest != args.conditions_sha256:
        print(f"conditions moved: {digest} != {args.conditions_sha256}", file=sys.stderr)
        return 1
    plan_ids = {row["environment_config"]["flywheel"]["run_plan_id"] for row in rows}
    if len(plan_ids) != 1:
        print(f"set mixes run plans {sorted(plan_ids)}", file=sys.stderr)
        return 1
    chunks = chunk_plan(rows, args.chunk, phases_for(rows))[: args.max_chunks]
    if only is not None:
        unknown = sorted(set(only) - {c.id for c in chunks})
        if unknown:
            parser.error(f"--chunks {unknown} not in the order {[c.id for c in chunks]}")
        chunks = [c for c in chunks if c.id in only]
    if args.dry_run:
        for chunk in chunks:
            print(chunk.id, chunk.seeds[0], chunk.seeds[-1], len(chunk.seeds))
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    setup = Setup(
        set_dir=args.set,
        server=args.server,
        listen=args.listen,
        simple_python=args.simple_python,
        proxy_python=args.proxy_python,
        pythonpath=args.pythonpath,
        run_plan_id=plan_ids.pop(),
    )
    return run_batch(args.out, chunks, launcher(setup), args.attempts)


if __name__ == "__main__":
    sys.exit(main())
