"""`train_window`: loss, gradients and validation cadence in a closed set of windows (3.2)."""

from __future__ import annotations

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import JobMetrics, ToolResult
from flywheel.eval.agentqa.tools.train import train_window, window_of
from helpers_tools import job_of, metric


def values(book: FactBook, result: ToolResult) -> dict[str, object]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def a_job() -> JobMetrics:
    rows = []
    for step in range(10, 101, 10):
        rows.append(metric("J", step, 1.0 / step, groups={"arm": step / 100, "hand": 0.5},
                           vlm=float(step), action=2.0))
        if step % 40 == 0:
            rows.append(metric("J", step, 2.0 / step, split="val"))
    return job_of("J", rows)


def test_the_whole_log() -> None:
    book = FactBook()
    result = train_window(book, a_job(), "all")
    got = values(book, result)
    p = "train_J_all"
    assert (got[f"{p}_first_step"], got[f"{p}_last_step"]) == (10, 100)
    assert got[f"{p}_train_loss_first"] == pytest.approx(0.1)
    assert got[f"{p}_train_loss_last"] == pytest.approx(0.01)
    assert got[f"{p}_train_loss_min"] == pytest.approx(0.01)
    assert got[f"{p}_loss_arm_mean"] == pytest.approx(0.55)
    assert got[f"{p}_loss_arm_last"] == 1.0 and got[f"{p}_loss_hand_mean"] == 0.5
    assert got[f"{p}_grad_norm_vlm_median"] == pytest.approx(55.0)
    assert got[f"{p}_grad_norm_vlm_p99"] == pytest.approx(99.1)
    assert got[f"{p}_grad_norm_action_p99"] == 2.0
    assert got[f"{p}_val_rows"] == 2 and got[f"{p}_val_gap_median"] == 40.0
    assert result.judged


@pytest.mark.parametrize(("which", "label", "lo", "first", "hi"), [
    ("last", "last", 80, 90, 100),   # no validation step after 80: up to the last logged step
    (50, "s50", 40, 50, 80),         # the interval 50 falls in
    (80, "s80", 40, 50, 80),         # a validation step ends its own interval
    (30, "s30", 9, 10, 40),          # before the first validation step: from the first row
])
def test_a_window_is_the_validation_interval_around_a_step(
        which: str | int, label: str, lo: int, first: int, hi: int) -> None:
    window = window_of(a_job(), which)
    assert window is not None and (window.label, window.lo, window.hi) == (label, lo, hi)
    book = FactBook()
    got = values(book, train_window(book, a_job(), which))
    assert got[f"train_J_{label}_last_step"] == hi
    assert got[f"train_J_{label}_first_step"] == first


def test_a_window_with_one_validation_row_uses_the_cadence_of_the_log() -> None:
    book = FactBook()
    got = values(book, train_window(book, a_job(), 50))
    assert "train_J_s50_val_gap_median" not in got
    assert got["train_J_s50_val_gap_median_whole_log"] == 40.0


def test_what_the_log_does_not_carry_is_not_judged() -> None:
    book = FactBook()
    job = job_of("J", [metric("J", 10, 1.0), metric("J", 20, "NaN")])
    result = train_window(book, job, "all")
    got = values(book, result)
    p = "train_J_all"
    assert got[f"{p}_train_nonfinite_losses"] == 1 and f"{p}_train_loss_min" in got
    for name in ("grad_norm_vlm", "grad_norm_action", "val_loss", "val_gap"):
        assert f"{p}_{name}_not_judged" in got
    assert not result.judged and len(result.not_judged) == 4
