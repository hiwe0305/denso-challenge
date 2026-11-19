"""`latch_consistency`: rollouts whose outcome says more than their step chain (DA-43 task 2.3).

The scorer latches its steps in order. A success means every step latched; a failure
label implies the robot got through some step first (an `L-PLACE-POSE` tray ended on
table B, so `reach_b` was done). A rollout whose first unlatched step comes at or before
the step its outcome implies has a broken chain: the outcome and the steps cannot both
be right. That is how the team found the scorer fault at `approach_a` (docs/he/tray.md
20.11, H1): 7/60, 10/60 and 7/60 rollouts of three runs, one of them a success.

Which step each label implies is the task view's (`labels.<label>.implies_step`); a
label the view does not know is reported, never guessed. The tool says where chains
break and how often, in how many runs; whether the scorer or the robot is at fault is
for the hypotheses that read it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, RunScores, ToolResult, not_judged
from flywheel.eval.agentqa.tools.task import TaskView

TOOL = "latch_consistency"


def implied_step(task: TaskView, score: Score) -> str | None:
    """The step the rollout's outcome says was done, or None when it says nothing."""
    if score.success:
        return task.success_implies_step
    spec = task.labels.get(score.failure_kind or "")
    return None if spec is None else spec.implies_step


def broken(task: TaskView, score: Score) -> bool:
    step = implied_step(task, score)
    first = score.first_failed_step
    return step is not None and first is not None and first <= task.index(step)


def latch_consistency(book: FactBook, task: TaskView, runs: Sequence[RunScores]) -> ToolResult:
    if not runs:
        return not_judged(book, TOOL, "no run given", "-")
    facts: list[str] = []
    rows: list[Row] = []
    not_known: list[str] = []
    at_step: dict[str, set[str]] = {}
    for run in runs:
        unknown = sorted({s.failure_kind or "none" for s in run.scores
                          if not s.success and (s.failure_kind or "none") not in task.labels})
        if unknown:
            reason = f"labels {unknown} are not in the task view of {task.task_id}"
            facts.append(book.add(f"{TOOL}_{run.run}_not_judged", reason, run.ref))
            not_known.append(reason)
        hits = [s for s in run.scores if broken(task, s)]
        where = Counter(task.step_name(s.first_failed_step) for s in hits)
        facts.append(book.add(f"{run.run}_chain_broken", len(hits), run.ref, "rollouts"))
        facts.append(book.add(f"{run.run}_rollouts", len(run.scores), run.ref, "rollouts"))
        facts.append(book.add(f"{run.run}_chain_broken_successes",
                              sum(1 for s in hits if s.success), run.ref, "rollouts"))
        for step, count in sorted(where.items(), key=lambda kv: task.index(kv[0])):
            facts.append(book.add(f"{run.run}_chain_broken_at_{step}", count, run.ref,
                                  "rollouts"))
            at_step.setdefault(step, set()).add(run.run)
        for s in hits:
            rows.append({"run": run.run, "episode": s.episode_id,
                         "outcome": "success" if s.success else (s.failure_kind or "none"),
                         "first_unlatched": task.step_name(s.first_failed_step),
                         "implied": implied_step(task, s) or "none"})
    for step, names in sorted(at_step.items(), key=lambda kv: task.index(kv[0])):
        facts.append(book.add(f"chain_broken_at_{step}_runs", len(names), "+".join(
            r.ref for r in runs), "runs"))
    facts.append(book.add("chain_runs_checked", len(runs), "+".join(r.ref for r in runs),
                          "runs"))
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(not_known))
