"""scripts/colab/cu_watch.py against a fake Colab backend and a fake clock.

The fake keeps the server's assignments (named or `[?]`), bills the balance for each
at its real rate as fake time passes, and prints what the real CLI prints
(colab_cli 0.7.5: `[name] endpoint | Hardware: X | ...`, `Current balance: ...`).
Like the real CLI, `stop` answers 0 whether or not it did anything.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import stat
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "colab" / "cu_watch.py"
_spec = importlib.util.spec_from_file_location("cu_watch", SCRIPT)
assert _spec is not None and _spec.loader is not None
cw = importlib.util.module_from_spec(_spec)
sys.modules["cu_watch"] = cw
_spec.loader.exec_module(cw)

COLAB = Path("/fake/venv/bin/colab")
EPOCH = 1_800_000_000.0
L4 = cw.RATES["L4"]


class FakeColab:
    def __init__(
        self,
        balance: float = 101.8,
        other_rate: float = 0.0,
        hardware: str | None = None,
        bill_rate: float | None = None,
        new_mode: str = "ok",
        stop_mode: str = "ok",
    ) -> None:
        self.balance = balance
        self.other_rate = other_rate  # CU/h of assignments outside the batch
        self.others = ["gpu-l4-other"] if other_rate else []
        self.hardware = hardware  # what the server assigns, whatever was asked
        self.bill_rate = bill_rate  # what a session really bills, if not its RATES
        self.new_mode, self.stop_mode = new_mode, stop_mode
        self.real = 0.0  # seconds of real time
        self.frozen: float | None = None  # clock value while the clock is stuck
        self.assigned: dict[str, list[str]] = {}  # endpoint -> [name, hardware]
        self.calls: list[list[str]] = []
        self.glitches = 0  # next `sessions` calls that print an empty list
        self.usage_down = 0  # next `usage` calls that fail
        self.flicker = 0  # next `sessions` calls after a stop that hide the session
        self.on_sleep: Callable[[int], None] | None = None
        self.on_call: Callable[[list[str]], None] | None = None
        self.sleeps = 0
        self.serial = 0
        self.billed = 0.0  # what the batch's sessions really cost

    def clock(self) -> float:
        return self.frozen if self.frozen is not None else EPOCH + self.real

    def rate(self, hardware: str) -> float:
        return self.bill_rate or cw.RATES[hardware]

    def advance(self, seconds: float) -> None:
        own = sum(self.rate(hw) for _, hw in self.assigned.values())
        self.billed += own * seconds / 3600
        self.balance -= (own + self.other_rate) * seconds / 3600
        self.real += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.sleeps > 5000:  # a watch that never stops fails here, not by hanging CI
            raise AssertionError("runaway watch")
        self.advance(seconds)
        if self.on_sleep:
            self.on_sleep(self.sleeps)

    def named(self, name: str) -> str | None:
        return next((e for e, (n, _) in self.assigned.items() if n == name), None)

    def __call__(self, argv: Sequence[str], timeout: float) -> tuple[int, str]:
        self.calls.append(list(argv))
        if self.on_call:
            self.on_call(list(argv))
        if argv[0].endswith("python"):  # UNASSIGN through the CLI's client
            if self.stop_mode != "stuck":
                self.assigned.pop(argv[3], None)
            return 0, ""
        command, args = argv[1], list(argv[2:])
        if command == "usage":
            if self.usage_down:
                self.usage_down -= 1
                return 1, "[colab] error"
            n = len(self.assigned) + len(self.others)
            rate = sum(self.rate(hw) for _, hw in self.assigned.values()) + self.other_rate
            return 0, (
                f"Current balance: {self.balance:.2f} compute units\n"
                f"Usage rate: {rate:.2f}/hr\nActive assignments: {n}"
            )
        if command == "sessions":
            lines = [
                f"[{name}] {endpoint} | Hardware: {hw} | Shape: Standard | Variant: GPU"
                for endpoint, (name, hw) in self.assigned.items()
            ] + [f"[?] {e} | Hardware: L4 | Shape: Standard | Variant: GPU" for e in self.others]
            if self.glitches or self.flicker:
                self.glitches, self.flicker = max(0, self.glitches - 1), max(0, self.flicker - 1)
                lines = [line for line in lines if line.startswith("[?]")]
            return 0, "\n".join(lines) or "[colab] No active sessions found on server."
        if command == "new":
            name, gpu = args[1], args[3]
            if self.new_mode == "refused":
                return 1, "[colab] Allocation refused (precondition failed)."
            self.serial += 1
            endpoint = f"gpu-{gpu.lower()}-s-{self.serial}"
            label = "?" if self.new_mode == "timeout_orphan" else name
            self.assigned[endpoint] = [label, self.hardware or gpu]
            if self.new_mode.startswith("timeout"):
                self.advance(timeout)
                return cw.TIMEOUT, "timed out"
            return 0, "[colab] Session READY."
        if command == "stop":
            endpoint = self.named(args[1])
            if endpoint is None:
                return 0, f"[colab] Session '{args[1]}' not found."
            if self.stop_mode == "ok":
                del self.assigned[endpoint]
            elif self.stop_mode == "flicker_once":
                self.flicker, self.stop_mode = 1, "ok"  # one listing hides it, still billing
            return 0, "[colab] Session terminated."  # also when it did nothing
        raise AssertionError(argv)

    def alive(self) -> list[str]:
        return [name for name, _ in self.assigned.values()]


def watcher(
    colab: FakeColab, tmp_path: Path, specs: list[str], floor: float | None = None, **kw: Any
) -> Any:
    parsed = [cw.parse_spec(s, attach=False) for s in specs]
    kw.setdefault("log_path", tmp_path / "watch.jsonl")
    return cw.Watcher(
        parsed, floor, run=colab, colab=COLAB, clock=colab.clock, sleep=colab.sleep, **kw
    )


def events(tmp_path: Path, name: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (tmp_path / "watch.jsonl").read_text().splitlines()]
    return [r for r in rows if name is None or r["event"] == name]


def polls(tmp_path: Path, session: str) -> list[dict[str, Any]]:
    return [r[session] for r in events(tmp_path, "poll") if session in r]


def stop_calls(colab: FakeColab, name: str) -> int:
    return sum(c[1:] == ["stop", "-s", name] for c in colab.calls if len(c) > 1)


@pytest.fixture
def handlers() -> Iterator[None]:
    saved = {s: signal.getsignal(s) for s in cw._SignalsIgnored.SIGNALS}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


# -- meter, cap, margin ---------------------------------------------------------------


def test_the_margin_counts_poll_cli_timeouts_and_a_retried_stop() -> None:
    t = cw.Timing(poll=60, cli_timeout=60, stop_backoff=(5, 15, 30), confirm_wait=10)
    # first attempt: stop + 2 listings + 1 wait; retry: stop + unassign + 2 listings + 1 wait
    assert t.stop_delay == (3 * 60 + 10) + 5 + (4 * 60 + 10)
    assert t.margin == 60 + 2 * 60 + t.stop_delay


def test_a_session_is_stopped_inside_its_cap(tmp_path: Path) -> None:
    colab = FakeColab()
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    threshold = 4 - L4 * cw.Timing().margin / 3600
    poll_cu = L4 * cw.Timing().poll / 3600  # spend moves by one poll between checks
    # balance_cu reads the CLI's 2-decimal balance: up to 0.01 over the exact spend
    assert threshold <= events(tmp_path, "cap")[0]["spent"] < threshold + poll_cu + 0.01
    assert colab.billed < 4


def test_a_frozen_clock_is_caught_by_the_balance_drop(tmp_path: Path) -> None:
    colab = FakeColab()
    colab.frozen = EPOCH  # time.monotonic over a suspend: the clock does not move
    assert watcher(colab, tmp_path, ["da30:L4:4"]).watch() == cw.EXIT_CAPPED
    last = polls(tmp_path, "da30")[-1]
    assert last["wall_cu"] == 0 and last["balance_cu"] > 3.5
    assert colab.billed < 4


def test_with_usage_down_the_wall_clock_still_caps(tmp_path: Path) -> None:
    colab = FakeColab()
    colab.usage_down = 10**6  # `colab usage` fails all run: no balance reading at all
    assert watcher(colab, tmp_path, ["da30:L4:2"]).watch() == cw.EXIT_CAPPED
    assert polls(tmp_path, "da30")[-1]["balance_cu"] == 0 and colab.billed < 2


def test_a_clock_jump_after_suspend_stops_at_the_next_poll(tmp_path: Path) -> None:
    colab = FakeColab()

    def suspend(n: int) -> None:
        if n == 5:
            colab.advance(3 * 3600)  # the laptop slept 3 h; the session kept running

    colab.on_sleep = suspend
    assert watcher(colab, tmp_path, ["da30:L4:5"]).watch() == cw.EXIT_CAPPED
    jumped = 5 * 60 / 3600 * L4 + 3 * L4  # 5.98 CU, over the cap only after the jump
    assert events(tmp_path, "cap")[0]["spent"] == pytest.approx(jumped, abs=0.05)
    assert len(events(tmp_path, "poll")) == 5


def test_a_session_billed_above_its_rate_is_caught_by_the_balance(tmp_path: Path) -> None:
    colab = FakeColab(bill_rate=3.0)  # bills 3 CU/h while RATES says 1.94
    assert watcher(colab, tmp_path, ["da30:L4:3"]).watch() == cw.EXIT_CAPPED
    last = polls(tmp_path, "da30")[-1]
    assert last["balance_cu"] > last["wall_cu"] and colab.billed <= 3.0


def test_two_sessions_share_the_balance_by_rate(tmp_path: Path) -> None:
    colab = FakeColab()
    assert watcher(colab, tmp_path, ["a:L4:3", "b:L4:3"]).watch() == cw.EXIT_CAPPED
    margin_cu = L4 * cw.Timing().margin / 3600
    for row in events(tmp_path, "cap"):  # each stops near its own cap, not at half
        assert row["spent"] > 3 - margin_cu - 0.1
    last = polls(tmp_path, "a")[-1]
    assert last["balance_cu"] == pytest.approx(last["wall_cu"], abs=0.05)


def test_another_job_on_the_account_is_not_charged_here(tmp_path: Path) -> None:
    colab = FakeColab(other_rate=6.73)
    assert watcher(colab, tmp_path, ["da30:L4:3"]).watch() == cw.EXIT_CAPPED
    margin_cu = L4 * cw.Timing().margin / 3600
    assert colab.billed > 3 - margin_cu - 0.1  # not stopped at a fifth of its cap


def test_the_floor_stops_every_session_on_the_real_balance(tmp_path: Path) -> None:
    colab = FakeColab(balance=20.0, other_rate=10.0)
    code = watcher(colab, tmp_path, ["a:L4:10", "b:L4:10"], floor=14.0).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert events(tmp_path, "floor")[0]["balance"] > 14
    assert [r["reason"] for r in events(tmp_path, "stopped")] == ["floor", "floor"]


def test_persist_runs_at_the_soft_cap_before_the_hard_stop(tmp_path: Path) -> None:
    colab = FakeColab()
    spawned: list[str] = []

    class Done:
        def poll(self) -> int:
            return 0

        def kill(self) -> None:
            raise AssertionError("finished")

    def spawn(command: str) -> Done:
        spawned.append(command)
        return Done()

    spec = cw.Spec("da30", "L4", 4.0, persist="colab exec -s da30 -f persist.py")
    w = cw.Watcher(
        [spec],
        None,
        tmp_path / "watch.jsonl",
        colab,
        colab=COLAB,
        clock=colab.clock,
        sleep=colab.sleep,
        spawn=spawn,
    )
    assert w.watch() == cw.EXIT_CAPPED
    assert spawned == ["colab exec -s da30 -f persist.py"]
    order = [r["event"] for r in events(tmp_path) if r["event"] in ("persist", "persisted", "cap")]
    assert order == ["persist", "persisted", "cap"]


# -- GPU type, ready file ---------------------------------------------------------------


def test_an_unknown_gpu_is_refused_before_any_new(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown GPU 'T4'"):
        cw.parse_spec("da30:T4:4", attach=False)
    colab_cli = tmp_path / "colab"
    colab_cli.write_text("")
    argv = ["--new", "da30:T4:4", "--log", str(tmp_path / "w.jsonl"), "--colab", str(colab_cli)]
    assert cw.main([*argv, "--no-inhibit"]) == cw.EXIT_NOTHING
    assert not (tmp_path / "w.jsonl").exists()


def test_a_wrong_gpu_is_stopped_at_once_without_a_ready_file(tmp_path: Path) -> None:
    colab = FakeColab(hardware="A100")  # asked L4, got A100
    ready = tmp_path / "ready"
    code = watcher(colab, tmp_path, ["da30:L4:4"], ready_dir=ready).watch()
    assert code == cw.EXIT_WRONG_GPU and colab.alive() == []
    assert events(tmp_path, "stopped")[0]["reason"] == "wrong_gpu"
    assert events(tmp_path, "poll") == [] and not ready.exists()


def test_the_ready_file_appears_once_the_gpu_is_right(tmp_path: Path) -> None:
    colab = FakeColab()
    seen: list[bool] = []
    ready = tmp_path / "ready" / "da30.ready"
    colab.on_call = lambda argv: seen.append(ready.exists()) if argv[1:2] == ["new"] else None
    watcher(colab, tmp_path, ["da30:L4:1"], ready_dir=tmp_path / "ready").watch()
    assert seen == [False] and ready.read_text() == "da30 L4\n"


# -- fail closed ----------------------------------------------------------------------


def test_a_new_that_timed_out_with_the_vm_assigned_is_attached(tmp_path: Path) -> None:
    colab = FakeColab(new_mode="timeout_named")
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert events(tmp_path, "new_failed_but_listed")
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert colab.billed < 4  # the timeout's time counted against the cap


def test_an_orphan_from_a_timed_out_new_is_unassigned(tmp_path: Path) -> None:
    colab = FakeColab(new_mode="timeout_orphan")
    colab.others = ["gpu-l4-older"]  # an unnamed assignment from before is left alone
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_CRASHED and colab.alive() == []
    assert [r["endpoint"] for r in events(tmp_path, "unassign")] == ["gpu-l4-s-1"]


def test_an_exception_in_the_runner_mid_loop_stops_every_session(tmp_path: Path) -> None:
    colab = FakeColab()

    def crash(argv: list[str]) -> None:
        if colab.sleeps == 3 and argv[1:] == ["usage"]:
            colab.sleeps += 1  # once
            raise RuntimeError("CLI wrapper broke")

    colab.on_call = crash
    code = watcher(colab, tmp_path, ["a:L4:4", "b:L4:4"]).watch()
    assert code == cw.EXIT_CRASHED and colab.alive() == []
    assert {r["reason"] for r in events(tmp_path, "stopped")} == {"cleanup"}


def test_a_base_exception_mid_loop_still_ends_in_exit_6(tmp_path: Path) -> None:
    colab = FakeColab()

    def leave(n: int) -> None:
        if n == 2:
            raise SystemExit(9)  # a library calling sys.exit

    colab.on_sleep = leave
    assert watcher(colab, tmp_path, ["da30:L4:4"]).watch() == cw.EXIT_CRASHED
    assert colab.alive() == []


def test_a_crash_whose_cleanup_stop_fails_is_stop_failed(tmp_path: Path) -> None:
    colab = FakeColab(stop_mode="stuck")
    colab.on_sleep = lambda n: (_ for _ in ()).throw(RuntimeError("boom")) if n == 2 else None
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_STOP_FAILED and colab.alive() == ["da30"]


def test_sigterm_stops_every_session(tmp_path: Path, handlers: None) -> None:
    colab = FakeColab()
    cw.install_signal_handlers()
    assert signal.getsignal(signal.SIGTERM) is cw._raise_interrupted  # or the kill ends pytest
    colab.on_sleep = lambda n: os.kill(os.getpid(), signal.SIGTERM) if n == 2 else None
    code = watcher(colab, tmp_path, ["a:L4:4", "b:L4:4"]).watch()
    assert code == cw.EXIT_CRASHED and colab.alive() == []
    assert events(tmp_path, "signal")[0]["signum"] == signal.SIGTERM


def test_a_stop_that_does_not_take_is_retried_through_unassign(tmp_path: Path) -> None:
    colab = FakeColab(stop_mode="noop")  # `colab stop` answers "terminated" and does nothing
    code = watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert events(tmp_path, "stopped")[0]["attempt"] == 2


def test_one_listing_without_the_session_does_not_confirm_a_stop(tmp_path: Path) -> None:
    colab = FakeColab(stop_mode="flicker_once")  # hidden once after stop, still billing
    code = watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert events(tmp_path, "stopped")[0]["attempt"] == 2


def test_a_stop_that_never_works_is_stop_failed_and_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    colab = FakeColab(stop_mode="stuck")
    code = watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    assert code == cw.EXIT_STOP_FAILED and colab.alive() == ["da30"]
    assert stop_calls(colab, "da30") == len(cw.Timing().stop_backoff)
    assert "STOP_FAILED: da30 may still be billing" in capsys.readouterr().err
    assert events(tmp_path, "exit")[0]["sessions"]["da30"]["unconfirmed"] is True


def test_three_missed_polls_end_a_session_and_fewer_do_not(tmp_path: Path) -> None:
    colab = FakeColab()

    def glitch_then_end(n: int) -> None:
        if n == 3:
            colab.glitches, colab.usage_down = 2, 2  # empty lists we cannot cross-check
        if n == 10:
            colab.assigned.clear()  # stopped by hand

    colab.on_sleep = glitch_then_end
    assert watcher(colab, tmp_path, ["da30:L4:4"]).watch() == cw.EXIT_OK
    assert len(events(tmp_path, "ended")) == 1 and len(events(tmp_path, "poll")) == 12
    assert stop_calls(colab, "da30") == 0


def test_an_empty_list_while_assignments_are_counted_is_not_a_miss(tmp_path: Path) -> None:
    colab = FakeColab()
    colab.on_sleep = lambda n: setattr(colab, "glitches", 5) if n == 2 else None
    watcher(colab, tmp_path, ["da30:L4:1"]).watch()
    assert max(p["misses"] for p in polls(tmp_path, "da30")) == 0


def test_names_match_whole_not_as_a_prefix(tmp_path: Path) -> None:
    text = "[da30-stage1] gpu-l4-s-1 | Hardware: L4 | Shape: Standard | Variant: GPU"
    assert [s.name for s in cw.parse_sessions(text)] == ["da30-stage1"]
    colab = FakeColab()
    colab.assigned["gpu-l4-s-9"] = ["da30-stage1", "L4"]
    listed = watcher(colab, tmp_path, ["da30:L4:4"]).listing()
    assert listed is not None and not any(s.name == "da30" for s in listed)


def test_a_log_that_cannot_be_written_does_not_stop_the_guard(tmp_path: Path) -> None:
    (tmp_path / "blocked").write_text("a file, not a directory")
    colab = FakeColab()
    w = watcher(colab, tmp_path, ["da30:L4:2"], log_path=tmp_path / "blocked" / "w.jsonl")
    assert w.watch() == cw.EXIT_CAPPED and colab.alive() == []


def test_undecodable_cli_output_is_read_not_crashed(tmp_path: Path) -> None:
    cli = tmp_path / "colab"
    cli.write_text("#!/bin/sh\nprintf 'Current balance: 9.5 compute units \\377\\n'\n")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    code, out = cw.subprocess_runner([str(cli), "usage"], 10)
    assert code == 0 and "�" in out
    assert cw.subprocess_runner(["/nonexistent/colab"], 10)[0] == 1


def test_attach_needs_the_session_listed(tmp_path: Path) -> None:
    colab = FakeColab()
    spec = cw.parse_spec("da26:L4:3:2026-11-04T21:00+07:00", attach=True)
    w = cw.Watcher(
        [spec],
        None,
        tmp_path / "watch.jsonl",
        colab,
        colab=COLAB,
        clock=colab.clock,
        sleep=colab.sleep,
    )
    assert w.watch() == cw.EXIT_NOTHING
    assert not any(c[1] == "new" for c in colab.calls if len(c) > 1)


# -- inbox ------------------------------------------------------------------------------


def test_a_session_added_through_the_inbox_is_watched_with_the_others(tmp_path: Path) -> None:
    colab = FakeColab()
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    def drop(n: int) -> None:
        if n == 5:
            (inbox / "eval.txt").write_text("# DA-26 eval server\nnew eval:L4:1\n")
        if n == 6:
            (inbox / "bad.txt").write_text("new t4:T4:1\n")

    colab.on_sleep = drop
    code = watcher(colab, tmp_path, ["ft:L4:2"], inbox=inbox).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert {r["session"] for r in events(tmp_path, "cap")} == {"ft", "eval"}
    assert sorted(p.name for p in inbox.iterdir()) == ["bad.txt.rejected", "eval.txt.taken"]


# -- main -----------------------------------------------------------------------------


def test_main_runs_itself_under_systemd_inhibit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    colab_cli = tmp_path / "colab"
    colab_cli.write_text("")
    seen: list[list[str]] = []
    monkeypatch.delenv("CU_WATCH_INHIBITED", raising=False)
    monkeypatch.setattr(cw.shutil, "which", lambda name: "/usr/bin/systemd-inhibit")

    def execv(path: str, argv: list[str]) -> None:
        seen.append(argv)
        raise SystemExit(0)

    monkeypatch.setattr(cw.os, "execv", execv)
    argv = ["--new", "da30:L4:4", "--log", str(tmp_path / "w.jsonl"), "--colab", str(colab_cli)]
    with pytest.raises(SystemExit):
        cw.main(argv)
    assert seen[0][0] == "/usr/bin/systemd-inhibit" and seen[0][1].startswith("--what=sleep")
    assert seen[0][-len(argv) :] == argv
    monkeypatch.setattr(cw.shutil, "which", lambda name: None)
    monkeypatch.delenv("CU_WATCH_INHIBITED", raising=False)
    assert cw.main(argv) == cw.EXIT_NOTHING  # no inhibit, no watch
