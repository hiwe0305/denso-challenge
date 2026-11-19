"""Step-latch check (H1) and signal presence (H3) on the 60k stage 1 rollouts (DA-43 task 2.3).

Expected numbers: docs/he/tray.md 20.11. H1: rollouts that never latched `approach_a`
without timing out, C_70 7/60 (5 L-PLACE-POSE, 1 L-PART-DROP, 1 success), C_ALL 10/60
(1 success), B_70 7/60 (none). H3: outcome and trace hold no failure time, contact or
tilt at failure, so tilt failures cannot be judged.
"""

from __future__ import annotations

from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunScores, ToolResult
from flywheel.eval.agentqa.tools.latch import latch_consistency
from flywheel.eval.agentqa.tools.signals import labels_seen, signal_presence
from flywheel.eval.agentqa.tools.task import TaskView


def named(book: FactBook, result: ToolResult) -> dict[str, object]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def test_broken_chains_are_the_h1_rollouts(tray: TaskView, runs: dict[str, RunScores]) -> None:
    book = FactBook()
    three = [runs["C_70"], runs["C_ALL"], runs["B_70"]]
    result = latch_consistency(book, tray, three)
    got = named(book, result)
    assert (got["C_70_chain_broken"], got["C_70_chain_broken_successes"]) == (7, 1)
    assert (got["C_ALL_chain_broken"], got["C_ALL_chain_broken_successes"]) == (10, 1)
    assert (got["B_70_chain_broken"], got["B_70_chain_broken_successes"]) == (7, 0)
    assert got["C_70_chain_broken_at_approach_a"] == 7
    assert got["chain_broken_at_approach_a_runs"] == 3
    c70 = [r for r in result.rows if r["run"] == "C_70"]
    assert sorted(str(r["outcome"]) for r in c70) == (
        ["L-PART-DROP"] + ["L-PLACE-POSE"] * 5 + ["success"])
    assert "C_70/l2-s1000115" in {r["episode"] for r in c70}  # the success of tray.md 20.11
    assert result.judged


def test_timeouts_never_break_a_chain(tray: TaskView, runs: dict[str, RunScores]) -> None:
    book = FactBook()
    result = latch_consistency(book, tray, [runs["C_70"]])
    assert all(r["outcome"] != "L-TIMEOUT" for r in result.rows)


def test_a_label_the_view_does_not_know_is_reported(tray: TaskView,
                                                    runs: dict[str, RunScores]) -> None:
    odd = runs["C_70"].scores[0].model_copy(update={"success": False, "failure_kind": "L-NEW"})
    book = FactBook()
    result = latch_consistency(book, tray, [RunScores("X", "pack/X", (odd,))])
    assert not result.judged and "L-NEW" in result.not_judged[0]


def test_tilt_cannot_be_judged_from_scores_and_traces(tray: TaskView,
                                                     runs: dict[str, RunScores]) -> None:
    labels = labels_seen([runs["C_70"]])
    assert labels == ["L-PART-DROP", "L-PLACE-POSE", "L-TIMEOUT", "L-TRAY-TILT"]
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores", "trace"], labels))
    assert got["L-TRAY-TILT_judgeable"] is False
    assert "failure_t" in str(got["L-TRAY-TILT_signals_missing"])
    assert got["L-TIMEOUT_judgeable"] is True  # the trace has command and measurement
    assert got["latch_approach_a_judgeable"] is False
    assert got["latch_approach_a_signals_missing"] == "palm_handle_distance_min"


def test_without_traces_a_timeout_cannot_be_judged_either(tray: TaskView) -> None:
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores"], ["L-TIMEOUT"]))
    assert got["L-TIMEOUT_judgeable"] is False


def test_unknown_kinds_and_labels_are_reported(tray: TaskView) -> None:
    book = FactBook()
    result = signal_presence(book, tray, ["scores", "rosbag"], ["L-NEW"])
    assert not result.judged and len(result.not_judged) == 2
