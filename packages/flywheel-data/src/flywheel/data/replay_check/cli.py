"""`python -m flywheel.data.replay_check replay | calibrate | reports` (DA-17).

    replay     run the SIMPLE adapter's dynamic replay of a dataset as one job:
               `<python> -m flywheel_simple.replay.outcomes`, in the SIMPLE venv the
               caller names, writes <work>/replay_outcomes.jsonl. The lane starts the
               process and never imports the adapter (03 section 7.3); the caller's
               environment (PYTHONPATH, MUJOCO_GL) is passed on as is.

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
from flywheel.data.ingest.lerobot import read_info
from flywheel.data.ledger import job_ledger

app = typer.Typer(no_args_is_help=True)
STORY = "DA-17"
ADAPTER = "flywheel_simple.replay.outcomes"
# Assumption for the estimated row, not a measurement: wall seconds per frame of one
# replay worker (one 581-frame psi-data episode took 26 s on rtx3060, 4/11/2026).
REPLAY_S_PER_FRAME = 0.05

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
    run_plan_id: RunPlan = None,
) -> None:
    """Dynamic replay of every episode through the decoupled WBC (AC 2)."""
    frames = sum(int(r["length"]) for r in _episode_rows(dataset))
    estimate = frames * REPLAY_S_PER_FRAME / max(workers, 1)
    note = f"{frames} frames x {REPLAY_S_PER_FRAME} s / {workers} workers (assumed)"
    cmd = [python, "-m", ADAPTER, str(dataset), "--work", str(work), "--workers", str(workers)]
    cmd += ["--env-id", env_id] if env_id else []
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


def _episode_rows(dataset: Path) -> list[dict[str, Any]]:
    read_info(dataset)
    rows = (dataset / "meta" / "episodes.jsonl").read_text().splitlines()
    return [json.loads(r) for r in rows if r.strip()]


def _refuse(reason: str) -> None:
    typer.echo(f"refused: {reason}", err=True)
    raise typer.Exit(2)
