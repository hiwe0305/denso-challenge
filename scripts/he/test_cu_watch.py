"""Checks of the CU watcher with a fake Colab CLI. Run: uv run pytest scripts/he -q"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from cu_watch import balance, must_stop, watch


class FakeColab:
    """Lists the session for `alive_polls` calls, then not; records every call."""

    def __init__(self, alive_polls: int, sessions_fail_at: int = -1) -> None:
        self.alive_polls = alive_polls
        self.sessions_fail_at = sessions_fail_at
        self.calls: list[list[str]] = []
        self.sessions_seen = 0
        self.stopped = False

    def __call__(self, args: Sequence[str]) -> tuple[int, str]:
        self.calls.append(list(args))
        if args[0] == "usage":
            return 0, "Current balance: 101.77 compute units\nUsage rate: 1.94/hr\n"
        if args[0] == "stop":
            self.stopped = True
            return 0, "stopped"
        index = self.sessions_seen
        self.sessions_seen += 1
        if index == self.sessions_fail_at:
            return 1, "network error"
        alive = index < self.alive_polls and not self.stopped
        return 0, "da26-ft-vego-n20  L4  RUNNING\n" if alive else "No active sessions"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def run_watch(colab: FakeColab, tmp_path: Path, cap: float) -> tuple[int, list[dict]]:
    clock = FakeClock()
    log = tmp_path / "cu.jsonl"
    code = watch(
        "da26-ft-vego-n20", cap, log, poll_s=600, run=colab, clock=clock, sleep=clock.sleep
    )
    return code, [json.loads(line) for line in log.read_text().splitlines()]


def test_stops_the_session_before_the_cap(tmp_path: Path) -> None:
    colab = FakeColab(alive_polls=1000)
    code, rows = run_watch(colab, tmp_path, cap=1.0)  # 1 CU = 30.9 min at 1.94 CU/h
    assert code == 3 and colab.stopped
    assert ["stop", "-s", "da26-ft-vego-n20"] in colab.calls
    assert rows[-1]["event"] == "stopped_at_cap"
    assert rows[-1]["spent_cu"] <= 1.0 and rows[-1]["balance_cu"] == 101.77


def test_a_session_that_ends_first_is_left_alone(tmp_path: Path) -> None:
    colab = FakeColab(alive_polls=3)
    code, rows = run_watch(colab, tmp_path, cap=17.5)
    assert code == 0 and not colab.stopped
    assert [r["event"] for r in rows] == ["start", "poll", "poll", "ended"]


def test_a_failed_cli_call_is_not_an_end(tmp_path: Path) -> None:
    colab = FakeColab(alive_polls=3, sessions_fail_at=1)
    code, rows = run_watch(colab, tmp_path, cap=17.5)
    assert code == 0
    assert "cli_error" in [r["event"] for r in rows]


def test_an_unlisted_session_is_refused(tmp_path: Path) -> None:
    code, rows = run_watch(FakeColab(alive_polls=0), tmp_path, cap=17.5)
    assert code == 2 and rows[0]["event"] == "not_listed_at_start"


def test_cap_arithmetic() -> None:
    assert not must_stop(8.5 * 3600, 1.94, 17.5, 60)  # R1 run, 16.5 CU
    assert must_stop(9.0 * 3600, 1.94, 17.5, 120)  # 17.46 CU + two minutes passes 17.5
    assert balance("Current balance: 101.77 compute units") == 101.77
    assert balance("garbage") is None
