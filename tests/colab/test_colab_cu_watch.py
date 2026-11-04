"""scripts/colab/cu_watch.py against a fake Colab backend and a fake clock.

The fake keeps the server's assignments by endpoint and the CLI's local names apart,
as colab_cli 0.7.5 does: a session whose local name is missing lists as `[?]`.
`colab new` runs in the background; the server assigns before the CLI saves the name.
Assignments bill the balance at their real rate as fake time passes.
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
L4, A100 = cw.RATES["L4"], cw.RATES["A100"]
MARGIN_H = cw.Timing().margin / 3600


class NewProc:
    """`colab new`: the server assigns at +assign_s, the CLI saves the name at +save_s
    and exits with `code` at +exit_s (None: never)."""

    MODES = {  # assign_s, save_s, exit_s, code
        "ok": (20.0, 40.0, 40.0, 0),
        "slow": (20.0, None, None, 0),  # assigned, then hangs
        "orphan": (20.0, None, 120.0, 1),  # assigned, the CLI dies before saving
        "refused": (None, None, 5.0, 1),
        "late": (40.0, None, None, 0),  # the server assigns even after a kill
        "slow_name": (20.0, 200.0, 200.0, 0),  # `[?]` for three minutes, then named
    }

    def __init__(self, fake: FakeColab, name: str, gpu: str, mode: str) -> None:
        self.fake, self.name, self.gpu, self.mode = fake, name, gpu, mode
        self.t0 = fake.real
        self.assign_s, self.save_s, self.exit_s, self.exit_code = self.MODES[mode]
        self.endpoint: str | None = None
        self.killed = False
        self.code: int | None = None

    def tick(self) -> None:
        age = self.fake.real - self.t0
        may_assign = not self.killed or self.mode == "late"
        if self.endpoint is None and self.assign_s is not None and age >= self.assign_s:
            if may_assign:
                self.endpoint = self.fake.assign(self.fake.hardware or self.gpu)
        if self.killed:
            return
        if self.save_s is not None and age >= self.save_s and self.endpoint:
            self.fake.local[self.name] = self.endpoint
        if self.exit_s is not None and age >= self.exit_s and self.code is None:
            self.code = self.exit_code

    def poll(self) -> int | None:
        self.tick()
        return -9 if self.killed and self.code is None else self.code

    def kill(self) -> None:
        self.killed = True


class PersistProc:
    def __init__(self, fake: FakeColab, seconds: float | None) -> None:
        self.fake, self.t0, self.seconds = fake, fake.real, seconds
        self.killed = False

    def poll(self) -> int | None:
        if self.killed:
            return -9
        done = self.seconds is not None and self.fake.real - self.t0 >= self.seconds
        return 0 if done else None

    def kill(self) -> None:
        self.killed = True


class FakeColab:
    def __init__(
        self,
        balance: float = 101.8,
        hardware: str | None = None,
        new_mode: str = "ok",
        persist_s: float | None = 30.0,
    ) -> None:
        self.balance = balance
        self.hardware = hardware  # what the server assigns, whatever was asked
        self.new_mode = new_mode
        self.persist_s = persist_s
        self.real = 0.0
        self.offset = 0.0  # a clock set back or forward
        self.frozen: float | None = None
        self.assigned: dict[str, str] = {}  # endpoint -> hardware
        self.local: dict[str, str] = {}  # the CLI's local names: name -> endpoint
        self.billed: dict[str, float] = {}
        self.procs: list[NewProc] = []
        self.calls: list[list[str]] = []
        self.usage_down = 0  # next `usage` calls that fail
        self.sessions_empty = 0  # next `sessions` calls that print no sessions, exit 0
        self.unassign_fails = 0  # next unassigns that do nothing (-1: all of them)
        self.unassign_noops = 0  # next unassigns that answer 0 and do nothing
        self.flicker = 0  # next cycles whose usage and sessions both leave one session out
        self.unassigns = 0
        self.on_sleep: Callable[[int], None] | None = None
        self.on_call: Callable[[list[str]], None] | None = None
        self.sleeps = 0
        self.serial = 0

    def clock(self) -> float:
        return self.frozen if self.frozen is not None else EPOCH + self.real + self.offset

    def assign(self, hardware: str, name: str | None = None) -> str:
        self.serial += 1
        endpoint = f"gpu-{hardware.lower()}-s-{self.serial}"
        self.assigned[endpoint] = hardware
        self.billed[endpoint] = 0.0
        if name:
            self.local[name] = endpoint
        return endpoint

    def rate(self) -> float:
        return float(sum(cw.RATES[hw] for hw in self.assigned.values()))

    def advance(self, seconds: float) -> None:
        for _ in range(int(seconds)):  # one second at a time, so `new` lands on time
            for endpoint, hardware in self.assigned.items():
                self.billed[endpoint] += cw.RATES[hardware] / 3600
            self.balance -= self.rate() / 3600
            self.real += 1
            for proc in self.procs:
                proc.tick()

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.sleeps > 3000:  # a watch that never stops fails here, not by hanging CI
            raise AssertionError("runaway watch")
        self.advance(seconds)
        if self.on_sleep:
            self.on_sleep(self.sleeps)

    def name_of(self, endpoint: str) -> str:
        return next((n for n, e in self.local.items() if e == endpoint), "?")

    def spawn(self, argv: Sequence[str]) -> Any:
        self.calls.append(list(argv))
        if argv[0] == "bash":
            return PersistProc(self, self.persist_s)
        proc = NewProc(self, argv[3], argv[5], self.new_mode)
        self.procs.append(proc)
        return proc

    def __call__(self, argv: Sequence[str], timeout: float) -> tuple[int, str]:
        self.calls.append(list(argv))
        if self.on_call:
            self.on_call(list(argv))
        if argv[0].endswith("python"):  # UNASSIGN through the CLI's client
            self.unassigns += 1
            if self.unassign_fails:
                self.unassign_fails -= 1 if self.unassign_fails > 0 else 0
                return 1, "ColabRequestError"
            if self.unassign_noops:
                self.unassign_noops -= 1
                return 0, ""
            if argv[3] not in self.assigned:
                return 1, "ColabRequestError: 404"
            del self.assigned[argv[3]]
            self.local = {n: e for n, e in self.local.items() if e != argv[3]}
            return 0, ""
        command = argv[1]
        if command == "usage":
            if self.usage_down:
                self.usage_down -= 1
                return 1, "[colab] Warning: failed to fetch compute-unit info"
            return 0, (
                f"Current balance: {self.balance:.2f} compute units\n"
                f"Usage rate: {self.rate():.2f}/hr\n"
                f"Active assignments: {len(self.assigned) - bool(self.flicker)}"
            )
        if command == "sessions":
            lines = [
                f"[{self.name_of(e)}] {e} | Hardware: {hw} | Shape: Standard | Variant: GPU"
                for e, hw in self.assigned.items()
            ]
            if self.flicker:
                self.flicker -= 1
                lines = lines[1:]
            if self.sessions_empty:
                self.sessions_empty -= 1
                lines = []  # what an auth failure prints
            return 0, "\n".join(lines) or "[colab] No active sessions found on server."
        raise AssertionError(argv)


def watcher(
    fake: FakeColab,
    tmp_path: Path,
    name: str = "da30",
    gpu: str = "L4",
    cap: float = 1.0,
    attach: bool = False,
    started: float | None = None,
    endpoint: str | None = None,
    persist: str | None = None,
    floor: float | None = None,
    **kw: Any,
) -> Any:
    spec = cw.Spec(name, gpu, cap, attach, started, endpoint, persist)
    cli = cw.Cli(fake, tmp_path / f"{name}.jsonl", colab=COLAB)
    return cw.Watcher(
        spec,
        cli,
        tmp_path / "reg",
        floor,
        clock=fake.clock,
        sleep=fake.sleep,
        spawn=fake.spawn,
        **kw,
    )


def guard(fake: FakeColab, tmp_path: Path, floor: float | None = None, **kw: Any) -> Any:
    cli = cw.Cli(fake, tmp_path / "guard.jsonl", colab=COLAB)
    kw.setdefault("alive", lambda pid: True)
    return cw.Guard(cli, tmp_path / "reg", floor, clock=fake.clock, sleep=fake.sleep, **kw)


def events(path: Path, name: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return [r for r in rows if name is None or r["event"] == name]


def entry(tmp_path: Path, name: str, endpoint: str, beat: float, state: str = "running") -> None:
    reg = tmp_path / "reg"
    reg.mkdir(exist_ok=True)
    cw.write_entry(reg, name, pid=4242, endpoint=endpoint, state=state, beat=beat)


@pytest.fixture
def handlers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    saved = {s: signal.getsignal(s) for s in cw._Deferred.SIGNALS}
    monkeypatch.setattr(cw, "_signalled", False)
    cw.install_signal_handlers()
    assert signal.getsignal(signal.SIGTERM) is cw._raise_interrupted  # or a kill ends pytest
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def kill_self() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


# -- meter and cap --------------------------------------------------------------------------


def test_the_margin_counts_a_poll_its_calls_and_one_retried_unassign() -> None:
    assert cw.Timing().margin == 60 + 3 * 60 + 10 + 3 * 60


def test_a_new_session_is_stopped_inside_its_cap(tmp_path: Path) -> None:
    fake = FakeColab()
    w = watcher(fake, tmp_path, cap=1.0)
    assert w.watch() == cw.EXIT_CAPPED and fake.assigned == {}
    (billed,) = fake.billed.values()
    assert 1.0 - L4 * (MARGIN_H + 2 * 60 / 3600) <= billed <= 1.0
    assert events(tmp_path / "da30.jsonl", "stopped")[0]["reason"] == "Capped"
    assert json.loads((tmp_path / "reg" / "da30.json").read_text())["state"] == "stopped"


def test_a_frozen_clock_is_caught_by_the_balance(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: setattr(fake, "frozen", fake.clock()) if n == 4 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert max(fake.billed.values()) <= 1.0


def test_with_usage_down_the_wall_clock_still_caps(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: setattr(fake, "usage_down", 10**6) if n == 5 else None

    def back(argv: list[str]) -> None:  # usage returns for the stop's listings
        if fake.unassigns:
            fake.usage_down = 0

    fake.on_call = back
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert max(fake.billed.values()) <= 1.0


def test_a_clock_set_back_does_not_lower_the_spend(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: setattr(fake, "offset", -3600.0) if n == 8 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    spent = [r["wall_cu"] for r in events(tmp_path / "da30.jsonl", "poll")]
    assert spent == sorted(spent)
    assert max(fake.billed.values()) <= 1.0


def test_another_session_on_the_account_is_not_charged_here(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.assign("A100", name="da26-ft")
    assert watcher(fake, tmp_path, cap=1.0).watch() == cw.EXIT_CAPPED
    ours = [e for e in fake.billed if e.startswith("gpu-l4")]
    assert 1.0 - L4 * (MARGIN_H + 2 * 60 / 3600) <= fake.billed[ours[0]] <= 1.0
    assert list(fake.assigned) == ["gpu-a100-s-1"]  # the other session runs on


def test_the_floor_stops_the_session_on_the_real_balance(tmp_path: Path) -> None:
    fake = FakeColab(balance=14.5)
    assert watcher(fake, tmp_path, cap=4.0, floor=14.0).watch() == cw.EXIT_CAPPED
    assert fake.assigned == {} and fake.balance > 14.0


# -- identity by endpoint (B1, B2) ----------------------------------------------------------


def test_a_session_whose_name_is_lost_is_still_capped_by_endpoint(tmp_path: Path) -> None:
    """B1: the CLI lists it as `[?]`; it has not ended, and it is stopped at its cap."""
    fake = FakeColab()
    fake.on_sleep = lambda n: fake.local.clear() if n == 6 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert fake.assigned == {}
    assert not events(tmp_path / "da30.jsonl", "ended")


def test_a_session_that_ended_is_still_unassigned_by_endpoint(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: fake.assigned.clear() if n == 6 else None
    assert watcher(fake, tmp_path, cap=4.0).watch() == cw.EXIT_OK
    assert events(tmp_path / "da30.jsonl", "ended")
    endpoint = events(tmp_path / "da30.jsonl", "bound")[0]["endpoint"]
    assert ["/fake/venv/bin/python", "-c", cw.UNASSIGN, endpoint] in fake.calls


def test_a_signal_during_new_after_the_assign_stops_the_unnamed_vm(
    tmp_path: Path, handlers: None
) -> None:
    """B2: the server assigned, the CLI has not saved the name; cleanup still stops it."""
    fake = FakeColab(new_mode="slow")
    fake.on_sleep = lambda n: kill_self() if n == 2 else None  # t = 30 s: assigned at 20
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert fake.assigned == {} and fake.procs[0].killed


def test_an_assign_that_lands_after_the_kill_is_found_and_stopped(
    tmp_path: Path, handlers: None
) -> None:
    fake = FakeColab(new_mode="late")
    fake.on_sleep = lambda n: kill_self() if n == 1 else None  # t = 15 s: not assigned yet
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert fake.serial == 1 and fake.assigned == {}


def test_a_new_that_dies_after_the_assign_is_stopped(tmp_path: Path) -> None:
    fake = FakeColab(new_mode="orphan")
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert fake.serial == 1 and fake.assigned == {}


def test_a_session_listed_as_unnamed_is_registered_before_its_name(tmp_path: Path) -> None:
    """The guard must see the endpoint while `new` still runs and lists it as `[?]`."""
    fake = FakeColab(new_mode="slow_name")
    g = guard(fake, tmp_path)
    fake.on_sleep = lambda n: g.cycle()
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert not events(tmp_path / "guard.jsonl", "ALERT")


def test_a_refused_new_stops_nothing(tmp_path: Path) -> None:
    fake = FakeColab(new_mode="refused")
    other = fake.assign("L4")  # an old `[?]` on the account
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert list(fake.assigned) == [other] and fake.unassigns == 0


def test_without_a_trusted_listing_no_new_is_run(tmp_path: Path) -> None:
    fake = FakeColab()
    other = fake.assign("L4")
    fake.usage_down = 10**6
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert fake.procs == [] and list(fake.assigned) == [other] and fake.unassigns == 0


def test_a_new_that_times_out_is_stopped(tmp_path: Path) -> None:
    fake = FakeColab(new_mode="slow")
    w = watcher(fake, tmp_path, cap=4.0, timing=cw.Timing(new_timeout=300))
    assert w.watch() == cw.EXIT_CRASHED and fake.assigned == {}


# -- nothing blocks the cap (B3, I1, I5) -----------------------------------------------------


def test_a_new_that_hangs_is_capped_while_it_runs(tmp_path: Path) -> None:
    """B3: a slow `new` (up to 900 s) does not hold off the cap check."""
    fake = FakeColab(new_mode="slow")
    assert watcher(fake, tmp_path, gpu="A100", cap=1.2).watch() == cw.EXIT_CAPPED
    assert fake.assigned == {} and max(fake.billed.values()) <= 1.2


def test_a_crash_stops_only_this_watchers_session(tmp_path: Path) -> None:
    """I1: one watcher's failure never stops another watcher's session."""
    fake = FakeColab()
    other = fake.assign("A100", name="da26-ft")

    def boom(n: int) -> None:
        if n == 6:
            raise RuntimeError("boom")

    fake.on_sleep = boom
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert list(fake.assigned) == [other]


def test_a_persist_that_hangs_is_killed_and_the_cap_still_holds(tmp_path: Path) -> None:
    """I5: persist runs in the background and is killed at persist_timeout."""
    fake = FakeColab(persist_s=None)
    w = watcher(fake, tmp_path, cap=4.0, persist="colab exec -s da30 -f p.py", persist_at=0.5)
    assert w.watch() == cw.EXIT_CAPPED and fake.assigned == {}
    log = tmp_path / "da30.jsonl"
    started = events(log, "persist")[0]
    killed = [r for r in events(log, "ALERT") if "persist" in r["message"]]
    assert killed and max(fake.billed.values()) <= 4.0
    assert started["spent"] >= 2.0


def test_persist_runs_before_the_cap(tmp_path: Path) -> None:
    fake = FakeColab()
    w = watcher(fake, tmp_path, cap=4.0, persist="colab exec -s da30 -f p.py")
    assert w.watch() == cw.EXIT_CAPPED
    names = [r["event"] for r in events(tmp_path / "da30.jsonl")]
    assert names.index("persist") < names.index("persisted") < names.index("stopped")


# -- attach (I2) -----------------------------------------------------------------------------


def test_attach_counts_spend_from_the_start_time(tmp_path: Path) -> None:
    """I2: a session 50 min old has spent 1.6 CU of a cap of 2 before the watcher came."""
    fake = FakeColab()
    fake.assign("L4", name="da26-ft")
    fake.advance(3000)
    w = watcher(fake, tmp_path, name="da26-ft", cap=2.0, attach=True, started=fake.clock() - 3000)
    assert w.watch() == cw.EXIT_CAPPED
    assert fake.assigned == {} and max(fake.billed.values()) <= 2.0


def test_attach_by_endpoint_finds_a_session_whose_name_is_lost(tmp_path: Path) -> None:
    fake = FakeColab()
    endpoint = fake.assign("L4")
    w = watcher(fake, tmp_path, name="lost", attach=True, started=fake.clock(), endpoint=endpoint)
    assert w.watch() == cw.EXIT_CAPPED and fake.assigned == {}


def test_attach_needs_the_session_listed(tmp_path: Path) -> None:
    fake = FakeColab()
    w = watcher(fake, tmp_path, attach=True, started=fake.clock())
    assert w.watch() == cw.EXIT_NOTHING and fake.procs == []


def test_attach_needs_a_start_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="started"):
        cw.check_spec(cw.Spec("da26", "L4", 2.0, attach=True))


# -- stopping (I3, I4) -----------------------------------------------------------------------


def test_a_stop_that_fails_is_retried_every_poll_until_it_works(tmp_path: Path) -> None:
    """I3: STOP_FAILED is loud and the stop goes on being retried."""
    fake = FakeColab()
    fake.unassign_fails = 6
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED and fake.assigned == {}
    assert events(tmp_path / "da30.jsonl", "STOP_FAILED")


def test_one_listing_without_the_session_does_not_confirm_its_stop(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.unassign_noops = 1  # the first unassign answers 0 and does nothing
    hidden: list[bool] = []

    def hide(argv: list[str]) -> None:  # then one listing leaves the session out
        if fake.unassigns == 1 and argv[1:] == ["usage"] and not hidden:
            fake.flicker = 1
            hidden.append(True)

    fake.on_call = hide
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED and fake.assigned == {}


def test_one_listing_without_the_session_does_not_end_it(tmp_path: Path) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: setattr(fake, "flicker", 1) if n in (6, 9) else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED and fake.assigned == {}
    assert not events(tmp_path / "da30.jsonl", "ended")


def test_a_stop_that_never_works_ends_in_5_only_when_told_to_give_up(
    tmp_path: Path, capfd: pytest.CaptureFixture[str], handlers: None
) -> None:
    fake = FakeColab()
    fake.unassign_fails = -1
    fake.on_sleep = lambda n: kill_self() if fake.unassigns == 12 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_STOP_FAILED
    assert fake.unassigns == 12 and len(fake.assigned) == 1
    assert "STOP_FAILED" in capfd.readouterr().err
    assert json.loads((tmp_path / "reg" / "da30.json").read_text())["state"] == "stop_failed"


@pytest.mark.parametrize("usage_down", [0, 10**6])
def test_an_empty_listing_from_an_auth_failure_confirms_no_stop(
    tmp_path: Path, usage_down: int, handlers: None
) -> None:
    """I4: `No active sessions` with exit 0 is no proof unless `usage` agrees."""
    fake = FakeColab()
    fake.unassign_fails = -1

    def glitch(argv: list[str]) -> None:
        if fake.unassigns == 1 and not fake.sessions_empty:
            fake.sessions_empty, fake.usage_down = 10**6, usage_down

    fake.on_call = glitch
    fake.on_sleep = lambda n: kill_self() if fake.unassigns == 6 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_STOP_FAILED
    assert not events(tmp_path / "da30.jsonl", "stopped")


def test_snapshot_trusts_only_a_listing_that_usage_backs() -> None:
    fake = FakeColab()
    fake.assign("L4", name="da30")
    cli = cw.Cli(fake, Path("/dev/null"), colab=COLAB)
    assert cli.snapshot()[1] is not None
    fake.sessions_empty = 1
    assert cli.snapshot()[1] is None
    fake.usage_down = 1
    assert cli.snapshot() == (None, None)


# -- signals and crashes ---------------------------------------------------------------------


def test_sigterm_stops_the_session(tmp_path: Path, handlers: None) -> None:
    fake = FakeColab()
    fake.on_sleep = lambda n: kill_self() if n == 6 else None
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED and fake.assigned == {}
    assert events(tmp_path / "da30.jsonl", "signal")[0]["signum"] == signal.SIGTERM


def test_only_the_first_signal_raises(handlers: None) -> None:
    with pytest.raises(cw.Interrupted):
        cw._raise_interrupted(signal.SIGTERM, None)
    cw._raise_interrupted(signal.SIGHUP, None)  # a second kill must not cut the stop short


def test_a_signal_during_a_cli_call_is_not_taken_for_a_failed_call(
    tmp_path: Path, handlers: None
) -> None:
    fake = FakeColab()
    fake.on_call = lambda argv: kill_self() if fake.sleeps == 6 and argv[1:] == ["usage"] else None
    assert watcher(fake, tmp_path, cap=4.0).watch() == cw.EXIT_CRASHED
    assert fake.assigned == {}


def test_a_signal_after_the_stop_still_logs_the_exit(tmp_path: Path, handlers: None) -> None:
    fake = FakeColab()

    def late(argv: list[str]) -> None:
        log = (tmp_path / "da30.jsonl").read_text()
        if argv[1:] == ["usage"] and '"event": "stopped"' in log:
            kill_self()

    fake.on_call = late
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert events(tmp_path / "da30.jsonl", "exit")[0]["code"] == cw.EXIT_CAPPED


def test_an_exception_from_the_cli_is_a_failed_call(tmp_path: Path) -> None:
    fake = FakeColab()

    def broken(argv: list[str]) -> None:
        if 6 <= fake.sleeps <= 9 and argv[1:] in (["usage"], ["sessions"]):
            raise RuntimeError("CLI wrapper broke")

    fake.on_call = broken
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED and fake.assigned == {}


def test_a_base_exception_mid_loop_still_stops_the_session(tmp_path: Path) -> None:
    fake = FakeColab()

    def leave(n: int) -> None:
        if n == 6:
            raise SystemExit(9)  # a library calling sys.exit

    fake.on_sleep = leave
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED and fake.assigned == {}


# -- GPU and ready file ----------------------------------------------------------------------


def test_a_wrong_gpu_is_stopped_and_never_ready(tmp_path: Path) -> None:
    fake = FakeColab(hardware="A100")
    assert watcher(fake, tmp_path).watch() == cw.EXIT_WRONG_GPU and fake.assigned == {}
    assert not (tmp_path / "reg" / "da30.ready").exists()


def test_the_ready_file_is_written_once_the_gpu_is_right(tmp_path: Path) -> None:
    fake = FakeColab()
    seen: list[bool] = []
    fake.on_sleep = lambda n: seen.append((tmp_path / "reg" / "da30.ready").exists())
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert seen[0] is False and seen[-1] is True


def test_a_stale_ready_file_is_removed_at_start(tmp_path: Path) -> None:
    (tmp_path / "reg").mkdir()
    (tmp_path / "reg" / "da30.ready").write_text("old run\n")
    fake = FakeColab(new_mode="refused")
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CRASHED
    assert not (tmp_path / "reg" / "da30.ready").exists()


def test_an_unknown_gpu_is_refused_before_any_new(tmp_path: Path) -> None:
    colab_cli = tmp_path / "colab"
    colab_cli.write_text("")
    argv = ["session", "--registry", str(tmp_path), "--log", str(tmp_path / "w.jsonl")]
    argv += ["--colab", str(colab_cli), "--new", "--name", "x", "--gpu", "T4", "--cap", "1"]
    assert cw.main(argv) == cw.EXIT_NOTHING


# -- the guard -------------------------------------------------------------------------------


def test_the_guard_stops_an_unregistered_assignment_after_its_grace(tmp_path: Path) -> None:
    fake = FakeColab()
    ours = fake.assign("L4", name="da30")
    stray = fake.assign("L4")  # `[?]`
    entry(tmp_path, "da30", ours, fake.clock())
    g = guard(fake, tmp_path, grace=2)
    for poll in range(3):
        assert g.cycle() is None
        assert (stray in fake.assigned) == (poll < 2)
    assert ours in fake.assigned


@pytest.mark.parametrize("why", ["dead", "stale", "stop_failed"])
def test_the_guard_stops_a_session_whose_watcher_is_gone(tmp_path: Path, why: str) -> None:
    fake = FakeColab()
    ours = fake.assign("L4", name="da30")
    beat = fake.clock() - (601 if why == "stale" else 0)
    entry(tmp_path, "da30", ours, beat, state="stop_failed" if why == "stop_failed" else "running")
    g = guard(fake, tmp_path, alive=lambda pid: why != "dead")
    for _ in range(3):
        g.cycle()
    assert fake.assigned == {}


def test_the_guard_floor_stops_everything(tmp_path: Path) -> None:
    fake = FakeColab(balance=14.3)
    a, b = fake.assign("L4", name="a"), fake.assign("A100", name="b")
    entry(tmp_path, "a", a, fake.clock())
    entry(tmp_path, "b", b, fake.clock())
    assert guard(fake, tmp_path, floor=14.0).watch() == cw.EXIT_CAPPED
    assert fake.assigned == {}


def test_the_guard_does_nothing_on_an_untrusted_listing(tmp_path: Path) -> None:
    fake = FakeColab()
    stray = fake.assign("L4")
    fake.usage_down = 10
    g = guard(fake, tmp_path, grace=0)
    for _ in range(10):
        assert g.cycle() is None
    assert stray in fake.assigned and fake.unassigns == 0


def test_the_guard_ends_when_every_watcher_is_done(tmp_path: Path) -> None:
    fake = FakeColab()
    entry(tmp_path, "da30", "gpu-l4-s-9", fake.clock(), state="stopped")
    assert guard(fake, tmp_path).watch() == cw.EXIT_OK


def test_the_guard_treats_an_unreadable_entry_as_no_watcher(tmp_path: Path) -> None:
    fake = FakeColab()
    stray = fake.assign("L4", name="da30")
    (tmp_path / "reg").mkdir()
    (tmp_path / "reg" / "da30.json").write_text("{not json")
    g = guard(fake, tmp_path)
    for _ in range(3):
        g.cycle()
    assert stray not in fake.assigned
    assert events(tmp_path / "guard.jsonl", "ALERT")


def test_a_watcher_and_the_guard_share_the_registry(tmp_path: Path) -> None:
    fake = FakeColab()
    g = guard(fake, tmp_path)  # default grace: 2 polls
    fake.on_sleep = lambda n: g.cycle()  # the guard polls as often as the watcher
    assert watcher(fake, tmp_path).watch() == cw.EXIT_CAPPED
    assert not events(tmp_path / "guard.jsonl", "ALERT")


# -- plumbing --------------------------------------------------------------------------------


def test_a_log_that_cannot_be_written_does_not_stop_the_watch(tmp_path: Path) -> None:
    (tmp_path / "blocked").write_text("a file, not a directory")
    fake = FakeColab()
    w = watcher(fake, tmp_path)
    w.cli.log_path = tmp_path / "blocked" / "w.jsonl"
    assert w.watch() == cw.EXIT_CAPPED and fake.assigned == {}


def test_undecodable_cli_output_is_read_not_crashed(tmp_path: Path) -> None:
    cli = tmp_path / "colab"
    cli.write_text("#!/bin/sh\nprintf 'Current balance: 9.5 compute units \\377\\n'\n")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    code, out = cw.subprocess_runner([str(cli), "usage"], 10)
    assert code == 0 and "�" in out
    assert cw.subprocess_runner(["/nonexistent/colab"], 10)[0] == 1


def test_parse_sessions_knows_the_cli_lines_and_nothing_else() -> None:
    line = "[da30] gpu-l4-s-1 | Hardware: L4 | Shape: Standard | Variant: GPU"
    pruned = "[colab] Pruned 1 stale local session(s)."
    assert cw.parse_sessions(f"{pruned}\n{line}") == [cw.Listed("da30", "gpu-l4-s-1", "L4")]
    assert cw.parse_sessions("[colab] No active sessions found on server.") == []
    assert cw.parse_sessions("Traceback (most recent call last):") is None
    assert cw.parse_sessions(f"{line}\nTraceback (most recent call last):") is None
    assert cw.parse_sessions("") is None


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
    argv = ["guard", "--registry", str(tmp_path), "--log", str(tmp_path / "g.jsonl")]
    argv += ["--colab", str(colab_cli), "--floor", "14"]
    with pytest.raises(SystemExit):
        cw.main(argv)
    assert seen[0][1] == "--what=sleep:idle:handle-lid-switch"
    assert seen[0][-len(argv) :] == argv
