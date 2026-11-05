"""Dry runs of the laptop fetch against a VM work dir on this disk (real rsync, no SSH).

Run: uv run pytest scripts/he -q
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Any

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
    listed,
    main,
    pause,
    probe,
    projected_cu,
    run,
    session_running,
    session_state,
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
    # new: the checkpoint, result.json, and the train phase in vm-logs/report.json
    report = (vm / "report.json").stat().st_size
    assert status["pulled_bytes"] == 4000 + 1 + len('{"checkpoint_step": 40000}') + report
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


def test_once_for_a_job_with_no_train_is_done_when_pulled(tmp_path: Path) -> None:
    """The eval's job: servers, logs, no train and no checkpoint. Without the flag
    `once` said 1 (not yet) after a full pull, and he1_eval logged vm_pulled code 1
    (eval attempt 3, 5/11/2026). A pass that pulls nothing is still 1."""
    vm = fake_vm(tmp_path / "vm", saved=(), complete=0)
    args = ["once", "--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l")]
    assert main([*args, "--local-vm", str(vm)]) == 1
    assert main([*args, "--no-checkpoint", "--local-vm", str(vm)]) == 0
    assert (tmp_path / "l" / JOB / "metrics.jsonl").is_file()
    empty = tmp_path / "empty-vm"
    empty.mkdir()
    assert main([*args, "--no-checkpoint", "--local-vm", str(empty)]) == 1


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


LINE = f"[{JOB}] gpu-l4-s-abc | Hardware: L4 | Shape: Standard | Variant: GPU"
LOST = "[?] gpu-l4-s-abc | Hardware: L4 | Shape: Standard | Variant: GPU"  # name lost
EMPTY = "[colab] No active sessions"


def cli(sessions: str, assignments: int = 1, codes: tuple[int, int] = (0, 0)) -> he1_fetch.Run:
    """A fake `colab` that answers `usage` and `sessions` as the real CLI prints them."""

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[1] == "usage":
            text = f"Current balance: 80.0\nUsage rate: 1.94\nActive assignments: {assignments}\n"
            return subprocess.CompletedProcess(argv, codes[0], text, "")
        return subprocess.CompletedProcess(argv, codes[1], sessions + "\n", "")

    return runner


def test_no_ssh_once_the_watcher_exited_or_the_session_is_gone(tmp_path: Path) -> None:
    out = tmp_path / f"{JOB}.out"
    out.write_text("")
    (tmp_path / f"{JOB}.json").write_text(json.dumps({"name": JOB, "endpoint": "gpu-l4-s-abc"}))
    assert session_running(JOB, tmp_path, Path("colab"), cli(LINE))
    assert session_running(JOB, tmp_path, Path("colab"), cli(LOST))  # found by endpoint
    assert session_state(JOB, tmp_path, Path("colab"), cli(EMPTY, 0)) == "gone"
    assert not session_running(JOB, tmp_path, Path("colab"), cli(LINE, codes=(0, 1)))
    out.write_text("exit 3\n")
    assert session_state(JOB, tmp_path, Path("colab"), cli(LINE)) == "gone"
    assert not session_running("missing", tmp_path, Path("colab"), cli(LINE))


def test_an_auth_failure_listing_is_not_trusted(tmp_path: Path) -> None:
    # On an auth failure `sessions` prints "No active sessions" and exits 0.
    assert listed(JOB, Path("colab"), cli(EMPTY, assignments=1)) is None
    assert listed(JOB, Path("colab"), cli(LINE, codes=(1, 0))) is None  # usage failed
    assert listed(JOB, Path("colab"), cli("garbled output")) is None
    assert listed(JOB, Path("colab"), cli(EMPTY, assignments=0)) is False
    (tmp_path / f"{JOB}.out").write_text("")
    assert session_state(JOB, tmp_path, Path("colab"), cli(EMPTY, 1)) == "unknown"


def colab_cli(
    listed_after: int, sessions_fail: bool = False
) -> tuple[list[list[str]], he1_fetch.Run]:
    """A fake `colab`: the job stays listed until `stop` has run `listed_after` times.

    `sessions_fail`: once stopped, `sessions` says "No active sessions" while `usage`
    still counts the assignment (the auth failure of cu_watch.py's docstring).
    """
    calls: list[list[str]] = []

    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        stops = sum(1 for c in calls if c[1] == "stop")
        if argv[1] == "stop":
            return subprocess.CompletedProcess(argv, 1 if stops < listed_after else 0, "", "")
        if stops >= listed_after:
            return cli(EMPTY, 0)(argv)
        return cli(EMPTY if sessions_fail else LINE, 1)(argv)

    return calls, runner


def no_wait(seconds: float) -> None:
    pass


def fake_watcher(registry: Path, state: str = "running", script: str = "cu_watch.py") -> Any:
    """A live process whose command line names `script`, registered as the watcher."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", script])
    entry = {"name": JOB, "pid": proc.pid, "state": state, "endpoint": "gpu-l4-s-abc"}
    (registry / f"{JOB}.json").write_text(json.dumps(entry))
    return proc


def test_once_retries_an_untrusted_listing_then_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = iter(["unknown", "unknown", "unknown"])
    monkeypatch.setattr(he1_fetch, "session_state", lambda *a, **k: next(states))
    monkeypatch.setattr(he1_fetch, "UNTRUSTED_RETRY_S", 0.0)
    args = ["once", "--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l")]
    with deadline(30):
        assert main(args) == 2  # three untrusted listings, never an ssh
    states = iter(["unknown", "gone"])
    with deadline(30):
        assert main(args) == 2


def test_a_stop_is_retried_until_two_trusted_listings_lack_the_session(tmp_path: Path) -> None:
    calls, runner = colab_cli(listed_after=2)
    assert stop_session(JOB, tmp_path, Path("colab"), runner, sleep=no_wait)
    assert [c[1] for c in calls].count("stop") == 2
    assert [c[1] for c in calls][-4:] == ["usage", "sessions", "usage", "sessions"]


def test_a_stop_is_not_confirmed_by_an_untrusted_listing(tmp_path: Path) -> None:
    calls, runner = colab_cli(listed_after=99, sessions_fail=True)
    assert not stop_session(JOB, tmp_path, Path("colab"), runner, sleep=no_wait, term_wait=60)
    assert [c[1] for c in calls].count("stop") == 3


def test_a_stop_that_never_confirms_signals_the_watcher_then_says_so(tmp_path: Path) -> None:
    watcher = fake_watcher(tmp_path)
    calls, runner = colab_cli(listed_after=99)
    ok = stop_session(JOB, tmp_path, Path("colab"), runner, sleep=no_wait, term_wait=90)
    assert not ok and watcher.wait(timeout=10) == -signal.SIGTERM
    assert sum(1 for c in calls if c[1] == "stop") == 3


@pytest.mark.parametrize(
    ("state", "script"), [("stopped", "cu_watch.py"), ("running", "other.py"), (None, None)]
)
def test_sigterm_only_reaches_a_live_cu_watch_process(
    tmp_path: Path, state: str | None, script: str | None
) -> None:
    proc = None
    if state is None:  # a null pid in the entry
        (tmp_path / f"{JOB}.json").write_text(json.dumps({"name": JOB, "pid": None}))
    else:
        proc = fake_watcher(tmp_path, state=state, script=script or "")
    _, runner = colab_cli(listed_after=99)
    assert not stop_session(JOB, tmp_path, Path("colab"), runner, sleep=no_wait)
    if proc is not None:
        assert proc.poll() is None  # not signalled: a reused pid, or no live watcher
        proc.kill()
        proc.wait()


def test_hung_commands_end_as_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(he1_fetch, "TIMEOUT_S", 0.2)
    assert run(["sleep", "5"]).returncode == 124
    limits: list[float] = []

    def spy(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        limits.append(kwargs["timeout"])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", spy)
    run(["rsync", "-a", "a", "b"])
    run(["ssh", "root@colab", "true"])
    assert limits == [he1_fetch.PULL_TIMEOUT_S, 0.2]


def test_the_real_transport_is_rsync_over_the_colab_proxy() -> None:
    remote = Remote(JOB, Path("/x/colab"))
    assert remote.ssh[:3] == ["ssh", "-o", f"ProxyCommand=/x/colab ssh --proxy-mode -s {JOB}"]
    assert remote.ssh[-1] == "root@colab" and "root@colab" not in remote.rsh
    stage = "cd /content/da26 && python3 fw/scripts/he/he1_colab.py stage --work /content/da26"
    assert remote.stage()[-1] == stage
    assert remote.source == "root@colab:/content/da26/runs"


def test_another_storys_job_names_its_own_vm_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[Remote] = []

    def stop_at_probe(remote: Remote, dest: Path) -> float:
        made.append(remote)
        return 2 * he1_fetch.SLOW_MB_S

    monkeypatch.setattr(he1_fetch, "probe", stop_at_probe)
    monkeypatch.setattr(he1_fetch, "session_state", lambda *a, **k: "running")
    common = ["probe", "--session", JOB, "--registry", "/nonexistent", "--colab", "/x/colab"]
    for dest, extra in (("a", []), ("b", ["--remote-work", "/content/da34"])):
        assert he1_fetch.main([*common, "--dest", str(tmp_path / dest), *extra]) == 0
    default, da34 = made
    assert (default.work, default.source) == ("/content/da26", "root@colab:/content/da26/runs")
    assert (da34.work, da34.source) == ("/content/da34", "root@colab:/content/da34/runs")
    assert da34.stage()[-1].endswith("he1_colab.py stage --work /content/da34")
    assert da34.stage()[-1].startswith("cd /content/da34 && ")


@pytest.mark.parametrize("work", ["content/da34", "/content/da 34", "/content/$(id)", "/x;y"])
def test_only_a_plain_absolute_remote_work_is_taken(
    work: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValueError, match="plain absolute path"):
        Remote(JOB, Path("/x/colab"), work=work)
    argv = ["probe", "--session", JOB, "--registry", "/r", "--dest", str(tmp_path)]
    with pytest.raises(SystemExit):
        he1_fetch.main([*argv, "--remote-work", work])
    assert "plain absolute path" in capsys.readouterr().err


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


def test_the_s104_estimate_at_cap_18_needs_only_a_slow_pull() -> None:
    # Step 2200 at S1-04's 8.5 h run: 0.753 s/step with validation, 8 min of setup.
    # At cap 18 (Hiếu 5/11) 6 MB/s is enough; a pull of 3 MB/s is not.
    spent = 1.94 * (8 * 60 + 2200 * 0.753) / 3600
    slow = projected_cu(spent, 2200, 0.753, 3.0, 6.25e9)
    enough = projected_cu(spent, 2200, 0.753, 6.0, 6.25e9)
    assert slow > stop_line(18.0) > enough
    assert judge(running(2200, 0.753), (spent, 18.0), 3.0)["verdict"] == "stop"  # type: ignore[index]
    assert judge(running(2200, 0.753), (spent, 18.0), 6.0)["verdict"] == "ok"  # type: ignore[index]
    assert judge(running(2100, 0.753), (spent, 18.0), 3.0) is None  # before the window
    late = judge(running(12000, 2.0), (spent, 18.0), 6.0)
    assert late is not None and late["verdict"] == "late"  # past ckpt_10000: ALERT only


def test_the_stop_line_follows_the_watchers_cap() -> None:
    # Hiếu 4/11: caps 18/18/16. The cap comes from the watcher's poll line, not a constant.
    assert stop_line(18.0) == pytest.approx(17.768, abs=1e-3)
    assert stop_line(16.0) == pytest.approx(15.768, abs=1e-3)
    spent = 1.94 * (8 * 60 + 2200 * 0.753) / 3600
    s104 = running(2200, 0.753)
    assert judge(s104, (spent, 17.5), 6.0)["verdict"] == "stop"  # type: ignore[index]
    assert judge(s104, (spent, 18.0), 6.0)["verdict"] == "ok"  # type: ignore[index]
    assert judge(s104, (spent, 18.0), 3.0)["verdict"] == "stop"  # type: ignore[index]


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


@pytest.mark.parametrize("code", [1, 0])
def test_a_train_that_died_before_its_job_dir_has_failed(tmp_path: Path, code: int) -> None:
    # No .env, a failed import or a refused hash: `train` exits before runs/<job>.
    vm = tmp_path / "vm"
    vm.mkdir()
    (vm / "train.log").write_text(f"Traceback ...\ntrain exit {code}\n")
    args = ["--session", JOB, "--registry", str(tmp_path), "--dest", str(tmp_path / "l")]
    assert main(["once", *args, "--local-vm", str(vm)]) == 5
    with deadline(60):
        assert main(["follow", *args, "--every", "0", "--local-vm", str(vm)]) == 5
    with pytest.raises(he1_fetch.TrainFailed):
        fetch_once(LocalRemote(vm), tmp_path / "l")


def test_before_train_exits_an_empty_stage_is_not_a_failure(tmp_path: Path) -> None:
    vm = tmp_path / "vm"
    vm.mkdir()  # setup done, train not yet started
    assert fetch_once(LocalRemote(vm), tmp_path / "l") == []


def test_a_run_that_ends_while_stage_hashes_is_running_then_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DA-26 b3, V-EGO: the phase and the `train exit 0` landed while `stage` hashed
    # ckpt_40000; a report read before and a log read after made the job "failed".
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000)
    phase = {"job_id": JOB, "infra_status": "ok", "checkpoint_step": 40000}
    hash_file = he1_colab.sha256

    def run_ends(path: Path) -> str:
        if not (vm / "train.log").exists():
            (vm / "report.json").write_text(json.dumps({"phases": {"train": phase}}))
            (vm / "train.log").write_text("train exit 0\n")
        return hash_file(path)

    monkeypatch.setattr(he1_colab, "sha256", run_ends)
    assert he1_colab.stage(vm)["jobs"][0]["train"] == "running"
    listing = he1_colab.stage(vm)
    assert listing["jobs"][0]["train"] == "done" and listing["train"] == "ended"


def test_a_link_out_of_the_job_dir_is_skipped_not_bad(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000, train_done=True)
    logs = vm / "runs" / JOB / "wandb/offline-run/logs"
    logs.mkdir(parents=True)
    cache = tmp_path / "root-cache" / "core-debug.log"  # W&B's link target
    cache.parent.mkdir()
    cache.write_text("core\n")
    (logs / "debug-core.log").symlink_to(cache)
    (logs / "debug.log").write_text("debug\n")
    (logs.parent.parent / "debug.log").symlink_to("offline-run/logs/debug.log")  # stays inside

    def laptop_lacks_the_cache(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        done = run(argv)
        if argv[0] == "rsync":  # the VM and the "laptop" share this disk here
            cache.unlink(missing_ok=True)
        return done

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l", runner=laptop_lacks_the_cache)
    assert status["skipped"] == ["wandb/offline-run/logs/debug-core.log"]
    assert status["bad_or_missing"] == [] and status["final"]
    assert (tmp_path / "l" / JOB / "wandb/debug.log").read_text() == "debug\n"


def test_a_log_that_differs_after_training_ended_is_bad(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(40000,), complete=40000, train_done=True)
    metrics = vm / "runs" / JOB / "metrics.jsonl"

    def late_write(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "rsync":
            metrics.write_text('{"step": 3}\n')
        return run(argv)

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l", runner=late_write)
    assert status["bad_or_missing"] == ["metrics.jsonl"] and status["grown"] == []
    assert not status["final"]


def test_a_checkpoint_that_changed_mid_pull_is_bad_not_grown(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    model = vm / "runs" / JOB / MODEL.format(10000)

    def rewrite(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "rsync":
            model.write_bytes(b"\1" * model.stat().st_size)
        return run(argv)

    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l", runner=rewrite)
    assert MODEL.format(10000) in status["bad_or_missing"]
    assert status["grown"] == [] and status["mb_per_s"] is None


def test_the_rate_counts_checkpoint_bytes_only(tmp_path: Path) -> None:
    vm = fake_vm(tmp_path / "vm", saved=(10000,), complete=10000)
    (vm / "runs" / JOB / "metrics.jsonl").write_text("x" * 1_000_000)  # a big log
    ticks = iter([0.0, 0.001])
    (status,) = fetch_once(LocalRemote(vm), tmp_path / "l", clock=lambda: next(ticks))
    assert status["checkpoint_pulled_bytes"] == 4001
    assert status["mb_per_s"] == round(4001 / 1e6 / 0.001, 2)


def test_passes_come_every_minute_near_the_end() -> None:
    going = [{"train": "running"}]
    assert pause(600, 37999, going) == 600
    assert pause(600, 38000, going) == 60
    assert pause(600, 5000, [{"train": "done"}]) == 60
    assert pause(30, 39000, going) == 30


def test_probe_times_a_pull_and_cleans_both_ends(tmp_path: Path) -> None:
    vm = tmp_path / "vm"
    mb_s = probe(LocalRemote(vm), tmp_path, megabytes=8)
    assert mb_s > 0
    assert not (vm / "probe.bin").exists() and not (tmp_path / ".probe.bin").exists()
