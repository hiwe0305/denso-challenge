"""`measure_compare` and `measure_tally`: one measure of a cluster against a reference (DA-52).

Two generic tools: no measure is named here. What a call may ask for is read off the pack:

    cluster    a failure cluster of a run, spelled as the hypotheses spell it,
               `<run>/<step>/<label>/l<level>` (the key of `failure_clusters`)
    against    `successes_same_level` (the run's successful rollouts of the cluster's
               level, per the scores; the default a caller should reach for first),
               `successes_all_levels` (of every level), or another cluster of the same run
    measure    a reference to a measure the pack's rollouts carry:
                 `<where>.<name>`      a scalar of the K1 outcome (`where`: final, extrema,
                                       at_failure, verdict) or of the rollout's condition
                                       (`condition`, from `Condition.values`)
                 `<where>.<name>[k]`   component k of a list-valued measure
                 `<where>.<name>.tilt` for a `_quat` (w, x, y, z): the angle between its z
                                       axis and the world's, computed here (`tilt_deg`);
                                       a quaternion's components are not offered (q and -q
                                       are the same rotation)
               numbers go to `measure_compare`, booleans and strings to `measure_tally`.

A rollout's condition is the `Condition` of an eval `conditions` entry of its run (those
naming the run, else those naming none) with the level and seed of its `episode_id`, as
`coverage_distance` joins them. A rollout that lacks the measure (no outcome, no condition,
the name absent or null, a list too short) is left out of the statistics, and counted: each
call gives, for the cluster and for the reference, its members, how many carry the measure
(judged) and how many do not (lacking).

Fact names are fixed by (run, cluster, measure, against), so the same call twice adds the same
facts and two calls never give one name two values. With `base` =
`{run}_cluster_{slug}_cmp__{measure slug}__vs__{reference}` (the measure slug joins where,
name and `i<k>` or `tilt` with `__`, which no measure name holds, so two references never
share a slug; the reference is `successes_same_level`, `successes_all_levels` or the other
cluster's slug):

    `{base}_members|judged|lacking`             the cluster's rollouts, with, without the measure
    `{base}_ref_members|ref_judged|ref_lacking` the same for the reference
    `{base}_median`, `{base}_ref_median`        in the measure's unit (its name's suffix)
    `{base}_ref_p<low>`, `{base}_ref_p<high>`   the reference's percentile bounds
    `{base}_outside_below|above|total`          judged members outside the bounds
    `{base}_separated`                          true when the members outside are a MAJORITY
                                                of the judged ones (more than half; exactly
                                                half is not)
    `{base}_beyond_threshold`, `{base}_ref_beyond_threshold`, `threshold_<key>`
                                                when the task view maps the measure to a
                                                scorer threshold (`measures.thresholds`)

The percentiles, the reference size the bounds need (`min_reference`), the cluster size
`separated` needs (`min_cluster`) and the threshold map are the task view's `measures`
block; they are facts too (`measure_compare_*`). A reference smaller than `min_reference`
leaves the bounds not judged (`measure_compare_{base}_bounds_not_judged`); fewer judged
members than `min_cluster` leave `separated` not judged
(`measure_compare_{base}_separated_not_judged`), the counts and medians still given; a cluster
none of whose members carries the measure leaves the rest of the call not judged
(`measure_compare_{base}_not_judged`) after the counts.

`measure_tally`, `base` = `{run}_cluster_{slug}_tally__{measure slug}__vs__{reference}`:
the same six counts, `{base}_values` (distinct values over both groups), `{base}_mode`,
`{base}_ref_mode` (most common value; a tie goes to the first in text order), and per value
`v<k>` (k = 1 for the most frequent over both groups, ties in text order):
`{base}_v<k>_value` (the value as text: a boolean is `true` or `false`), `{base}_v<k>_count`,
`{base}_v<k>_ref_count`. Beyond `measures.max_values` values, the rest are summed in
`{base}_other_count`, `{base}_other_ref_count`, and `{base}_values_left_out` says how many.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

import numpy as np
from flywheel.contracts.entities import Condition, Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import (
    ConditionSet,
    Row,
    RunOutcomes,
    RunScores,
    ToolResult,
    condition_of,
    not_judged,
)
from flywheel.eval.agentqa.tools.carry import measure_value
from flywheel.eval.agentqa.tools.clusters import Key, keys_of, slug
from flywheel.eval.agentqa.tools.relaxed import tilt_deg
from flywheel.eval.agentqa.tools.task import (
    MEASURE_REF,
    VERDICT_FIELDS,
    MeasuresSpec,
    TaskView,
    measure_unit,
)

COMPARE = "measure_compare"
TALLY = "measure_tally"
SAME_LEVEL = "successes_same_level"  # the run's successes of the cluster's level
ALL_LEVELS = "successes_all_levels"  # the run's successes of every level
REFERENCES = (SAME_LEVEL, ALL_LEVELS)  # listed before the clusters; the first is the default
ROLLOUTS = "rollouts"
OUTCOME_WHERE = ("final", "extrema", "at_failure", "verdict")
_CONDITION = re.compile(r"^l(?P<level>\d+)-s(?P<seed>\d+)$")


# --- references and domains ---------------------------------------------------------------


@dataclass(frozen=True)
class MeasureRef:
    where: str
    name: str
    index: int | None = None
    derived: str | None = None

    @property
    def text(self) -> str:
        tail = (f"[{self.index}]" if self.index is not None
                else f".{self.derived}" if self.derived else "")
        return f"{self.where}.{self.name}{tail}"

    @property
    def slug(self) -> str:
        """The reference in a fact name: parts joined by `__`, which no measure name holds
        (lower_snake), so two references never share a slug (`final.a_m[0]` is
        `final__a_m__i0`, a measure named `a_m_i0` is `final__a_m_i0`)."""
        tail = (f"__i{self.index}" if self.index is not None
                else f"__{self.derived}" if self.derived else "")
        return f"{self.where}__{self.name}{tail}"


def parse_ref(text: object) -> MeasureRef | None:
    """The reference `text` spells; None when it is not one."""
    if not isinstance(text, str):
        return None
    hit = re.match(MEASURE_REF, text)
    if hit is None:
        return None
    index = None if hit["index"] is None else int(hit["index"])
    return MeasureRef(hit["where"], hit["name"], index, hit["derived"])


def _is_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _refs_of(where: str, name: str, value: object, numbers: set[str],
             categories: set[str]) -> None:
    """Add the references one measure value gives to the two sets."""
    if value is None:
        return
    if isinstance(value, (bool, str)):
        categories.add(f"{where}.{name}")
    elif _is_number(value):
        numbers.add(f"{where}.{name}")
    elif isinstance(value, list):
        if name.endswith("_quat"):
            if len(value) == 4 and all(_is_number(v) for v in value):
                numbers.add(f"{where}.{name}.tilt")
            return
        numbers.update(f"{where}.{name}[{k}]" for k, v in enumerate(value) if _is_number(v))


def _outcome_measures(outcome: RolloutOutcome) -> list[tuple[str, str, object]]:
    found: list[tuple[str, str, object]] = []
    for where, held in (("final", outcome.final), ("extrema", outcome.extrema),
                        ("at_failure", outcome.verdict.at_failure or {})):
        found += [(where, name, value) for name, value in held.items()]
    found += [("verdict", name, getattr(outcome.verdict, name, None))
              for name in VERDICT_FIELDS if name != "at_failure"]
    return found


def _eval_sets(sets: Sequence[ConditionSet], run: str) -> list[ConditionSet]:
    """The eval `conditions` entries of `run`: those naming it, else those naming none."""
    of_role = [s for s in sets if s.role == "eval"]
    return [s for s in of_role if run and s.run == run] or [s for s in of_role if not s.run]


@dataclass(frozen=True)
class Domains:
    """The closed values the two tools' parameters take, read off the pack."""

    clusters: tuple[str, ...]  # cluster ids, sorted
    run_of: Mapping[str, str]  # cluster id -> its run
    numbers: tuple[str, ...]  # numeric measure references, sorted
    categories: tuple[str, ...]  # boolean or string measure references, sorted


def cluster_id(run: str, key: Key) -> str:
    step, label, level = key
    return f"{run}/{step}/{label}/l{level}"


def domains(task: TaskView, runs: Mapping[str, RunScores], outcomes: Mapping[str, RunOutcomes],
            sets: Sequence[ConditionSet]) -> Domains:
    run_of = {cluster_id(name, key): name for name, run in runs.items()
              for key in keys_of(task, run)}
    numbers: set[str] = set()
    categories: set[str] = set()
    for held in outcomes.values():
        for outcome in held.outcomes:
            for where, name, value in _outcome_measures(outcome):
                _refs_of(where, name, value, numbers, categories)
    for s in sets:
        if s.role != "eval":
            continue
        for cond in s.conditions:
            for name, value in cond.values.items():
                if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name):
                    _refs_of("condition", name, value, numbers, categories)
    return Domains(tuple(sorted(run_of)), run_of, tuple(sorted(numbers)),
                   tuple(sorted(categories)))


# --- values of a rollout --------------------------------------------------------------------


@dataclass(frozen=True)
class _Source:
    """Where the values of a run come from: its outcomes, or its eval conditions."""

    ref: str  # the entry (or entries) facts cite
    outcomes: Mapping[str, RolloutOutcome]  # episode_id -> outcome
    conditions: Mapping[tuple[int, int], Condition]  # (level, seed) -> condition


def _source(ref: MeasureRef, run: RunScores, outcomes: Mapping[str, RunOutcomes],
            sets: Sequence[ConditionSet]) -> _Source:
    if ref.where == "condition":
        mine = _eval_sets(sets, run.run)
        by_key = {(c.level, c.condition_seed): c for s in mine for c in s.conditions}
        return _Source(", ".join(s.ref for s in mine) or run.ref, {}, by_key)
    held = outcomes.get(run.run)
    return _Source(run.ref if held is None else held.ref,
                   {} if held is None else held.by_episode(), {})


def _raw(ref: MeasureRef, score: Score, source: _Source) -> object:
    if ref.where == "condition":
        hit = _CONDITION.match(condition_of(score))
        cond = (source.conditions.get((int(hit["level"]), int(hit["seed"])))
                if hit else None)
        return None if cond is None else cond.values.get(ref.name)
    outcome = source.outcomes.get(score.episode_id)
    return None if outcome is None else measure_value(outcome, ref.where, ref.name)


def number_of(ref: MeasureRef, score: Score, source: _Source) -> float | None:
    """The number `ref` gives for a rollout; None when the rollout does not carry it."""
    value = _raw(ref, score, source)
    if ref.derived == "tilt":
        if (not isinstance(value, list) or len(value) != 4
                or not all(_is_number(v) for v in value)):
            return None
        return tilt_deg([float(v) for v in value])
    if ref.index is not None:
        if not isinstance(value, list) or ref.index >= len(value):
            return None
        value = value[ref.index]
    return float(value) if _is_number(value) else None  # type: ignore[arg-type]


def category_of(ref: MeasureRef, score: Score, source: _Source) -> str | None:
    """The value `ref` gives for a rollout, as text; None when it is missing or a number."""
    value = _raw(ref, score, source)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else None


# --- groups ---------------------------------------------------------------------------------


def _groups(task: TaskView, runs: Mapping[str, RunScores], cluster: str,
            against: str) -> tuple[RunScores, Key, list[Score], list[Score], str] | None:
    """(run, key, members, reference, reference slug); None when a name is not of the pack."""
    for name, run in runs.items():
        clusters = keys_of(task, run)
        by_id = {cluster_id(name, k): k for k in clusters}
        if cluster not in by_id:
            continue
        key = by_id[cluster]
        successes = [s for s in run.scores if s.success is True]
        if against == SAME_LEVEL:
            return run, key, clusters[key], [s for s in successes if s.level == key[2]], \
                SAME_LEVEL
        if against == ALL_LEVELS:
            return run, key, clusters[key], successes, ALL_LEVELS
        other = by_id.get(against)
        if other is None or other == key:
            return None
        return run, key, clusters[key], clusters[other], slug(other)
    return None


def _base(run: str, key: Key, tool: str, ref: MeasureRef, other: str) -> str:
    """The prefix of a call's fact names; `__` cannot occur in a measure name, so the
    measure part and the reference part are read back unambiguously."""
    return f"{run}_cluster_{slug(key)}_{tool}__{ref.slug}__vs__{other}"


def _group_facts(book: FactBook, base: str, ref: str, members: int, judged: int,
                 ref_members: int, ref_judged: int) -> list[str]:
    """Members, judged and lacking (members without the measure) of the cluster and reference."""
    return [book.add(f"{base}_members", members, ref, ROLLOUTS),
            book.add(f"{base}_judged", judged, ref, ROLLOUTS),
            book.add(f"{base}_lacking", members - judged, ref, ROLLOUTS),
            book.add(f"{base}_ref_members", ref_members, ref, ROLLOUTS),
            book.add(f"{base}_ref_judged", ref_judged, ref, ROLLOUTS),
            book.add(f"{base}_ref_lacking", ref_members - ref_judged, ref, ROLLOUTS)]


def _config_facts(book: FactBook, task: TaskView, spec: MeasuresSpec) -> list[str]:
    ref = task.source_ref
    return [book.add(f"{COMPARE}_low_percentile", float(spec.low_percentile), ref, "%"),
            book.add(f"{COMPARE}_high_percentile", float(spec.high_percentile), ref, "%"),
            book.add(f"{COMPARE}_min_reference", spec.min_reference, ref, ROLLOUTS),
            book.add(f"{COMPARE}_min_cluster", spec.min_cluster, ref, ROLLOUTS)]


def _no_block(book: FactBook, tool: str, task: TaskView) -> ToolResult:
    return not_judged(book, tool, f"the task view of {task.task_id} declares no measures block",
                      task.source_ref)


def _percent(value: float) -> str:
    return f"{value:g}".replace(".", "_")


NO_MEMBER = "no rollout of the cluster carries the measure"


# --- measure_compare ------------------------------------------------------------------------


def measure_compare(book: FactBook, task: TaskView, runs: Mapping[str, RunScores],
                    outcomes: Mapping[str, RunOutcomes], sets: Sequence[ConditionSet],
                    cluster: str, measure: str, against: str) -> ToolResult:
    """One numeric measure of `cluster` against `against`; see the module docstring."""
    spec = task.measures
    if spec is None:
        return _no_block(book, COMPARE, task)
    ref = parse_ref(measure)
    found = _groups(task, runs, cluster, against)
    if ref is None or found is None:  # check_params keeps these out of a round
        return not_judged(book, COMPARE, "the cluster, measure or reference is not of the "
                          "pack", "pack.json")
    run, key, members, reference, other = found
    source = _source(ref, run, outcomes, sets)
    base = _base(run.run, key, "cmp", ref, other)
    unit = measure_unit(ref.text)
    mine = [v for s in members for v in [number_of(ref, s, source)] if v is not None]
    theirs = [v for s in reference for v in [number_of(ref, s, source)] if v is not None]
    facts = _config_facts(book, task, spec)
    facts += _group_facts(book, base, source.ref, len(members), len(mine), len(reference),
                          len(theirs))
    if not mine:
        part = not_judged(book, COMPARE, NO_MEMBER, source.ref, base)
        return ToolResult(COMPARE, (*facts, *part.facts), (), part.not_judged)
    facts.append(book.add(f"{base}_median", float(median(mine)), source.ref, unit))
    row: dict[str, float | int | str | bool] = {
        "cluster": cluster, "measure": ref.text, "against": against, "unit": unit,
        "members": len(members), "judged": len(mine), "median": float(median(mine)),
        "ref_members": len(reference), "ref_judged": len(theirs)}
    if theirs:
        facts.append(book.add(f"{base}_ref_median", float(median(theirs)), source.ref, unit))
        row["ref_median"] = float(median(theirs))
    threshold = spec.thresholds.get(ref.text)
    if threshold is not None and threshold.threshold in task.thresholds:
        limit = float(task.thresholds[threshold.threshold])

        def beyond(v: float) -> bool:
            x = abs(v) if threshold.absolute else v
            return x > limit if threshold.beyond == "above" else x < limit

        over, ref_over = sum(map(beyond, mine)), sum(map(beyond, theirs))
        facts += [book.add(f"threshold_{threshold.threshold}", limit, task.source_ref,
                           task.threshold_units[threshold.threshold]),
                  book.add(f"{base}_beyond_threshold", over, source.ref, ROLLOUTS),
                  book.add(f"{base}_ref_beyond_threshold", ref_over, source.ref, ROLLOUTS)]
        row.update({"threshold": threshold.threshold, "beyond_threshold": over,
                    "ref_beyond_threshold": ref_over})
    left_out: list[str] = []
    if len(theirs) < spec.min_reference:
        part = not_judged(book, COMPARE, "the reference group holds fewer rollouts with the "
                          "measure than measures.min_reference, so it has no percentile bounds",
                          source.ref, f"{base}_bounds")
        facts += part.facts
        left_out += part.not_judged
    else:
        low, high = (float(x) for x in np.percentile(
            theirs, [spec.low_percentile, spec.high_percentile]))
        below = sum(1 for v in mine if v < low)
        above = sum(1 for v in mine if v > high)
        facts += [
            book.add(f"{base}_ref_p{_percent(spec.low_percentile)}", low, source.ref, unit),
            book.add(f"{base}_ref_p{_percent(spec.high_percentile)}", high, source.ref, unit),
            book.add(f"{base}_outside_below", below, source.ref, ROLLOUTS),
            book.add(f"{base}_outside_above", above, source.ref, ROLLOUTS),
            book.add(f"{base}_outside_total", below + above, source.ref, ROLLOUTS)]
        row.update({"ref_low": low, "ref_high": high, "outside_below": below,
                    "outside_above": above})
        if len(mine) < spec.min_cluster:
            part = not_judged(book, COMPARE, "the cluster holds fewer rollouts with the measure "
                              "than measures.min_cluster, so separation is not judged",
                              source.ref, f"{base}_separated")
            facts += part.facts
            left_out += part.not_judged
        else:
            separated = 2 * (below + above) > len(mine)
            facts.append(book.add(f"{base}_separated", separated, source.ref))
            row["separated"] = separated
    rows: tuple[Row, ...] = (row,)
    return ToolResult(COMPARE, tuple(facts), rows, tuple(left_out))


# --- measure_tally --------------------------------------------------------------------------


def _mode(counts: Counter[str]) -> str:
    return min(counts, key=lambda v: (-counts[v], v))


def measure_tally(book: FactBook, task: TaskView, runs: Mapping[str, RunScores],
                  outcomes: Mapping[str, RunOutcomes], sets: Sequence[ConditionSet],
                  cluster: str, measure: str, against: str) -> ToolResult:
    """Counts per value of one boolean or string measure; see the module docstring."""
    spec = task.measures
    if spec is None:
        return _no_block(book, TALLY, task)
    ref = parse_ref(measure)
    found = _groups(task, runs, cluster, against)
    if ref is None or found is None:
        return not_judged(book, TALLY, "the cluster, measure or reference is not of the pack",
                          "pack.json")
    run, key, members, reference, other = found
    source = _source(ref, run, outcomes, sets)
    base = _base(run.run, key, "tally", ref, other)
    mine = Counter(v for s in members for v in [category_of(ref, s, source)] if v is not None)
    theirs = Counter(v for s in reference for v in [category_of(ref, s, source)]
                     if v is not None)
    facts = [book.add(f"{TALLY}_max_values", spec.max_values, task.source_ref, "values")]
    facts += _group_facts(book, base, source.ref, len(members), sum(mine.values()),
                          len(reference), sum(theirs.values()))
    if not mine:
        part = not_judged(book, TALLY, NO_MEMBER, source.ref, base)
        return ToolResult(TALLY, (*facts, *part.facts), (), part.not_judged)
    values = sorted(set(mine) | set(theirs), key=lambda v: (-(mine[v] + theirs[v]), v))
    kept, rest = values[:spec.max_values], values[spec.max_values:]
    facts += [book.add(f"{base}_values", len(values), source.ref, "values"),
              book.add(f"{base}_mode", _mode(mine), source.ref)]
    if theirs:
        facts.append(book.add(f"{base}_ref_mode", _mode(theirs), source.ref))
    rows: list[Row] = []
    for k, value in enumerate(kept, start=1):
        facts += [book.add(f"{base}_v{k}_value", value, source.ref),
                  book.add(f"{base}_v{k}_count", mine[value], source.ref, ROLLOUTS),
                  book.add(f"{base}_v{k}_ref_count", theirs[value], source.ref, ROLLOUTS)]
        rows.append({"cluster": cluster, "measure": ref.text, "against": against,
                     "value": value, "count": mine[value], "ref_count": theirs[value]})
    if rest:
        other_mine = sum(mine[v] for v in rest)
        other_theirs = sum(theirs[v] for v in rest)
        facts += [book.add(f"{base}_values_left_out", len(rest), source.ref, "values"),
                  book.add(f"{base}_other_count", other_mine, source.ref, ROLLOUTS),
                  book.add(f"{base}_other_ref_count", other_theirs, source.ref, ROLLOUTS)]
        rows.append({"cluster": cluster, "measure": ref.text, "against": against,
                     "value": f"({len(rest)} other values)", "count": other_mine,
                     "ref_count": other_theirs})
    return ToolResult(TALLY, tuple(facts), tuple(rows))


__all__ = ["ALL_LEVELS", "COMPARE", "REFERENCES", "SAME_LEVEL", "TALLY", "Domains",
           "MeasureRef", "cluster_id", "domains", "measure_compare", "measure_tally",
           "parse_ref"]
