"""Dry runs of the laptop fetch against a VM work dir on this disk (real rsync, no SSH).

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import he1_fetch
import pytest
import yaml
from he1_colab import REPO, progress
from he1_fetch import (
    LocalRemote,
    Remote,
    early_stop,
    fetch_once,
    main,
    probe,
    projected_cu,
    run,
    session_running,
    stop_line,
    watcher_meter,
)

JOB = "da26-t2-ft-vego-n20-s0"


def fake_vm(work: Path, saved: Sequence[int], complete: int, train_done: bool = False) -> Path:
    """A VM work dir as Psi0Trainer leaves it: checkpoints up to `complete` written."""
    job = work / "runs" / JOB
    run = job / "psi0/exp/run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "argv.txt").write_text("--seed=0\n")
    (job / "metrics.jsonl").write_text('{"step": 1}\n')
    (job / "result.json").write_text(json.dumps({"checkpoint_step": complete}))
    for step in saved:
        ckpt = run / "checkpoints" / f"ckpt_{step}"
        ckpt.mkdir(parents=True, exist_ok=True)
        (ckpt / "model.safetensors").write_bytes(step.to_bytes(4, "little") * 1000)
        (ckpt / "optimizer.bin").write_bytes(b"o" * 5000)
        (ckpt / "scheduler.bin").write_bytes(b"s")
    phases = {"train": {"job_id": JOB}} if train_done else {}
    (work / "report.json").write_text(json.dumps({"phases": phases}))
    return work


def test_pulls_the_latest_complete_checkpoint_without_optimizer(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000, 20000, 30000), complete=20000)  # 30000 mid-write
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    here = tmp_path / "laptop" / JOB
    ckpts = here / "psi0/exp/run/checkpoints"
    assert (ckpts / "ckpt_20000/model.safetensors").read_bytes() == (20000).to_bytes(
        4, "little"
    ) * 1000
    assert (ckpts / "ckpt_20000/scheduler.bin").is_file()
    assert not (ckpts / "ckpt_20000/optimizer.bin").exists()
    assert not (ckpts / "ckpt_10000").exists() and not (ckpts / "ckpt_30000").exists()
    assert (here / "metrics.jsonl").is_file() and (here / "psi0/exp/run/argv.txt").is_file()
    assert status["checkpoint"] == "ckpt_20000" and status["bad_or_missing"] == []
    assert not status["final"]  # training still runs
    assert json.loads((here / "fetched.json").read_text()) == status


def test_the_final_pull_takes_only_what_is_new_and_ends_the_job(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000, 20000), complete=20000)
    fetch_once(LocalRemote(vm), tmp_path / "laptop")
    fake_vm(vm, saved=(40000,), complete=40000, train_done=True)
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    assert status["checkpoint"] == "ckpt_40000" and status["final"]
    assert status["pulled_bytes"] == 4000 + 1 + len('{"checkpoint_step": 40000}')


def test_a_wrong_copy_here_is_pulled_again(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000, train_done=True)
    fetch_once(LocalRemote(vm), tmp_path / "laptop")
    model = tmp_path / "laptop" / JOB / "psi0/exp/run/checkpoints/ckpt_10000/model.safetensors"
    stat = model.stat()
    model.write_bytes(b"x" * stat.st_size)  # same size and mtime: rsync's quick check passes
    import os

    os.utime(model, (stat.st_atime, stat.st_mtime))
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    assert status["final"] and model.read_bytes() == (10000).to_bytes(4, "little") * 1000


def test_once_reports_not_done_then_done(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    args = ["once", "--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l")]
    assert main([*args, "--local-vm", str(vm)]) == 1
    fake_vm(vm, saved=(), complete=10000, train_done=True)
    assert main([*args, "--local-vm", str(vm)]) == 0


def listing(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["colab", "sessions"], 0, text, "")


def test_no_ssh_once_the_watcher_exited_or_the_session_is_gone(tmp_path: Path) -> None:
    out = tmp_path / f"{JOB}.out"
    line = f"[{JOB}] gpu-l4-s-abc | Hardware: L4 | Shape: Standard | Variant: GPU"
    out.write_text("")
    assert session_running(JOB, tmp_path, Path("colab"), lambda argv: listing(line))
    assert not session_running(JOB, tmp_path, Path("colab"), lambda argv: listing("[other] x"))
    out.write_text("exit 3\n")
    assert not session_running(JOB, tmp_path, Path("colab"), lambda argv: listing(line))
    assert not session_running("missing", tmp_path, Path("colab"), lambda argv: listing(line))


def test_the_real_transport_is_rsync_over_the_colab_proxy() -> None:
    remote = Remote(JOB, Path("/x/colab"))
    assert remote.ssh[:3] == ["ssh", "-o", f"ProxyCommand=/x/colab ssh --proxy-mode -s {JOB}"]
    assert remote.ssh[-1] == "root@colab" and "root@colab" not in remote.rsh
    assert remote.stage()[-1] == "cd /content/da26 && python3 fw/scripts/he/he1_colab.py stage"
    assert remote.source == "root@colab:/content/da26/runs"


def test_a_failed_pull_is_never_counted_as_fetched(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000, train_done=True)

    def cut_rsync(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "rsync":
            return subprocess.CompletedProcess(argv, 12, "", "connection unexpectedly closed")
        return run(argv)

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop", runner=cut_rsync)
    assert not status["final"] and status["pulled_bytes"] is None
    assert "psi0/exp/run/checkpoints/ckpt_10000/model.safetensors" in status["bad_or_missing"]


def train_lines(path: Path, steps: Sequence[int], s_per_step: float, attempt: int = 0) -> None:
    rows = [
        {"split": "train", "step": k, "wall_time_s": 30.0 + k * s_per_step, "attempt": attempt}
        for k in steps
    ]
    rows.insert(1, {"split": "val", "step": 2000, "wall_time_s": 1.0, "attempt": attempt})
    with path.open("a") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))


def test_progress_reads_the_latest_attempt_after_warm_up(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    train_lines(metrics, range(1, 3001), 2.0, attempt=0)
    train_lines(metrics, range(1, 2501), 0.75, attempt=1)
    assert progress(metrics) == {"step": 2500, "s_per_step": pytest.approx(0.75)}
    assert progress(tmp_path / "none.jsonl") == {"step": None, "s_per_step": None}


def test_the_constants_match_the_recipe_and_the_watcher() -> None:
    recipe = yaml.safe_load((REPO / "configs/models/psi0-stage3.yaml").read_text())["args"]
    assert he1_fetch.TOTAL_STEPS == recipe["train.max_training_steps"]
    assert he1_fetch.SAVE_EVERY == recipe["train.checkpointing_steps"]
    import sys

    sys.path.insert(0, str(REPO / "scripts/colab"))
    from cu_watch import Timing

    assert he1_fetch.MARGIN_S == Timing().margin
    assert stop_line(17.5) == pytest.approx(17.268, abs=1e-3)


def test_the_s104_estimate_fits_only_with_a_fast_pull() -> None:
    # Step 2200 at S1-04's 8.5 h run: 0.753 s/step with validation, 8 min of setup.
    spent = 1.94 * (8 * 60 + 2200 * 0.753) / 3600
    slow = projected_cu(spent, 2200, 0.753, 6.0, 6.25e9)
    fast = projected_cu(spent, 2200, 0.753, 30.0, 6.25e9)
    assert slow > stop_line(17.5) > fast
    status = {"progress": {"step": 2200, "s_per_step": 0.753}, "checkpoint_bytes": 0}
    assert early_stop(status, (spent, 17.5), 6.0) is not None
    assert early_stop(status, (spent, 17.5), 30.0) is None
    assert early_stop(status, None, 6.0) is None  # no meter yet: never stop blind
    late = {"progress": {"step": 12000, "s_per_step": 2.0}, "checkpoint_bytes": 0}
    assert early_stop(late, (spent, 17.5), 6.0) is None  # past the first checkpoint


def test_the_meter_is_the_watchers_last_poll(tmp_path: Path) -> None:
    log = tmp_path / f"{JOB}.jsonl"
    rows = [
        {"event": "start"},
        {"event": "poll", "spent": 1.2, "cap": 17.5},
        {"event": "poll", "spent": 1.3, "cap": 17.5},
        {"event": "persist", "spent": 9},
    ]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
    assert watcher_meter(tmp_path, JOB) == (1.3, 17.5)
    assert watcher_meter(tmp_path, "other") is None


def test_follow_stops_a_run_that_cannot_finish(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(), complete=0)
    metrics = vm / "runs" / JOB / "metrics.jsonl"
    metrics.write_text("")
    train_lines(metrics, range(1, 2301), 0.85)  # slower than S1-04
    reg = tmp_path / "reg"
    reg.mkdir()
    (reg / f"{JOB}.jsonl").write_text(json.dumps({"event": "poll", "spent": 1.5, "cap": 17.5}))
    args = ["follow", "--session", JOB, "--registry", str(reg), "--dest", str(tmp_path / "l")]
    assert main([*args, "--every", "0", "--local-vm", str(vm)]) == 3


def test_probe_times_a_pull_and_cleans_both_ends(tmp_path: Path) -> None:
    vm = tmp_path / "vm"
    mb_s = probe(LocalRemote(vm), tmp_path, megabytes=8)
    assert mb_s > 0
    assert not (vm / "probe.bin").exists() and not (tmp_path / ".probe.bin").exists()
