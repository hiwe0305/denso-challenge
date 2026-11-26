"""What the tools know about a task, and the `task_lookup` tool (DA-43 task 2.1).

The task view lives in `configs/eval/agentqa/tasks/<task>.yaml`: the scorer's step
order, which step each failure label implies, the signals each label needs, what each
artifact kind carries, and the relaxed-tolerance grid. Thresholds come from the
scorer's own config the view names, each with the unit the view gives it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from flywheel.contracts.outcome import MEASURE_NAME, ScorerVerdict
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


MeasureName = Annotated[str, Field(pattern=MEASURE_NAME)]
# Fields of a `ScorerVerdict` that a rollout may leave null: what `where: verdict` may name.
VERDICT_FIELDS = ("failure_label", "failure_t", "step_latch_t", "at_failure")


class SignalMeasures(_Frozen):
    """Where a signal sits in a `RolloutOutcome` (K1): the measures that carry it.

    `where`: `final` and `extrema` are the outcome's measure maps, `at_failure` the
    verdict's, `verdict` the verdict's own fields (`failure_t`). The signal is there for
    a rollout when every name is there and not null.
    """

    where: Literal["final", "extrema", "at_failure", "verdict"]
    names: list[MeasureName] = Field(min_length=1)

    @model_validator(mode="after")
    def verdict_fields(self) -> Self:
        if self.where == "verdict":
            wrong = [n for n in self.names
                     if n not in VERDICT_FIELDS or n not in ScorerVerdict.model_fields]
            if wrong:
                raise ValueError(f"{wrong} is not a field a verdict may leave null "
                                 f"(fields: {', '.join(VERDICT_FIELDS)})")
        return self


class RelaxedSpec(_Frozen):
    label: str
    position_m: list[float] = Field(min_length=1)
    yaw_deg: float
    # A `signal_measures` entry, `where: final`, with one name in `_m` (the distance to
    # the target) and one in `_deg` (the yaw error): the measures the sweep compares.
    signal: str
    # Where the tray comes to rest (optional, both or neither): a `signal_measures` entry,
    # `where: final`, with one name in `_m` (the position [x, y, z]) and one in `_quat` (the
    # orientation, w x y z), and the margin (m) above the successes' rest height beyond
    # which a failed rollout counts as resting raised.
    rest_signal: str | None = None
    rest_margin_m: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def rest_both_or_neither(self) -> Self:
        if (self.rest_signal is None) != (self.rest_margin_m is None):
            raise ValueError("relaxed: rest_signal and rest_margin_m go together")
        return self


class CarrySpec(_Frozen):
    """How the tray was held when a carrying label was raised (`signal_presence` v3).

    Each `*_signal` is a `signal_measures` entry that `labels.<label>.signals` lists:
    `tilt_signal` one name in `_deg`; `contact_signal` the hands' contacts, every name a
    boolean (both hands hold the tray when all are true); `table_signal` one name, the table
    the tray is on, `off_table` the value that means on no table; `time_signal` one name,
    the time of the failure in s (the verdict's `failure_t`, or a name in `_s`).
    """

    label: str
    tilt_signal: str
    contact_signal: str
    table_signal: str
    off_table: str
    time_signal: str


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
    # True: tau_cov, d and the domain bounds use every train condition of the run, projected
    # onto the level's components (spec 6.8); False: only the train conditions of that level.
    pool_levels: bool = True

    @model_validator(mode="after")
    def names_known(self) -> Self:
        known = {c.name for c in self.components}
        unknown = sorted({n for names in self.level_components.values() for n in names} - known)
        if unknown:
            raise ValueError(f"level_components name {unknown}, not components")
        return self


# A measure reference of `measure_compare` and `measure_tally` (DA-52): where it sits, the
# measure name, then optionally `[k]` (one component of a list) or `.tilt` (the tilt of a
# `_quat`). `condition` reads the rollout's `Condition.values`.
MEASURE_WHERE = ("final", "extrema", "at_failure", "verdict", "condition")
MEASURE_REF = (r"^(?P<where>final|extrema|at_failure|verdict|condition)\."
               r"(?P<name>[a-z][a-z0-9]*(?:_[a-z0-9]+)*)"
               r"(?:\[(?P<index>0|[1-9][0-9]*)\]|\.(?P<derived>tilt))?$")
# The unit of a number, read off its name (contract `flywheel.contracts.outcome`).
SUFFIX_UNITS = {"_m": "m", "_deg": "deg", "_rad": "rad", "_s": "s", "_frac": "frac"}


def measure_unit(ref: str) -> str:
    """The unit of the number a measure reference gives; "" when its name says none.

    A `.tilt` is in deg; a verdict field ending in `_t` is a sim time (contract
    `ScorerVerdict`: `failure_t`, `step_latch_t`), in s; otherwise the name's suffix.
    """
    hit = re.match(MEASURE_REF, ref)
    if hit is None:
        return ""
    if hit["derived"] == "tilt":
        return "deg"
    name = hit["name"]
    if hit["where"] == "verdict" and name.endswith("_t"):
        return "s"
    return next((u for s, u in SUFFIX_UNITS.items() if name.endswith(s)), "")


class ThresholdRef(_Frozen):
    """A scorer threshold a measure is compared with: its key, and which side is beyond it.

    `beyond: above` counts a value greater than the threshold, `below` a smaller one;
    `absolute` compares the absolute value (a signed error).
    """

    threshold: str
    beyond: Literal["above", "below"]
    absolute: bool = False


class MeasuresSpec(_Frozen):
    """How `measure_compare` and `measure_tally` compare a cluster with a reference (DA-52)."""

    low_percentile: float = Field(ge=0, lt=100)
    high_percentile: float = Field(gt=0, le=100)
    min_reference: int = Field(gt=0)  # judged rollouts the reference needs for bounds
    max_values: int = Field(gt=0)  # distinct values of a tally given their own facts
    thresholds: dict[Annotated[str, Field(pattern=MEASURE_REF)], ThresholdRef] = Field(
        default_factory=dict)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.low_percentile >= self.high_percentile:
            raise ValueError("measures: low_percentile must be below high_percentile")
        return self


class TaskView(_Frozen):
    task_id: str
    scorer_config: str
    steps: list[str] = Field(min_length=1)
    threshold_units: dict[str, str] = Field(default_factory=dict)
    success_implies_step: str
    labels: dict[str, LabelSpec]
    # Labels whose cause may be the whole-body controller, and steps in which the robot
    # walks: the scope of the run-level tracking rules (design 19/11 section 5.3 rows 3-4).
    runtime_labels: list[str] = Field(default_factory=list)
    motion_steps: list[str] = Field(default_factory=list)
    latch_signals: dict[str, list[str]] = Field(default_factory=dict)
    provides: dict[str, list[str]] = Field(default_factory=dict)
    signal_measures: dict[str, SignalMeasures] = Field(default_factory=dict)
    relaxed: RelaxedSpec | None = None
    carry: CarrySpec | None = None
    coverage: CoverageSpec | None = None
    measures: MeasuresSpec | None = None
    thresholds: dict[str, Any] = Field(default_factory=dict)  # filled from scorer_config
    source_ref: str = ""

    @model_validator(mode="after")
    def steps_known(self) -> Self:
        named = [self.success_implies_step, *self.latch_signals, *self.motion_steps]
        named += [s.implies_step for s in self.labels.values() if s.implies_step]
        unknown = sorted({n for n in named if n not in self.steps})
        if unknown:
            raise ValueError(f"steps {unknown} are not steps of {self.task_id}")
        strange = sorted(set(self.runtime_labels) - set(self.labels))
        if strange:
            raise ValueError(f"runtime_labels {strange} are not labels of {self.task_id}")
        missing = sorted(set(self.thresholds) - set(self.threshold_units))
        if missing:
            raise ValueError(f"thresholds {missing} have no unit in threshold_units")
        if self.relaxed is not None:
            self.relaxed_measures()
            if self.relaxed.rest_signal is not None:
                self.rest_measures()
        if self.carry is not None:
            self.carry_measures()
        if self.measures is not None:
            self.measure_thresholds()
        return self

    def measure_thresholds(self) -> None:
        """Check the `measures.thresholds` map: known keys, and units that agree."""
        assert self.measures is not None
        for ref, spec in self.measures.thresholds.items():
            if spec.threshold not in self.thresholds:
                raise ValueError(f"measures.thresholds.{ref}: {spec.threshold!r} is not a "
                                 f"threshold of {self.scorer_config}")
            want = self.threshold_units.get(spec.threshold, "")
            if measure_unit(ref) != want:
                raise ValueError(f"measures.thresholds.{ref}: the measure is in "
                                 f"{measure_unit(ref) or 'no unit'}, {spec.threshold} in {want}")

    def relaxed_measures(self) -> tuple[str, str]:
        """(distance, yaw) measure names of `final` the relaxed sweep reads.

        Read by unit from the `signal_measures` entry `relaxed.signal` names, so each
        measure name is written once in the task view.
        """
        if self.relaxed is None:
            raise ValueError(f"{self.task_id} declares no relaxed block")
        spec = self.signal_measures.get(self.relaxed.signal)
        if spec is None:
            raise ValueError(f"relaxed.signal {self.relaxed.signal!r} is not in signal_measures")
        if spec.where != "final":
            raise ValueError(f"relaxed.signal {self.relaxed.signal!r}: the measures must be "
                             "final ones (where: final)")
        dist = [n for n in spec.names if n.endswith("_m")]
        yaw = [n for n in spec.names if n.endswith("_deg")]
        if len(dist) != 1 or len(yaw) != 1:
            raise ValueError(f"relaxed.signal {self.relaxed.signal!r}: one name in _m and one "
                             f"in _deg are needed, got {spec.names}")
        return dist[0], yaw[0]

    def rest_measures(self) -> tuple[str, str] | None:
        """(position, quaternion) measure names of `final` where the tray comes to rest.

        Read by unit from the `signal_measures` entry `relaxed.rest_signal` names; None when
        the relaxed block declares no rest signal.
        """
        if self.relaxed is None or self.relaxed.rest_signal is None:
            return None
        name = self.relaxed.rest_signal
        spec = self.signal_measures.get(name)
        if spec is None:
            raise ValueError(f"relaxed.rest_signal {name!r} is not in signal_measures")
        if spec.where != "final":
            raise ValueError(f"relaxed.rest_signal {name!r}: the measures must be final ones "
                             "(where: final)")
        pos = [n for n in spec.names if n.endswith("_m")]
        quat = [n for n in spec.names if n.endswith("_quat")]
        if len(pos) != 1 or len(quat) != 1:
            raise ValueError(f"relaxed.rest_signal {name!r}: one name in _m and one in _quat "
                             f"are needed, got {spec.names}")
        return pos[0], quat[0]

    def carry_measures(self) -> dict[str, tuple[str, list[str]]]:
        """role (tilt, contact, table, time) -> (where, names) of the `carry` block's signals."""
        if self.carry is None:
            raise ValueError(f"{self.task_id} declares no carry block")
        c = self.carry
        label = self.labels.get(c.label)
        if label is None:
            raise ValueError(f"carry.label {c.label!r} is not a label of {self.task_id}")
        out: dict[str, tuple[str, list[str]]] = {}
        for role, name in (("tilt", c.tilt_signal), ("contact", c.contact_signal),
                           ("table", c.table_signal), ("time", c.time_signal)):
            spec = self.signal_measures.get(name)
            if spec is None:
                raise ValueError(f"carry.{role}_signal {name!r} is not in signal_measures")
            if name not in label.signals:
                raise ValueError(f"carry.{role}_signal {name!r} is not a signal of {c.label}")
            out[role] = (spec.where, list(spec.names))
        tilt, table, time = out["tilt"][1], out["table"][1], out["time"][1]
        if len(tilt) != 1 or not tilt[0].endswith("_deg"):
            raise ValueError(f"carry.tilt_signal {c.tilt_signal!r}: one name in _deg is "
                             f"needed, got {tilt}")
        if len(table) != 1:
            raise ValueError(f"carry.table_signal {c.table_signal!r}: one name is needed, "
                             f"got {table}")
        if len(time) != 1 or not (time[0].endswith("_s") or time[0] == "failure_t"):
            raise ValueError(f"carry.time_signal {c.time_signal!r}: one name in _s (or "
                             f"failure_t) is needed, got {time}")
        return out

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
        return not_judged(book, tool, f"{step!r} is not a step of {task.task_id}", ref,
                          step)
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
