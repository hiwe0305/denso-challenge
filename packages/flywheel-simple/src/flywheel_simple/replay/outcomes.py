"""Replay a SIMPLE LeRobot dataset through the decoupled WBC: replay_outcomes.jsonl (DA-17 AC 2).

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.replay.outcomes <dataset> --work <dir> --workers 4

Works for any dataset SIMPLE's `replay-decoupled-wbc` reads: psi-data, the tray
releases (post-processed, 36-D action) and raw SIMPLE recordings, as long as
`meta/episodes.jsonl` holds each episode's `environment_config`. The episodes
are split into `workers` contiguous shards, one process each (`replay.run`, one
live env per process, as `tray/replay_qa.py` runs). Every shard replays a
staged copy of the dataset - `meta/` copied, its own parquet files symlinked -
so SIMPLE's `meta/replay.txt` never lands in the source and each process loads
only its own episodes. The replay runs on sim time unless `clock="wall"`
(`run.py` says why).

Writes into `work`: `replay_outcomes.jsonl` (one line per episode, ascending,
see `compare.outcome`), `replay_run.json` (counts, wall seconds per shard,
failed shards) and `shard-NN/` (stage, log, outcomes). A shard that exits
non-zero or an episode without an outcome raises after both files are written.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

OUTCOMES = "replay_outcomes.jsonl"
SUMMARY = "replay_run.json"
STARTUP_STAGGER_S = 5.0  # between shard starts, so the scene builds do not all hit at once


@dataclass(frozen=True)
class Shard:
    name: str
    episodes: list[int]


def episode_indices(root: Path) -> list[int]:
    rows = (root / "meta" / "episodes.jsonl").read_text().splitlines()
    indices = sorted(int(json.loads(r)["episode_index"]) for r in rows if r.strip())
    if not indices:
        raise ValueError(f"{root}: no episodes in meta/episodes.jsonl")
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError(f"{root}: episode indices are not contiguous; SIMPLE replays a range")
    return indices


def shards(indices: list[int], workers: int) -> list[Shard]:
    """Contiguous shards of near-equal size, at most `workers` of them."""
    count = max(1, min(workers, len(indices)))
    size, extra = divmod(len(indices), count)
    out, start = [], 0
    for k in range(count):
        end = start + size + (k < extra)
        out.append(Shard(f"shard-{k:02d}", indices[start:end]))
        start = end
    return out


def env_id_of(root: Path) -> str:
    """SIMPLE's env id of a psi-data package: its directory is named after the env."""
    if root.name.endswith("-v0") or root.name.endswith("-v1"):
        return f"simple/{root.name}"
    raise ValueError(f"{root}: cannot tell the env id from the name; pass env_id")


def stage(root: Path, shard: Shard, into: Path) -> Path:
    """A copy of root holding meta/ and shard's parquet files (symlinks)."""
    info = json.loads((root / "meta" / "info.json").read_text())
    size = int(info.get("chunks_size", 1000))
    if into.exists():
        shutil.rmtree(into)
    shutil.copytree(root / "meta", into / "meta")
    (into / "meta" / "replay.txt").unlink(missing_ok=True)
    for index in shard.episodes:
        rel = info["data_path"].format(episode_chunk=index // size, episode_index=index)
        link = into / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to((root / rel).resolve())
    return into


def shard_command(
    python: str, data: Path, env_id: str, shard: Shard, out: Path, clock: str
) -> list[str]:
    return [
        python, "-m", "flywheel_simple.replay.run",
        "--data-dir", str(data), "--env-id", env_id, "--outcomes", str(out / OUTCOMES),
        "--episode-start", str(shard.episodes[0]), "--num-episodes", str(len(shard.episodes)),
        "--save-dir", str(out / "unused"), "--clock", clock,
    ]  # fmt: skip


def replay_lerobot(
    root: Path,
    work: Path,
    workers: int,
    *,
    env_id: str | None = None,
    clock: str = "sim",
    python: str = sys.executable,
    stagger_s: float = STARTUP_STAGGER_S,
) -> Path:
    """Replay every episode of root into work/replay_outcomes.jsonl; returns its path."""
    env = env_id or env_id_of(root)
    plan = shards(episode_indices(root), workers)
    work.mkdir(parents=True, exist_ok=True)
    running: list[tuple[Shard, subprocess.Popen[bytes], float]] = []
    for k, shard in enumerate(plan):
        out = work / shard.name
        data = stage(root, shard, out / "stage")
        (out / OUTCOMES).unlink(missing_ok=True)
        if k:
            time.sleep(stagger_s)
        with (out / "replay.log").open("w") as log:
            cmd = shard_command(python, data, env, shard, out, clock)
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))
        running.append((shard, proc, time.monotonic()))
    walls: dict[str, float] = {}
    failed: dict[str, int] = {}
    for shard, proc, started in running:
        code = proc.wait()
        walls[shard.name] = round(time.monotonic() - started, 1)
        if code:
            failed[shard.name] = code
    return _merge(work, plan, env, clock, walls, failed)


def _merge(
    work: Path,
    plan: list[Shard],
    env: str,
    clock: str,
    walls: dict[str, float],
    failed: dict[str, int],
) -> Path:
    lines: dict[int, str] = {}
    for shard in plan:
        path = work / shard.name / OUTCOMES
        for line in path.read_text().splitlines() if path.exists() else []:
            if line.strip():
                lines[int(json.loads(line)["episode_index"])] = line
    expected = [i for s in plan for i in s.episodes]
    missing = [i for i in expected if i not in lines]
    outcomes = work / OUTCOMES
    outcomes.write_text("".join(lines[i] + "\n" for i in sorted(lines)))
    successes = sum(bool(json.loads(lines[i])["success"]) for i in lines)
    summary = {
        "env_id": env,
        "clock": clock,
        "episodes": len(expected),
        "replayed": len(lines),
        "succeeded": successes,
        "missing": missing,
        "workers": len(plan),
        "wall_s_by_shard": walls,
        "failed_shards": failed,
    }
    (work / SUMMARY).write_text(json.dumps(summary, indent=2) + "\n")
    if failed or missing:
        raise RuntimeError(
            f"replay incomplete: shards {sorted(failed)} failed, {len(missing)} episodes without"
            f" an outcome; see {work}/shard-*/replay.log"
        )
    return outcomes


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="flywheel_simple.replay.outcomes")
    ap.add_argument("root", type=Path)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--env-id")
    ap.add_argument("--clock", choices=("sim", "wall"), default="sim")
    args = ap.parse_args(argv)
    path = replay_lerobot(args.root, args.work, args.workers, env_id=args.env_id,
                          clock=args.clock)
    print(json.loads((args.work / SUMMARY).read_text()))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
