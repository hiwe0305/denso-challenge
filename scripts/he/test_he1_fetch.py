"""Dry runs of the laptop fetch against a VM work dir on this disk (real rsync, no SSH).

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import json
import signal
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType

import he1_colab
import he1_fetch
import pytest
import yaml
from he1_colab import REPO, progress
from he1_fetch import (
    LocalRemote,
    Remote,
    fetch_once,
    judge,
    main,
    probe,
    projected_cu,
    run,
    session_running,
    stop_line,
    stop_session,
    watcher_meter,
)

JOB = "da26-t2-ft-vego-n20-s0"
MODEL = "psi0/exp/run/checkpoints/ckpt_{}/model.safetensors"


def fake_vm(
    work: Path,
    saved: Sequence[int],
    complete: int,
    train_done: bool = False,
    infra_status: str = "ok",
) -> Path:
    """A VM work dir as Psi0Trainer leaves it: checkpoints up to `complete` written.

    `train_done` writes the train phase as `train` does when the trainer returns,
    with `infra_status` and the last complete checkpoint's step.
    """
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
    phase = {"job_id": JOB, "infra_status": infra_status, "checkpoint_step": complete}
    phases = {"train": phase} if train_done else {}
    (work / "report.json").write_text(json.dumps({"phases": phases}))
    return work


def weights(step: int) -> bytes:
    return step.to_bytes(4, "little") * 1000


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    """Fail the test instead of hanging when a `follow` loop never returns."""

    def expire(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError(f"no return within {seconds} s")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def test_pulls_the_latest_complete_checkpoint_without_optimizer(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000, 20000, 30000), complete=20000)  # 30000 mid-write
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    here = tmp_path / "laptop" / JOB
    ckpts = here / "psi0/exp/run/checkpoints"
    assert (ckpts / "ckpt_20000/model.safetensors").read_bytes() == weights(20000)
    assert (ckpts / "ckpt_20000/scheduler.bin").is_file()
    assert not (ckpts / "ckpt_20000/optimizer.bin").exists()
    assert not (ckpts / "ckpt_10000").exists() and not (ckpts / "ckpt_30000").exists()
    assert (here / "metrics.jsonl").is_file() and (here / "psi0/exp/run/argv.txt").is_file()
    assert status["checkpoint"] == "ckpt_20000" and status["bad_or_missing"] == []
    assert status["train"] == "running" and not status["final"]
    assert json.loads((here / "fetched.json").read_text()) == status
    (vm / "runs" / JOB / "metrics.jsonl").write_text('{"step": 2}\n')
    (again,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")  # logs only: no rate
    assert again["pulled_bytes"] == 12 and again["mb_per_s"] is None


def test_a_train_that_ended_ok_without_its_last_checkpoint_is_not_final(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(30000,), complete=40000, train_done=True)
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    assert status["train"] == "done" and status["checkpoint"] == "ckpt_30000"
    assert not status["final"]


def test_the_final_pull_takes_only_what_is_new_and_ends_the_job(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000, 20000), complete=20000)
    fetch_once(LocalRemote(vm), tmp_path / "laptop")
    fake_vm(vm, saved=(40000,), complete=40000, train_done=True)
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    assert status["checkpoint"] == "ckpt_40000" and status["train"] == "done" and status["final"]
    assert status["pulled_bytes"] == 4000 + 1 + len('{"checkpoint_step": 40000}')
    assert status["checkpoint_pulled_bytes"] == 4000 + 1


def test_a_wrong_copy_here_is_pulled_again(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000, train_done=True)
    fetch_once(LocalRemote(vm), tmp_path / "laptop")
    model = tmp_path / "laptop" / JOB / MODEL.format(40000)
    stat = model.stat()
    model.write_bytes(b"x" * stat.st_size)  # same size and mtime: rsync's quick check passes
    import os

    os.utime(model, (stat.st_atime, stat.st_mtime))
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop")
    assert status["final"] and model.read_bytes() == weights(40000)


def test_a_pull_corrupted_on_the_way_is_caught_by_its_sha256(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000, train_done=True)
    laptop = tmp_path / "laptop"

    def corrupting_rsync(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        done = run(argv)
        if argv[0] == "rsync":  # rsync says 0, the bytes here are wrong
            model = laptop / JOB / MODEL.format(40000)
            model.write_bytes(b"\0" * model.stat().st_size)
        return done

    (status,) = fetch_once(LocalRemote(vm), laptop, runner=corrupting_rsync)
    assert MODEL.format(40000) in status["bad_or_missing"]
    assert not status["final"] and status["mb_per_s"] is None


def test_once_reports_not_done_then_done_only_at_the_last_step(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    args = ["once", "--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l")]
    assert main([*args, "--local-vm", str(vm)]) == 1
    fake_vm(vm, saved=(40000,), complete=40000, train_done=True)
    assert main([*args, "--local-vm", str(vm)]) == 0


@pytest.mark.parametrize(
    ("infra_status", "complete"), [("failed", 20000), ("ok", 20000), ("failed", 40000)]
)
def test_a_failed_train_is_pulled_but_never_final(
    tmp_path: Path, infra_status: str, complete: int
) -> None:
    # A crash at 25k: `train` wrote its phase before raising, ckpt_20000 is on disk.
    vm = fake_vm(
        tmp_path / "vm",
        saved=(10000, 20000),
        complete=complete,
        train_done=True,
        infra_status=infra_status,
    )
    if complete == 40000:
        fake_vm(vm, saved=(40000,), complete=40000, train_done=True, infra_status=infra_status)
    laptop = tmp_path / "l"
    args = ["--session", JOB, "--registry", str(tmp_path), "--dest", str(laptop)]
    assert main(["once", *args, "--local-vm", str(vm)]) == 5
    with deadline(60):
        assert main(["follow", *args, "--every", "0", "--local-vm", str(vm)]) == 5
    status = json.loads((laptop / JOB / "fetched.json").read_text())
    assert status["train"] == "failed" and not status["final"]
    assert (laptop / JOB / MODEL.format(complete)).read_bytes() == weights(complete)


def test_a_train_process_that_died_without_its_phase_has_failed(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    (vm / "train.log").write_text("Killed\ntrain exit 137\n")
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l")
    assert status["train"] == "failed"


def test_a_log_written_to_during_the_pull_is_grown_not_bad(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    metrics = vm / "runs" / JOB / "metrics.jsonl"

    def training_meanwhile(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "rsync":  # the trainer appends between `stage` and the pull
            with metrics.open("a") as f:
                f.write('{"step": 2}\n')
        return run(argv)

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l", runner=training_meanwhile)
    assert status["bad_or_missing"] == [] and status["grown"] == ["metrics.jsonl"]
    assert status["mb_per_s"] is not None and status["checkpoint_pulled_bytes"] == 4001


def listing(text: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["colab", "sessions"], code, text, "")


LINE = f"[{JOB}] gpu-l4-s-abc | Hardware: L4 | Shape: Standard | Variant: GPU"


def test_no_ssh_once_the_watcher_exited_or_the_session_is_gone(tmp_path: Path) -> None:
    out = tmp_path / f"{JOB}.out"
    out.write_text("")
    assert session_running(JOB, tmp_path, Path("colab"), lambda argv: listing(LINE))
    assert not session_running(JOB, tmp_path, Path("colab"), lambda argv: listing("[other] x"))
    assert not session_running(JOB, tmp_path, Path("colab"), lambda argv: listing(LINE, 1))
    out.write_text("exit 3\n")
    assert not session_running(JOB, tmp_path, Path("colab"), lambda argv: listing(LINE))
    assert not session_running("missing", tmp_path, Path("colab"), lambda argv: listing(LINE))


def colab_cli(listed_after: int) -> tuple[list[list[str]], he1_fetch.Run]:
    """A fake `colab`: `sessions` lists the job until `stop` has run `listed_after` times."""
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        stops = sum(1 for c in calls if c[1] == "stop")
        if argv[1] == "stop":
            return subprocess.CompletedProcess(argv, 1 if stops < listed_after else 0, "", "")
        return listing("" if stops >= listed_after else LINE)

    return calls, runner


def test_a_stop_is_retried_until_the_session_is_gone(tmp_path: Path) -> None:
    calls, runner = colab_cli(listed_after=2)
    assert stop_session(JOB, tmp_path, Path("colab"), runner, sleep=lambda s: None)
    assert [c[1] for c in calls] == ["stop", "sessions", "stop", "sessions"]


def test_a_stop_that_never_confirms_signals_the_watcher_then_says_so(tmp_path: Path) -> None:
    watcher = subprocess.Popen(["sleep", "60"])
    (tmp_path / f"{JOB}.json").write_text(json.dumps({"name": JOB, "pid": watcher.pid}))
    calls, runner = colab_cli(listed_after=99)
    ok = stop_session(JOB, tmp_path, Path("colab"), runner, sleep=lambda s: None, term_wait=90)
    assert not ok and watcher.wait(timeout=10) == -signal.SIGTERM
    assert sum(1 for c in calls if c[1] == "stop") == 3
    (tmp_path / f"{JOB}.json").unlink()  # no registry entry: no watcher to signal
    _, runner = colab_cli(listed_after=99)
    assert not stop_session(JOB, tmp_path, Path("colab"), runner, sleep=lambda s: None)


def test_hung_commands_end_as_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(he1_fetch, "TIMEOUT_S", 0.2)
    assert run(["sleep", "5"]).returncode == 124


def test_the_real_transport_is_rsync_over_the_colab_proxy() -> None:
    remote = Remote(JOB, Path("/x/colab"))
    assert remote.ssh[:3] == ["ssh", "-o", f"ProxyCommand=/x/colab ssh --proxy-mode -s {JOB}"]
    assert remote.ssh[-1] == "root@colab" and "root@colab" not in remote.rsh
    assert remote.stage()[-1] == "cd /content/da26 && python3 fw/scripts/he/he1_colab.py stage"
    assert remote.source == "root@colab:/content/da26/runs"


def test_a_failed_pull_is_never_counted_as_fetched(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000, train_done=True)

    def cut_rsync(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "rsync":
            return subprocess.CompletedProcess(argv, 12, "", "connection unexpectedly closed")
        return run(argv)

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "laptop", runner=cut_rsync)
    assert not status["final"] and status["pulled_bytes"] is None
    assert MODEL.format(40000) in status["bad_or_missing"]


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
    with metrics.open("a") as f:
        f.write('{"split": "train", "step": 25')  # the trainer is mid-line
    assert progress(metrics) == {"step": 2500, "s_per_step": pytest.approx(0.75)}
    assert progress(tmp_path / "none.jsonl") == {"step": None, "s_per_step": None}


def test_the_constants_match_the_recipe_and_the_watcher() -> None:
    recipe = yaml.safe_load((REPO / "configs/models/psi0-stage3.yaml").read_text())["args"]
    assert he1_fetch.TOTAL_STEPS == he1_colab.TOTAL_STEPS == recipe["train.max_training_steps"]
    assert he1_fetch.SAVE_EVERY == recipe["train.checkpointing_steps"]
    import sys

    sys.path.insert(0, str(REPO / "scripts/colab"))
    from cu_watch import Timing

    assert he1_fetch.MARGIN_S == Timing().margin
    assert stop_line(17.5) == pytest.approx(17.268, abs=1e-3)


def running(step: int, rate: float | None) -> dict[str, object]:
    return {
        "train": "running",
        "progress": {"step": step, "s_per_step": rate},
        "checkpoint_bytes": 0,
    }


def test_the_s104_estimate_fits_only_with_a_fast_pull() -> None:
    # Step 2200 at S1-04's 8.5 h run: 0.753 s/step with validation, 8 min of setup.
    spent = 1.94 * (8 * 60 + 2200 * 0.753) / 3600
    slow = projected_cu(spent, 2200, 0.753, 6.0, 6.25e9)
    fast = projected_cu(spent, 2200, 0.753, 30.0, 6.25e9)
    assert slow > stop_line(17.5) > fast
    assert judge(running(2200, 0.753), (spent, 17.5), 6.0)["verdict"] == "stop"  # type: ignore[index]
    assert judge(running(2200, 0.753), (spent, 17.5), 30.0)["verdict"] == "ok"  # type: ignore[index]
    assert judge(running(2100, 0.753), (spent, 17.5), 6.0) is None  # before the window
    late = judge(running(12000, 2.0), (spent, 17.5), 6.0)
    assert late is not None and late["verdict"] == "late"  # past ckpt_10000: ALERT only


def test_a_pass_that_cannot_project_is_blind_not_ok() -> None:
    blind = judge(running(2500, 0.75), None, 30.0)
    assert blind is not None and blind["verdict"] == "blind"
    assert "poll" in blind["reason"]
    no_rate = judge(running(2500, None), (1.0, 17.5), 30.0)
    assert no_rate is not None and no_rate["verdict"] == "blind"
    assert judge({**running(2500, 9.0), "train": "done"}, (1.0, 17.5), 6.0) is None


def poll(spent: float, age_s: float = 0.0) -> dict[str, object]:
    when = datetime.now(timezone.utc).timestamp() - age_s
    stamp = datetime.fromtimestamp(when, timezone.utc).isoformat(timespec="seconds")
    return {"time": stamp, "event": "poll", "spent": spent, "cap": 17.5}


def test_the_meter_is_the_watchers_last_poll_while_fresh(tmp_path: Path) -> None:
    log = tmp_path / f"{JOB}.jsonl"
    rows = [{"event": "start"}, poll(1.2, 120), poll(1.3, 60), {"event": "persist", "spent": 9}]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
    assert watcher_meter(tmp_path, JOB) == (1.3, 17.5)
    assert watcher_meter(tmp_path, "other") is None
    log.write_text(json.dumps(poll(1.3, 400)) + "\n")  # the watcher stopped polling
    assert watcher_meter(tmp_path, JOB) is None


def test_the_projection_counts_every_second_left(tmp_path: Path) -> None:
    # step 39000 at 1 s/step: 1000 s, one save, the final pass lag, the hashes, 100 s pull
    seconds = 1000 + 60 + 60 + 60 + 1e9 / 10e6
    assert projected_cu(2.0, 39000, 1.0, 10.0, 1e9) == pytest.approx(
        2.0 + 1.94 * seconds / 3600 + 0.1
    )


def slow_run(tmp_path: Path) -> list[str]:
    """A VM at step 2300 running slower than S1-04, and `follow` arguments for it."""
    vm = fake_vm(tmp_path / "vm", saved=(), complete=0)
    metrics = vm / "runs" / JOB / "metrics.jsonl"
    metrics.write_text("")
    train_lines(metrics, range(1, 2301), 0.85)
    reg = tmp_path / "reg"
    reg.mkdir()
    (reg / f"{JOB}.jsonl").write_text(json.dumps(poll(1.5)))
    args = ["follow", "--session", JOB, "--registry", str(reg), "--dest", str(tmp_path / "l")]
    return [*args, "--every", "0", "--local-vm", str(vm)]


def test_a_stop_that_is_not_confirmed_exits_6(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(he1_fetch, "stop_session", lambda *a, **k: False)
    with deadline(60):
        assert main(slow_run(tmp_path)) == 6
    vm = fake_vm(tmp_path / "vm2", saved=(10000,), complete=10000, train_done=True)
    args = ["--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l2")]
    with deadline(60):
        assert main(["follow", *args, "--every", "0", "--local-vm", str(vm)]) == 6
        fake_vm(vm, saved=(40000,), complete=40000, train_done=True)
        assert main(["follow", *args, "--stop-when-done", "--local-vm", str(vm)]) == 6
        assert main(["follow", *args, "--local-vm", str(vm)]) == 0  # no stop asked


def test_follow_stops_a_run_that_cannot_finish(tmp_path: Path) -> None:
    with deadline(60):
        assert main(slow_run(tmp_path)) == 3


def test_probe_times_a_pull_and_cleans_both_ends(tmp_path: Path) -> None:
    vm = tmp_path / "vm"
    mb_s = probe(LocalRemote(vm), tmp_path, megabytes=8)
    assert mb_s > 0
    assert not (vm / "probe.bin").exists() and not (tmp_path / ".probe.bin").exists()
