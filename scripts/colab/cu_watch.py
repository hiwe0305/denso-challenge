#!/usr/bin/env python3
"""Stop paid Colab sessions before they pass their CU cap: one watcher per session.

Two kinds of process, on the laptop whose `colab` CLI owns the sessions, sharing one
fresh registry directory per batch. One batch per account at a time: the guard stops
every assignment its registry does not know, so it refuses to start while another
guard holds `~/.cache/cu_watch/guard.lock` ($CU_WATCH_LOCK).

- `session`: one per Colab session. It creates (`--new`) or takes over (`--attach`)
  one session, meters it, and stops it at its cap. One session's slow `new` or stuck
  stop never delays another session's cap check.
- `guard`: one per batch, the backstop. It stops every session when the account's
  real balance falls to `--floor`, and any assignment (named or `[?]`) whose endpoint
  no live session watcher has registered, after `--grace-polls` polls.

Launch the guard first, then each session watcher, in a new registry; start a job only
once its `.ready` file exists and the guard's heartbeat is younger than two polls:

    R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R
    nohup setsid bash -c 'trap "" TERM HUP INT
        python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 \\
            --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
    nohup setsid bash -c 'trap "" TERM HUP INT
        python3 scripts/colab/cu_watch.py session --registry "$0" --new \\
            --name da30-stage1 --gpu L4 --cap 4 --floor 14 \\
            --persist "colab exec -s da30-stage1 -f p.py" \\
            --log "$0/da30-stage1.jsonl"; echo "exit $?"' $R \\
        < /dev/null > $R/da30-stage1.out 2>&1 &
    ( until [ -f $R/da30-stage1.ready ]; do
          grep -q '^exit ' $R/da30-stage1.out && exit 1; sleep 5; done
      [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ]
    ) && echo READY || echo "NOT READY: do not start the job"
    # only after READY start the job on the VM

A session added later (DA-26's eval server) gets its own `session` watcher in the
same registry; if the guard has exited meanwhile, start a new one there first (a
guard counts only entries that beat after it started).

The `trap` keeps each wrapper alive when its process group is killed, so it still
writes "exit N"; Python installs its own handlers over the inherited ignore.

Identity. A session is tracked by its endpoint, never by its name alone: the CLI keeps
names only locally and lists a session whose name it lost as `[?] <endpoint>`. With
`--new`, the watcher takes a trusted listing, runs `colab new` in the background while
holding `<registry>/new.lock` (so no two watchers create at once), and binds the
endpoint that appears in the listings under its own name or as `[?]`; a session that
appears under another name is never its own. If `new` fails, times out or is
interrupted, every such assignment that appeared meanwhile is stopped. A name already
watched by a live watcher in the registry is refused. `--attach` finds
the session by `--endpoint` or by name, and needs its start time (`--started` ISO
8601, or `--started-min-ago`). Stops go through the CLI's own client by endpoint
(`colab stop` needs the local name).

Trust. A listing counts only when `colab usage` succeeded in the same cycle, `colab
sessions` exited 0, every line parses, and it lists at least as many assignments as
`usage` counts: on an auth failure the CLI prints "No active sessions" and exits 0. A
session has ended only after 3 trusted listings in a row without its endpoint, and is
then stopped by endpoint anyway; when the guard stopped it, the watcher says so and
exits 3 (floor) or 6. A stop counts after 2 trusted listings without the
endpoint; until then it is retried every poll, with STOP_FAILED on stderr from the
third try, until it works or a signal says to give up (exit 5).

Meter. The larger of two. (1) Wall clock: `time.time()` since the session started,
counting only forward moves (a clock set back neither lowers it nor stalls it), times
its GPU's rate (`RATES`); it keeps counting through a laptop suspend, as Colab's
billing does. The `new` and persist timeouts use the same clock. (2) Balance:
each drop of `colab usage`'s balance, in full while the account has one assignment,
in proportion to the session's rate over the account's usage rate while more run.
A session is stopped when spend + rate x margin reaches its cap (`Timing.margin`: a
poll, its two CLI calls, and an unassign that works on its second try). Its
`--persist` command runs in the background at `--persist-at` of the cap, or earlier so
it has `persist_timeout` to finish; its whole process group is killed after that. Use
`colab exec -s NAME -f ...` there, never `colab ssh`: `ssh -s NAME` creates the
session again.

Fail closed. A GPU type is checked against `RATES` before any `new` (the CLI maps an
unknown `--gpu` to A100), and the listed `Hardware:` must match the plan. An exception
from a CLI call is a failed call. Any other exception, and the first SIGTERM, SIGINT
or SIGHUP, ends in a `finally` that stops the session; later signals are deferred.
CLI output is decoded with `errors="replace"`; a log that cannot be written goes to
stderr.

Exit codes: 0 the session ended (or, for the guard, the batch is done); 2 nothing
watched (bad arguments, no CLI, an attached session not listed); 3 a cap or the floor
stopped it; 4 it ran on the wrong accelerator and was stopped; 5 STOP_FAILED, it may
still be billing (check `colab sessions` now); 6 a crash, a signal or a failed `new`,
and every assignment it made was stopped.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
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
CONFIRM_ABSENT = 2  # trusted listings without the endpoint that confirm a stop
LOUD_AFTER = 3  # stop rounds before STOP_FAILED is raised on stderr
LIVE_STATES = ("starting", "running")
GUARD_LOCK = Path(
    os.environ.get("CU_WATCH_LOCK", Path.home() / ".cache" / "cu_watch" / "guard.lock")
)

# Unassign an endpoint with the CLI's own client: `colab stop` needs a local name.
UNASSIGN = "import sys; from colab_cli.common import state; state.client.unassign(sys.argv[1])"

# (argv, timeout in s) -> (returncode, stdout + stderr)
Run = Callable[[Sequence[str], float], "tuple[int, str]"]


class Process(Protocol):
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...


Spawn = Callable[[Sequence[str]], Process]

_LINE = re.compile(r"^\[(?P<name>[^\]]*)\] (?P<endpoint>\S+) \| Hardware: (?P<hardware>[^|]+?) \|")
_BALANCE = re.compile(r"Current balance:\s*([\d.]+)")
_RATE = re.compile(r"Usage rate:\s*([\d.]+)")
_ASSIGNMENTS = re.compile(r"Active assignments:\s*(\d+)")


class WatchError(Exception):
    code = EXIT_CRASHED


class NothingWatched(WatchError):
    code = EXIT_NOTHING


class Capped(WatchError):
    code = EXIT_CAPPED


class WrongGpu(WatchError):
    code = EXIT_WRONG_GPU


class GuardStopped(WatchError):
    """The guard unassigned the session: at the floor (3) or with no live watcher (6)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"the guard stopped the session: {reason}")
        self.code = EXIT_CAPPED if reason == "floor" else EXIT_CRASHED


class Interrupted(BaseException):
    """Raised by SIGTERM, SIGHUP or SIGINT so the watcher stops its session first."""

    def __init__(self, signum: int) -> None:
        super().__init__(signal.Signals(signum).name)
        self.signum = signum


# -- what the CLI prints -----------------------------------------------------------------


@dataclass(frozen=True)
class Listed:
    name: str  # "?" when the CLI lost the local name
    endpoint: str
    hardware: str


def parse_sessions(text: str) -> list[Listed] | None:
    """`colab sessions`, or None for an output this parser does not know."""
    listed, empty = [], False
    for line in filter(None, (raw.strip() for raw in text.splitlines())):
        if match := _LINE.match(line):
            listed.append(Listed(match["name"], match["endpoint"], match["hardware"].strip()))
        elif line.startswith("[colab]"):
            empty = empty or "No active sessions" in line
        else:
            return None
    return listed if listed or empty else None


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
class Snapshot:
    """A listing that can be trusted, with the usage read in the same cycle."""

    usage: Usage
    listed: list[Listed]

    def find(self, endpoint: str | None) -> Listed | None:
        return next((s for s in self.listed if s.endpoint == endpoint), None)


@dataclass(frozen=True)
class Timing:
    poll: float = 60.0
    cli_timeout: float = 60.0
    new_timeout: float = 900.0
    new_poll: float = 15.0  # listings while `colab new` runs
    confirm_wait: float = 10.0  # between the first stop rounds; later ones wait a poll
    persist_timeout: float = 600.0

    @property
    def margin(self) -> float:
        """Seconds a session can keep billing after a cycle found it under its cap: the
        poll and its usage + sessions calls, an unassign, and one more round of the three
        in case the first unassign did not take."""
        cycle = 3 * self.cli_timeout
        return self.poll + cycle + self.confirm_wait + cycle


@dataclass
class Cli:
    run: Run
    log_path: Path
    colab: Path = COLAB
    timeout: float = 60.0

    def call(self, argv: Sequence[str], timeout: float | None = None) -> tuple[int, str]:
        """A CLI call; an exception from the runner is a failed call, not a crash."""
        try:
            return self.run(argv, timeout or self.timeout)
        except Exception as error:
            return 1, f"cli_error {type(error).__name__}: {error}"

    def usage(self) -> Usage | None:
        code, text = self.call([str(self.colab), "usage"])
        return parse_usage(text) if code == 0 else None

    def snapshot(self) -> tuple[Usage | None, Snapshot | None]:
        """The usage, and a trusted listing or None."""
        usage = self.usage()
        if usage is None:
            return None, None  # without usage an empty listing may be an auth failure
        code, text = self.call([str(self.colab), "sessions"])
        listed = parse_sessions(text) if code == 0 else None
        if listed is None or len(listed) < usage.assignments:
            return usage, None
        return usage, Snapshot(usage, listed)

    def unassign(self, endpoint: str) -> int:
        python = self.colab.parent / "python"
        code, text = self.call([str(python), "-c", UNASSIGN, endpoint])
        self.log("unassign", endpoint=endpoint, code=code, output=text[-300:])
        return code

    def log(self, event: str, **fields: Any) -> None:
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


# -- registry: what the guard may leave running ---------------------------------------


@dataclass(frozen=True)
class Entry:
    name: str
    pid: int
    endpoint: str | None
    state: str  # starting, running, stopping, stopped, stop_failed
    beat: float  # the watcher's clock at its last heartbeat


def write_entry(registry: Path, name: str, **fields: Any) -> None:
    tmp = registry / f".{name}.json.tmp"
    tmp.write_text(json.dumps({"name": name, **fields}), encoding="utf-8")
    os.replace(tmp, registry / f"{name}.json")


def read_entries(registry: Path) -> tuple[list[Entry], list[str]]:
    """The entries, and the files that could not be read."""
    entries, bad = [], []
    for path in sorted(registry.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries.append(
                Entry(
                    str(data["name"]),
                    int(data["pid"]),
                    data.get("endpoint"),
                    str(data["state"]),
                    float(data["beat"]),
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            bad.append(path.name)
    return entries, bad


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# -- one session -------------------------------------------------------------------------


@dataclass(frozen=True)
class Spec:
    name: str
    gpu: str
    cap: float
    attach: bool = False
    started: float | None = None  # epoch seconds, --attach only
    endpoint: str | None = None  # --attach only
    persist: str | None = None

    @property
    def rate(self) -> float:
        return RATES[self.gpu]


def check_spec(spec: Spec) -> None:
    """Refuse a plan before anything is created or watched."""
    if spec.gpu not in RATES:
        raise ValueError(f"unknown GPU {spec.gpu!r}; rates are known for {sorted(RATES)}")
    if not re.fullmatch(r"[\w.-]+", spec.name):
        raise ValueError(f"{spec.name!r}: session names are letters, digits, '.', '_', '-'")
    if spec.cap <= 0:
        raise ValueError("the cap must be positive")
    if spec.attach and spec.started is None:
        raise ValueError("--attach needs --started or --started-min-ago: spend before it counts")
    if not spec.attach and (spec.started is not None or spec.endpoint is not None):
        raise ValueError("--started, --started-min-ago and --endpoint are for --attach")


@dataclass
class Watcher:
    spec: Spec
    cli: Cli
    registry: Path
    floor: float | None = None
    timing: Timing = field(default_factory=Timing)
    persist_at: float = 0.9
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    spawn: Spawn | None = None
    alive: Callable[[int], bool] = field(default=lambda pid: pid_alive(pid))
    registered: bool = False
    started: float | None = None
    endpoint: str | None = None
    claimed: set[str] = field(default_factory=set)  # every assignment this watcher stops
    ticks: float = 0.0  # what now() returns
    last_clock: float | None = None
    last_balance: float | None = None
    start_balance: float | None = None
    balance_cu: float = 0.0
    misses: int = 0
    persist: Process | None = None
    persist_started: float = 0.0
    persist_done: bool = False

    # -- meter ---------------------------------------------------------------------------

    def now(self) -> float:
        """Wall time that only moves forward: each reading adds what the clock moved on
        since the last one, and nothing when it was set back. A suspend still counts, as
        Colab still bills it."""
        reading = self.clock()
        if self.last_clock is None:
            self.ticks = reading  # starts as the clock, so --started compares with it
        else:
            self.ticks += max(0.0, reading - self.last_clock)
        self.last_clock = reading
        return self.ticks

    def wall_cu(self) -> float:
        if self.started is None:
            return 0.0
        return max(0.0, self.now() - self.started) / 3600 * self.spec.rate

    def meter(self, usage: Usage | None) -> float:
        """Charge this session its share of the balance drop; return its spend."""
        if usage is not None:
            if self.last_balance is not None and usage.balance < self.last_balance:
                share = 1.0  # alone: the whole drop is ours (fail closed)
                if usage.assignments > 1 and usage.rate > self.spec.rate:
                    share = self.spec.rate / usage.rate
                self.balance_cu += (self.last_balance - usage.balance) * share
            self.last_balance = usage.balance
        return max(self.wall_cu(), self.balance_cu)

    def over(self, spent: float, lead_s: float = 0.0) -> bool:
        return spent + self.spec.rate * (self.timing.margin + lead_s) / 3600 >= self.spec.cap

    def check_floor(self, usage: Usage | None) -> None:
        if self.floor is None or usage is None:
            return
        rate = max(usage.rate, self.spec.rate)
        if usage.balance - rate * self.timing.margin / 3600 <= self.floor:
            raise Capped(f"balance {usage.balance} is at the floor {self.floor}")

    # -- registry ------------------------------------------------------------------------

    def register(self, state: str) -> None:
        self.registered = True
        write_entry(
            self.registry,
            self.spec.name,
            pid=os.getpid(),
            endpoint=self.endpoint,
            state=state,
            beat=self.clock(),
            gpu=self.spec.gpu,
            cap=self.spec.cap,
        )

    @contextmanager
    def new_lock(self) -> Iterator[None]:
        with (self.registry / "new.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    # -- start -----------------------------------------------------------------------------

    def trusted(self) -> tuple[Usage, Snapshot] | None:
        for attempt in range(3):
            if attempt:
                self.sleep(self.timing.new_poll)
            usage, snap = self.cli.snapshot()
            if usage is not None and snap is not None:
                return usage, snap
        return None

    def check_gpu(self, listed: Listed | None) -> None:
        if listed is not None and listed.hardware != self.spec.gpu:
            raise WrongGpu(f"{self.spec.name} runs on {listed.hardware}, planned {self.spec.gpu}")

    def attach(self) -> None:
        found = self.trusted()
        if found is None:
            raise NothingWatched("no trusted listing to attach from")
        usage, snap = found
        spec = self.spec
        matches = [
            s
            for s in snap.listed
            if (s.endpoint == spec.endpoint if spec.endpoint else s.name == spec.name)
        ]
        if len(matches) != 1:
            raise NothingWatched(f"{spec.name}: {len(matches)} listed sessions match")
        self.endpoint = matches[0].endpoint
        self.claimed.add(self.endpoint)
        self.started = spec.started
        self.last_balance = self.start_balance = usage.balance
        self.cli.log("attach", session=spec.name, endpoint=self.endpoint, started=self.started)
        self.check_gpu(matches[0])

    def create(self) -> None:
        with self.new_lock():
            found = self.trusted()
            if found is None:  # without it every old `[?]` would look like ours
                raise WatchError("no trusted listing before `colab new`; nothing created")
            usage, before = found
            known = {s.endpoint for s in before.listed}
            self.started = self.now()
            self.last_balance = self.start_balance = usage.balance
            argv = [str(self.cli.colab), "new", "-s", self.spec.name, "--gpu", self.spec.gpu]
            process = (self.spawn or spawn_process)(argv)
            self.cli.log("new", session=self.spec.name, known=sorted(known))
            try:
                code = self.await_new(process, known)
                if code != 0 or self.endpoint is None:
                    raise WatchError(f"colab new exited {code}, endpoint {self.endpoint}")
            except BaseException:
                if process.poll() is None:
                    process.kill()
                self.claim_fresh(known)  # still under the lock: what appears now is ours
                raise

    def take_fresh(self, snap: Snapshot, known: set[str]) -> None:
        """Claim what appeared since `known` under this name or as `[?]`; never a
        session another process named."""
        fresh = [
            s for s in snap.listed if s.endpoint not in known and s.name in (self.spec.name, "?")
        ]
        if not fresh:
            return
        new = {s.endpoint for s in fresh} - self.claimed
        if new:
            self.claimed |= new
            self.cli.log("claimed", session=self.spec.name, endpoints=sorted(new))
        if self.endpoint is None:
            named = [s for s in fresh if s.name == self.spec.name]
            pick = named[0] if named else fresh[0] if len(fresh) == 1 else None
            if pick is not None:
                self.endpoint = pick.endpoint
                self.cli.log("bound", session=self.spec.name, endpoint=pick.endpoint)
                self.register("starting")

    def await_new(self, process: Process, known: set[str]) -> int:
        assert self.started is not None
        deadline, exited = self.started + self.timing.new_timeout, 0
        while True:
            code = process.poll()
            usage, snap = self.cli.snapshot()
            spent = self.meter(usage)
            self.register("starting")
            if snap is not None:
                self.take_fresh(snap, known)
                self.check_gpu(snap.find(self.endpoint))
            if code is not None:
                exited += 1
                if self.endpoint is not None or exited > MISSES_TO_END:
                    return code
            self.check_floor(usage)
            if self.over(spent):
                raise Capped(f"{self.spec.name} reached its cap during `colab new`")
            if self.now() >= deadline:
                raise WatchError(f"colab new did not finish in {self.timing.new_timeout:.0f} s")
            self.sleep(self.timing.new_poll)

    def claim_fresh(self, known: set[str]) -> None:
        """After a failed `new`: look for assignments that landed late."""
        for look in range(CONFIRM_ABSENT + 1):
            if look:
                self.sleep(self.timing.new_poll)
            _, snap = self.cli.snapshot()
            if snap is not None:
                self.take_fresh(snap, known)

    def ready(self) -> None:
        path = self.registry / f"{self.spec.name}.ready"
        path.write_text(f"{self.spec.name} {self.spec.gpu} {self.endpoint}\n", encoding="utf-8")

    # -- watch ---------------------------------------------------------------------------

    def loop(self) -> None:
        """Poll until the session has ended; a cap, the floor or a wrong GPU raises."""
        while True:
            self.sleep(self.timing.poll)
            usage, snap = self.cli.snapshot()
            spent = self.meter(usage)
            self.register("running")
            listed = None if snap is None else snap.find(self.endpoint)
            if snap is not None:
                self.misses = 0 if listed else self.misses + 1
            self.cli.log(
                "poll",
                session=self.spec.name,
                spent=round(spent, 3),
                wall_cu=round(self.wall_cu(), 3),
                balance_cu=round(self.balance_cu, 3),
                cap=self.spec.cap,
                balance=usage.balance if usage else None,
                listed=None if snap is None else listed is not None,
                misses=self.misses,
            )
            self.check_gpu(listed)
            if self.misses >= MISSES_TO_END:
                note = self.registry / f"guard-stopped-{self.endpoint}"
                if note.exists():
                    raise GuardStopped(note.read_text(encoding="utf-8").strip())
                self.cli.log("ended", session=self.spec.name, spent=round(spent, 3))
                return
            self.check_floor(usage)
            self.persist_step(spent)
            if self.over(spent):
                raise Capped(f"{self.spec.name} reached its cap at {spent:.3f} CU")

    def persist_step(self, spent: float) -> None:
        if self.spec.persist is None or self.persist_done:
            return
        if self.persist is not None:
            code = self.persist.poll()
            if code is not None:
                self.persist_done = True
                self.cli.log("persisted", session=self.spec.name, code=code)
            elif self.now() - self.persist_started > self.timing.persist_timeout:
                self.persist.kill()
                self.persist_done = True
                self.cli.log("ALERT", message=f"{self.spec.name}: persist killed at its timeout")
            return
        if spent >= self.persist_at * self.spec.cap or self.over(
            spent, self.timing.persist_timeout
        ):
            self.persist = (self.spawn or spawn_process)(["bash", "-c", self.spec.persist])
            self.persist_started = self.now()
            self.cli.log("persist", session=self.spec.name, spent=round(spent, 3))

    def stop(self, reason: str, deferred: _Deferred) -> bool:
        """Unassign every claimed endpoint until trusted listings confirm it is gone."""
        if not self.claimed:
            return True
        absent = dict.fromkeys(sorted(self.claimed), 0)
        rounds = 0
        while True:
            for endpoint, count in absent.items():
                if count == 0:
                    self.cli.unassign(endpoint)
            rounds += 1
            self.sleep(self.timing.confirm_wait if rounds < LOUD_AFTER else self.timing.poll)
            _, snap = self.cli.snapshot()
            if snap is not None:
                for endpoint in absent:
                    absent[endpoint] = 0 if snap.find(endpoint) else absent[endpoint] + 1
            self.register("stopping")
            if all(count >= CONFIRM_ABSENT for count in absent.values()):
                break
            if rounds >= LOUD_AFTER:
                left = [e for e, count in absent.items() if count < CONFIRM_ABSENT]
                message = f"{self.spec.name}: {left} may still be billing; stop it by hand"
                self.cli.log("STOP_FAILED", rounds=rounds, message=message)
                if deferred.count:  # a signal now means: give up, a human takes over
                    return False
        self.cli.log("stopped", session=self.spec.name, reason=reason, endpoints=list(absent))
        return True

    def refuse_duplicate(self) -> None:
        entries, _ = read_entries(self.registry)
        for e in entries:
            if e.name == self.spec.name and e.state in LIVE_STATES and self.alive(e.pid):
                raise NothingWatched(f"{e.name} is already watched by pid {e.pid}")

    def run(self, outcome: list[Any]) -> None:
        """The watch; each handler records its exit code first, so a signal that lands
        inside a handler cannot replace it."""
        try:
            self.registry.mkdir(parents=True, exist_ok=True)
            self.refuse_duplicate()
            (self.registry / f"{self.spec.name}.ready").unlink(missing_ok=True)
            self.register("starting")
            self.cli.log("start", session=self.spec.name, margin_s=self.timing.margin)
            self.attach() if self.spec.attach else self.create()
            self.register("running")
            self.ready()
            self.loop()
        except Interrupted as stop:
            outcome[:] = [EXIT_CRASHED, "signal"]
            self.cli.log("signal", signum=stop.signum)
        except WatchError as error:
            outcome[:] = [error.code, type(error).__name__]
            self.cli.log("error", kind=type(error).__name__, message=str(error))
        except BaseException as error:  # fail closed on anything
            outcome[:] = [EXIT_CRASHED, "crash"]
            self.cli.log("error", kind=type(error).__name__, message=repr(error))

    def watch(self) -> int:
        outcome: list[Any] = [EXIT_OK, "ended"]
        try:
            self.run(outcome)
        except BaseException as late:  # a signal inside a handler: keep its code
            if outcome[0] == EXIT_OK:
                outcome[:] = [EXIT_CRASHED, type(late).__name__]
        finally:
            with _Deferred() as deferred:
                code = self.finish(outcome[0], outcome[1], deferred)
        return code

    def finish(self, code: int, reason: str, deferred: _Deferred) -> int:
        confirmed = False
        try:
            confirmed = self.stop(reason, deferred)
            if self.persist is not None and self.persist.poll() is None:
                self.persist.kill()
        except BaseException as error:
            self.cli.log("error", kind=type(error).__name__, message=repr(error))
        if not confirmed:
            code = EXIT_STOP_FAILED
        try:
            if self.registered:  # a refused duplicate leaves the other watcher's entry
                self.register("stopped" if confirmed else "stop_failed")
            usage = self.cli.usage()
            self.cli.log(
                "exit",
                session=self.spec.name,
                code=code,
                reason=reason,
                endpoint=self.endpoint,
                spent=round(self.meter(usage), 3),
                wall_cu=round(self.wall_cu(), 3),
                balance_cu=round(self.balance_cu, 3),
                balance=usage.balance if usage else None,
                balance_drop=(
                    round(self.start_balance - usage.balance, 3)
                    if usage is not None and self.start_balance is not None
                    else None
                ),
            )
        except BaseException as error:
            print(f"cu_watch: exit log failed: {error!r}", file=sys.stderr, flush=True)
        return code


# -- the batch guard ---------------------------------------------------------------------


@dataclass
class Guard:
    cli: Cli
    registry: Path
    floor: float | None
    allow: frozenset[str] = frozenset()
    grace: int = 2
    stale: float = 600.0
    timing: Timing = field(default_factory=Timing)
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    alive: Callable[[int], bool] = pid_alive
    lock_path: Path = GUARD_LOCK
    unregistered: dict[str, int] = field(default_factory=dict)
    watchers_seen: bool = False
    floored: bool = False
    started_at: float = 0.0

    def allowed(self) -> tuple[set[str], bool]:
        """Endpoints of live watchers, and whether any watcher is live."""
        entries, bad = read_entries(self.registry)
        for name in bad:
            self.cli.log("ALERT", message=f"registry file {name} unreadable: not allowed")
        now = self.clock()
        live = [
            e
            for e in entries
            if e.state in LIVE_STATES and self.alive(e.pid) and now - e.beat <= self.stale
        ]
        # an entry left from an earlier run is no watcher of this guard's
        self.watchers_seen = self.watchers_seen or any(e.beat >= self.started_at for e in entries)
        return {e.endpoint for e in live if e.endpoint} | set(self.allow), bool(live)

    def cycle(self) -> int | None:
        self.registry.mkdir(parents=True, exist_ok=True)
        (self.registry / "guard.beat").write_text(f"{self.clock()}\n", encoding="utf-8")
        usage, snap = self.cli.snapshot()
        if usage is None or snap is None:
            self.cli.log("untrusted", usage=usage is not None)
            return None
        allowed, any_live = self.allowed()
        listed = {s.endpoint: s for s in snap.listed}
        for gone in set(self.unregistered) - set(listed):
            del self.unregistered[gone]
        margin_h = self.timing.margin / 3600
        if self.floor is not None and usage.balance - usage.rate * margin_h <= self.floor:
            self.floored = True
            targets = sorted(listed)
            self.cli.log("floor", balance=usage.balance, floor=self.floor)
        else:
            for endpoint in listed:
                if endpoint in allowed:
                    self.unregistered.pop(endpoint, None)
                else:
                    self.unregistered[endpoint] = self.unregistered.get(endpoint, 0) + 1
            targets = sorted(e for e, n in self.unregistered.items() if n > self.grace)
        for endpoint in targets:
            why = "floor" if self.floored else "no live watcher"
            message = f"stopping {listed[endpoint].name} {endpoint}: {why}"
            self.cli.log("ALERT", endpoint=endpoint, message=message)
            (self.registry / f"guard-stopped-{endpoint}").write_text(why + "\n", encoding="utf-8")
            self.cli.unassign(endpoint)
        self.cli.log(
            "poll",
            balance=usage.balance,
            rate=usage.rate,
            listed=sorted(listed),
            allowed=sorted(allowed),
            unregistered=self.unregistered,
        )
        if self.floored and not listed:
            return EXIT_CAPPED
        if self.watchers_seen and not any_live and not listed:
            return EXIT_OK
        return None

    def run(self, outcome: list[int]) -> None:
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    outcome[0] = EXIT_NOTHING
                    self.cli.log("error", message=f"another guard holds {self.lock_path}")
                    return
                self.registry.mkdir(parents=True, exist_ok=True)
                self.started_at = self.clock()
                self.cli.log("start", floor=self.floor, grace=self.grace, allow=sorted(self.allow))
                while (code := self.cycle()) is None:
                    self.sleep(self.timing.poll)
                outcome[0] = code
        except Interrupted as stop:
            outcome[0] = EXIT_CRASHED
            self.cli.log("signal", signum=stop.signum)
        except BaseException as error:
            outcome[0] = EXIT_CRASHED
            self.cli.log("error", kind=type(error).__name__, message=repr(error))

    def watch(self) -> int:
        outcome = [EXIT_CRASHED]
        try:
            self.run(outcome)
        except BaseException:  # a signal inside a handler: keep its code
            pass
        finally:
            with _Deferred():
                self.cli.log("exit", code=outcome[0])
        return outcome[0]


# -- process plumbing --------------------------------------------------------------------


class _Deferred:
    """Signals during cleanup are counted, not raised, so a stop is never cut in half."""

    SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

    def __enter__(self) -> _Deferred:
        self.count = 0
        self.saved = [signal.signal(s, self._count) for s in self.SIGNALS]
        return self

    def _count(self, signum: int, frame: object) -> None:
        self.count += 1

    def __exit__(self, *exc: object) -> None:
        for sig, handler in zip(self.SIGNALS, self.saved):
            signal.signal(sig, handler)


_signalled = False


def _raise_interrupted(signum: int, frame: object) -> None:
    """The first signal raises; later ones are ignored so they cannot cut a stop short
    (from DA-26, 3539f09)."""
    global _signalled
    if _signalled:
        return
    _signalled = True
    raise Interrupted(signum)


def install_signal_handlers() -> None:
    for sig in _Deferred.SIGNALS:
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


class _Group:
    """A child in its own process group; kill() takes the whole group (bash and the
    `colab exec` it started)."""

    def __init__(self, argv: Sequence[str]) -> None:
        self.popen = subprocess.Popen(list(argv), stdin=subprocess.DEVNULL, start_new_session=True)

    def poll(self) -> int | None:
        return self.popen.poll()

    def kill(self) -> None:
        try:
            os.killpg(self.popen.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.popen.poll()


def spawn_process(argv: Sequence[str]) -> Process:
    return _Group(argv)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    session = sub.add_parser("session", help="watch one Colab session")
    guard = sub.add_parser("guard", help="the batch backstop: floor and unregistered sessions")
    for each in (session, guard):
        each.add_argument("--registry", type=Path, required=True, help="one per batch")
        each.add_argument("--log", type=Path, required=True, help="JSON lines, one per event")
        each.add_argument("--colab", type=Path, default=COLAB, help="the colab CLI ($COLAB_CLI)")
        each.add_argument("--poll", type=float, default=60.0, help="seconds between polls")
        each.add_argument("--floor", type=float, help="stop below this account balance")
        each.add_argument("--no-inhibit", action="store_true", help="do not hold off suspend")
    mode = session.add_mutually_exclusive_group(required=True)
    mode.add_argument("--new", action="store_true", help="run `colab new` and watch it")
    mode.add_argument("--attach", action="store_true", help="watch a running session")
    session.add_argument("--name", required=True)
    session.add_argument("--gpu", required=True, type=str.upper)
    session.add_argument("--cap", required=True, type=float, help="CU")
    session.add_argument("--started", help="--attach: start time, ISO 8601")
    session.add_argument("--started-min-ago", type=float, help="--attach: minutes since start")
    session.add_argument("--endpoint", help="--attach: match this endpoint, not the name")
    session.add_argument("--persist", help="shell command run once before the cap")
    session.add_argument("--persist-at", type=float, default=0.9, help="fraction of the cap")
    guard.add_argument("--allow", action="append", default=[], help="an endpoint to leave")
    guard.add_argument("--grace-polls", type=int, default=2)
    guard.add_argument("--stale", type=float, default=600.0, help="seconds without heartbeat")
    return parser.parse_args(argv)


def build_spec(args: argparse.Namespace, now: float) -> Spec:
    if args.started is not None and args.started_min_ago is not None:
        raise ValueError("pass --started or --started-min-ago, not both")
    started = None
    if args.started is not None:
        started = datetime.fromisoformat(args.started).timestamp()
    elif args.started_min_ago is not None:
        started = now - args.started_min_ago * 60
    if not 0 < args.persist_at <= 1:
        raise ValueError("--persist-at is a fraction of the cap, in (0, 1]")
    spec = Spec(args.name, args.gpu, args.cap, args.attach, started, args.endpoint, args.persist)
    check_spec(spec)
    return spec


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    try:
        spec = build_spec(args, time.time()) if args.command == "session" else None
    except ValueError as error:
        print(f"cu_watch: {error}", file=sys.stderr)
        return EXIT_NOTHING
    if not args.colab.exists() or not (args.colab.parent / "python").exists():
        print(f"cu_watch: no colab CLI or python beside it at {args.colab}", file=sys.stderr)
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
    cli = Cli(subprocess_runner, args.log, colab=args.colab)
    timing = Timing(poll=args.poll)
    if spec is None:
        return Guard(
            cli,
            args.registry,
            args.floor,
            frozenset(args.allow),
            grace=args.grace_polls,
            stale=args.stale,
            timing=timing,
        ).watch()
    return Watcher(
        spec, cli, args.registry, args.floor, timing=timing, persist_at=args.persist_at
    ).watch()


if __name__ == "__main__":
    sys.exit(main())
