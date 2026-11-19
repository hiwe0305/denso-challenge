"""`step_pass_table`: how far rollouts got, step by step (DA-43 task 2.2).

For each run and each level, and for all levels together: rollouts, successes, the
fraction that latched each scorer step, and the step with the largest drop from the
step before it (the first step drops from 1). This is the table that shows a run's
failures piling up at `place` (docs/he/tray.md 19.2 b, 20.2).
"""

from __future__ import annotations

from collections.abc import Sequence

from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunScores, ToolResult, merge, not_judged
from flywheel.eval.agentqa.tools.task import TaskView

TOOL = "step_pass_table"


def _group(book: FactBook, task: TaskView, run: RunScores, label: str,
           scores: Sequence[Score]) -> ToolResult:
    ref = run.ref
    prefix = f"{run.run}_{label}"
    n = len(scores)
    facts = [
        book.add(f"{prefix}_rollouts", n, ref, "rollouts"),
        book.add(f"{prefix}_successes", sum(bool(s.success) for s in scores), ref, "rollouts"),
    ]
    row: dict[str, float | int | str | bool] = {"run": run.run, "levels": label, "rollouts": n}
    rates = []
    for k, step in enumerate(task.steps):
        status = [s.step_status[k] for s in scores if len(s.step_status) == len(task.steps)]
        unknown = sum(1 for st in status if st == "unknown")
        rate = sum(1 for st in status if st == "pass") / n
        rates.append(rate)
        facts.append(book.add(f"{prefix}_pass_{step}", rate, ref, "fraction"))
        if unknown:
            facts.append(book.add(f"{prefix}_unknown_{step}", unknown, ref, "rollouts"))
        row[step] = rate
    drops = [(1.0 if k == 0 else rates[k - 1]) - rate for k, rate in enumerate(rates)]
    worst = max(range(len(drops)), key=lambda k: drops[k])  # first of equal drops
    facts.append(book.add(f"{prefix}_largest_drop_step", task.steps[worst], ref))
    facts.append(book.add(f"{prefix}_largest_drop", drops[worst], ref, "fraction"))
    row["largest_drop_step"] = task.steps[worst]
    return ToolResult(TOOL, tuple(facts), (row,))


def step_pass_table(book: FactBook, task: TaskView, runs: Sequence[RunScores]) -> ToolResult:
    parts: list[ToolResult] = []
    for run in runs:
        scored = [s for s in run.scores if len(s.step_status) == len(task.steps)]
        if len(scored) < len(run.scores):
            parts.append(not_judged(
                book, TOOL, f"{len(run.scores) - len(scored)} rollouts lack the "
                f"{len(task.steps)} step states of {task.task_id}", run.ref, run.run))
        if not scored:
            continue
        for level in run.levels():
            at = [s for s in scored if s.level == level]
            if at:
                parts.append(_group(book, task, run, f"l{level}", at))
        if len(run.levels()) != 1:
            parts.append(_group(book, task, run, "all", scored))
    if not parts:
        return not_judged(book, TOOL, "no run given", "-")
    return merge(TOOL, parts)
