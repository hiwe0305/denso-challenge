"""`failure_clusters`: failures grouped by (first failed step, label, level) (DA-43 task 2.2).

The key of spec 6.3, as the team grouped `C_70`'s 50 failures into c1-c8 and the rest
(docs/he/tray.md 20.2). Per cluster: its size, its members, and how many other runs
given have a cluster with the same key, so a fault that repeats across checkpoints
(a scorer fault, say) shows as such. Successes are left out; a success whose steps
did not all latch is the business of `latch_consistency`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, RunScores, ToolResult, not_judged
from flywheel.eval.agentqa.tools.task import TaskView

TOOL = "failure_clusters"
Key = tuple[str, str, int | None]


def keys_of(task: TaskView, run: RunScores) -> dict[Key, list[Score]]:
    out: dict[Key, list[Score]] = defaultdict(list)
    for s in run.scores:
        if s.success:
            continue
        out[(task.step_name(s.first_failed_step), s.failure_kind or "none", s.level)].append(s)
    return out


def slug(key: Key) -> str:
    step, label, level = key
    return f"{step}_{label}_l{level}"


def failure_clusters(book: FactBook, task: TaskView, runs: Sequence[RunScores],
                     min_size: int = 1) -> ToolResult:
    if not runs:
        return not_judged(book, TOOL, "no run given", "-")
    by_run = {run.run: keys_of(task, run) for run in runs}
    facts: list[str] = []
    rows: list[Row] = []
    for run in runs:
        clusters = by_run[run.run]
        facts.append(book.add(f"{run.run}_failures", sum(len(m) for m in clusters.values()),
                              run.ref, "rollouts"))
        facts.append(book.add(f"{run.run}_clusters", len(clusters), run.ref, "clusters"))
        order = sorted(clusters, key=lambda k: (-len(clusters[k]), task.steps.index(k[0])
                                               if k[0] in task.steps else len(task.steps),
                                               k[1], k[2] if k[2] is not None else -1))
        for key in order:
            members = clusters[key]
            if len(members) < min_size:
                continue
            name = f"{run.run}_cluster_{slug(key)}"
            others = sum(1 for other, c in by_run.items() if other != run.run and key in c)
            facts.append(book.add(f"{name}_size", len(members), run.ref, "rollouts"))
            facts.append(book.add(f"{name}_in_other_runs", others, run.ref, "runs"))
            step, label, level = key
            rows.append({"run": run.run, "first_failed_step": step, "label": label,
                         "level": -1 if level is None else level, "size": len(members),
                         "in_other_runs": others,
                         "members": " ".join(s.episode_id for s in members)})
    return ToolResult(TOOL, tuple(facts), tuple(rows))
