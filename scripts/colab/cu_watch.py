#!/usr/bin/env python3
"""Watch a batch of Colab sessions and stop each before it passes its CU cap.

One process supervises every session of a batch (DA-26, DA-30 under tier 2). Run it
on the laptop that has the `colab` CLI, detached, for the whole batch:

    nohup setsid python3 scripts/colab/cu_watch.py --floor 14 \\
        --new da30-stage1:L4:4 --persist 'da30-stage1=colab exec -s da30-stage1 -f p.py' \\
        --attach da26-ft-vego-n20:L4:17.5:2026-11-04T21:00+07:00 \\
        --log fwdata/colab/cu_watch.jsonl < /dev/null > /dev/null 2>&1 &

`--new NAME:GPU:CAP` creates the session (`colab new -s NAME --gpu GPU`);
`--attach NAME:GPU:CAP[:STARTED]` takes over one already running (STARTED is ISO 8601,
default now). The process re-executes itself under `systemd-inhibit --what=sleep` so
the laptop does not suspend while sessions are paid for (`--no-inhibit` skips that).

Meter. A session's spend is wall-clock time since it started (`time.time()`, which
keeps counting through a suspend, unlike `time.monotonic`) times its GPU's rate
(`RATES`). While it is the batch's only session and the account's only assignment,
the real balance drop from `colab usage` is counted too and the larger of the two is
taken. The balance is per account, so once several assignments share it the
per-session spend is the time estimate only; `--floor` uses the real balance: below
it, every session is stopped.

A session is stopped when spend + rate x margin reaches its cap, the margin being one
poll, the CLI timeouts of a cycle and the time a stop with its retries can take.
Before that, at `--soft` of the cap (or earlier, so it has `persist_timeout` to run),
its `--persist` command runs once on the laptop, so logs survive a cap stop. Use
`colab exec -s NAME -f ...` there, never `colab ssh`: `ssh -s NAME` creates the
session again when it is gone.

Fail closed. Every GPU type is checked against `RATES` before any `new` (the CLI maps
an unknown `--gpu` to A100). The `Hardware:` of each session in `colab sessions` must
match its plan, or it is stopped and the watch ends. A `new` that fails or times out
is followed by a look at `colab sessions`: a session listed under its name is
attached, an unnamed `[?]` assignment that appeared meanwhile is unassigned through
the CLI's own client. Any exception, SIGTERM, SIGINT or SIGHUP ends in a `finally`
that stops every supervised session. `colab stop` returns 0 even for a missing
session, so a stop counts only once `colab sessions` lists neither the name nor the
endpoint; it is retried with backoff. A session has ended by itself only after 3
polls in a row that list the server's sessions without it; a failed call, or an empty
list while `colab usage` still counts assignments, is not a miss.

Each event is a JSON line in `--log` (and on stdout); ALERT lines also go to stderr.
Exit codes: 0 every session ended by itself; 1 unexpected error (sessions stopped);
2 bad arguments, nothing started; 3 a cap or the floor stopped a session; 4 a stop
was not confirmed, a session may still be running (check `colab sessions` now);
5 wrong GPU; 6 `new` failed; 128 + N on signal N.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

COLAB = Path(
    os.environ.get(
        "COLAB_CLI",
        Path.home() / "project" / "wm-wam-review" / ".venv-colab-cli" / "bin" / "colab",
    )
)
# CU per hour: the rise of `colab usage` when a session opens (docs/g0/psi0-finetune-cost.md).
RATES = {"L4": 1.94, "A100": 6.73}

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_CAPPED = 0, 1, 2, 3
EXIT_STILL_RUNNING, EXIT_WRONG_GPU, EXIT_NEW_FAILED = 4, 5, 6
TIMEOUT = 124  # returncode of a call that timed out
MISSES_TO_END = 3

# Unassign an endpoint with the CLI's own client: `colab stop` needs a local name.
UNASSIGN = "import sys; from colab_cli.common import state; state.client.unassign(sys.argv[1])"

# (argv, timeout in s) -> (returncode, stdout + stderr)
Run = Callable[[Sequence[str], float], "tuple[int, str]"]


class Process(Protocol):
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...


Spawn = Callable[[str], Process]

_LINE = re.compile(
    r"^\[(?P<name>[^\]]*)\] (?P<endpoint>\S+) \| Hardware: (?P<hardware>[^|]+?) \|", re.M
)
_BALANCE = re.compile(r"Current balance:\s*([\d.]+)")
_RATE = re.compile(r"Usage rate:\s*([\d.]+)")
_ASSIGNMENTS = re.compile(r"Active assignments:\s*(\d+)")


class WatchError(Exception):
    code = EXIT_ERROR


class WrongGpu(WatchError):
    code = EXIT_WRONG_GPU


class NewFailed(WatchError):
    code = EXIT_NEW_FAILED


class Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(f"signal {signum}")
        self.signum = signum


@dataclass(frozen=True)
class Spec:
    name: str
    gpu: str
    cap: float
    attach: bool = False
    started: float | None = None  # epoch seconds, --attach only
    persist: str | None = None

    @property
    def rate(self) -> float:
        return RATES[self.gpu]


def parse_spec(text: str, attach: bool) -> Spec:
    """`NAME:GPU:CAP[:STARTED]`; an unknown GPU is an error here, before any `new`."""
    parts = text.split(":", 3)
    if len(parts) < 3:
        raise ValueError(f"{text!r}: expected NAME:GPU:CAP")
    name, gpu, cap, *rest = parts
    gpu = gpu.upper()
    if gpu not in RATES:
        raise ValueError(f"{name}: unknown GPU {gpu!r}; rates are known for {sorted(RATES)}")
    if not re.fullmatch(r"[\w.-]+", name):
        raise ValueError(f"{name!r}: session names are letters, digits, '.', '_', '-'")
    if float(cap) <= 0:
        raise ValueError(f"{name}: the cap must be positive")
    started = None
    if rest:
        if not attach:
            raise ValueError(f"{name}: a start time is for --attach only")
        started = datetime.fromisoformat(rest[0]).timestamp()
    return Spec(name, gpu, float(cap), attach, started)


@dataclass(frozen=True)
class Listed:
    name: str
    endpoint: str
    hardware: str


def parse_sessions(text: str) -> list[Listed]:
    return [Listed(m["name"], m["endpoint"], m["hardware"].strip()) for m in _LINE.finditer(text)]


@dataclass(frozen=True)
class Usage:
    balance: float
    rate: float
    assignments: int


def parse_usage(text: str) -> Usage | None:
    found = [p.search(text) for p in (_BALANCE, _RATE, _ASSIGNMENTS)]
    if not all(found):
        return None
    balance, rate, assignments = (m.group(1) for m in found if m)
    return Usage(float(balance), float(rate), int(assignments))


@dataclass(frozen=True)
class Timing:
    poll: float = 60.0
    cli_timeout: float = 60.0
    new_timeout: float = 900.0
    stop_backoff: tuple[float, ...] = (5.0, 15.0, 30.0)
    persist_timeout: float = 600.0

    @property
    def stop_budget(self) -> float:
        """A stop with every retry: stop, unassign and confirm calls, then the backoff."""
        return sum(3 * self.cli_timeout + pause for pause in self.stop_backoff)

    @property
    def margin(self) -> float:
        """Seconds a session can keep spending after a poll found it under its cap."""
        return self.poll + 2 * self.cli_timeout + self.stop_budget


@dataclass
class Session:
    spec: Spec
    started: float
    endpoint: str | None = None
    misses: int = 0
    ended: bool = False  # gone from the server, by itself or stopped and confirmed
    stopped_by: str | None = None  # "cap", "floor", "wrong_gpu", "cleanup"
    unconfirmed: bool = False
    persist: Process | None = None
    persist_done: bool = False

    def by_time(self, now: float) -> float:
        return max(0.0, now - self.started) / 3600 * self.spec.rate


@dataclass
class Watcher:
    specs: list[Spec]
    floor: float | None
    log_path: Path
    run: Run
    colab: Path = COLAB
    timing: Timing = field(default_factory=Timing)
    soft: float = 0.9
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    spawn: Spawn | None = None
    sessions: list[Session] = field(default_factory=list)
    start_balance: float | None = None
    shared: bool = False  # the balance has counted more than one assignment

    # -- CLI -----------------------------------------------------------------------

    def colab_call(self, *args: str, timeout: float | None = None) -> tuple[int, str]:
        return self.run([str(self.colab), *args], timeout or self.timing.cli_timeout)

    def usage(self) -> Usage | None:
        code, text = self.colab_call("usage")
        return parse_usage(text) if code == 0 else None

    def listing(self, usage: Usage | None = None) -> list[Listed] | None:
        """The server's sessions, or None when the answer cannot be trusted."""
        code, text = self.colab_call("sessions")
        if code != 0:
            return None
        listed = parse_sessions(text)
        if not listed and "No active sessions" not in text:
            return None  # an output this parser does not know
        if not listed and usage is not None and usage.assignments > 0:
            return None  # an empty list while assignments are counted (auth glitch)
        return listed

    def log(self, event: str, **fields: Any) -> dict[str, Any]:
        record = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        line = json.dumps(record)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as sink:
            sink.write(line + "\n")
        print(line, flush=True)
        if event == "ALERT":
            print(f"ALERT {fields.get('message', '')}", file=sys.stderr, flush=True)
        return record

    # -- start -----------------------------------------------------------------------

    def start(self) -> None:
        usage = self.usage()
        self.start_balance = usage.balance if usage else None
        if usage is not None and usage.assignments > sum(s.attach for s in self.specs):
            self.shared = True  # something outside the batch already draws on the balance
        self.log(
            "start",
            balance=self.start_balance,
            assignments=usage.assignments if usage else None,
            floor=self.floor,
            margin_s=self.timing.margin,
            sessions=[asdict(s) for s in self.specs],
        )
        for spec in self.specs:
            if spec.attach:
                self.attach(spec)
            else:
                self.new(spec)

    def attach(self, spec: Spec) -> None:
        listed = self.listing()
        match = next((s for s in listed or [] if s.name == spec.name), None)
        if match is None:
            raise WatchError(f"{spec.name} is not listed by `colab sessions`; nothing to attach")
        session = Session(spec, spec.started or self.clock(), endpoint=match.endpoint)
        self.sessions.append(session)
        self.log("attach", session=spec.name, endpoint=match.endpoint, started=session.started)
        self.check_gpu(session, match)

    def new(self, spec: Spec) -> None:
        before = self.listing()
        known = {s.endpoint for s in before or []}
        session = Session(spec, self.clock())
        self.sessions.append(session)  # supervised from now: `finally` stops it
        code, text = self.colab_call(
            "new", "-s", spec.name, "--gpu", spec.gpu, timeout=self.timing.new_timeout
        )
        self.log("new", session=spec.name, code=code, output=text[-500:])
        listed = self.listing()
        match = next((s for s in listed or [] if s.name == spec.name), None)
        if match is not None:
            session.endpoint = match.endpoint
            if code != 0:
                self.log("new_failed_but_listed", session=spec.name, endpoint=match.endpoint)
            self.check_gpu(session, match)
            return
        orphans = [s for s in listed or [] if s.name == "?" and s.endpoint not in known]
        for orphan in orphans:
            self.log("orphan", session=spec.name, endpoint=orphan.endpoint)
            self.unassign(orphan.endpoint)
        if listed is None or not all(self.gone(o.endpoint) for o in orphans):
            session.unconfirmed = True
            self.log("ALERT", message=f"{spec.name}: an assignment from `new` may be running")
        else:
            session.ended = True
        raise NewFailed(f"colab new -s {spec.name} failed (code {code}): {text[-300:]}")

    def check_gpu(self, session: Session, listed: Listed) -> None:
        if listed.hardware != session.spec.gpu:
            message = f"{session.spec.name} runs on {listed.hardware}, planned {session.spec.gpu}"
            self.log("ALERT", message=message)
            self.stop(session, "wrong_gpu")
            raise WrongGpu(message)

    # -- stop ------------------------------------------------------------------------

    def gone(self, endpoint: str | None, name: str | None = None) -> bool:
        listed = self.listing()
        if listed is None:
            return False
        return not any(s.endpoint == endpoint or (name and s.name == name) for s in listed)

    def unassign(self, endpoint: str) -> None:
        python = self.colab.parent / "python"
        code, text = self.run([str(python), "-c", UNASSIGN, endpoint], self.timing.cli_timeout)
        self.log("unassign", endpoint=endpoint, code=code, output=text[-300:])

    def stop(self, session: Session, reason: str) -> bool:
        name = session.spec.name
        attempts = len(self.timing.stop_backoff)
        for attempt, pause in enumerate(self.timing.stop_backoff, start=1):
            code, text = self.colab_call("stop", "-s", name)
            if session.endpoint and attempt > 1:
                self.unassign(session.endpoint)  # the named stop did not take
            if self.gone(session.endpoint, name):
                session.ended, session.stopped_by = True, reason
                self.log("stopped", session=name, reason=reason, attempt=attempt, code=code)
                return True
            self.log("stop_unconfirmed", session=name, attempt=attempt, output=text[-300:])
            self.sleep(pause)
        session.unconfirmed = True
        self.log("ALERT", message=f"{name} still listed after {attempts} stops: stop it by hand")
        return False

    # -- poll ------------------------------------------------------------------------

    def live(self) -> list[Session]:
        return [s for s in self.sessions if not s.ended and not s.unconfirmed]

    def by_balance(self, usage: Usage | None) -> float | None:
        """The balance drop, while it can only be this batch's single session."""
        if self.shared or usage is None or self.start_balance is None:
            return None
        return self.start_balance - usage.balance if len(self.sessions) == 1 else None

    def cycle(self) -> None:
        now, usage = self.clock(), self.usage()
        if usage is not None and usage.assignments > 1:
            self.shared = True
        listed = self.listing(usage)
        margin_h = self.timing.margin / 3600
        by_balance = self.by_balance(usage)
        report: dict[str, Any] = {
            "balance": usage.balance if usage else None,
            "assignments": usage.assignments if usage else None,
            "shared": self.shared,
        }
        for session in self.live():
            name = session.spec.name
            spent = max(session.by_time(now), by_balance or 0.0)
            match = None if listed is None else next((s for s in listed if s.name == name), None)
            if listed is not None:
                session.misses = 0 if match else session.misses + 1
            report[name] = {
                "elapsed_s": round(now - session.started),
                "spent": round(spent, 3),
                "by_time": round(session.by_time(now), 3),
                "by_balance": None if by_balance is None else round(by_balance, 3),
                "cap": session.spec.cap,
                "listed": None if listed is None else match is not None,
                "misses": session.misses,
            }
            if match is not None:
                session.endpoint = session.endpoint or match.endpoint
                self.check_gpu(session, match)
            if session.misses >= MISSES_TO_END:
                session.ended = True
                self.log("ended", session=name, spent=round(spent, 3))
                continue
            self.persist_step(session, spent)
            if spent + session.spec.rate * margin_h >= session.spec.cap:
                self.log("cap", session=name, spent=round(spent, 3), cap=session.spec.cap)
                self.stop(session, "cap")
        self.log("poll", **report)
        self.check_floor(usage, margin_h)

    def check_floor(self, usage: Usage | None, margin_h: float) -> None:
        live = self.live()
        if self.floor is None or usage is None or not live:
            return
        rate = max(usage.rate, sum(s.spec.rate for s in live))
        if usage.balance - rate * margin_h <= self.floor:
            self.log("floor", balance=usage.balance, floor=self.floor, rate=rate)
            for session in live:
                self.stop(session, "floor")

    def persist_step(self, session: Session, spent: float) -> None:
        spec = session.spec
        if spec.persist is None or session.persist_done:
            return
        if session.persist is not None:
            code = session.persist.poll()
            if code is not None:
                session.persist_done = True
                self.log("persisted", session=spec.name, code=code)
            return
        lead_h = (self.timing.margin + self.timing.persist_timeout) / 3600
        if spent >= self.soft * spec.cap or spent + spec.rate * lead_h >= spec.cap:
            session.persist = (self.spawn or _spawn_shell)(spec.persist)
            self.log("persist", session=spec.name, spent=round(spent, 3), command=spec.persist)

    # -- whole run -------------------------------------------------------------------

    def cleanup(self) -> None:
        for session in self.live():
            self.stop(session, "cleanup")
        for session in self.sessions:
            if session.persist is not None and session.persist.poll() is None:
                session.persist.kill()

    def watch(self) -> int:
        code = EXIT_OK
        try:
            self.start()
            while self.live():
                self.sleep(self.timing.poll)
                self.cycle()
        except Interrupted as stop:
            self.log("signal", signum=stop.signum)
            code = 128 + stop.signum
        except WatchError as error:
            self.log("error", kind=type(error).__name__, message=str(error))
            code = error.code
        except Exception as error:  # fail closed on anything: the finally stops sessions
            self.log("error", kind=type(error).__name__, message=repr(error))
            code = EXIT_ERROR
        finally:
            with _SignalsIgnored():
                self.cleanup()
        usage = self.usage()
        if any(s.unconfirmed for s in self.sessions):
            code = EXIT_STILL_RUNNING
        elif code == EXIT_OK and any(s.stopped_by in ("cap", "floor") for s in self.sessions):
            code = EXIT_CAPPED
        drop = None
        if usage is not None and self.start_balance is not None:
            drop = round(self.start_balance - usage.balance, 3)
        self.log(
            "exit",
            code=code,
            balance=usage.balance if usage else None,
            balance_drop=drop,
            shared=self.shared,
            sessions={
                s.spec.name: {
                    "stopped_by": s.stopped_by,
                    "unconfirmed": s.unconfirmed,
                    "by_time": round(s.by_time(self.clock()), 3),
                }
                for s in self.sessions
            },
        )
        return code


class _SignalsIgnored:
    """Let cleanup finish: a second SIGTERM must not cut a stop in half."""

    SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

    def __enter__(self) -> None:
        self.saved = [signal.signal(s, signal.SIG_IGN) for s in self.SIGNALS]

    def __exit__(self, *exc: object) -> None:
        for sig, handler in zip(self.SIGNALS, self.saved):
            signal.signal(sig, handler)


def _raise_interrupted(signum: int, frame: object) -> None:
    raise Interrupted(signum)


def install_signal_handlers() -> None:
    for sig in _SignalsIgnored.SIGNALS:
        signal.signal(sig, _raise_interrupted)


def subprocess_runner(argv: Sequence[str], timeout: float) -> tuple[int, str]:
    try:
        done = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        return TIMEOUT, f"timed out after {timeout:.0f} s: {error.output or ''}"
    except OSError as error:
        return 1, f"{type(error).__name__}: {error}"
    return done.returncode, done.stdout + done.stderr


def _spawn_shell(command: str) -> Process:
    return subprocess.Popen(command, shell=True)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--new", action="append", default=[], metavar="NAME:GPU:CAP")
    parser.add_argument("--attach", action="append", default=[], metavar="NAME:GPU:CAP[:START]")
    parser.add_argument("--persist", action="append", default=[], metavar="NAME=COMMAND")
    parser.add_argument("--floor", type=float, help="stop everything below this balance")
    parser.add_argument("--soft", type=float, default=0.9, help="fraction of the cap for persist")
    parser.add_argument("--log", type=Path, required=True, help="JSON lines, one per event")
    parser.add_argument("--colab", type=Path, default=COLAB, help="the colab CLI ($COLAB_CLI)")
    parser.add_argument("--poll", type=float, default=60.0, help="seconds between polls")
    parser.add_argument("--no-inhibit", action="store_true", help="do not hold off suspend")
    return parser.parse_args(argv)


def build_specs(args: argparse.Namespace) -> list[Spec]:
    specs = [parse_spec(t, attach=False) for t in args.new]
    specs += [parse_spec(t, attach=True) for t in args.attach]
    if not specs:
        raise ValueError("nothing to watch: pass --new or --attach")
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ValueError(f"a session is given twice: {names}")
    if bad := [item for item in args.persist if "=" not in item]:
        raise ValueError(f"--persist takes NAME=COMMAND: {bad}")
    persist = dict(item.split("=", 1) for item in args.persist)
    if unknown := set(persist) - set(names):
        raise ValueError(f"--persist for sessions not in the batch: {sorted(unknown)}")
    return [Spec(s.name, s.gpu, s.cap, s.attach, s.started, persist.get(s.name)) for s in specs]


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    try:
        specs = build_specs(args)
    except ValueError as error:
        print(f"cu_watch: {error}", file=sys.stderr)
        return EXIT_USAGE
    if not args.colab.exists():
        print(f"cu_watch: no colab CLI at {args.colab}; pass --colab", file=sys.stderr)
        return EXIT_USAGE
    if not args.no_inhibit and os.environ.get("CU_WATCH_INHIBITED") != "1":
        inhibit = shutil.which("systemd-inhibit")
        if inhibit is None:
            print("cu_watch: no systemd-inhibit; pass --no-inhibit to run anyway", file=sys.stderr)
            return EXIT_USAGE
        os.environ["CU_WATCH_INHIBITED"] = "1"
        os.execv(
            inhibit,
            [
                inhibit,
                "--what=sleep",
                "--who=cu_watch",
                "--why=Colab sessions are paid while they run",
                sys.executable,
                os.path.abspath(__file__),
                *argv,
            ],
        )
    install_signal_handlers()
    watcher = Watcher(
        specs,
        args.floor,
        args.log,
        subprocess_runner,
        colab=args.colab,
        timing=Timing(poll=args.poll),
        soft=args.soft,
    )
    return watcher.watch()


if __name__ == "__main__":
    sys.exit(main())
