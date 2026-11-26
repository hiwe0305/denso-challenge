"""The tools a plan may call, and the closed domains of their parameters (DA-43 task 4.2).

A plan (`configs/eval/agentqa/plans/<task>.yaml`) names tools and gives them parameters.
No parameter is a free number: each takes its value from a closed domain (a run of the
pack, a level that occurs in it, a label of the task view), and a plan value outside its
domain is refused when the plan is checked, before anything runs (architecture 20/11
section 6, B2; section 7).

Tools are registered explicitly: nothing is discovered, so the list of what the agent can
call is read from this file.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, get_args

from flywheel.contracts.artifacts import DatasetReport, Episode
from flywheel.contracts.evidence import InterventionKind
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import (
    ConditionSet,
    EntryView,
    JobMetrics,
    RunOutcomes,
    RunScores,
    RunTrace,
    StoreRows,
    ToolResult,
    merge,
    not_judged,
)
from flywheel.eval.agentqa.tools.clusters import failure_clusters
from flywheel.eval.agentqa.tools.cost import (
    check_costs,
    cost_lookup,
    load_costs,
    no_costs,
)
from flywheel.eval.agentqa.tools.coverage import coverage_distance
from flywheel.eval.agentqa.tools.history import history_lookup
from flywheel.eval.agentqa.tools.latch import latch_consistency
from flywheel.eval.agentqa.tools.lineage import lineage
from flywheel.eval.agentqa.tools.paired import paired_compare
from flywheel.eval.agentqa.tools.relaxed import relaxed_sweep
from flywheel.eval.agentqa.tools.signals import labels_seen, signal_presence
from flywheel.eval.agentqa.tools.steps import step_pass_table
from flywheel.eval.agentqa.tools.task import TaskView, task_lookup
from flywheel.eval.agentqa.tools.trace import no_tolerance, trace_stats
from flywheel.eval.agentqa.tools.train import logged_steps, train_window
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG
from flywheel.eval.config import ConfigError, load_system_thresholds


@dataclass(frozen=True)
class MeasureContext:
    task: TaskView
    runs: Mapping[str, RunScores]  # run name -> scores, in pack order
    kinds: frozenset[str]  # artifact kinds accepted in the pack
    # What the other accepted kinds hold; empty when the pack has none of them.
    traces: Mapping[str, RunTrace] = field(default_factory=dict)  # run name -> its trace
    jobs: Mapping[str, JobMetrics] = field(default_factory=dict)  # job_id -> its training log
    episodes: tuple[Episode, ...] = ()
    reports: Mapping[str, DatasetReport] = field(default_factory=dict)  # entry ref -> report
    entries: tuple[EntryView, ...] = ()  # every accepted entry as the pack declares it
    conditions: tuple[ConditionSet, ...] = ()  # `conditions` entries with their declared role
    ledger: StoreRows | None = None  # the pack's store snapshot of the ledger
    fix_rate: StoreRows | None = None  # and of the fix-rate events
    outcomes: Mapping[str, RunOutcomes] = field(default_factory=dict)  # run -> its K1 outcomes


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: int
    needs: tuple[str, ...]  # artifact kinds that must be in ctx.kinds
    params: Mapping[str, str]  # param name -> domain name
    run: Callable[[FactBook, MeasureContext, Mapping[str, Any]], ToolResult]
    reads_all: bool = False  # the result depends on every accepted entry, not only `needs`
    context_runs: bool = False  # reads every run of its kinds, whatever runs it names


# Domains a plan must give a value for; the others may be left out.
OPTIONAL = frozenset({"levels", "step"})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _names(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) for v in value)


def concerned_runs(params: Mapping[str, Any], ctx: MeasureContext) -> list[str]:
    """Names of the runs a call reads, in pack order; every run when it names none."""
    named: set[str] = set()
    constrained = False
    for key in ("runs", "run", "pairs"):
        if key not in params:
            continue
        constrained = True
        value = params[key]
        if value == "all":
            return list(ctx.runs)
        if isinstance(value, str):
            named.add(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    named.add(item)
                elif isinstance(item, list):
                    named.update(n for n in item if isinstance(n, str))
    if not constrained:
        return list(ctx.runs)
    return [r for r in ctx.runs if r in named]


def _check_one(domain: str, name: str, value: object, params: Mapping[str, Any],
               ctx: MeasureContext) -> list[str]:
    known = ", ".join(ctx.runs) or "none"
    if domain == "runs":
        if value == "all":
            return []
        if not _names(value):
            return [f"{name}: 'all' or a list of run names, got {value!r}"]
        assert isinstance(value, list)
        return [f"{name}: run {v!r} is not in the pack (runs: {known})"
                for v in value if v not in ctx.runs]
    if domain == "run":
        if not isinstance(value, str):
            return [f"{name}: one run name, got {value!r}"]
        return [] if value in ctx.runs else [
            f"{name}: run {value!r} is not in the pack (runs: {known})"]
    if domain == "pairs":
        if value == "all":
            return []
        if not isinstance(value, list) or not value:
            return [f"{name}: 'all' or a list of [a, b] run names, got {value!r}"]
        problems: list[str] = []
        for pair in value:
            if not (isinstance(pair, list) and len(pair) == 2
                    and all(isinstance(p, str) for p in pair)):
                problems.append(f"{name}: {pair!r} is not a pair [a, b] of run names")
                continue
            problems += [f"{name}: run {p!r} is not in the pack (runs: {known})"
                         for p in pair if p not in ctx.runs]
            if pair[0] == pair[1]:
                problems.append(f"{name}: {pair!r} compares a run with itself")
        return problems
    if domain == "levels":
        if value == "all":
            return []
        if not isinstance(value, list) or not value or not all(_is_int(v) for v in value):
            return [f"{name}: 'all' or a list of integer levels, got {value!r}"]
        present = {lv for r in concerned_runs(params, ctx) for lv in ctx.runs[r].levels()}
        return [f"{name}: level {v} does not occur in the runs concerned "
                f"(levels: {sorted(present)})" for v in value if v not in present]
    if domain == "labels":
        if value in ("seen", "all"):
            return []
        if not _names(value):
            return [f"{name}: 'seen', 'all' or a list of labels, got {value!r}"]
        assert isinstance(value, list)
        return [f"{name}: label {v!r} is not a label of {ctx.task.task_id}"
                for v in value if v not in ctx.task.labels]
    if domain == "jobs":
        if value == "all":
            return []
        if not _names(value):
            return [f"{name}: 'all' or a list of job ids, got {value!r}"]
        assert isinstance(value, list)
        known = ", ".join(ctx.jobs) or "none"
        return [f"{name}: job {v!r} is not in the pack (jobs: {known})"
                for v in value if v not in ctx.jobs]
    if domain == "window":
        if value in ("all", "last"):
            return []
        if not _is_int(value):
            return [f"{name}: 'all', 'last' or a logged step of the jobs, got {value!r}"]
        chosen = params.get("jobs", "all")
        names = (list(ctx.jobs) if chosen == "all" else
                 [j for j in chosen if isinstance(j, str) and j in ctx.jobs]
                 if isinstance(chosen, list) else [])
        return [f"{name}: step {value} is not a logged step of job {j}"
                for j in names if value not in logged_steps(ctx.jobs[j])]
    if domain in ("checks", "interventions"):
        valid = list(check_costs()) if domain == "checks" else list(get_args(InterventionKind))
        if value == "all":
            return []
        if not _names(value):
            return [f"{name}: 'all' or a list of {domain}, got {value!r}"]
        assert isinstance(value, list)
        return [f"{name}: {v!r} is not one of {', '.join(valid)}" for v in value
                if v not in valid]
    if domain == "step":
        if isinstance(value, str) and value in ctx.task.steps:
            return []
        return [f"{name}: {value!r} is not a step of {ctx.task.task_id} "
                f"(steps: {', '.join(ctx.task.steps)})"]
    return [f"{name}: unknown domain {domain!r}"]


def check_params(spec: ToolSpec, params: Mapping[str, Any], ctx: MeasureContext) -> list[str]:
    """What is wrong with `params` for `spec`: unknown, missing, or outside its domain."""
    problems = [f"{spec.name}: unknown parameter {p!r}" for p in params if p not in spec.params]
    for name, domain in spec.params.items():
        if name not in params:
            if name not in OPTIONAL:
                problems.append(f"{spec.name}: parameter {name!r} is missing")
            continue
        problems += [f"{spec.name}: {p}"
                     for p in _check_one(domain, name, params[name], params, ctx)]
    return problems


def _runs(params: Mapping[str, Any], ctx: MeasureContext) -> list[RunScores]:
    value = params.get("runs", "all")
    names = list(ctx.runs) if value == "all" else list(value)
    return [ctx.runs[n] for n in names]


def _task_lookup(book: FactBook, ctx: MeasureContext, params: Mapping[str, Any]) -> ToolResult:
    return task_lookup(book, ctx.task, params.get("step"))


def _step_pass_table(book: FactBook, ctx: MeasureContext,
                     params: Mapping[str, Any]) -> ToolResult:
    return step_pass_table(book, ctx.task, _runs(params, ctx))


def _failure_clusters(book: FactBook, ctx: MeasureContext,
                      params: Mapping[str, Any]) -> ToolResult:
    return failure_clusters(book, ctx.task, _runs(params, ctx), context=list(ctx.runs.values()))


def _latch_consistency(book: FactBook, ctx: MeasureContext,
                       params: Mapping[str, Any]) -> ToolResult:
    return latch_consistency(book, ctx.task, _runs(params, ctx))


def _signal_presence(book: FactBook, ctx: MeasureContext,
                     params: Mapping[str, Any]) -> ToolResult:
    value = params["labels"]
    if value == "seen":
        labels = labels_seen(list(ctx.runs.values()))
    elif value == "all":
        labels = sorted(ctx.task.labels)
    else:
        labels = list(value)
    return signal_presence(book, ctx.task, ctx.kinds, labels, list(ctx.runs.values()),
                           ctx.outcomes)


def _relaxed_sweep(book: FactBook, ctx: MeasureContext,
                   params: Mapping[str, Any]) -> ToolResult:
    return relaxed_sweep(book, ctx.task, _runs(params, ctx), ctx.outcomes, list(ctx.runs))


def _trace_stats(book: FactBook, ctx: MeasureContext,
                 params: Mapping[str, Any]) -> ToolResult:
    try:
        cfg, _ = load_system_thresholds(DEFAULT_SYSTEM_CONFIG)
    except ConfigError as error:
        return no_tolerance(book, f"tau_track cannot be read: {str(error)[:150]}")
    return trace_stats(book, _runs(params, ctx), dict(ctx.traces), cfg.r3,
                       f"{DEFAULT_SYSTEM_CONFIG.as_posix()} (r3)")


def _train_window(book: FactBook, ctx: MeasureContext,
                  params: Mapping[str, Any]) -> ToolResult:
    value = params["jobs"]
    names = list(ctx.jobs) if value == "all" else list(value)
    if not names:
        return not_judged(book, "train_window", "no job log in the pack", "pack.json")
    return merge("train_window", [train_window(book, ctx.jobs[n], params["window"])
                                  for n in names])


def _lineage(book: FactBook, ctx: MeasureContext, params: Mapping[str, Any]) -> ToolResult:
    return lineage(book, list(ctx.runs.values()), ctx.entries, ctx.episodes, ctx.jobs,
                   ctx.reports)


def _coverage_distance(book: FactBook, ctx: MeasureContext,
                       params: Mapping[str, Any]) -> ToolResult:
    return coverage_distance(book, ctx.task, _runs(params, ctx), ctx.conditions)


def _chosen(value: Any, known: list[str]) -> list[str]:
    return known if value == "all" else list(value)


def _cost_lookup(book: FactBook, ctx: MeasureContext, params: Mapping[str, Any]) -> ToolResult:
    try:
        costs, checks = load_costs(), check_costs()
    except (OSError, ValueError, KeyError) as error:
        return no_costs(book, f"costs.yaml or checks.yaml cannot be read: {str(error)[:150]}")
    held = ctx.ledger
    assert held is not None  # `needs` holds the kind, so measure skipped the call otherwise
    return cost_lookup(book, costs, checks, _chosen(params["checks"], list(checks)),
                       _chosen(params["interventions"], list(get_args(InterventionKind))),
                       held.rows, held.unreadable, "configs/eval/agentqa/costs.yaml", held.ref)


def _history_lookup(book: FactBook, ctx: MeasureContext,
                    params: Mapping[str, Any]) -> ToolResult:
    held = ctx.fix_rate
    assert held is not None
    return history_lookup(book, _chosen(params["interventions"],
                                        list(get_args(InterventionKind))), held.rows,
                          held.unreadable, held.ref)


def pairs_of(params: Mapping[str, Any], ctx: MeasureContext) -> list[tuple[str, str]]:
    value = params["pairs"]
    if value == "all":
        return list(combinations(ctx.runs, 2))
    return [(p[0], p[1]) for p in value]


def _paired_compare(book: FactBook, ctx: MeasureContext,
                    params: Mapping[str, Any]) -> ToolResult:
    pairs = pairs_of(params, ctx)
    if not pairs:
        return not_judged(book, "paired_compare", "fewer than two runs, so no pair", "-")
    levels = params.get("levels", "all")
    chosen = None if levels == "all" else list(levels)
    return merge("paired_compare", [
        paired_compare(book, ctx.runs[a], ctx.runs[b], chosen) for a, b in pairs])


REGISTRY: dict[str, ToolSpec] = {spec.name: spec for spec in (
    ToolSpec("task_lookup", 1, (), {"step": "step"}, _task_lookup),
    ToolSpec("step_pass_table", 1, ("scores",), {"runs": "runs"}, _step_pass_table),
    ToolSpec("failure_clusters", 2, ("scores",), {"runs": "runs"}, _failure_clusters,
             context_runs=True),
    ToolSpec("latch_consistency", 1, ("scores",), {"runs": "runs"}, _latch_consistency),
    # v2: a signal of `signal_measures` counts when the run's outcomes carry its measures
    ToolSpec("signal_presence", 2, ("scores",), {"labels": "labels"}, _signal_presence,
             reads_all=True),
    ToolSpec("paired_compare", 1, ("scores",), {"pairs": "pairs", "levels": "levels"},
             _paired_compare),
    ToolSpec("trace_stats", 2, ("scores", "trace"), {"runs": "runs"}, _trace_stats),
    ToolSpec("train_window", 1, ("metrics",), {"jobs": "jobs", "window": "window"},
             _train_window),
    ToolSpec("lineage", 1, ("scores",), {}, _lineage, reads_all=True),
    ToolSpec("coverage_distance", 3, ("scores", "conditions"), {"runs": "runs"},
             _coverage_distance),
    ToolSpec("cost_lookup", 2, ("ledger",),
             {"checks": "checks", "interventions": "interventions"}, _cost_lookup),
    ToolSpec("history_lookup", 2, ("fix_rate",), {"interventions": "interventions"},
             _history_lookup),
    # v2: per cluster, the yaw miss and where the tray comes to rest (height, tilt)
    ToolSpec("relaxed_sweep", 2, ("scores", "outcomes"), {"runs": "runs"}, _relaxed_sweep),
)}
