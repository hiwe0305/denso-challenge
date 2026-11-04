"""The Colab driver's `run`, `repeat` and `persist` on a fake Psi0, before any CU is spent.

`setup` needs the network and Psi0's environment; only its order is run here, with
the shell faked: the DeepSpeed pre-flight comes before any download.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import pytest
from flywheel_psi0.stage1 import colab, preflight
from flywheel_psi0.stage1.runplan import Stage1Plan
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
    launched = json.loads((work / "runs" / "da30-egodex-short" / "launch.json").read_text())
    config = work / "fw" / "configs" / "runplans" / "stage1" / "zero3_offload.json"
    assert f"--train.deepspeed_config={config}" in launched["argv"]

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


def test_the_preflight_gets_the_recipe_values_and_the_plan_config() -> None:
    plan = Stage1Plan.load(PLAN)
    command = shlex.split(colab.preflight_command(plan, Path("/content/da30/Psi0"), REPO))
    assert command[:4] == [
        "/content/da30/Psi0/.venv-psi/bin/torchrun",
        "--nproc_per_node=1",
        "-m",
        "flywheel_psi0.stage1.preflight",
    ]
    args = preflight.parse_args(command[4:])
    assert args.config == str(REPO / "configs" / "runplans" / "stage1" / "zero3_offload.json")
    assert (args.lr, args.betas, args.eps, args.weight_decay) == (1e-4, [0.9, 0.999], 1e-8, 0.0)
    assert (args.micro_batch, args.accumulation, args.precision) == (16, 2, "bf16")
    assert args.total_steps == 200


@pytest.mark.parametrize("preflight_fails", [False, True])
def test_setup_runs_the_preflight_before_any_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preflight_fails: bool
) -> None:
    work = tmp_path / "da30"
    (work / "Psi0").mkdir(parents=True)
    (work / "fw").symlink_to(REPO)
    commands: list[str] = []

    def sh(command: str, cwd: Path | None = None) -> None:
        commands.append(command)
        if preflight_fails and "stage1.preflight" in command:
            raise subprocess.CalledProcessError(1, command)

    class Fetched(Exception):
        pass

    def fetch(*args: object) -> None:
        raise Fetched  # the EgoDex download: far enough for this test

    monkeypatch.setattr(colab, "setup_psi0_env", lambda work: None)
    monkeypatch.setattr(colab, "sh", sh)
    monkeypatch.setattr(colab, "fetch", fetch)
    with pytest.raises(subprocess.CalledProcessError if preflight_fails else Fetched):
        colab.setup(work, PLAN)
    assert "stage1.preflight" in commands[0]
    report = phases(work)["preflight"]
    if preflight_fails:
        assert commands == commands[:1] and "error" in report  # no parent download
    else:
        assert "snapshot_download" in commands[1] and "error" not in report
