"""`python -m flywheel.data.replay_check replay | calibrate | reports` (DA-17).

    replay     run the SIMPLE adapter's dynamic replay of a dataset as one job:
               `<python> -m flywheel_simple.replay.outcomes`, in the SIMPLE venv the
               caller names, writes <work>/replay_outcomes.jsonl. The lane starts the
               process and never imports the adapter (03 section 7.3); the caller's
               environment (PYTHONPATH, MUJOCO_GL) is passed on as is.
    calibrate  thresholds from a clean dataset and its replay outcomes: writes
               configs/data/replay.yaml (AC 3) and prints its version@hash.

Every command is one job with its estimated and measured LedgerEntry
(`job_ledger`, run plan `g0-DA-17-<yyyymmdd>` unless one is given). A refusal
exits 2 with the reason; the measured row is still written.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from flywheel.data.config import load_layout
from flywheel.data.ingest.lerobot import iter_episodes, read_info
from flywheel.data.ledger import job_ledger
from flywheel.data.replay_check.dynamic import read_outcomes
from flywheel.data.replay_check.thresholds import (
    REPLAY_YAML,
    dump_thresholds,
    load_thresholds,
)
from flywheel.data.replay_check.thresholds import (
    calibrate as calibrate_thresholds,
)

app = typer.Typer(no_args_is_help=True)
STORY = "DA-17"
ADAPTER = "flywheel_simple.replay.outcomes"
# Assumption for the estimated row, not a measurement: wall seconds per frame of one
# replay worker (one 581-frame psi-data episode took 26 s on rtx3060, 4/11/2026).
REPLAY_S_PER_FRAME = 0.05
CHECK_S_PER_FRAME = 5e-5  # as `fw data qa`
LAYOUT = Path("configs/embodiments/g1.yaml")
HEADER = """\
# Thresholds of the replay checks (DA-17 AC 3; design 6.3, 10 D7). Written by
# `python -m flywheel.data.replay_check calibrate`; do not edit by hand, calibrate again.
#
# Every key is required (flywheel.data.replay_check.thresholds.load_thresholds); a
# ReplayThresholds carries version@<first 12 hex of the sha256 of this file>.
# kinematic: at `quantile` of the clean episodes (1.0 = their largest value), since a
#   kinematic issue rejects the episode (qa.yaml replay_kinematic). The timestamp
#   tolerance, min_std and the 1e-5 rad floor of limit_tolerance are fixed in code.
# dynamic: at `quantile` (p99, design 6.3) of the episodes whose replay succeeded; a
#   dynamic issue flags the episode (qa.yaml replay_dynamic).
"""

RunPlan = Annotated[str | None, typer.Option(help="RunPlan id; default g0-DA-17-<yyyymmdd>")]


@app.callback()
def root() -> None:
    """Replay checks of the robot sources (DA-17)."""


@app.command()
def replay(
    dataset: Annotated[Path, typer.Argument(help="SIMPLE LeRobot v2.1 dataset")],
    work: Annotated[Path, typer.Option(help="directory for replay_outcomes.jsonl")],
    python: Annotated[str, typer.Option(help="python of the SIMPLE venv")],
    workers: Annotated[int, typer.Option(help="replay processes, one env each")] = 1,
    env_id: Annotated[str | None, typer.Option(help="default simple/<dataset dir name>")] = None,
    clock: Annotated[str | None, typer.Option(help="sim (adapter default) or wall")] = None,
    run_plan_id: RunPlan = None,
) -> None:
    """Dynamic replay of every episode through the decoupled WBC (AC 2)."""
    frames = sum(int(r["length"]) for r in _episode_rows(dataset))
    estimate = frames * REPLAY_S_PER_FRAME / max(workers, 1)
    note = f"{frames} frames x {REPLAY_S_PER_FRAME} s / {workers} workers (assumed)"
    cmd = [python, "-m", ADAPTER, str(dataset), "--work", str(work), "--workers", str(workers)]
    cmd += ["--env-id", env_id] if env_id else []
    cmd += ["--clock", clock] if clock else []
    with job_ledger("replay", "replay", estimate, note=note, story=STORY,
                    run_plan_id=run_plan_id) as job:
        code = subprocess.run(cmd).returncode
        summary = work / "replay_run.json"
        if summary.is_file():
            job.notes.append(summary.read_text().replace("\n", " "))
        if code:
            job.notes.append(f"adapter exit {code}")
    if code:
        _refuse(f"replay of {dataset} failed (exit {code}); see {work}/shard-*/replay.log")
    typer.echo(f"outcomes: {work / 'replay_outcomes.jsonl'}")
    typer.echo(f"ledger: {job.run_plan_id}/{job.job_id}")


@app.command()
def calibrate(
    dataset: Annotated[Path, typer.Argument(help="clean LeRobot v2.1 dataset")],
    outcomes: Annotated[Path, typer.Option(help="replay_outcomes.jsonl of the dataset")],
    calibration: Annotated[str, typer.Option(help="what was calibrated on, for the file")],
    out: Annotated[Path, typer.Option(help="thresholds file to write")] = REPLAY_YAML,
    layout: Annotated[Path, typer.Option(help="embodiment with the action_layout")] = LAYOUT,
    quantile: Annotated[float, typer.Option(help="dynamic quantile")] = 0.99,
    kinematic_quantile: Annotated[float, typer.Option(help="kinematic quantile")] = 1.0,
    run_plan_id: RunPlan = None,
) -> None:
    """Calibrate the replay thresholds on clean episodes (AC 3)."""
    frames_count = sum(int(r["length"]) for r in _episode_rows(dataset))
    with job_ledger("qa", "replay_calibrate", frames_count * CHECK_S_PER_FRAME,
                    note=f"{frames_count} frames x {CHECK_S_PER_FRAME} s (assumed)",
                    story=STORY, run_plan_id=run_plan_id) as job:
        by_index = read_outcomes(outcomes)
        frames = list(iter_episodes(dataset))
        missing = [f.episode_index for f in frames if f.episode_index not in by_index]
        if missing:
            job.notes.append(f"{len(missing)} episodes without an outcome")
            _refuse(f"{outcomes}: no outcome for episodes {missing[:5]}")
        th = calibrate_thresholds([by_index[f.episode_index] for f in frames], quantile,
                                  frames=frames, layout=load_layout(layout),
                                  kinematic_quantile=kinematic_quantile)
        out.write_text(HEADER + dump_thresholds(th, calibration))
        version = load_thresholds(out).version
        passed = sum(by_index[f.episode_index].success for f in frames)
        job.notes.append(f"{version}; {passed}/{len(frames)} replays succeeded")
    typer.echo(f"{out}: {version}; {passed}/{len(frames)} replays succeeded")
    typer.echo(f"ledger: {job.run_plan_id}/{job.job_id}")


def _episode_rows(dataset: Path) -> list[dict[str, Any]]:
    read_info(dataset)
    rows = (dataset / "meta" / "episodes.jsonl").read_text().splitlines()
    return [json.loads(r) for r in rows if r.strip()]


def _refuse(reason: str) -> None:
    typer.echo(f"refused: {reason}", err=True)
    raise typer.Exit(2)
