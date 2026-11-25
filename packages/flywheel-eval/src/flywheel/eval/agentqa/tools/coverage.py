"""`coverage_distance`: is a failed condition near what the policy was trained on? (task 3.3)

Spec 6.8, step 8. For each failed eval rollout whose condition the pack holds:

- `d`: the mean distance to the `k` nearest train conditions;
- `tau_cov` per level: the percentile (`coverage.percentile`) of the same quantity over the
  train conditions, each left out of its own neighbours (leave-one-out);
- in domain: every component the level varies lies within [min, max] of the train
  conditions.

The train conditions are all of the run's, both levels (spec 6.8: "in the train set"); the
level only picks which components enter the vector (`level_components`). With
`coverage.pool_levels: false` only the train conditions of the failure's own level are used.

Each component is read by name from `Condition.values`, never by its place in `vector`.
The distance is the Euclidean norm of the component differences, each divided by the scale
the task view gives it; an angle takes the shorter way round. The lane cannot import the
adapter's own distance, so the groups, scales and `k` are the task view's (`coverage`).

The pack says which `conditions` entry is train and which is eval (`subject.role`); an entry
that does not say is not read. An entry may also name the run it belongs to (`subject.run`):
runs of one pack may have trained on different cuts. A run reads the entries of its role that
name it, else those that name no run. While no train entry names a run, every run reads the
same pooled train conditions and the facts are `tau_cov_l{level}` and
`coverage_train_l{level}`; once one does, each run has its own tau_cov and the facts are
`{run}_tau_cov_l{level}` and `{run}_coverage_train_l{level}` (never the unprefixed ones).

A cluster gets a verdict only from members whose condition is found (by the level and seed
of the rollout's `episode_id`); the rest are counted and said.
Evidence cards are not an admitted kind, so no `coverage_distance` check is taken from one.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

import numpy as np
from flywheel.contracts.entities import Condition
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import (
    ConditionSet,
    Row,
    RunScores,
    ToolResult,
    condition_of,
    not_judged,
)
from flywheel.eval.agentqa.tools.clusters import keys_of, slug
from flywheel.eval.agentqa.tools.task import CoverageSpec, TaskView
from numpy.typing import NDArray

TOOL = "coverage_distance"
UNIT = "jitter"  # the distance counts each component in the unit of its scale
_CONDITION = re.compile(r"^l(?P<level>\d+)-s(?P<seed>\d+)$")

Matrix = NDArray[np.float64]


def _split(sets: Sequence[ConditionSet], role: str, run: str = "") -> list[Condition]:
    """The conditions of `role` for `run`: the entries naming the run, else the undeclared ones."""
    of_role = [s for s in sets if s.role == role]
    named = [s for s in of_role if run and s.run == run]
    return [c for s in (named or [s for s in of_role if not s.run]) for c in s.conditions]


def _distances(spec: CoverageSpec, names: Sequence[str], point: Matrix, others: Matrix) -> Matrix:
    """Distance of `point` (vector of the level's components) to every row of `others`."""
    scales = np.array([c.scale for c in spec.components if c.name in names])
    periodic = np.array([c.periodic for c in spec.components if c.name in names])
    diff = others - point
    wrapped = np.arctan2(np.sin(diff), np.cos(diff))
    diff = np.where(periodic, wrapped, diff)
    return np.sqrt(((diff / scales) ** 2).sum(axis=1))  # type: ignore[no-any-return]


def _matrix(spec: CoverageSpec, level: int,
            conds: Sequence[Condition]) -> tuple[Matrix | None, str]:
    """The components of `level`, read by name from `Condition.values`, one row per condition.

    None and the reason (a name) when a condition lacks a component or holds a non-number.
    """
    keep = [c.name for c in spec.components if c.name in spec.level_components[level]]
    rows = []
    for cond in conds:
        row = []
        for name in keep:
            value = cond.values.get(name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                return None, f"component {name!r} is missing or not a number in a condition"
            row.append(float(value))
        rows.append(row)
    return np.array(rows, dtype=np.float64), ""


def _knn_mean(spec: CoverageSpec, level: int, point: Matrix, train: Matrix,
              skip: int | None = None) -> float:
    names = spec.level_components[level]
    dist = _distances(spec, names, point, train)
    if skip is not None:
        dist = np.delete(dist, skip)
    return float(np.sort(dist)[: spec.k].mean())


def _level_reference(spec: CoverageSpec, level: int, train: Matrix) -> float:
    """tau_cov: the percentile of the leave-one-out mean-kNN distance over `train`."""
    loo = [_knn_mean(spec, level, train[i], train, skip=i) for i in range(len(train))]
    return float(np.percentile(loo, spec.percentile))


def _scope(book: FactBook, task: TaskView, spec: CoverageSpec, runs: Sequence[RunScores],
           train: list[Condition], evals: Mapping[str, list[Condition]], prefix: str,
           facts: list[str], rows: list[Row], reasons: list[str]) -> None:
    """One tau_cov per level over `train`, then the clusters of `runs` against it."""
    ref = task.source_ref
    levels = sorted({s.level for r in runs for s in r.scores if not s.success
                     and s.level is not None})
    reference: dict[int, tuple[float, Matrix] | None] = {}
    for level in levels:
        mine = list(train) if spec.pool_levels else [c for c in train if c.level == level]
        matrix, missing = (_matrix(spec, level, mine) if level in spec.level_components
                           else (None, "not in the coverage block of the task view"))
        if matrix is None or len(mine) <= spec.k:
            why = (f"level {level}: train conditions: {missing}" if matrix is None else
                   f"level {level}: {len(mine)} train conditions, leave-one-out needs more "
                   f"than k = {spec.k}")
            if prefix:
                why = f"run {prefix}, {why}"
            facts.append(book.add(f"{TOOL}_{prefix + '_' if prefix else ''}l{level}_not_judged",
                                  why, "pack.json"))
            reasons.append(why)
            reference[level] = None
            continue
        tau = _level_reference(spec, level, matrix)
        reference[level] = (tau, matrix)
        pre = f"{prefix}_" if prefix else ""
        facts += [book.add(f"{pre}coverage_train_l{level}", len(mine), "pack.json", "conditions"),
                  book.add(f"{pre}tau_cov_l{level}", tau, ref, UNIT)]
    for run in runs:
        by_key = {(c.level, c.condition_seed): c for c in evals[run.run]}
        lost = 0
        for key, members in keys_of(task, run).items():
            lv = key[2]
            ref_level = None if lv is None else reference.get(lv)
            if lv is None or ref_level is None:
                continue
            tau, train_matrix = ref_level
            found = []
            for m in members:
                hit = _CONDITION.match(condition_of(m))
                cond = by_key.get((int(hit["level"]), int(hit["seed"]))) if hit else None
                if cond is None:
                    lost += 1
                else:
                    found.append(cond)
            if not found:
                continue
            matrix, missing = _matrix(spec, lv, found)
            if matrix is None:
                why = f"run {run.run}, cluster {slug(key)}: eval conditions: {missing}"
                facts.append(book.add(f"{TOOL}_{run.run}_{slug(key)}_not_judged", why, run.ref))
                reasons.append(why)
                continue
            d = [_knn_mean(spec, lv, p, train_matrix) for p in matrix]
            inside = bool(((matrix >= train_matrix.min(axis=0))
                           & (matrix <= train_matrix.max(axis=0))).all(axis=1).all())
            name = f"{run.run}_cluster_{slug(key)}_coverage"
            above = sum(x > tau for x in d)
            facts += [book.add(f"{name}_matched", len(found), run.ref, "rollouts"),
                      book.add(f"{name}_d_mean", float(np.mean(d)), run.ref, UNIT),
                      book.add(f"{name}_above_tau", above, run.ref, "rollouts"),
                      book.add(f"{name}_in_domain", inside, run.ref)]
            rows.append({"run": run.run, "cluster": slug(key), "size": len(members),
                         "matched": len(found), "d_mean": float(np.mean(d)), "tau_cov": tau,
                         "above_tau": above, "in_domain": inside})
        if lost:
            why = f"run {run.run}: {lost} failed rollouts have no condition of role eval"
            facts.append(book.add(f"{TOOL}_{run.run}_not_judged", why, run.ref))
            reasons.append(why)


def coverage_distance(book: FactBook, task: TaskView, runs: Sequence[RunScores],
                      sets: Sequence[ConditionSet]) -> ToolResult:
    spec = task.coverage
    if spec is None:
        return not_judged(book, TOOL, f"the task view of {task.task_id} has no coverage block",
                          task.source_ref)
    undeclared = [s.ref for s in sets if s.role not in ("train", "eval")]
    if undeclared:
        return not_judged(book, TOOL, f"{', '.join(undeclared)}: the pack does not declare "
                          "subject.role as train or eval", "pack.json")
    if not any(s.role == "train" and s.conditions for s in sets) or not any(
            s.role == "eval" and s.conditions for s in sets):
        missing = "train" if not any(s.role == "train" and s.conditions for s in sets) else "eval"
        return not_judged(book, TOOL, f"no conditions entry has the role {missing}", "pack.json")
    ref = task.source_ref
    facts = [book.add("coverage_k", spec.k, ref, "conditions"),
             book.add("coverage_percentile", spec.percentile, ref, "%")]
    reasons: list[str] = []
    rows: list[Row] = []
    in_pack = {r.run for r in runs}
    per_run = any(s.role == "train" and s.run for s in sets)
    for s in sets:
        if s.run and s.role == "train" and s.run not in in_pack:
            why = f"{s.ref}: names run {s.run!r}, which is not in the pack"
            facts.append(book.add(f"{TOOL}_train_run_{s.run}_not_judged", why, "pack.json"))
            reasons.append(why)
    if not per_run:
        _scope(book, task, spec, runs, _split(sets, "train"),
               {r.run: _split(sets, "eval", r.run) for r in runs}, "", facts, rows, reasons)
    else:
        for run in runs:
            train, evals = _split(sets, "train", run.run), _split(sets, "eval", run.run)
            if not train or not evals:
                missing = "train" if not train else "eval"
                why = f"run {run.run}: no conditions entry of the role {missing} for it"
                facts.append(book.add(f"{TOOL}_{run.run}_not_judged", why, run.ref))
                reasons.append(why)
                continue
            _scope(book, task, spec, [run], train, {run.run: evals}, run.run, facts, rows, reasons)
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))
