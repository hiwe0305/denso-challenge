"""Tray tests check the code against the plans, not the live tree against the plans.

A frozen tray plan pins sim files by sha256 (`pinned_files`), and a job refuses to
launch once one of them changes (`runplan.pinned_file_drift`: an error at launch, a
warning on CI). A later scene revision changes some of them on purpose: DA-33 draws the
target zone (`+zone1`, Decision 11/11/2026), so v2, C+, B and C-max, which pin the old
`mjcf.py` and `simple_task.py`, no longer launch. That is the guard working, and it is
not what these tests are about: they check the setup, train, check and freeze logic
against the plans as frozen.

So drift the live tree itself has is set aside here. A file a test changed (its copy
differs from the live file) still drifts, which keeps the drift tests honest: the file
they edit drifts whatever the live tree holds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flywheel_psi0.tray import colab_train, pairplan, runplan
from flywheel_psi0.tray.runplan import TrayRunPlan

LIVE = Path(__file__).resolve().parents[4]
PREFIX = "pinned file "


def same_as_live(repo: Path, rel: str) -> bool:
    mine, live = repo / rel, LIVE / rel
    return mine.is_file() and live.is_file() and mine.read_bytes() == live.read_bytes()


def set_aside(lines: list[str], repo: Path) -> list[str]:
    kept = []
    for line in lines:
        rel = line.removeprefix(PREFIX).split(" ", 1)[0]
        if not (line.startswith(PREFIX) and same_as_live(repo, rel)):
            kept.append(line)
    return kept


@pytest.fixture(autouse=True)
def live_drift_set_aside(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both drift checks: `pinned_file_drift` (run plans) and `file_pin_drift` (any plan kind).
    real = runplan.pinned_file_drift
    real_pins = runplan.file_pin_drift

    def drift(plan: TrayRunPlan, repo: Path = runplan.REPO) -> list[str]:
        return set_aside(real(plan, repo), repo)

    def pin_drift(pins: dict[str, str] | None, repo: Path = runplan.REPO) -> list[str]:
        return set_aside(real_pins(pins, repo), repo)

    monkeypatch.setattr(runplan, "pinned_file_drift", drift)
    monkeypatch.setattr(colab_train, "pinned_file_drift", drift)
    monkeypatch.setattr(runplan, "file_pin_drift", pin_drift)
    monkeypatch.setattr(pairplan, "file_pin_drift", pin_drift)
