"""Dry runs of the laptop fetch against a VM work dir on this disk (real rsync, no SSH).

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from he1_fetch import LocalRemote, Remote, fetch_once, main, run, session_running

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
