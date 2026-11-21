"""`trace_stats`: failed and succeeded rollouts measured alike (DA-43 task 3.1)."""

from __future__ import annotations

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ToolResult
from flywheel.eval.agentqa.tools.trace import trace_stats
from flywheel.eval.config import R3Thresholds
from helpers_tools import rollout, run_of, trace_of

CFG = R3Thresholds(tau_track_upper=0.10, tau_track_lower=0.15, percentile=99.0)
REF = "system.yaml (r3)"


def values(book: FactBook, result: ToolResult) -> dict[str, object]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def run_trace(book: FactBook, steps: list, outcomes: dict) -> tuple[ToolResult, dict]:  # type: ignore[type-arg]
    result = trace_stats(book, [run_of("R", outcomes)], {"R": trace_of("R", steps)}, CFG, REF)
    return result, values(book, result)


def test_failed_and_succeeded_rollouts_get_the_same_measurements() -> None:
    steps = (rollout("R", "ok", upper_gap=0.01)
             + rollout("R", "bad", upper_gap=0.5, lower_gap=0.3, speed=0.2))
    book = FactBook()
    result, got = run_trace(book, steps, {"ok": True, "bad": False})
    for group in ("succeeded", "failed"):
        for name in ("rollouts", "cycles", "track_error_upper", "track_error_lower",
                     "worst_channel_upper", "worst_channel_lower", "velocity_command_share",
                     "path_length_mean", "exceeds_tau_upper", "exceeds_tau_lower"):
            assert f"R_{group}_{name}" in got, (group, name)
    assert got["R_failed_rollouts"] == got["R_succeeded_rollouts"] == 1
    assert got["R_failed_cycles"] == 10
    assert got["R_failed_track_error_upper"] == pytest.approx(0.5)
    assert got["R_succeeded_track_error_upper"] == pytest.approx(0.01)
    assert got["R_failed_worst_channel_upper"] == "left_hand_thumb_0_joint"
    assert got["R_failed_worst_channel_lower"] == "waist_pitch"
    assert got["R_failed_exceeds_tau_upper"] is True
    assert got["R_succeeded_exceeds_tau_upper"] is False
    assert got["R_tau_separates_upper"] is True and got["R_tau_separates_lower"] is True
    assert got["R_failed_velocity_command_share"] == 1.0
    assert got["R_succeeded_velocity_command_share"] == 0.0
    assert got["R_failed_path_length_mean"] == pytest.approx(9 * 0.2 * 0.1)
    assert got["tau_track_upper"] == 0.10 and got["track_percentile"] == 99.0
    assert {r["part"] for r in result.rows} == {"upper", "lower"}


def test_a_threshold_both_groups_cross_does_not_separate() -> None:
    steps = rollout("R", "ok", upper_gap=0.4) + rollout("R", "bad", upper_gap=0.5)
    _, got = run_trace(FactBook(), steps, {"ok": True, "bad": False})
    assert got["R_succeeded_exceeds_tau_upper"] is True
    assert got["R_tau_separates_upper"] is False


def test_full_traces_of_both_groups_leave_nothing_unjudged() -> None:
    result, got = run_trace(FactBook(), rollout("R", "ok") + rollout("R", "bad"),
                            {"ok": True, "bad": False})
    assert result.judged and result.not_judged == ()
    assert not any(name.endswith("_not_judged") for name in got)


def test_non_finite_values_are_counted_and_never_scored() -> None:
    steps = rollout("R", "ok") + rollout("R", "bad", upper_gap=0.5, nan_at=3)
    _, got = run_trace(FactBook(), steps, {"ok": True, "bad": False})
    assert got["R_failed_nonfinite_cycles"] == 1 and got["R_succeeded_nonfinite_cycles"] == 0
    assert got["R_failed_track_error_upper"] == pytest.approx(0.5)  # cycle 3 left out


def test_a_group_with_nothing_finite_is_not_judged_not_clean() -> None:
    every = [s.model_copy(update={"meas_upper": ["NaN"] * 28}) for s in rollout("R", "bad")]
    result, got = run_trace(FactBook(), rollout("R", "ok") + every, {"ok": True, "bad": False})
    assert "R_failed_track_error_upper" not in got and "R_failed_exceeds_tau_upper" not in got
    assert "R_failed_upper_not_judged" in got and "R_tau_separates_upper" not in got
    assert any("non-finite" in r for r in result.not_judged)


def test_a_run_without_failures_or_without_trace_is_not_judged() -> None:
    result, got = run_trace(FactBook(), rollout("R", "ok"), {"ok": True})
    assert "R_failed_not_judged" in got and "R_failed_track_error_upper" not in got
    assert got["R_succeeded_rollouts"] == 1 and "R_tau_separates_upper" not in got
    book = FactBook()
    bare = trace_stats(book, [run_of("R", {"ok": True})], {}, CFG, REF)
    assert not bare.judged and "no trace entry" in bare.not_judged[0]
    assert "trace_stats_R_not_judged" in values(book, bare)


def test_rollouts_without_a_verdict_are_counted_not_grouped() -> None:
    steps = rollout("R", "ok") + rollout("R", "lost") + rollout("R", "open")
    _, got = run_trace(FactBook(), steps, {"ok": True, "open": None, "gone": False})
    assert got["R_trace_undecided_rollouts"] == 2  # "lost" has no score, "open" has no verdict
    assert got["R_scored_without_trace"] == 1  # "gone"
    assert got["R_succeeded_rollouts"] == 1 and got["R_failed_rollouts"] == 0
