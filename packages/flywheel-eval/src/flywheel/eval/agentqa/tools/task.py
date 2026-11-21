"""What the tools know about a task, and the `task_lookup` tool (DA-43 task 2.1).

The task view lives in `configs/eval/agentqa/tasks/<task>.yaml`: the scorer's step
order, which step each failure label implies, the signals each label needs, what each
artifact kind carries, and the relaxed-tolerance grid. Thresholds come from the
scorer's own config the view names, each with the unit the view gives it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, ToolResult, not_judged
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

TASKS = Path("configs") / "eval" / "agentqa" / "tasks"  # from the repo root, as agent.yaml


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LabelSpec(_Frozen):
    implies_step: str | None
    signals: list[str] = Field(default_factory=list)


class RelaxedSpec(_Frozen):
    label: str
    position_m: list[float] = Field(min_length=1)
    yaw_deg: float


class Component(_Frozen):
    name: str
    scale: float = Field(gt=0)  # the unit the distance counts this component in
    periodic: bool = False  # an angle: the difference is the shorter way round


class CoverageSpec(_Frozen):
    """How `coverage_distance` reads `Condition.vector` (spec 6.8)."""

    k: int = Field(gt=0)
    percentile: float = Field(gt=0, le=100)
    components: list[Component] = Field(min_length=1)  # in the order of the vector
    level_components: dict[int, list[str]]  # the physical components each level varies

    @model_validator(mode="after")
    def names_known(self) -> Self:
        known = {c.name for c in self.components}
        unknown = sorted({n for names in self.level_components.values() for n in names} - known)
        if unknown:
            raise ValueError(f"level_components name {unknown}, not components")
        return self


class TaskView(_Frozen):
    task_id: str
    scorer_config: str
    steps: list[str] = Field(min_length=1)
    threshold_units: dict[str, str] = Field(default_factory=dict)
    success_implies_step: str
    labels: dict[str, LabelSpec]
    latch_signals: dict[str, list[str]] = Field(default_factory=dict)
    provides: dict[str, list[str]] = Field(default_factory=dict)
    relaxed: RelaxedSpec | None = None
    coverage: CoverageSpec | None = None
    thresholds: dict[str, Any] = Field(default_factory=dict)  # filled from scorer_config
    source_ref: str = ""

    @model_validator(mode="after")
    def steps_known(self) -> Self:
        named = [self.success_implies_step, *self.latch_signals]
        named += [s.implies_step for s in self.labels.values() if s.implies_step]
        unknown = sorted({n for n in named if n not in self.steps})
        if unknown:
            raise ValueError(f"steps {unknown} are not steps of {self.task_id}")
        missing = sorted(set(self.thresholds) - set(self.threshold_units))
        if missing:
            raise ValueError(f"thresholds {missing} have no unit in threshold_units")
        return self

    def index(self, step: str) -> int:
        return self.steps.index(step)

    def step_name(self, index: int | None) -> str:
        return "none" if index is None else self.steps[index]


def load_task(task_id: str, root: Path = TASKS) -> TaskView:
    path = root / f"{task_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    scorer = yaml.safe_load((path.parent / raw["scorer_config"]).read_text(encoding="utf-8"))
    raw["thresholds"] = dict(scorer.get("thresholds") or {})
    raw["source_ref"] = path.as_posix()
    return TaskView.model_validate(raw)


def task_lookup(book: FactBook, task: TaskView, step: str | None = None) -> ToolResult:
    """Facts of the task: its steps in order, or one step; the scorer thresholds.

    `step` must be one of the task's steps (the closed set a model may ask for).
    """
    tool = "task_lookup"
    ref = task.source_ref
    if step is not None and step not in task.steps:
        return not_judged(book, tool, f"{step!r} is not a step of {task.task_id}", ref)
    facts = [book.add("task_steps", len(task.steps), ref, "steps")]
    rows: list[Row] = []
    for k, name in enumerate(task.steps):
        if step is not None and name != step:
            continue
        facts.append(book.add(f"step_{k + 1}_name", name, ref))
        rows.append({"step": k + 1, "name": name})
    for key, value in sorted(task.thresholds.items()):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            facts.append(book.add(f"threshold_{key}", float(value), ref,
                                  task.threshold_units[key]))
    return ToolResult(tool, tuple(facts), tuple(rows))
