"""Task view, `task_lookup` and the not-judged rule (DA-43 task 2.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ToolResult, merge, not_judged
from flywheel.eval.agentqa.tools.task import TaskView, load_task, task_lookup


def values(book: FactBook, result: ToolResult) -> dict[str, object]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def test_the_tray_view_reads_the_scorer_thresholds_with_units(tray: TaskView) -> None:
    assert tray.steps[0] == "approach_a" and tray.steps[-1] == "release_stand"
    assert tray.thresholds["r_reach"] == 0.10
    book = FactBook()
    result = task_lookup(book, tray)
    got = values(book, result)
    assert got["task_steps"] == 7 and got["step_6_name"] == "place"
    r_reach = next(book.get(f) for f in result.facts if book.get(f).name == "threshold_r_reach")
    assert (r_reach.value, r_reach.unit) == (0.10, "m")
    assert result.judged


def test_one_step_is_asked_by_name_from_the_closed_set(tray: TaskView) -> None:
    book = FactBook()
    got = values(book, task_lookup(book, tray, step="place"))
    assert got["step_6_name"] == "place" and "step_1_name" not in got
    refused = task_lookup(book, tray, step="0.12 m")
    assert not refused.judged
    assert "is not a step" in str(book.get(refused.facts[0]).value)


def test_not_judged_is_a_fact_and_merge_keeps_it() -> None:
    book = FactBook()
    a = not_judged(book, "relaxed_sweep", "no final tray pose in the inputs", "pack", "C_70")
    b = ToolResult("relaxed_sweep", (book.add("x", 1, "pack"),))
    both = merge("relaxed_sweep", [a, b])
    assert not both.judged and len(both.facts) == 2
    assert book.get(a.facts[0]).name == "relaxed_sweep_C_70_not_judged"


def test_a_label_implying_an_unknown_step_is_refused(tmp_path: Path) -> None:
    (tmp_path / "scorer.yaml").write_text("thresholds: {r_reach: 0.1}\n")
    (tmp_path / "t.yaml").write_text(
        "task_id: t\nscorer_config: scorer.yaml\nsteps: [a, b]\nsuccess_implies_step: b\n"
        "threshold_units: {r_reach: m}\nlabels: {L-X: {implies_step: c}}\n")
    with pytest.raises(ValueError, match="not steps of t"):
        load_task("t", tmp_path)


def test_a_threshold_without_a_unit_is_refused(tmp_path: Path) -> None:
    (tmp_path / "scorer.yaml").write_text("thresholds: {r_reach: 0.1}\n")
    (tmp_path / "t.yaml").write_text(
        "task_id: t\nscorer_config: scorer.yaml\nsteps: [a]\nsuccess_implies_step: a\n"
        "labels: {}\n")
    with pytest.raises(ValueError, match="no unit"):
        load_task("t", tmp_path)
