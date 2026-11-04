"""Open the stage 1 Colab session and stop it before it passes the plan's CU cap (DA-30).

Runs on the machine with the `colab` CLI, in the background for the whole run:

    nohup setsid uv run python -m flywheel_psi0.stage1.cu_watch \\
        --plan configs/runplans/stage1/egodex-short.yaml --session da30-stage1 \\
        --log fwdata/da30/cu_watch.jsonl &

It reads the balance, creates the session (`colab new -s <session> --gpu <plan gpu>`),
then polls. What the session has spent is the larger of two estimates:

- elapsed time x the GPU's rate (`RATES`, the rise of `colab usage` when a session
  opens, S1-04);
- the drop of `colab usage`'s balance since the start, only while this session is the
  account's only assignment: the balance is per account, so another job running at
  the same time would be counted against this one.

It runs `colab stop -s <session>` once the next poll would pass
`compute.max_compute_units`, and exits when the session is gone (no longer in
`colab sessions`, or no assignment left). A failed `colab` call is logged and never
ends the watch. Each poll is a JSON line in `--log`; the last line carries the
balance drop for the ledger's `measured` row.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COLAB = Path.home() / "project" / "wm-wam-review" / ".venv-colab-cli" / "bin" / "colab"
RATES = {"L4": 1.94, "A100": 6.73}  # CU per hour, docs/g0/psi0-finetune-cost.md

# (returncode, stdout + stderr) of one `colab` call
Runner = Callable[[Sequence[str]], tuple[int, str]]

_BALANCE = re.compile(r"Current balance:\s*([\d.]+)")
_RATE = re.compile(r"Usage rate:\s*([\d.]+)")
_ASSIGNMENTS = re.compile(r"Active assignments:\s*(\d+)")


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


@dataclass
class Watch:
    """What the session has spent and whether to stop it; no I/O, for tests."""

    cap: float
    rate: float
    interval: float
    started: float
    start_balance: float | None = None
    balance_alone: bool = True  # this session has been the only assignment so far
    seen_listed: bool = False
    seen_assigned: bool = False
    gone_polls: int = 0

    def by_time(self, now: float) -> float:
        return (now - self.started) / 3600 * self.rate

    def by_balance(self, usage: Usage | None) -> float | None:
        if usage is None or self.start_balance is None:
            return None
        if usage.assignments > 1:
            self.balance_alone = False
        return self.start_balance - usage.balance if self.balance_alone else None

    def spent(self, now: float, usage: Usage | None) -> float:
        return max(self.by_time(now), self.by_balance(usage) or 0.0)

    def must_stop(self, spent: float) -> bool:
        return spent + self.rate * self.interval / 3600 >= self.cap

    def gone(self, listed: bool | None, usage: Usage | None) -> bool:
        """Two polls in a row without the session; an unknown answer is not 'gone'.

        Each sign counts only once it has shown the session: a name never found in
        `colab sessions` (another output format) proves nothing.
        """
        assignments = usage.assignments if usage is not None else None
        self.seen_listed = self.seen_listed or listed is True
        self.seen_assigned = self.seen_assigned or bool(assignments)
        absent = (self.seen_listed and listed is False) or (self.seen_assigned and assignments == 0)
        self.gone_polls = self.gone_polls + 1 if absent else 0
        return self.gone_polls >= 2


def subprocess_runner(colab: Path) -> Runner:
    def run(args: Sequence[str]) -> tuple[int, str]:
        try:
            done = subprocess.run([str(colab), *args], capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as error:
            return 1, str(error)
        return done.returncode, done.stdout + done.stderr

    return run


def watch(
    session: str,
    gpu: str,
    cap: float,
    log_path: Path,
    run: Runner,
    interval: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Create `session`, watch it until it is gone; return the last log record."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def usage() -> Usage | None:
        code, text = run(["usage"])
        return parse_usage(text) if code == 0 else None

    def log(record: dict[str, Any]) -> dict[str, Any]:
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "session": session, **record}
        with log_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        return record

    before = usage()
    code, text = run(["new", "-s", session, "--gpu", gpu])
    state = Watch(cap=cap, rate=RATES[gpu], interval=interval, started=clock())
    state.start_balance = before.balance if before else None
    log({"event": "new", "code": code, "start_balance": state.start_balance, "cap": cap})
    if code != 0:
        log({"event": "new_failed", "output": text[-2000:]})
        raise SystemExit(f"colab new failed: {text[-500:]}")

    stopped = False
    while True:
        sleep(interval)
        now, current = clock(), usage()
        code, text = run(["sessions"])
        listed = (session in text) if code == 0 else None
        spent, by_balance = state.spent(now, current), state.by_balance(current)
        record: dict[str, Any] = {
            "event": "poll",
            "elapsed_s": round(now - state.started),
            "balance": current.balance if current else None,
            "rate": current.rate if current else None,
            "assignments": current.assignments if current else None,
            "listed": listed,
            "spent_by_time": round(state.by_time(now), 3),
            "spent_by_balance": by_balance and round(by_balance, 3),
            "spent": round(spent, 3),
        }
        if state.gone(listed, current):
            return log(
                {
                    **record,
                    "event": "gone",
                    "stopped_by_watch": stopped,
                    "balance_alone": state.balance_alone,
                }
            )
        # After a stop that worked, only a session still listed is stopped again.
        if state.must_stop(spent) and (not stopped or listed is True):
            code, text = run(["stop", "-s", session])
            stopped = stopped or code == 0
            record.update(event="stop", stop_code=code, stop_output=text[-500:])
        log(record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--plan", type=Path, required=True, help="stage 1 RunPlan YAML")
    parser.add_argument("--session", required=True, help="Colab session name")
    parser.add_argument("--log", type=Path, required=True, help="JSON lines, one per poll")
    parser.add_argument("--colab", type=Path, default=COLAB, help="colab CLI")
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between polls")
    args = parser.parse_args(argv)
    from flywheel_psi0.stage1.runplan import Stage1Plan

    compute = Stage1Plan.load(args.plan).compute
    last = watch(
        args.session,
        compute.gpu,
        compute.max_compute_units,
        args.log,
        subprocess_runner(args.colab),
        interval=args.interval,
    )
    return 3 if last["stopped_by_watch"] else 0


if __name__ == "__main__":
    sys.exit(main())
