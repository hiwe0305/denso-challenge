"""Stop a Colab session before its compute-unit spend reaches a cap (DA-26 task 3).

Hiếu approved tier 2 on 4/11/2026 with a hard ceiling of 52 CU for DA-26; each job
has its own cap in docs/g0/ledger/DA-26.csv. The watcher fails closed:

- Spend is the larger of two meters. (1) Balance: each drop of `Current balance`
  in `colab usage` is charged to this session in full while it is the only active
  assignment (start balance minus current balance), and in proportion to its rate
  over the account's `Usage rate` while other stories' sessions also run, so they
  are not charged here. (2) Wall clock:
  `time.time()` since the session opened times the session's rate. Wall time keeps
  counting through a laptop suspend (monotonic time does not), as Colab's billing
  does.
- The session must run on the expected accelerator (`Hardware:` in
  `colab sessions`; default L4 at 1.94 CU/h, S1-04). Any other is stopped at once:
  an A100 bills about 6.7 CU/h (DA-19).
- It stops when spend + rate x (poll + 2 x CLI timeout + stop delay) reaches the
  cap, so a slow CLI or a retried stop still ends inside the cap.
- `colab stop` exits 0 even when it did nothing, so every stop is confirmed by
  two successful `colab sessions` listings without the session, and retried with
  backoff. A session still listed after the retries ends the watcher with exit 5
  and a STOP_FAILED line on stderr and in the log.
- "Ended" needs 3 consecutive successful listings without the session; a failed
  CLI call is neither a listing nor a miss.
- `--ready-file` is written only after the session is seen on the right
  accelerator. Training starts only once it exists (launch below).

The laptop must stay awake for the whole run: while it sleeps nothing is stopped.
Run it under systemd-inhibit, on the machine whose Colab CLI state created the
session (`colab stop` only finds sessions in that local state), with the CLI from
`--colab` or `$COLAB_CLI` (on the team laptop:
~/project/wm-wam-review/.venv-colab-cli/bin/colab). Output goes to a file and the
exit code is written after it, so neither is lost:

    nohup setsid bash -c 'systemd-inhibit --what=sleep:idle:handle-lid-switch \\
        --who=cu_watch --why="Colab CU cap" python3 scripts/he/cu_watch.py \\
        --session da26-ft-vego-n20 --cap-cu 17.5 --log fwdata/he/cu/da26-ft-vego-n20.jsonl \\
        --ready-file fwdata/he/cu/da26-ft-vego-n20.ready; echo "exit $?"' \\
        < /dev/null >> fwdata/he/cu/da26-ft-vego-n20.out 2>&1 &
    until [ -f fwdata/he/cu/da26-ft-vego-n20.ready ]; do
        grep -q '^exit ' fwdata/he/cu/da26-ft-vego-n20.out && exit 1; sleep 5; done
    # only now start the job on the VM

Exit codes: 0 the session ended by itself; 2 nothing watched (CLI missing, session
not listed at start); 3 stopped at the cap; 4 stopped for a wrong accelerator;
5 STOP_FAILED, the session may still be billing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

COLAB = os.environ.get("COLAB_CLI", "colab")
CU_PER_HOUR = {"L4": 1.94}  # `colab usage` rise when an L4 session opens (S1-04)
CLI_TIMEOUT_S = 120
STOP_BACKOFF_S = (30, 60, 120)  # waits before the 2nd, 3rd and 4th stop attempt
STOP_DELAY_S = sum(STOP_BACKOFF_S) + 60  # backoffs plus the confirming listings
CONFIRM_POLLS = 4  # listings tried after each stop, CONFIRM_WAIT_S apart
CONFIRM_WAIT_S = 10
MISSES_TO_END = 3

Run = Callable[[Sequence[str]], tuple[int, str]]
State = Literal["listed", "absent", "error"]


def colab_runner(cli: str) -> Run:
    def run(args: Sequence[str]) -> tuple[int, str]:
        try:
            done = subprocess.run(
                [cli, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CLI_TIMEOUT_S,
                check=False,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return 1, f"{type(error).__name__}: {error}"
        return done.returncode, done.stdout + done.stderr

    return run


@dataclass
class Usage:
    balance: float | None
    rate: float | None  # account-wide CU per hour
    assignments: int | None = None


def read_usage(run: Run) -> Usage:
    code, out = run(["usage"])
    if code != 0:
        return Usage(None, None)
    balance = re.search(r"Current balance:\s*([0-9.]+)", out)
    rate = re.search(r"Usage rate:\s*([0-9.]+)", out)
    count = re.search(r"Active assignments:\s*([0-9]+)", out)
    return Usage(
        float(balance.group(1)) if balance else None,
        float(rate.group(1)) if rate else None,
        int(count.group(1)) if count else None,
    )


def session_state(session: str, run: Run) -> tuple[State, str | None]:
    """(state, accelerator) from `colab sessions`, whose lines read
    `[name] endpoint | Hardware: L4 | Shape: ... | Variant: GPU`."""
    code, out = run(["sessions"])
    if code != 0:
        return "error", None
    for line in out.splitlines():
        if line.startswith(f"[{session}] "):
            hardware = re.search(r"\|\s*Hardware:\s*([A-Za-z0-9]+)", line)
            return "listed", hardware.group(1) if hardware else None
    if "No active sessions" in out or out.lstrip().startswith("["):
        return "absent", None
    return "error", None  # output not understood: neither listed nor absent


class Meter:
    """CU spent by one session: the larger of the balance and wall-clock meters."""

    def __init__(self, rate: float, started_wall: float, balance: float | None) -> None:
        self.rate = rate
        self.started_wall = started_wall
        self.last_balance = balance
        self.balance_cu = 0.0

    def wall_cu(self, now: float) -> float:
        return max(0.0, now - self.started_wall) / 3600 * self.rate

    def update(self, usage: Usage) -> None:
        if usage.balance is None:
            return
        if self.last_balance is not None and usage.balance < self.last_balance:
            share = 1.0  # alone, or unknown: the whole drop is ours (fail closed)
            shared = usage.assignments is not None and usage.assignments > 1
            if shared and usage.rate is not None and usage.rate > self.rate:
                share = self.rate / usage.rate
            self.balance_cu += (self.last_balance - usage.balance) * share
        self.last_balance = usage.balance

    def spent(self, now: float) -> float:
        return max(self.wall_cu(now), self.balance_cu)


def margin_s(poll_s: float) -> float:
    """Seconds of spend still to come once a stop is decided."""
    return poll_s + 2 * CLI_TIMEOUT_S + STOP_DELAY_S


def must_stop(spent: float, rate: float, cap_cu: float, poll_s: float) -> bool:
    return spent + rate * margin_s(poll_s) / 3600 >= cap_cu


def watch(
    session: str,
    cap_cu: float,
    log: Path,
    *,
    run: Run,
    expect_gpu: str = "L4",
    rate: float | None = None,
    poll_s: float = 60.0,
    started_s_ago: float = 0.0,
    ready_file: Path | None = None,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    rate = CU_PER_HOUR[expect_gpu] if rate is None else rate
    started = now() - started_s_ago

    def record(event: str, meter: Meter | None = None, **extra: object) -> None:
        t = now()
        row: dict[str, object] = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session": session,
            "event": event,
            "elapsed_h": round((t - started) / 3600, 3),
            "cap_cu": cap_cu,
            **extra,
        }
        if meter is not None:
            row |= {
                "spent_cu": round(meter.spent(t), 3),
                "wall_cu": round(meter.wall_cu(t), 3),
                "balance_cu": round(meter.balance_cu, 3),
                "balance": meter.last_balance,
            }
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as error:  # the watcher keeps guarding even if the log fails
            print(f"log write failed: {error}; {json.dumps(row)}", file=sys.stderr, flush=True)

    def stop(reason: str, meter: Meter | None) -> bool:
        for attempt, wait in enumerate((0, *STOP_BACKOFF_S)):
            if wait:
                sleep(wait)
            code, out = run(["stop", "-s", session])
            record(
                "stop_attempt",
                meter,
                reason=reason,
                attempt=attempt + 1,
                stop_exit=code,
                stop_output=out.strip()[-200:],
            )
            misses = 0
            for _ in range(CONFIRM_POLLS):
                state, _ = session_state(session, run)
                if state == "listed":
                    break
                if state == "absent":
                    misses += 1
                    if misses == 2:
                        record("stop_confirmed", meter, reason=reason)
                        return True
                sleep(CONFIRM_WAIT_S)
        record("STOP_FAILED", meter, reason=reason)
        print(
            f"STOP_FAILED: Colab session {session} may still be billing; stop it by hand",
            file=sys.stderr,
            flush=True,
        )
        return False

    state, gpu = session_state(session, run)
    if state != "listed":
        record("not_listed_at_start", state=state)
        return 2
    meter = Meter(rate, started, read_usage(run).balance)
    if gpu != expect_gpu:
        record("wrong_gpu", meter, gpu=gpu, expected=expect_gpu)
        return 4 if stop("wrong_gpu", meter) else 5
    record("start", meter, gpu=gpu, rate_cu_per_hour=rate, margin_s=margin_s(poll_s))
    if ready_file is not None:
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text(f"{session} {gpu}\n", encoding="utf-8")
    misses = 0
    while True:
        sleep(poll_s)
        state, gpu = session_state(session, run)
        meter.update(read_usage(run))
        if state == "absent":
            misses += 1
            if misses >= MISSES_TO_END:
                record("ended", meter)
                return 0
        elif state == "listed":
            misses = 0
            if gpu != expect_gpu:
                record("wrong_gpu", meter, gpu=gpu, expected=expect_gpu)
                return 4 if stop("wrong_gpu", meter) else 5
        record({"listed": "poll", "absent": "poll_missing", "error": "cli_error"}[state], meter)
        if must_stop(meter.spent(now()), rate, cap_cu, poll_s):
            return 3 if stop("cap", meter) else 5


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", required=True)
    parser.add_argument("--cap-cu", type=float, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--colab", default=COLAB, help="Colab CLI (default $COLAB_CLI or colab)")
    parser.add_argument("--expect-gpu", default="L4")
    parser.add_argument("--rate", type=float, help="CU per hour; required unless the GPU is L4")
    parser.add_argument("--poll", type=float, default=60.0, help="seconds between checks")
    parser.add_argument(
        "--started-min-ago", type=float, default=0.0, help="if the session opened earlier"
    )
    args = parser.parse_args(argv)
    if args.cap_cu <= 0:
        print("--cap-cu must be positive", file=sys.stderr)
        return 2
    if args.rate is None and args.expect_gpu not in CU_PER_HOUR:
        print(f"no known rate for {args.expect_gpu}; pass --rate", file=sys.stderr)
        return 2
    if shutil.which(args.colab) is None:
        print(f"Colab CLI {args.colab} not found; pass --colab or set COLAB_CLI", file=sys.stderr)
        return 2
    return watch(
        args.session,
        args.cap_cu,
        args.log,
        run=colab_runner(args.colab),
        expect_gpu=args.expect_gpu,
        rate=args.rate,
        poll_s=args.poll,
        started_s_ago=args.started_min_ago * 60,
        ready_file=args.ready_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
