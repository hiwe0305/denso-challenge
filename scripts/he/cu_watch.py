"""Stop a Colab session once its compute-unit spend reaches a cap (DA-26 task 3).

Hiếu approved tier 2 on 4/11/2026 with a hard ceiling of 52 CU for DA-26; each job
gets its own cap in docs/g0/ledger/DA-26.csv. The account balance is shared with
other stories' sessions running at the same time, so the balance cannot say what one
session spent. Spend is therefore wall time since the session started times its rate
(L4: 1.94 CU/h, the rise of `colab usage` when a session opens, S1-04). The balance
`colab usage` reports is logged beside it for the measured ledger row.

Start it on the laptop right after `colab new`, detached like every long job:

    nohup setsid python3 scripts/he/cu_watch.py --session da26-ft-vego-n20 --cap-cu 17.5 \\
        --log fwdata/he/cu/da26-ft-vego-n20.jsonl < /dev/null > /dev/null 2>&1 &

Exit codes: 0 the session ended by itself, 3 the watcher stopped it at the cap,
2 the session was not listed at start (nothing is watched; fix the name first).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

COLAB = "colab"
L4_CU_PER_HOUR = 1.94

Run = Callable[[Sequence[str]], tuple[int, str]]


def run_colab(args: Sequence[str]) -> tuple[int, str]:
    done = subprocess.run([COLAB, *args], capture_output=True, text=True, timeout=120, check=False)
    return done.returncode, done.stdout + done.stderr


def spent_cu(elapsed_s: float, rate_cu_per_hour: float) -> float:
    return elapsed_s / 3600 * rate_cu_per_hour


def must_stop(elapsed_s: float, rate: float, cap_cu: float, poll_s: float) -> bool:
    """True when the spend would pass the cap before the next poll."""
    return spent_cu(elapsed_s + poll_s, rate) >= cap_cu


def balance(text: str) -> float | None:
    found = re.search(r"Current balance:\s*([0-9.]+)", text)
    return float(found.group(1)) if found else None


def listed(session: str, run: Run) -> bool | None:
    """Whether `colab sessions` lists the session; None when the CLI call failed."""
    code, out = run(["sessions"])
    if code != 0:
        return None
    return re.search(rf"(?<![\w-]){re.escape(session)}(?![\w-])", out) is not None


def watch(
    session: str,
    cap_cu: float,
    log: Path,
    rate: float = L4_CU_PER_HOUR,
    poll_s: float = 60.0,
    started_s_ago: float = 0.0,
    run: Run = run_colab,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    start = clock() - started_s_ago

    def record(event: str, **extra: object) -> float:
        elapsed = clock() - start
        _, usage = run(["usage"])
        row = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session": session,
            "event": event,
            "elapsed_h": round(elapsed / 3600, 3),
            "spent_cu": round(spent_cu(elapsed, rate), 2),
            "cap_cu": cap_cu,
            "balance_cu": balance(usage),
            **extra,
        }
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return elapsed

    if listed(session, run) is not True:
        record("not_listed_at_start")
        return 2
    record("start", rate_cu_per_hour=rate)
    while True:
        sleep(poll_s)
        state = listed(session, run)
        if state is False:
            record("ended")
            return 0
        elapsed = record("poll" if state else "cli_error")
        if must_stop(elapsed, rate, cap_cu, poll_s):
            code, out = run(["stop", "-s", session])
            record("stopped_at_cap", stop_exit=code, stop_output=out.strip()[-200:])
            return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", required=True)
    parser.add_argument("--cap-cu", type=float, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--rate", type=float, default=L4_CU_PER_HOUR, help="CU per hour")
    parser.add_argument("--poll", type=float, default=60.0, help="seconds between checks")
    parser.add_argument(
        "--started-min-ago", type=float, default=0.0, help="if the session opened earlier"
    )
    args = parser.parse_args(argv)
    if args.cap_cu <= 0:
        print("--cap-cu must be positive", file=sys.stderr)
        return 2
    return watch(
        args.session,
        args.cap_cu,
        args.log,
        rate=args.rate,
        poll_s=args.poll,
        started_s_ago=args.started_min_ago * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())
