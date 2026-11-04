"""Checks of the CU watcher with a fake Colab CLI. Run: uv run pytest scripts/he -q"""

from __future__ import annotations

import inspect
import json
import stat
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from cu_watch import colab_runner, main, margin_s, must_stop, read_usage, watch

NAME = "da26-ft-vego-n20"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0
        self.jumps: dict[int, float] = {}  # sleep call index -> extra seconds (suspend)
        self.sleeps = 0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds + self.jumps.pop(self.sleeps, 0.0)
        self.sleeps += 1


class FakeColab:
    """A Colab account seen through the CLI: the watched session plus optional others.

    The balance falls with simulated time at the live sessions' real rates, as Colab
    bills; `colab stop` exits 0 whether or not it worked, as the real CLI does.
    """

    def __init__(
        self,
        clock: FakeClock,
        hardware: str = "L4",
        real_rate: float = 1.94,
        other_rate: float = 0.0,
        stop_works_at: int = 1,
        false_misses: Sequence[int] = (),
        failed_listings: Sequence[int] = (),
        ends_at_listing: int | None = None,
    ) -> None:
        self.clock = clock
        self.hardware = hardware
        self.real_rate = real_rate
        self.other_rate = other_rate
        self.stop_works_at = stop_works_at
        self.false_misses = set(false_misses)
        self.failed_listings = set(failed_listings)
        self.ends_at_listing = ends_at_listing
        self.alive = True
        self.billed = 0.0  # CU this session really cost
        self.balance = 100.0
        self.last = clock.now
        self.listings = 0
        self.stops = 0

    def _bill(self) -> None:
        hours = (self.clock.now - self.last) / 3600
        self.last = self.clock.now
        own = self.real_rate * hours if self.alive else 0.0
        self.billed += own
        self.balance -= own + self.other_rate * hours

    def __call__(self, args: Sequence[str]) -> tuple[int, str]:
        self._bill()
        if args[0] == "usage":
            rate = (self.real_rate if self.alive else 0.0) + self.other_rate
            count = int(self.alive) + int(self.other_rate > 0)
            return 0, (
                f"Current balance: {self.balance:.2f} compute units\n"
                f"Usage rate: {rate:.2f}/hr\nActive assignments: {count}"
            )
        if args[0] == "stop":
            self.stops += 1
            if self.stops >= self.stop_works_at:
                self.alive = False
            return 0, f"[colab] Stopping session '{NAME}'...\n[colab] Session terminated."
        index = self.listings
        self.listings += 1
        if index == self.ends_at_listing:
            self.alive = False
        if index in self.failed_listings:
            return 1, "[colab] Error: connection reset"
        if self.alive and index not in self.false_misses:
            line = f"[{NAME}] gpu-l4-s-abc | Hardware: {self.hardware} | Shape: Standard"
            return 0, line + " | Variant: GPU"
        return 0, "[colab] No active sessions found on server."


def run_watch(
    tmp_path: Path, cap: float, clock: FakeClock | None = None, **fake: Any
) -> tuple[int, FakeColab, list[dict[str, Any]]]:
    clock = clock or FakeClock()
    colab = FakeColab(clock, **fake)
    log = tmp_path / "cu.jsonl"
    ready = tmp_path / "ready"
    code = watch(NAME, cap, log, run=colab, ready_file=ready, now=clock, sleep=clock.sleep)
    return code, colab, [json.loads(line) for line in log.read_text().splitlines()]


def events(rows: list[dict[str, Any]]) -> list[str]:
    return [r["event"] for r in rows]


def test_stops_the_session_inside_the_cap(tmp_path: Path) -> None:
    code, colab, rows = run_watch(tmp_path, cap=2.0)
    assert code == 3 and not colab.alive
    assert colab.billed <= 2.0
    assert events(rows)[-1] == "stop_confirmed"
    assert (tmp_path / "ready").read_text().startswith(NAME)


def test_a_failed_stop_is_retried_until_the_session_is_gone(tmp_path: Path) -> None:
    code, colab, rows = run_watch(tmp_path, cap=2.0, stop_works_at=3)
    assert code == 3 and not colab.alive and colab.stops == 3
    assert events(rows).count("stop_attempt") == 3
    assert colab.billed <= 2.0  # the margin covers the retries


def test_a_stop_that_never_works_exits_5_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, colab, rows = run_watch(tmp_path, cap=2.0, stop_works_at=99)
    assert code == 5 and colab.alive
    assert events(rows)[-1] == "STOP_FAILED"
    assert "STOP_FAILED" in capsys.readouterr().err


def test_a_false_unlisting_is_not_an_end(tmp_path: Path) -> None:
    code, colab, rows = run_watch(tmp_path, cap=2.0, false_misses=(2, 3), failed_listings=(5,))
    assert code == 3 and not colab.alive  # still watched to the cap, then stopped
    assert "ended" not in events(rows)
    assert {"poll_missing", "cli_error"} <= set(events(rows))


def test_three_missing_polls_end_the_watch(tmp_path: Path) -> None:
    code, colab, rows = run_watch(tmp_path, cap=17.5, ends_at_listing=4)
    assert code == 0 and colab.stops == 0
    assert events(rows)[-3:] == ["poll_missing", "poll_missing", "ended"]


def test_a_suspend_is_billed_as_wall_time(tmp_path: Path) -> None:
    clock = FakeClock()
    clock.jumps[3] = 3 * 3600  # the laptop sleeps 3 h during the 4th poll interval
    code, _, rows = run_watch(tmp_path, cap=5.0, clock=clock)
    assert code == 3
    assert rows[-1]["wall_cu"] >= 5.8  # the 3 h at 1.94 CU/h are counted, not skipped
    assert inspect.signature(watch).parameters["now"].default is time.time


def test_a_balance_drop_beyond_the_wall_estimate_stops_the_session(tmp_path: Path) -> None:
    # Billed at 3 CU/h while the watcher assumes L4's 1.94: only the balance shows it.
    code, colab, rows = run_watch(tmp_path, cap=3.0, real_rate=3.0)
    assert code == 3
    assert colab.billed <= 3.0
    assert rows[-1]["balance_cu"] > rows[-1]["wall_cu"]


def test_other_sessions_on_the_account_are_not_charged_here(tmp_path: Path) -> None:
    code, colab, _ = run_watch(tmp_path, cap=3.0, other_rate=1.94)
    assert code == 3
    assert colab.billed > 3.0 - 1.94 * margin_s(60) / 3600 - 0.1  # not stopped at half


def test_a_non_l4_session_is_stopped_at_once(tmp_path: Path) -> None:
    code, colab, rows = run_watch(tmp_path, cap=17.5, hardware="A100", real_rate=6.73)
    assert code == 4 and not colab.alive
    assert "start" not in events(rows) and events(rows)[0] == "wrong_gpu"
    assert not (tmp_path / "ready").exists()


def test_an_unlisted_session_is_refused_without_a_ready_file(tmp_path: Path) -> None:
    code, _, rows = run_watch(tmp_path, cap=17.5, false_misses=(0,))
    assert code == 2 and events(rows) == ["not_listed_at_start"]
    assert not (tmp_path / "ready").exists()


def test_a_log_that_cannot_be_written_does_not_stop_the_guard(tmp_path: Path) -> None:
    (tmp_path / "blocked").write_text("a file, not a directory")
    clock = FakeClock()
    colab = FakeColab(clock)
    log = tmp_path / "blocked" / "cu.jsonl"
    code = watch(NAME, 2.0, log, run=colab, now=clock, sleep=clock.sleep)
    assert code == 3 and not colab.alive


def test_undecodable_cli_output_is_not_a_crash(tmp_path: Path) -> None:
    cli = tmp_path / "colab"
    cli.write_text("#!/bin/sh\nprintf 'Current balance: 9.5 compute units \\377\\n'\n")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    code, out = colab_runner(str(cli))(["usage"])
    assert code == 0 and "�" in out
    assert read_usage(colab_runner(str(cli))).balance == 9.5


def test_a_missing_cli_is_refused_not_crashed(tmp_path: Path) -> None:
    log = tmp_path / "cu.jsonl"
    args = ["--session", "s", "--cap-cu", "1", "--log", str(log), "--colab", "/nonexistent/colab"]
    assert main(args) == 2
    assert colab_runner("/nonexistent/colab")(["sessions"])[0] == 1


def test_cap_arithmetic() -> None:
    assert margin_s(60) == 60 + 240 + 270
    assert not must_stop(16.6, 1.94, 17.5, 60)  # R1 run estimate
    assert must_stop(17.25, 1.94, 17.5, 60)  # 17.25 + 0.31 margin passes 17.5
