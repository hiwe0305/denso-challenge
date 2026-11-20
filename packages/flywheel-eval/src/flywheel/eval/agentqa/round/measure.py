"""Step B2, measure: run the plan's tools over what step B1 admitted (DA-43 task 4.2).

The plan is checked as a whole first: an unknown tool, a missing or unknown parameter, a
value outside its closed domain refuses it before anything runs. Then each call runs in
plan order; a call whose artifact kind is not in the pack is skipped, and the reason is
written as a fact, so silence is never read as "clean". A tool that raises is a
programming error and propagates.

Written into the run directory: `facts.jsonl` (every fact, with the call that first made
it), `tool_calls.jsonl` (what each call read and produced), `tables/<call>-<tool>.json`
(the rows behind each call's facts). Same pack and same plan give the same bytes.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.round.admit import Admitted
from flywheel.eval.agentqa.round.records import (
    FactRecord,
    Pack,
    PackEntry,
    Record,
    ToolCallRecord,
)
from flywheel.eval.agentqa.tools.base import RunScores, ToolResult, not_judged
from flywheel.eval.agentqa.tools.registry import (
    REGISTRY,
    MeasureContext,
    ToolSpec,
    check_params,
    concerned_runs,
)
from flywheel.eval.agentqa.tools.task import load_task
from pydantic import Field, ValidationError

FACTS_FILE = "facts.jsonl"
CALLS_FILE = "tool_calls.jsonl"
TABLES_DIR = "tables"


class PlanRefused(ValueError):
    """The plan or the declaration of the runs cannot be used; nothing was run."""


class PlanCall(Record):
    tool: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class Plan(Record):
    task_id: str = Field(min_length=1)
    calls: list[PlanCall] = Field(min_length=1)


@dataclass(frozen=True)
class MeasureResult:
    book: FactBook
    calls: list[ToolCallRecord]
    facts: list[FactRecord]


def plan_of(task_id: str) -> Path:
    """The plan of a task, from the repo root (as `tools.task.TASKS`)."""
    return Path("configs") / "eval" / "agentqa" / "plans" / f"{task_id}.yaml"


def read_plan(path: Path) -> Plan:
    try:
        return Plan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise PlanRefused(f"{path}: {str(error).strip().splitlines()[0][:200]}") from error


def needed_kinds(plan: Plan) -> list[str]:
    """Artifact kinds the plan's known tools need, in plan order, once each."""
    kinds: list[str] = []
    for call in plan.calls:
        spec = REGISTRY.get(call.tool)
        for kind in () if spec is None else spec.needs:
            if kind not in kinds:
                kinds.append(kind)
    return kinds


def _context(pack: Pack, admitted: Admitted) -> tuple[MeasureContext, list[PackEntry]]:
    entries = [e for e in pack.entries if e.ref in admitted.records]
    runs: dict[str, RunScores] = {}
    for entry in entries:
        if entry.kind != "scores":
            continue
        name = entry.subject.get("run")
        if not name:
            raise PlanRefused(f"{entry.ref}: a scores entry must declare subject.run")
        if name in runs:
            raise PlanRefused(f"{entry.ref}: run {name!r} is already declared by "
                              f"{runs[name].ref}")
        scores = tuple(r for r in admitted.records[entry.ref] if isinstance(r, Score))
        runs[name] = RunScores(run=name, ref=entry.ref, scores=scores)
    task = load_task(pack.task_id)
    return MeasureContext(task, runs, frozenset(e.kind for e in entries)), entries


def check_plan(plan: Plan, ctx: MeasureContext) -> list[str]:
    problems: list[str] = []
    for k, call in enumerate(plan.calls, start=1):
        spec = REGISTRY.get(call.tool)
        if spec is None:
            problems.append(f"call {k}: unknown tool {call.tool!r} "
                            f"(tools: {', '.join(sorted(REGISTRY))})")
        else:
            problems += [f"call {k}: {p}" for p in check_params(spec, call.params, ctx)]
    return problems


def _inputs(spec: ToolSpec, params: dict[str, Any], ctx: MeasureContext,
            entries: Sequence[PackEntry]) -> list[str]:
    """sha256 of the accepted entries a call reads, sorted and once each."""
    runs = set(concerned_runs(params, ctx))
    shas: set[str] = set()
    for entry in entries:
        if not (spec.reads_all or entry.kind in spec.needs):
            continue
        if entry.kind == "scores" and not spec.reads_all and entry.subject.get("run") not in runs:
            continue
        shas.add(entry.sha256)
    return sorted(shas)


def _jsonl(lines: Sequence[Record]) -> str:
    return "".join(r.model_dump_json() + "\n" for r in lines)


def measure(pack: Pack, admitted: Admitted, plan_path: Path, out: Path) -> MeasureResult:
    plan = read_plan(plan_path)
    if plan.task_id != pack.task_id:
        raise PlanRefused(f"{plan_path}: the plan is for {plan.task_id!r}, the pack for "
                          f"{pack.task_id!r}")
    ctx, entries = _context(pack, admitted)
    problems = check_plan(plan, ctx)
    if problems:
        raise PlanRefused("; ".join(problems))

    book = FactBook()
    calls: list[ToolCallRecord] = []
    facts: list[FactRecord] = []
    tables: dict[str, list[Any]] = {}
    for k, call in enumerate(plan.calls, start=1):
        spec = REGISTRY[call.tool]
        call_id = f"T{k}"
        missing = [kind for kind in spec.needs if kind not in ctx.kinds]
        before = len(book.facts)
        result: ToolResult
        if missing:
            reason = f"no entry of kind {', '.join(missing)} in the pack"
            result = not_judged(book, spec.name, reason, "pack.json")
            status = "skipped"
        else:
            result = spec.run(book, ctx, call.params)
            status = "ran"
            reason = ""
        facts += [FactRecord(fact_id=f.fact_id, name=f.name, value=f.value, unit=f.unit,
                             source_ref=f.source_ref, provenance="code", tool_call_id=call_id)
                  for f in book.facts[before:]]
        if result.rows:
            tables[f"{call_id}-{spec.name}.json"] = [dict(row) for row in result.rows]
        calls.append(ToolCallRecord(
            call_id=call_id, tool=spec.name, version=spec.version, params=call.params,
            input_sha256=[] if missing else _inputs(spec, call.params, ctx, entries),
            fact_ids=list(dict.fromkeys(result.facts)), not_judged=list(result.not_judged),
            status=status, reason=reason))  # type: ignore[arg-type]

    out.mkdir(parents=True, exist_ok=True)
    (out / FACTS_FILE).write_text(_jsonl(facts), encoding="utf-8")
    (out / CALLS_FILE).write_text(_jsonl(calls), encoding="utf-8")
    if tables:
        (out / TABLES_DIR).mkdir(exist_ok=True)
    for name, rows in tables.items():
        (out / TABLES_DIR / name).write_text(json.dumps(rows, indent=2) + "\n",
                                             encoding="utf-8")
    return MeasureResult(book, calls, facts)
