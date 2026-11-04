#!/usr/bin/env python3
"""Watch a batch of Colab sessions and stop each before it passes its CU cap.

One process supervises every session of a batch (tier 2: DA-26's three sessions and
DA-30's one) on the laptop that has the `colab` CLI and created the sessions (`colab
stop` only finds names in that CLI's local state). It merges DA-26's fail-closed
single-session watcher (2408e45, scripts/he/cu_watch.py) with DA-30's batch one.

    nohup setsid bash -c 'python3 scripts/colab/cu_watch.py --floor 14 \\
        --new da30-stage1:L4:4 --persist "da30-stage1=colab exec -s da30-stage1 -f p.py" \\
        --ready-dir fwdata/colab/ready --inbox fwdata/colab/inbox \\
        --log fwdata/colab/cu_watch.jsonl; echo "exit $?"' \\
        < /dev/null >> fwdata/colab/cu_watch.out 2>&1 &
    until [ -f fwdata/colab/ready/da30-stage1.ready ]; do
        grep -q '^exit ' fwdata/colab/cu_watch.out && exit 1; sleep 5; done
    # only now start the job on the VM

Sessions. `--new NAME:GPU:CAP` runs `colab new -s NAME --gpu GPU` and meters from
just before it; `--attach NAME:GPU:CAP[:STARTED]` takes over a running session
(STARTED in ISO 8601, default now). A session added later goes into `--inbox` as a
file of such lines (`new ...`, `attach ...`, `persist NAME=COMMAND`), read at each
poll and renamed `.taken` or `.rejected`: stopping the watcher to restart it would
stop every session. `<ready-dir>/<NAME>.ready` is written once the session is seen
on its planned accelerator; start the job only after it exists.

Meter. The larger of two, per session. (1) Wall clock: `time.time()` since the
session started times its GPU's rate (`RATES`); wall time keeps counting through a
laptop suspend, as Colab's billing does (monotonic time does not). (2) Balance: each
drop of `colab usage`'s balance is charged in full while the account has one active
assignment, and in proportion to the session's rate over the account's usage rate
while more run, so a parallel session does not trip this one's cap. `--floor` stops
every session when the account's real balance would fall below it.

A session is stopped when spend + rate x margin reaches its cap: one poll, the two
CLI timeouts of a cycle and the time a stop with one retry can take. At `--persist-at`
of the cap (or earlier, so it has `persist_timeout` to run) its `--persist` command
runs once on the laptop, so logs survive a cap stop. Use `colab exec -s NAME -f ...`
there, never `colab ssh`: `ssh -s NAME` creates the session again when it is gone.

Fail closed. Every GPU type is checked against `RATES` before any `new` (the CLI maps
an unknown `--gpu` to A100). The `Hardware:` of each session in `colab sessions` must
match its plan, or it is stopped and the watch ends. A `new` that fails or times out
is followed by a look at `colab sessions`: a session listed under its name is
attached, an unnamed `[?]` assignment that appeared meanwhile is unassigned through
the CLI's own client. Any exception, SIGTERM, SIGINT or SIGHUP ends in a `finally`
that stops every supervised session. `colab stop` exits 0 even when it did nothing,
so a stop counts only after two successful listings without the name or endpoint;
it is retried with backoff and an unassign. A session has ended by itself only after
3 successful listings in a row without it; a failed call, output that cannot be
parsed, or an empty list while `colab usage` counts assignments is no listing. CLI
output is decoded with `errors="replace"`; a log that cannot be written goes to
stderr and the guard goes on.

Exit codes: 0 every session ended by itself; 2 nothing watched (bad arguments, no
CLI, an attached session not listed); 3 a cap or the floor stopped a session; 4 a
session ran on the wrong accelerator and was stopped; 5 STOP_FAILED, a session may
still be billing (also on stderr; check `colab sessions` now); 6 a crash, signal or
failed `new`, every session stopped.
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

EXIT_OK, EXIT_NOTHING, EXIT_CAPPED, EXIT_WRONG_GPU = 0, 2, 3, 4
EXIT_STOP_FAILED, EXIT_CRASHED = 5, 6
TIMEOUT = 124  # returncode of a call that timed out
MISSES_TO_END = 3
CONFIRM_ABSENT = 2  # listings without the session that confirm a stop

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
    code = EXIT_CRASHED


class NothingWatched(WatchError):
    code = EXIT_NOTHING


class WrongGpu(WatchError):
    code = EXIT_WRONG_GPU


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


def build_specs(new: Sequence[str], attach: Sequence[str], persist: Sequence[str]) -> list[Spec]:
    specs = [parse_spec(t, attach=False) for t in new]
    specs += [parse_spec(t, attach=True) for t in attach]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ValueError(f"a session is given twice: {names}")
    if bad := [item for item in persist if "=" not in item]:
        raise ValueError(f"persist takes NAME=COMMAND: {bad}")
    commands = dict(item.split("=", 1) for item in persist)
    if unknown := set(commands) - set(names):
        raise ValueError(f"persist for sessions not given: {sorted(unknown)}")
    return [Spec(s.name, s.gpu, s.cap, s.attach, s.started, commands.get(s.name)) for s in specs]


def parse_inbox(text: str) -> list[Spec]:
    """Lines `new NAME:GPU:CAP`, `attach NAME:GPU:CAP[:STARTED]`, `persist NAME=CMD`."""
    found: dict[str, list[str]] = {"new": [], "attach": [], "persist": []}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            kind, _, value = line.partition(" ")
            if kind not in found:
                raise ValueError(f"unknown inbox line {line!r}")
            found[kind].append(value.strip())
    return build_specs(found["new"], found["attach"], found["persist"])


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
    stop_backoff: tuple[float, ...] = (5.0, 15.0, 30.0)  # waits after attempts 1, 2, 3
    confirm_polls: int = 4  # listings tried after each stop attempt
    confirm_wait: float = 10.0
    persist_timeout: float = 600.0

    def attempt_s(self, unassign: bool) -> float:
        """One stop attempt that succeeds: stop, maybe unassign, two confirming listings."""
        calls = 1 + unassign + CONFIRM_ABSENT
        return calls * self.cli_timeout + (CONFIRM_ABSENT - 1) * self.confirm_wait

    @property
    def stop_delay(self) -> float:
        """A stop that works on its first retry; a later one may pass the cap."""
        return self.attempt_s(False) + self.stop_backoff[0] + self.attempt_s(True)

    @property
    def margin(self) -> float:
        """Seconds a session can keep spending after a poll found it under its cap."""
        return self.poll + 2 * self.cli_timeout + self.stop_delay


@dataclass
class Session:
    spec: Spec
    started: float
    last_balance: float | None = None
    balance_cu: float = 0.0
    endpoint: str | None = None
    misses: int = 0
    ended: bool = False  # gone from the server, by itself or stopped and confirmed
    stopped_by: str | None = None  # "cap", "floor", "wrong_gpu", "cleanup"
    unconfirmed: bool = False
    persist: Process | None = None
    persist_done: bool = False

    def wall_cu(self, now: float) -> float:
        return max(0.0, now - self.started) / 3600 * self.spec.rate

    def update(self, usage: Usage | None) -> None:
        """Charge this session its share of the balance drop since the last reading."""
        if usage is None:
            return
        if self.last_balance is not None and usage.balance < self.last_balance:
            share = 1.0  # alone: the whole drop is ours (fail closed)
            if usage.assignments > 1 and usage.rate > self.spec.rate:
                share = self.spec.rate / usage.rate
            self.balance_cu += (self.last_balance - usage.balance) * share
        self.last_balance = usage.balance

    def spent(self, now: float) -> float:
        return max(self.wall_cu(now), self.balance_cu)


@dataclass
class Watcher:
    specs: list[Spec]
    floor: float | None
    log_path: Path
    run: Run
    colab: Path = COLAB
    timing: Timing = field(default_factory=Timing)
    persist_at: float = 0.9
    ready_dir: Path | None = None
    inbox: Path | None = None
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    spawn: Spawn | None = None
    sessions: list[Session] = field(default_factory=list)
    start_balance: float | None = None
    balance: float | None = None  # the latest reading

    # -- CLI -----------------------------------------------------------------------

    def colab_call(self, *args: str, timeout: float | None = None) -> tuple[int, str]:
        return self.run([str(self.colab), *args], timeout or self.timing.cli_timeout)

    def usage(self) -> Usage | None:
        code, text = self.colab_call("usage")
        usage = parse_usage(text) if code == 0 else None
        if usage is not None:
            self.balance = usage.balance
        return usage

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
        line = json.dumps(record, ensure_ascii=False)
        print(line, flush=True)
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as sink:
                sink.write(line + "\n")
        except OSError as error:  # the guard goes on without its log
            print(f"log write failed: {error}; {line}", file=sys.stderr, flush=True)
        if event in ("STOP_FAILED", "ALERT"):
            print(f"{event}: {fields.get('message', '')}", file=sys.stderr, flush=True)
        return record

    # -- adding sessions -------------------------------------------------------------

    def start(self) -> None:
        usage = self.usage()
        self.start_balance = usage.balance if usage else None
        self.log(
            "start",
            balance=self.start_balance,
            assignments=usage.assignments if usage else None,
            floor=self.floor,
            margin_s=self.timing.margin,
            sessions=[asdict(s) for s in self.specs],
        )
        self.add(self.specs)

    def add(self, specs: Sequence[Spec]) -> None:
        taken = {s.spec.name for s in self.sessions if not s.ended}
        if clash := taken & {s.name for s in specs}:
            raise NothingWatched(f"already watched: {sorted(clash)}")
        for spec in specs:
            if spec.attach:
                self.attach(spec)
            else:
                self.new(spec)

    def attach(self, spec: Spec) -> None:
        listed = self.listing()
        match = next((s for s in listed or [] if s.name == spec.name), None)
        if match is None:
            raise NothingWatched(f"{spec.name} is not listed by `colab sessions`")
        started = spec.started or self.clock()
        session = Session(spec, started, self.balance, endpoint=match.endpoint)
        self.sessions.append(session)
        self.log("attach", session=spec.name, endpoint=match.endpoint, started=started)
        self.check_gpu(session, match)
        self.ready(session)

    def new(self, spec: Spec) -> None:
        before = self.listing()
        known = {s.endpoint for s in before or []}
        session = Session(spec, self.clock(), self.balance)
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
            self.ready(session)
            return
        orphans = [s for s in listed or [] if s.name == "?" and s.endpoint not in known]
        for orphan in orphans:
            self.log("orphan", session=spec.name, endpoint=orphan.endpoint)
            self.unassign(orphan.endpoint)
        if listed is None or not all(self.confirmed_gone(o.endpoint, None) for o in orphans):
            session.unconfirmed = True
            self.log("STOP_FAILED", message=f"{spec.name}: an assignment from `new` may bill")
        else:
            session.ended = True
        raise WatchError(f"colab new -s {spec.name} failed (code {code}): {text[-300:]}")

    def check_gpu(self, session: Session, listed: Listed) -> None:
        if listed.hardware != session.spec.gpu:
            message = f"{session.spec.name} runs on {listed.hardware}, planned {session.spec.gpu}"
            self.log("wrong_gpu", session=session.spec.name, message=message)
            self.stop(session, "wrong_gpu")
            raise WrongGpu(message)

    def ready(self, session: Session) -> None:
        if self.ready_dir is not None:
            self.ready_dir.mkdir(parents=True, exist_ok=True)
            path = self.ready_dir / f"{session.spec.name}.ready"
            path.write_text(f"{session.spec.name} {session.spec.gpu}\n", encoding="utf-8")

    def read_inbox(self) -> None:
        if self.inbox is None or not self.inbox.is_dir():
            return
        waiting = [p for p in self.inbox.iterdir() if p.suffix not in (".taken", ".rejected")]
        for path in sorted(waiting):
            try:
                specs = parse_inbox(path.read_text(encoding="utf-8", errors="replace"))
            except ValueError as error:
                path.rename(path.with_name(path.name + ".rejected"))
                self.log("ALERT", message=f"inbox {path.name} rejected: {error}")
                continue
            path.rename(path.with_name(path.name + ".taken"))
            self.log("inbox", file=path.name, sessions=[asdict(s) for s in specs])
            self.add(specs)

    # -- stop ------------------------------------------------------------------------

    def confirmed_gone(self, endpoint: str | None, name: str | None) -> bool:
        """Two successful listings without the session; a listing with it ends the wait."""
        absent = 0
        for poll in range(self.timing.confirm_polls):
            if poll:
                self.sleep(self.timing.confirm_wait)
            listed = self.listing()
            if listed is None:
                continue
            if any(s.endpoint == endpoint or (name and s.name == name) for s in listed):
                return False
            absent += 1
            if absent == CONFIRM_ABSENT:
                return True
        return False

    def unassign(self, endpoint: str) -> None:
        python = self.colab.parent / "python"
        code, text = self.run([str(python), "-c", UNASSIGN, endpoint], self.timing.cli_timeout)
        self.log("unassign", endpoint=endpoint, code=code, output=text[-300:])

    def stop(self, session: Session, reason: str) -> bool:
        name = session.spec.name
        for attempt, pause in enumerate(self.timing.stop_backoff, start=1):
            code, text = self.colab_call("stop", "-s", name)
            if session.endpoint and attempt > 1:
                self.unassign(session.endpoint)  # the named stop did not take
            if self.confirmed_gone(session.endpoint, name):
                session.ended, session.stopped_by = True, reason
                self.log("stopped", session=name, reason=reason, attempt=attempt, code=code)
                return True
            self.log("stop_unconfirmed", session=name, attempt=attempt, output=text[-300:])
            self.sleep(pause)
        session.unconfirmed = True
        self.log("STOP_FAILED", session=name, message=f"{name} may still be billing: stop it")
        return False

    # -- poll ------------------------------------------------------------------------

    def live(self) -> list[Session]:
        return [s for s in self.sessions if not s.ended and not s.unconfirmed]

    def cycle(self) -> None:
        now, usage = self.clock(), self.usage()
        listed = self.listing(usage)
        margin_h = self.timing.margin / 3600
        report: dict[str, Any] = {
            "balance": usage.balance if usage else None,
            "rate": usage.rate if usage else None,
            "assignments": usage.assignments if usage else None,
        }
        for session in self.live():
            name = session.spec.name
            session.update(usage)
            spent = session.spent(now)
            match = None if listed is None else next((s for s in listed if s.name == name), None)
            if listed is not None:
                session.misses = 0 if match else session.misses + 1
            report[name] = {
                "elapsed_s": round(now - session.started),
                "spent": round(spent, 3),
                "wall_cu": round(session.wall_cu(now), 3),
                "balance_cu": round(session.balance_cu, 3),
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
        if spent >= self.persist_at * spec.cap or spent + spec.rate * lead_h >= spec.cap:
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
                self.read_inbox()
        except Interrupted as stop:
            self.log("signal", signum=stop.signum)
            code = EXIT_CRASHED
        except WatchError as error:
            self.log("error", kind=type(error).__name__, message=str(error))
            code = error.code
        except BaseException as error:  # fail closed on anything: the finally stops sessions
            self.log("error", kind=type(error).__name__, message=repr(error))
            code = EXIT_CRASHED
        finally:
            with _SignalsIgnored():
                self.cleanup()
        usage = self.usage()
        if any(s.unconfirmed for s in self.sessions):
            code = EXIT_STOP_FAILED
        elif code == EXIT_OK and any(s.stopped_by in ("cap", "floor") for s in self.sessions):
            code = EXIT_CAPPED
        drop = None
        if usage is not None and self.start_balance is not None:
            drop = round(self.start_balance - usage.balance, 3)
        now = self.clock()
        self.log(
            "exit",
            code=code,
            balance=usage.balance if usage else None,
            balance_drop=drop,
            sessions={
                s.spec.name: {
                    "stopped_by": s.stopped_by,
                    "unconfirmed": s.unconfirmed,
                    "spent": round(s.spent(now), 3),
                    "wall_cu": round(s.wall_cu(now), 3),
                    "balance_cu": round(s.balance_cu, 3),
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
        done = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # the CLI can print bytes that are not UTF-8
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TIMEOUT, f"timed out after {timeout:.0f} s"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return 1, f"{type(error).__name__}: {error}"
    return done.returncode, done.stdout + done.stderr


def _spawn_shell(command: str) -> Process:
    return subprocess.Popen(command, shell=True)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--new", action="append", default=[], metavar="NAME:GPU:CAP")
    parser.add_argument("--attach", action="append", default=[], metavar="NAME:GPU:CAP[:START]")
    parser.add_argument("--persist", action="append", default=[], metavar="NAME=COMMAND")
    parser.add_argument("--persist-at", type=float, default=0.9, help="fraction of the cap")
    parser.add_argument("--floor", type=float, help="stop everything below this balance")
    parser.add_argument("--ready-dir", type=Path, help="<NAME>.ready once on the right GPU")
    parser.add_argument("--inbox", type=Path, help="directory read for sessions added later")
    parser.add_argument("--log", type=Path, required=True, help="JSON lines, one per event")
    parser.add_argument("--colab", type=Path, default=COLAB, help="the colab CLI ($COLAB_CLI)")
    parser.add_argument("--poll", type=float, default=60.0, help="seconds between polls")
    parser.add_argument("--no-inhibit", action="store_true", help="do not hold off suspend")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    try:
        specs = build_specs(args.new, args.attach, args.persist)
        if not specs:
            raise ValueError("nothing to watch: pass --new or --attach")
        if not 0 < args.persist_at <= 1:
            raise ValueError("--persist-at is a fraction of the cap, in (0, 1]")
    except ValueError as error:
        print(f"cu_watch: {error}", file=sys.stderr)
        return EXIT_NOTHING
    if not args.colab.exists():
        print(f"cu_watch: no colab CLI at {args.colab}; pass --colab", file=sys.stderr)
        return EXIT_NOTHING
    if not args.no_inhibit and os.environ.get("CU_WATCH_INHIBITED") != "1":
        inhibit = shutil.which("systemd-inhibit")
        if inhibit is None:
            print("cu_watch: no systemd-inhibit; pass --no-inhibit to run anyway", file=sys.stderr)
            return EXIT_NOTHING
        os.environ["CU_WATCH_INHIBITED"] = "1"
        os.execv(
            inhibit,
            [
                inhibit,
                "--what=sleep:idle:handle-lid-switch",
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
        persist_at=args.persist_at,
        ready_dir=args.ready_dir,
        inbox=args.inbox,
    )
    return watcher.watch()


if __name__ == "__main__":
    sys.exit(main())
