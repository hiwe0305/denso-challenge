"""The CU watcher against a fake `colab` CLI and a fake clock."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from flywheel_psi0.stage1.cu_watch import Usage, Watch, main, parse_usage, watch

USAGE = (
    "Current balance: {balance:.2f} compute units\n"
    "Usage rate: {rate:.2f}/hr\n"
    "Active assignments: {n}\n"
)


def test_parse_usage_reads_the_cli_text() -> None:
    text = "Current balance: 101.77 compute units\nUsage rate: 1.94/hr\nActive assignments: 1\n"
    assert parse_usage(text) == Usage(101.77, 1.94, 1)
    assert parse_usage("[colab] error") is None


class FakeColab:
    """A session that spends `rate` CU per hour of the fake clock; `others` more jobs."""

    def __init__(self, rate: float = 1.94, others: int = 0, lag_cu: float = 0.0) -> None:
        self.now = 0.0
        self.rate, self.others, self.lag_cu = rate, others, lag_cu
        self.alive = False
        self.calls: list[list[str]] = []
        self.balance0 = 101.77

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def spent(self) -> float:
        return max(0.0, self.now / 3600 * self.rate * (1 + self.others) - self.lag_cu)

    def __call__(self, args: Sequence[str]) -> tuple[int, str]:
        self.calls.append(list(args))
        if args[0] == "new":
            self.alive = True
            return 0, "created"
        if args[0] == "stop":
            self.alive = False
            return 0, "stopped"
        if args[0] == "sessions":
            names = (["da30"] if self.alive else []) + ["other"] * self.others
            return 0, "\n".join(names) or "[colab] No active sessions found on server."
        n = int(self.alive) + self.others
        rate = self.rate * n
        return 0, USAGE.format(balance=self.balance0 - self.spent(), rate=rate, n=n)


def records(log: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_the_session_is_stopped_before_the_cap(tmp_path: Path) -> None:
    colab = FakeColab()
    log = tmp_path / "watch.jsonl"
    last = watch("da30", "L4", 4.0, log, colab, interval=60, clock=colab.clock, sleep=colab.sleep)

    assert colab.calls[:2] == [["usage"], ["new", "-s", "da30", "--gpu", "L4"]]
    assert colab.calls.count(["stop", "-s", "da30"]) == 1  # not again once it is gone
    stop = next(r for r in records(log) if r["event"] == "stop")
    assert 3.9 <= float(stop["spent"]) < 4.0  # one more poll would have passed 4
    assert last["event"] == "gone" and last["stopped_by_watch"] is True


def test_a_lagging_balance_does_not_delay_the_stop(tmp_path: Path) -> None:
    colab = FakeColab(lag_cu=2.0)  # the balance shows 2 CU less than spent
    log = tmp_path / "watch.jsonl"
    watch("da30", "L4", 4.0, log, colab, interval=60, clock=colab.clock, sleep=colab.sleep)
    stop = next(r for r in records(log) if r["event"] == "stop")
    assert float(stop["elapsed_s"]) <= 4.0 / 1.94 * 3600


def test_other_jobs_on_the_account_are_not_counted(tmp_path: Path) -> None:
    colab = FakeColab(others=1)  # the balance drops twice as fast
    log = tmp_path / "watch.jsonl"
    watch("da30", "L4", 4.0, log, colab, interval=60, clock=colab.clock, sleep=colab.sleep)
    stop = next(r for r in records(log) if r["event"] == "stop")
    assert stop["spent_by_balance"] is None
    assert float(stop["elapsed_s"]) > 0.95 * 4.0 / 1.94 * 3600


def test_the_watch_ends_when_the_session_is_stopped_by_hand(tmp_path: Path) -> None:
    colab = FakeColab()
    log = tmp_path / "watch.jsonl"
    polls = 0

    def sleep(seconds: float) -> None:
        nonlocal polls
        colab.sleep(seconds)
        polls += 1
        if polls == 30:
            colab.alive = False  # the run finished and was stopped from the shell

    last = watch("da30", "L4", 4.0, log, colab, interval=60, clock=colab.clock, sleep=sleep)
    assert ["stop", "-s", "da30"] not in colab.calls
    assert last["event"] == "gone" and last["stopped_by_watch"] is False
    assert abs(float(last["spent_by_balance"]) - 31 * 60 / 3600 * 1.94) < 0.05


def test_failed_cli_calls_never_end_the_watch() -> None:
    state = Watch(cap=4.0, rate=1.94, interval=60, started=0.0)
    assert not state.gone(True, Usage(100.0, 1.94, 1))
    assert not state.gone(None, None)
    assert not state.gone(None, None)
    assert not state.gone(False, None)
    assert state.gone(False, None)


def test_a_name_never_listed_proves_nothing() -> None:
    state = Watch(cap=4.0, rate=1.94, interval=60, started=0.0)
    for _ in range(5):  # `colab sessions` prints no names, the session is up
        assert not state.gone(False, Usage(100.0, 1.94, 1))


def test_main_reads_the_cap_from_the_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = Path(__file__).resolve().parents[4] / "configs/runplans/stage1/egodex-short.yaml"
    seen: dict[str, object] = {}

    def fake_watch(
        session: str, gpu: str, cap: float, log: Path, run: object, **kw: object
    ) -> dict[str, object]:
        seen.update(session=session, gpu=gpu, cap=cap)
        return {"stopped_by_watch": True}

    monkeypatch.setattr("flywheel_psi0.stage1.cu_watch.watch", fake_watch)
    code = main(["--plan", str(plan), "--session", "da30", "--log", str(tmp_path / "w.jsonl")])
    assert (code, seen) == (3, {"session": "da30", "gpu": "L4", "cap": 4.0})


def test_a_failed_stop_is_tried_again(tmp_path: Path) -> None:
    colab = FakeColab()
    serve = colab.__call__
    failures = iter([True])

    def flaky(args: Sequence[str]) -> tuple[int, str]:
        if args[0] == "stop" and next(failures, False):
            colab.calls.append(list(args))
            return 1, "[colab] backend error"
        return serve(args)

    log = tmp_path / "watch.jsonl"
    last = watch("da30", "L4", 4.0, log, flaky, interval=60, clock=colab.clock, sleep=colab.sleep)
    assert colab.calls.count(["stop", "-s", "da30"]) == 2
    assert last["stopped_by_watch"] is True
