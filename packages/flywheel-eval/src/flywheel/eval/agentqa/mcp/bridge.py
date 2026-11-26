"""A transport-free bridge between the tool registry and a tool-calling shell (DA-49 task 2.1).

`ToolSession` holds one admitted pack open: its `MeasureContext` and one `FactBook` for
the session's life. From them it describes the 13 tools of `tools/registry.py` (name,
version, a short English description and a JSON Schema of the parameters whose closed
domains are `enum`s computed from the pack), and it runs a call exactly as step B2
(`round/measure.py`) runs one call of a plan: the parameters are checked with
`check_params` first, a value outside its domain refuses the call and nothing runs; a tool
whose artifact kind the pack lacks is skipped with the same `not_judged` fact as in a round.

Nothing here knows a wire protocol: a stdio server (task 2.2) or an agent loop imports it
directly. No parameter names a file: every value comes from a closed domain of the pack.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from flywheel.contracts.agentqa import AgentFact
from flywheel.contracts.evidence import InterventionKind
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.round.admit import Admitted

# Private, but `round/` may not be edited by DA-49; the round tests import it the same way.
from flywheel.eval.agentqa.round.measure import _context
from flywheel.eval.agentqa.round.records import Pack
from flywheel.eval.agentqa.tools.base import Row, ToolResult, not_judged
from flywheel.eval.agentqa.tools.cost import check_costs
from flywheel.eval.agentqa.tools.registry import (
    OPTIONAL,
    REGISTRY,
    MeasureContext,
    ToolSpec,
    check_params,
)
from flywheel.eval.agentqa.tools.train import logged_steps

MAX_STEP_ENUM = 64  # a job log can have tens of thousands of logged steps

Status = Literal["ran", "skipped", "refused"]

DESCRIPTIONS: dict[str, str] = {
    "task_lookup": (
        "Facts of the task view: the scorer's steps in order (or one step), and the scorer "
        "thresholds with their units."),
    "step_pass_table": (
        "For each run and level, and for all levels together: rollouts, successes, the "
        "fraction that latched each scorer step, and the step with the largest drop from "
        "the step before it."),
    "failure_clusters": (
        "Failed rollouts grouped by (first failed step, failure label, level), with each "
        "cluster's size and members and how many other runs of the pack have a cluster "
        "with the same key."),
    "latch_consistency": (
        "Rollouts whose outcome (a success, or a failure label that implies a step was done) "
        "contradicts their step chain, because the first unlatched step comes at or before "
        "the step the outcome implies; counted per run."),
    "signal_presence": (
        "For each failure label, whether the pack's artifacts carry the signals needed to "
        "judge it and which are missing; with K1 outcomes, per run, and for the carry label "
        "how the tray was held at the failure, per failure cluster."),
    "paired_compare": (
        "Run a minus run b, paired by condition: the mean difference with a bootstrap CI "
        "resampled within each level, the exact McNemar p on the discordant pairs, and a "
        "Wilson 95% interval of each run's success."),
    "trace_stats": (
        "From the trace files, the tracking error (command minus measured, upper and lower "
        "body) of failed and of succeeded rollouts against the tolerance of the system "
        "config, the worst channel, the share of cycles commanding a velocity, and the path "
        "length."),
    "train_window": (
        "For each training job, train and validation loss, loss per group, gradient norms "
        "and validation cadence over a window of the log: all of it, the validation interval "
        "of the last logged step, or the one around a logged step."),
    "lineage": (
        "The chain eval run -> checkpoint -> train job -> release -> dataset report, built "
        "only from ids the admitted records carry; a link that cannot be made is reported "
        "as not judged."),
    "coverage_distance": (
        "For each failed eval rollout whose condition the pack holds, its distance to the "
        "nearest train conditions against a leave-one-out threshold per level, and whether "
        "it lies within the train range; a verdict per failure cluster."),
    "cost_lookup": (
        "For each check of the check catalog and each intervention kind, the unit price from "
        "the price book and the ledger rows of past jobs of the same kind, estimated and "
        "measured kept apart."),
    "history_lookup": (
        "For each intervention kind, from the pack's fix-rate events: how many events, how "
        "many conditions they measured, how many were fixed, and the fixed share."),
    "relaxed_sweep": (
        "Per run and level, how many rollouts pass when the position tolerance is widened "
        "over the task's grid, from K1 outcome measures; per failure cluster of the relaxed "
        "label, the distance, the yaw miss and where the tray comes to rest."),
}

_PARAM_HELP: dict[str, str] = {
    "runs": "'all', or a non-empty list of run names of the pack.",
    "run": "One run name of the pack.",
    "pairs": ("'all' (every pair of runs, in pack order), or a non-empty list of [a, b] "
              "pairs of two different run names of the pack."),
    "levels": ("'all', or a non-empty list of levels; each level must occur in the runs "
               "the call concerns. Optional: 'all' when left out."),
    "labels": ("'seen' (the labels raised in the runs), 'all' (every label of the task), "
               "or a non-empty list of labels of the task."),
    "jobs": "'all', or a non-empty list of job ids logged in the pack.",
    "window": ("'all' (the whole log), 'last' (the validation interval of the last logged "
               "step), or a logged step of each job the call names (the validation "
               "interval it falls in)."),
    "checks": "'all', or a non-empty list of check ids of the check catalog.",
    "interventions": "'all', or a non-empty list of intervention kinds.",
    "step": "One step of the task. Optional: every step when left out.",
}


@dataclass(frozen=True)
class ToolDescription:
    name: str
    version: int
    description: str  # one or two English sentences for a model
    input_schema: dict[str, Any]  # JSON Schema (2020-12 vocabulary) of the params object
    needs: tuple[str, ...]  # artifact kinds the tool needs
    missing: tuple[str, ...]  # those of `needs` the pack does not hold


def _words(*words: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(words)}


def _strings(values: list[str]) -> dict[str, Any] | None:
    return {"type": "string", "enum": values} if values else None


def _list_of(item: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if item is None else {"type": "array", "minItems": 1, "items": item}


def _one_of(description: str, *alternatives: dict[str, Any] | None) -> dict[str, Any]:
    """`alternatives` that exist, under one description; `{"not": {}}` when none does."""
    kept = [a for a in alternatives if a is not None]
    if not kept:
        return {"description": description, "not": {}}
    if len(kept) == 1:
        return {"description": description, **kept[0]}
    return {"description": description, "anyOf": kept}


def _window_steps(ctx: MeasureContext) -> dict[str, Any] | None:
    steps = sorted({s for job in ctx.jobs.values() for s in logged_steps(job)})
    if not steps:
        return None
    if len(steps) <= MAX_STEP_ENUM:
        return {"type": "integer", "enum": steps}
    return {"type": "integer", "minimum": steps[0], "maximum": steps[-1],
            "description": "Must be a logged step of each job the call names."}


def param_schema(domain: str, ctx: MeasureContext) -> dict[str, Any]:
    """The JSON Schema of one parameter of `domain`, its closed domain read from `ctx`.

    It never accepts a value `check_params` refuses for its type or for a name the pack
    lacks; it is wider only where the domain depends on the other parameters of the call
    (the levels of the runs it concerns, the steps of the jobs it names, a pair of one run
    with itself). `window` streams the training logs: call it once per pack.
    """
    if domain not in _PARAM_HELP:
        raise ValueError(f"unknown parameter domain {domain!r}")
    help_ = _PARAM_HELP[domain]
    runs = _strings(list(ctx.runs))
    if domain == "runs":
        return _one_of(help_, _words("all"), _list_of(runs))
    if domain == "run":
        return _one_of(help_, runs)
    if domain == "pairs":
        pair = None if runs is None else {"type": "array", "minItems": 2, "maxItems": 2,
                                          "items": runs}
        return _one_of(help_, _words("all"), _list_of(pair))
    if domain == "levels":
        present = sorted({lv for r in ctx.runs.values() for lv in r.levels()})
        level = {"type": "integer", "enum": present} if present else None
        return _one_of(help_, _words("all"), _list_of(level))
    if domain == "labels":
        return _one_of(help_, _words("seen", "all"), _list_of(_strings(sorted(ctx.task.labels))))
    if domain == "jobs":
        return _one_of(help_, _words("all"), _list_of(_strings(list(ctx.jobs))))
    if domain == "window":
        return _one_of(help_, _words("all", "last"), _window_steps(ctx))
    if domain == "checks":
        return _one_of(help_, _words("all"), _list_of(_strings(list(check_costs()))))
    if domain == "interventions":
        kinds = [str(k) for k in get_args(InterventionKind)]
        return _one_of(help_, _words("all"), _list_of(_strings(kinds)))
    assert domain == "step"
    return _one_of(help_, _strings(list(ctx.task.steps)))


def _object_schema(spec: ToolSpec, schema_of: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: schema_of(domain) for name, domain in spec.params.items()},
        "required": [name for name in spec.params if name not in OPTIONAL],
        "additionalProperties": False,
    }


def input_schema(spec: ToolSpec, ctx: MeasureContext) -> dict[str, Any]:
    """The JSON Schema of the params object of `spec` on the pack of `ctx`."""
    return _object_schema(spec, lambda domain: param_schema(domain, ctx))


def _json_ready(value: Any) -> Any:
    """`value` with every non-finite float as its `str()`, as `FactBook` stores them."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


@dataclass(frozen=True)
class CallOutcome:
    tool: str
    version: int
    params: Mapping[str, Any]
    status: Status
    problems: tuple[str, ...] = ()  # check_params messages when refused
    facts: tuple[AgentFact, ...] = ()  # the facts the ToolResult cites, in order, once each
    rows: tuple[Row, ...] = ()
    not_judged: tuple[str, ...] = ()

    @property
    def is_error(self) -> bool:
        return self.status == "refused"

    @property
    def fact_ids(self) -> tuple[str, ...]:
        return tuple(f.fact_id for f in self.facts)

    def payload(self) -> dict[str, Any]:
        """The outcome as plain JSON values (`json.dumps(..., allow_nan=False)` accepts it)."""
        return {
            "tool": self.tool,
            "version": self.version,
            "status": self.status,
            "problems": list(self.problems),
            "facts": [{"fact_id": f.fact_id, "name": f.name, "value": _json_ready(f.value),
                       "unit": f.unit, "source_ref": f.source_ref} for f in self.facts],
            "rows": [_json_ready(row) for row in self.rows],
            "not_judged": list(self.not_judged),
        }


class UnknownTool(KeyError):
    """A call names a tool the registry does not hold."""


@dataclass
class _Cache:
    tools: list[ToolDescription] | None = None
    schemas: dict[str, dict[str, Any]] = field(default_factory=dict)


class ToolSession:
    """One pack held open: its MeasureContext and one FactBook for the session's life.

    A fact name fixes its value within a round, so calling the same tool with the same
    parameters again returns the same facts, with the same ids.
    """

    def __init__(self, ctx: MeasureContext, book: FactBook | None = None) -> None:
        self._ctx = ctx
        self._book = FactBook() if book is None else book
        self._cache = _Cache()

    @classmethod
    def from_admitted(cls, pack: Pack, admitted: Admitted) -> ToolSession:
        """The session of a pack that step B1 admitted; `PlanRefused` if its runs clash."""
        ctx, _ = _context(pack, admitted)
        return cls(ctx)

    @property
    def ctx(self) -> MeasureContext:
        return self._ctx

    @property
    def book(self) -> FactBook:
        return self._book

    def _schema_of(self, domain: str) -> dict[str, Any]:
        if domain not in self._cache.schemas:
            self._cache.schemas[domain] = param_schema(domain, self._ctx)
        return copy.deepcopy(self._cache.schemas[domain])

    def _missing(self, spec: ToolSpec) -> tuple[str, ...]:
        return tuple(kind for kind in spec.needs if kind not in self._ctx.kinds)

    def tools(self) -> list[ToolDescription]:
        """Every tool of the registry, in its order; one missing a kind is still listed."""
        if self._cache.tools is None:
            described = []
            for spec in REGISTRY.values():
                missing = self._missing(spec)
                text = DESCRIPTIONS[spec.name]
                if missing:
                    text += (" Not available on this pack: no entry of kind "
                             f"{', '.join(missing)}.")
                described.append(ToolDescription(
                    spec.name, spec.version, text, _object_schema(spec, self._schema_of),
                    spec.needs, missing))
            self._cache.tools = described
        return list(self._cache.tools)

    def call(self, name: str, params: Mapping[str, Any]) -> CallOutcome:
        """Run one tool as step B2 runs one call of a plan.

        Raises `UnknownTool` for a name the registry does not hold. Parameters outside
        their domain refuse the call: nothing runs and no fact is written. A tool that
        raises is a programming error and propagates; the caller decides what to do.
        """
        spec = REGISTRY.get(name)
        if spec is None:
            raise UnknownTool(name)
        given = dict(params)
        problems = check_params(spec, given, self._ctx)
        if problems:
            return CallOutcome(spec.name, spec.version, given, "refused", tuple(problems))
        missing = self._missing(spec)
        result: ToolResult
        status: Status
        if missing:
            result = not_judged(self._book, spec.name,
                                f"no entry of kind {', '.join(missing)} in the pack",
                                "pack.json")
            status = "skipped"
        else:
            result = spec.run(self._book, self._ctx, given)
            status = "ran"
        facts = tuple(self._book.get(f) for f in dict.fromkeys(result.facts))
        return CallOutcome(spec.name, spec.version, given, status, (), facts,
                           tuple(result.rows), tuple(result.not_judged))
