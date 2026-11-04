"""scripts/colab/cu_watch.py against a fake Colab backend and a fake clock.

The fake keeps the server's assignments (named or `[?]`), charges the balance for
each by its GPU's rate as fake time passes, and prints what the real CLI prints
(colab_cli 0.7.5: `[name] endpoint | Hardware: X | ...`, `Current balance: ...`).
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
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


class FakeColab:
    def __init__(
        self,
        balance: float = 101.8,
        other_rate: float = 0.0,
        hardware: str | None = None,
        new_mode: str = "ok",
        stop_mode: str = "ok",
    ) -> None:
        self.balance = balance
        self.other_rate = other_rate  # CU/h of assignments outside the batch
        self.others = ["gpu-l4-other"] if other_rate else []
        self.hardware = hardware  # what the server assigns, whatever was asked
        self.new_mode, self.stop_mode = new_mode, stop_mode
        self.real = 0.0  # seconds of real time
        self.frozen: float | None = None  # clock value while the clock is stuck
        self.assigned: dict[str, list[str]] = {}  # endpoint -> [name, hardware]
        self.calls: list[list[str]] = []
        self.glitches = 0  # next `sessions` calls that print an empty list
        self.usage_down = 0  # next `usage` calls that fail
        self.on_sleep: Callable[[int], None] | None = None
        self.sleeps = 0

    def clock(self) -> float:
        return self.frozen if self.frozen is not None else EPOCH + self.real

    def advance(self, seconds: float) -> None:
        rate = sum(cw.RATES[hw] for _, hw in self.assigned.values()) + self.other_rate
        self.balance -= rate * seconds / 3600
        self.real += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.sleeps > 2000:  # a watch that never stops fails here, not by hanging CI
            raise AssertionError("runaway watch")
        self.advance(seconds)
        if self.on_sleep:
            self.on_sleep(self.sleeps)

    def named(self, name: str) -> str | None:
        return next((e for e, (n, _) in self.assigned.items() if n == name), None)

    def __call__(self, argv: Sequence[str], timeout: float) -> tuple[int, str]:
        self.calls.append(list(argv))
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
            rate = sum(cw.RATES[hw] for _, hw in self.assigned.values()) + self.other_rate
            return 0, (
                f"Current balance: {self.balance:.2f} compute units\n"
                f"Usage rate: {rate:.2f}/hr\nActive assignments: {n}"
            )
        if command == "sessions":
            lines = [
                f"[{name}] {endpoint} | Hardware: {hw} | Shape: Standard | Variant: GPU"
                for endpoint, (name, hw) in self.assigned.items()
            ] + [f"[?] {e} | Hardware: L4 | Shape: Standard | Variant: GPU" for e in self.others]
            if self.glitches:
                self.glitches -= 1
                lines = []
            return 0, "\n".join(lines) or "[colab] No active sessions found on server."
        if command == "new":
            name, gpu = args[1], args[3]
            if self.new_mode == "refused":
                return 1, "[colab] Allocation refused (precondition failed)."
            endpoint = f"gpu-{gpu.lower()}-s-{len(self.calls)}"
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
            return 0, "[colab] Session terminated."  # also when it did nothing
        raise AssertionError(argv)

    def alive(self) -> list[str]:
        return [name for name, _ in self.assigned.values()]


def watcher(
    colab: FakeColab, tmp_path: Path, specs: list[str], floor: float | None = None, **kw: Any
) -> Any:
    parsed = [cw.parse_spec(s, attach=False) for s in specs]
    return cw.Watcher(
        parsed,
        floor,
        tmp_path / "watch.jsonl",
        colab,
        colab=COLAB,
        clock=colab.clock,
        sleep=colab.sleep,
        **kw,
    )


def events(tmp_path: Path, name: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (tmp_path / "watch.jsonl").read_text().splitlines()]
    return [r for r in rows if name is None or r["event"] == name]


def stop_calls(colab: FakeColab, name: str) -> int:
    return sum(c[1:] == ["stop", "-s", name] for c in colab.calls if len(c) > 1)


@pytest.fixture
def handlers() -> Iterator[None]:
    saved = {s: signal.getsignal(s) for s in cw._SignalsIgnored.SIGNALS}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


# -- meter, cap, margin ---------------------------------------------------------------


def test_the_margin_counts_poll_cli_timeouts_and_stop_retries() -> None:
    timing = cw.Timing(poll=60, cli_timeout=60, stop_backoff=(5, 15, 30))
    assert timing.stop_budget == 3 * (3 * 60) + 50
    assert timing.margin == 60 + 2 * 60 + timing.stop_budget


def test_a_session_is_stopped_one_margin_before_its_cap(tmp_path: Path) -> None:
    colab = FakeColab()
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    cap = events(tmp_path, "cap")[0]
    margin_cu = cw.RATES["L4"] * cw.Timing().margin / 3600
    # by_balance reads the CLI's 2-decimal balance: up to 0.005 over the exact spend
    assert 4 - margin_cu - 0.05 <= cap["spent"] < 4 - margin_cu + 0.01
    assert 101.8 - colab.balance < 4  # the real spend stayed under the cap


def test_a_frozen_clock_is_caught_by_the_balance_drop(tmp_path: Path) -> None:
    colab = FakeColab()
    colab.frozen = EPOCH  # time.monotonic over a suspend: the clock does not move
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_CAPPED
    cap = events(tmp_path, "cap")[0]
    poll = [r for r in events(tmp_path, "poll") if "da30" in r][-1]["da30"]
    assert poll["by_time"] == 0 and poll["by_balance"] > 3.5
    assert cap["spent"] < 4


def test_a_clock_jump_after_suspend_stops_at_the_next_poll(tmp_path: Path) -> None:
    colab = FakeColab()

    def suspend(n: int) -> None:
        if n == 5:
            colab.advance(3 * 3600)  # the laptop slept 3 h; the session kept running

    colab.on_sleep = suspend
    code = watcher(colab, tmp_path, ["da30:L4:5"]).watch()
    assert code == cw.EXIT_CAPPED
    jumped = 5 * 60 / 3600 * 1.94 + 3 * 1.94  # 5.98 CU, over the cap only after the jump
    assert events(tmp_path, "cap")[0]["spent"] == pytest.approx(jumped, abs=0.05)
    assert len(events(tmp_path, "poll")) == 5  # the first poll after the jump stopped it


def test_with_a_shared_balance_each_session_meters_its_own_time(tmp_path: Path) -> None:
    colab = FakeColab()
    code = watcher(colab, tmp_path, ["a:L4:1", "b:A100:6"]).watch()
    assert code == cw.EXIT_CAPPED
    first, second = (r["session"] for r in events(tmp_path, "cap"))
    assert (first, second) == ("a", "b")
    polls = [r for r in events(tmp_path, "poll") if "a" in r]
    assert all(r["a"]["by_balance"] is None for r in polls)  # the drop is both sessions'
    a_stop = polls[-1]["a"]
    assert a_stop["spent"] == pytest.approx(a_stop["by_time"]) and a_stop["spent"] < 1
    # The account paid both: more than a's cap went in a's lifetime.
    assert 101.8 - polls[-1]["balance"] > 1


def test_another_job_on_the_account_turns_the_balance_meter_off(tmp_path: Path) -> None:
    colab = FakeColab(other_rate=6.73)
    watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    polls = [r for r in events(tmp_path, "poll") if "da30" in r]
    assert all(r["da30"]["by_balance"] is None for r in polls)
    assert polls[-1]["da30"]["spent"] < 2


def test_the_floor_stops_every_session_on_the_real_balance(tmp_path: Path) -> None:
    colab = FakeColab(balance=20.0, other_rate=10.0)
    code = watcher(colab, tmp_path, ["a:L4:10", "b:L4:10"], floor=14.0).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    floor = events(tmp_path, "floor")[0]
    assert floor["balance"] > 14
    assert {r["session"] for r in events(tmp_path, "stopped")} == {"a", "b"}
    assert all(r["reason"] == "floor" for r in events(tmp_path, "stopped"))


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


# -- GPU type -------------------------------------------------------------------------


def test_an_unknown_gpu_is_refused_before_any_new(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown GPU 'T4'"):
        cw.parse_spec("da30:T4:4", attach=False)
    colab_cli = tmp_path / "colab"
    colab_cli.write_text("")
    argv = ["--new", "da30:T4:4", "--log", str(tmp_path / "w.jsonl"), "--colab", str(colab_cli)]
    assert cw.main([*argv, "--no-inhibit"]) == cw.EXIT_USAGE
    assert not (tmp_path / "w.jsonl").exists()


def test_a_wrong_gpu_is_stopped_at_once_and_ends_the_watch(tmp_path: Path) -> None:
    colab = FakeColab(hardware="A100")  # asked L4, got A100
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_WRONG_GPU and colab.alive() == []
    assert events(tmp_path, "stopped")[0]["reason"] == "wrong_gpu"
    assert events(tmp_path, "poll") == []


# -- fail closed ----------------------------------------------------------------------


def test_a_new_that_timed_out_with_the_vm_assigned_is_attached(tmp_path: Path) -> None:
    colab = FakeColab(new_mode="timeout_named")
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert events(tmp_path, "new_failed_but_listed")
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert 101.8 - colab.balance < 4  # the timeout's time counted against the cap


def test_an_orphan_from_a_timed_out_new_is_unassigned(tmp_path: Path) -> None:
    colab = FakeColab(new_mode="timeout_orphan")
    colab.others = ["gpu-l4-older"]  # an unnamed assignment from before is left alone
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_NEW_FAILED and colab.alive() == []
    assert [r["endpoint"] for r in events(tmp_path, "unassign")] == ["gpu-l4-s-3"]


def test_an_exception_stops_every_session(tmp_path: Path) -> None:
    colab = FakeColab()

    def crash(n: int) -> None:
        if n == 3:
            raise RuntimeError("disk full")

    colab.on_sleep = crash
    code = watcher(colab, tmp_path, ["a:L4:4", "b:L4:4"]).watch()
    assert code == cw.EXIT_ERROR and colab.alive() == []
    assert {r["reason"] for r in events(tmp_path, "stopped")} == {"cleanup"}


def test_sigterm_stops_every_session(tmp_path: Path, handlers: None) -> None:
    colab = FakeColab()
    cw.install_signal_handlers()
    colab.on_sleep = lambda n: os.kill(os.getpid(), signal.SIGTERM) if n == 2 else None
    code = watcher(colab, tmp_path, ["a:L4:4", "b:L4:4"]).watch()
    assert code == 128 + signal.SIGTERM and colab.alive() == []
    assert events(tmp_path, "signal")[0]["signum"] == signal.SIGTERM


def test_a_stop_that_does_not_take_is_retried_through_unassign(tmp_path: Path) -> None:
    colab = FakeColab(stop_mode="noop")  # `colab stop` answers "terminated" and does nothing
    code = watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    assert code == cw.EXIT_CAPPED and colab.alive() == []
    assert events(tmp_path, "stopped")[0]["attempt"] == 2


def test_a_failed_stop_ends_loud_with_its_own_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    colab = FakeColab(stop_mode="stuck")
    code = watcher(colab, tmp_path, ["da30:L4:2"]).watch()
    assert code == cw.EXIT_STILL_RUNNING and colab.alive() == ["da30"]
    assert stop_calls(colab, "da30") == len(cw.Timing().stop_backoff)
    assert "ALERT da30 still listed" in capsys.readouterr().err
    assert events(tmp_path, "exit")[0]["sessions"]["da30"]["unconfirmed"] is True


def test_three_missed_polls_end_a_session_and_fewer_do_not(tmp_path: Path) -> None:
    colab = FakeColab()

    def glitch_then_end(n: int) -> None:
        if n == 3:
            colab.glitches, colab.usage_down = 2, 2  # empty lists we cannot cross-check
        if n == 10:
            colab.assigned.clear()  # stopped by hand

    colab.on_sleep = glitch_then_end
    code = watcher(colab, tmp_path, ["da30:L4:4"]).watch()
    assert code == cw.EXIT_OK
    ended = events(tmp_path, "ended")
    assert len(ended) == 1 and len(events(tmp_path, "poll")) == 12
    assert stop_calls(colab, "da30") == 0


def test_an_empty_list_while_assignments_are_counted_is_not_a_miss(tmp_path: Path) -> None:
    colab = FakeColab()
    colab.on_sleep = lambda n: setattr(colab, "glitches", 5) if n == 2 else None
    watcher(colab, tmp_path, ["da30:L4:1"]).watch()
    misses = [r["da30"]["misses"] for r in events(tmp_path, "poll") if "da30" in r]
    assert max(misses) == 0


def test_names_match_whole_not_as_a_prefix() -> None:
    text = "[da30-stage1] gpu-l4-s-1 | Hardware: L4 | Shape: Standard | Variant: GPU"
    assert [s.name for s in cw.parse_sessions(text)] == ["da30-stage1"]
    colab = FakeColab()
    colab.assigned["gpu-l4-s-9"] = ["da30-stage1", "L4"]
    w = watcher(colab, Path("/tmp"), ["da30:L4:4"])
    listed = w.listing()
    assert listed is not None and not any(s.name == "da30" for s in listed)


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
    assert w.watch() == cw.EXIT_ERROR
    assert not any(c[1] == "new" for c in colab.calls if len(c) > 1)


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
    assert seen[0][:2] == ["/usr/bin/systemd-inhibit", "--what=sleep"]
    assert seen[0][-len(argv) :] == argv
    monkeypatch.setattr(cw.shutil, "which", lambda name: None)
    monkeypatch.delenv("CU_WATCH_INHIBITED", raising=False)
    assert cw.main(argv) == cw.EXIT_USAGE  # no inhibit, no watch
