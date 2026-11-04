"""The Colab driver's `run`, `repeat` and `persist` on a fake Psi0, before any CU is spent.

`setup` needs the network and Psi0's environment and is not run here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel_psi0.stage1 import colab
from flywheel_psi0.trainer.psi0_trainer import Runner

REPO = Path(__file__).resolve().parents[4]
PLAN = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"


@pytest.fixture
def work(fake_psi0: Path, in_process: Runner, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A VM work directory: Psi0 beside the flywheel sources and the export."""
    work = fake_psi0.parent
    (work / "fw").symlink_to(REPO)
    (work / "data" / "egodex" / "part1").mkdir(parents=True)
    monkeypatch.setattr(colab, "logging_runner", lambda path: in_process)
    return work


def phases(work: Path) -> dict[str, dict[str, object]]:
    return json.loads((work / "report.json").read_text())["phases"]  # type: ignore[no-any-return]


def test_run_then_repeat_reports_both_criteria(work: Path) -> None:
    colab.train(work, PLAN, repeat=False)
    run = phases(work)["run"]
    assert run["infra_status"] == "ok" and run["checkpoint_step"] == 200
    assert run["train_lines"] == 200
    assert run["loss_decreased"]["passed"]  # type: ignore[index]
    assert str(run["run_plan_id"]).startswith("rp_")

    colab.train(work, PLAN, repeat=True)
    repeat = phases(work)["repeat"]
    assert repeat["job_id"] == "da30-egodex-short-repeat"
    assert repeat["train_lines"] == 3 and repeat["checkpoint_step"] == 3
    assert repeat["first_loss"]["passed"]  # type: ignore[index]


def test_a_launch_that_writes_no_result_is_reported(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(colab, "logging_runner", lambda path: lambda command, cwd, env: 1)
    colab.train(work, PLAN, repeat=False)
    run = phases(work)["run"]
    assert run["infra_status"] == "policy_error"
    assert run["train_lines"] == 0 and not run["loss_decreased"]["passed"]  # type: ignore[index]


def test_persist_copies_logs_and_metrics_without_weights(work: Path, tmp_path: Path) -> None:
    colab.train(work, PLAN, repeat=False)
    (work / "data" / "egodex" / "manifest.json").write_text("{}")
    drive = tmp_path / "drive"
    colab.persist(work, PLAN, drive)
    job = drive / "da30-egodex-short"
    assert (job / "metrics.jsonl").exists() and (job / "launch.json").exists()
    assert not (job / "psi0").exists()  # Psi0's run folder with the checkpoint stays on the VM
    assert (drive / "report.json").exists() and (drive / "manifest.json").exists()
