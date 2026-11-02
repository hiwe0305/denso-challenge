"""Generate planner episodes in batches with an append-only attempt log (DA-33 Task 6, AC 4, 5).

A batch directory holds one shard per worker process (one live env per process,
D-11): `shard-NN/raw/` is that worker's LeRobot dataset, `shard-NN/gen_log.jsonl`
gets one line per attempt, failed or not, and is never rewritten. Shard k of W
takes seeds start + k, start + k + W, ... from the train range, skipping every
seed already logged in any shard, so running the same command again resumes.
SIMPLE's `postprocess_psi0_sonic.py` merges shards by glob (Task 8).

Only successful attempts are recorded; each gets `minimal_qa`. Recorded episodes
that fail QA stay in the dataset and are dropped downstream by their log row.

The pure parts (seeds, log, QA rules) import in the workspace; `generate` and
`minimal_qa` run in the SIMPLE venv.
"""

from __future__ import annotations

import importlib
import json
import math
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flywheel_simple.tray.randomize import SEED_RANGES
from flywheel_simple.tray.visuals import default_manifest_path

FPS = 50
MIN_EPISODE_S = 5.0
MAX_EPISODE_S = 90.0
# Phases every kept episode passes through; BACK_OFF, TURN and ARRIVE_B may be skipped.
REQUIRED_PHASES = ("APPROACH_A", "REACH", "GRASP", "LIFT", "CARRY", "LOWER", "RELEASE", "RETREAT")
LOG_NAME = "gen_log.jsonl"


@dataclass(frozen=True)
class AttemptRow:
    """One line of gen_log.jsonl: an attempt's outcome, cost and what was kept."""

    seed: int
    level: int
    shard: int
    success: bool
    failure: str | None
    abort_reason: str | None
    phase_reached: str
    steps: int
    sim_s: float
    wall_s: float
    gpu_name: str
    planner_version: str
    visuals_revision: str
    recorded: bool
    episode_index: int | None
    qa: str  # "pass", the first failing check, or "not_recorded"


@dataclass(frozen=True)
class GenSummary:
    attempts: int
    successes: int
    recorded: int
    qa_pass: int


def shard_dir(out: Path, shard: int) -> Path:
    return Path(out) / f"shard-{shard:02d}"


def append_attempt(log: Path, row: AttemptRow) -> None:
    """Append one row; serialise first so a bad row writes nothing."""
    line = json.dumps(asdict(row))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(line + "\n")


def read_log(log: Path) -> list[dict[str, Any]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line]


def logged_seeds(out: Path) -> set[int]:
    """Seeds attempted in any shard of the batch."""
    return {
        int(row["seed"])
        for log in sorted(Path(out).glob(f"shard-*/{LOG_NAME}"))
        for row in read_log(log)
    }


def next_seeds(used: set[int], start: int, n: int, shard: int = 0, workers: int = 1) -> list[int]:
    """The next n train seeds of this shard (start + shard + k * workers), skipping used ones."""
    train = SEED_RANGES["train"]
    seeds: list[int] = []
    seed = start + shard
    while len(seeds) < n:
        if seed not in train:
            raise ValueError(f"seed {seed} is past the train range {train}")
        if seed not in used:
            seeds.append(seed)
        seed += workers
    return seeds


def split_attempts(n: int, workers: int) -> list[int]:
    """n attempts over workers, shares differing by at most one."""
    base, extra = divmod(n, workers)
    return [base + (k < extra) for k in range(workers)]


def episode_qa(
    *, success: bool, rows: int, video_frames: int, has_nan: bool, phases: Sequence[str]
) -> str:
    """ "pass" or the first failing check of a recorded episode."""
    if not success:
        return "not_success"
    if rows < MIN_EPISODE_S * FPS:
        return "too_short"
    if rows > MAX_EPISODE_S * FPS:
        return "too_long"
    if has_nan:
        return "nan"
    if video_frames != rows:
        return "video_rows_mismatch"
    if not set(REQUIRED_PHASES) <= set(phases):
        return "phases_incomplete"
    return "pass"


def minimal_qa(dataset_root: Path, index: int, phases: Sequence[str]) -> str:
    """episode_qa on a saved episode: its recorded success, parquet rows and ego_view video."""
    import numpy as np

    av = importlib.import_module("av")
    pq = importlib.import_module("pyarrow.parquet")

    episodes = read_log(dataset_root / "meta" / "episodes.jsonl")
    env_cfg = json.loads(episodes[index]["environment_config"])
    report = env_cfg["tray"]["report"]
    chunk = f"chunk-{index // 1000:03d}"
    table = pq.read_table(dataset_root / "data" / chunk / f"episode_{index:06d}.parquet")
    has_nan = False
    for name in table.column_names:
        values = table.column(name).to_pylist()
        if values and isinstance(values[0], (float, list)):
            has_nan = has_nan or bool(np.isnan(np.asarray(values, dtype=float)).any())
    video = (
        dataset_root / "videos" / chunk / "observation.images.ego_view" / f"episode_{index:06d}.mp4"
    )
    with av.open(str(video)) as container:
        frames = sum(1 for _ in container.decode(video=0))
    return episode_qa(
        success=bool(report and report["success"]),
        rows=table.num_rows,
        video_frames=frames,
        has_nan=has_nan,
        phases=phases,
    )


def gpu_name() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.splitlines()[0].strip() if out.stdout.strip() else "unknown"


def _check_resume(raw: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """The dataset must hold exactly the episodes the log says were recorded."""
    info = raw / "meta" / "info.json"
    saved = json.loads(info.read_text())["total_episodes"] if info.exists() else 0
    logged = sum(bool(r["recorded"]) for r in rows)
    if saved != logged:
        raise RuntimeError(
            f"{raw} holds {saved} episodes but its log records {logged}; fix the shard by hand"
        )


def generate(
    out: Path,
    n_attempts: int,
    level: int,
    seed_start: int,
    allow_plain: bool = False,
    shard: int = 0,
    workers: int = 1,
) -> GenSummary:
    """Run n_attempts new seeds of this shard; record, QA and log each attempt."""
    from flywheel_simple.tray.agent import EpisodeResult, TrayAgent, run_episode
    from flywheel_simple.tray.planner import PlannerConfig
    from flywheel_simple.tray.recorder import (
        EpisodeRecorder,
        FlywheelMeta,
        planner_version,
        visuals_revision,
    )
    from flywheel_simple.tray.simple_task import make_env

    manifest = default_manifest_path()
    if manifest is None and not allow_plain:
        raise RuntimeError(
            "SimReady manifest missing: run scripts/g0/tray/import_simready.py or pass allow_plain"
        )
    revision = visuals_revision(manifest)
    work = shard_dir(out, shard)
    log, raw = work / LOG_NAME, work / "raw"
    _check_resume(raw, read_log(log))
    seeds = next_seeds(logged_seeds(out), seed_start, n_attempts, shard, workers)

    cfg = PlannerConfig.load()
    version = planner_version(cfg)
    gpu = gpu_name()
    env = make_env(seed=seeds[0], level=level)
    agent = TrayAgent(env, cfg)
    recorder = EpisodeRecorder.for_env(env, agent, raw)
    successes = recorded = qa_pass = 0
    try:
        for seed in seeds:
            wall0 = time.perf_counter()
            try:
                result = run_episode(env, agent, seed=seed, level=level, on_frame=recorder.add)
            except RuntimeError as exc:  # e.g. a renderer error; the next reset rebuilds the scene
                recorder.discard()
                result = EpisodeResult(False, f"error:{type(exc).__name__}", str(exc)[:200])
            index: int | None = None
            qa = "not_recorded"
            if result.success:
                successes += 1
                task = env.unwrapped.task
                task.set_flywheel_meta(FlywheelMeta(seed, level, version, revision))
                index = recorder.save(task.state_dict())
                recorded += 1
                qa = minimal_qa(raw, index, [name for name, _ in result.phases])
                qa_pass += qa == "pass"
            else:
                recorder.discard()
            append_attempt(
                log,
                AttemptRow(
                    seed=seed,
                    level=level,
                    shard=shard,
                    success=result.success,
                    failure=result.failure,
                    abort_reason=result.abort_reason,
                    phase_reached=result.phases[-1][0] if result.phases else "none",
                    steps=result.steps,
                    sim_s=result.sim_s,
                    wall_s=round(time.perf_counter() - wall0, 1),
                    gpu_name=gpu,
                    planner_version=version,
                    visuals_revision=revision,
                    recorded=index is not None,
                    episode_index=index,
                    qa=qa,
                ),
            )
    finally:
        recorder.close()
        env.close()
    return GenSummary(len(seeds), successes, recorded, qa_pass)


def summarize(out: Path) -> dict[str, Any]:
    """Counts, failure labels and seconds per attempt over every shard's log."""
    rows = [r for log in sorted(Path(out).glob(f"shard-*/{LOG_NAME}")) for r in read_log(log)]
    walls = sorted(float(r["wall_s"]) for r in rows)
    failures: dict[str, int] = {}
    for r in rows:
        if not r["success"]:
            label = r["failure"] or (f"abort:{r['abort_reason']}" if r["abort_reason"] else "none")
            failures[label] = failures.get(label, 0) + 1
    return {
        "attempts": len(rows),
        "successes": sum(bool(r["success"]) for r in rows),
        "recorded": sum(bool(r["recorded"]) for r in rows),
        "qa_pass": sum(r["qa"] == "pass" for r in rows),
        "failures": dict(sorted(failures.items())),
        "wall_s_mean": round(sum(walls) / len(walls), 1) if walls else None,
        "wall_s_p95": walls[min(len(walls) - 1, math.ceil(0.95 * len(walls)) - 1)]
        if walls
        else None,
        "worker_s": round(sum(walls), 1),
    }
