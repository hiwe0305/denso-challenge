"""Inputs of the tool tests: the stage 1 rollouts of the four 60k runs, as `Score` records.

`data/pair60k_stage1.jsonl` is the output of `flywheel_psi0.tray.export_scores` on the
eval batches `pair60k-<run>-60000-rp_a04c14e79dfd` (60 conditions, levels 1-2), cut to
the fields the tools read: run, level, seed, success, failure label, and the step flags
as a string of 0 and 1. Simulation data of the demo, `public`. The numbers the tests
check are the ones docs/he/tray.md 19.2, 20.2 and 20.11 report on the same rollouts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.tools.base import RunScores
from flywheel.eval.agentqa.tools.task import TaskView, load_task

DATA = Path(__file__).parent / "data" / "pair60k_stage1.jsonl"
SHA = "0" * 64


def status_of(flags: str) -> list[str]:
    out, failed = [], False
    for flag in flags:
        if flag == "1":
            out.append("pass")
        elif not failed:
            out.append("fail")
            failed = True
        else:
            out.append("not_attempted")
    return out


def score(run: str, level: int, seed: int, success: bool, failure: str | None,
          steps: str) -> Score:
    status = status_of(steps)
    return Score(
        episode_id=f"{run}/l{level}-s{seed}", task_id="tray", config_sha256=SHA,
        trace_sha256=SHA, success=success, step_status=status,  # type: ignore[arg-type]
        first_failed_step=next((k for k, s in enumerate(status) if s == "fail"), None),
        failure_kind=failure, level=level,
    )


def load_runs() -> dict[str, RunScores]:
    by_run: dict[str, list[Score]] = {}
    for line in DATA.read_text().splitlines():
        row = json.loads(line)
        by_run.setdefault(row["run"], []).append(
            score(row["run"], row["level"], row["seed"], row["success"], row["failure"],
                  row["steps"]))
    return {run: RunScores(run, f"pack/{run}/scores.jsonl", tuple(scores))
            for run, scores in by_run.items()}


@pytest.fixture(scope="session")
def runs() -> dict[str, RunScores]:
    return load_runs()


@pytest.fixture(scope="session")
def tray() -> TaskView:
    return load_task("tray")
