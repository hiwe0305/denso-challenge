"""`relaxed_sweep`: how many rollouts pass when the position tolerance is widened (DA-43 2.4).

Design 19/11/2026 section 4; tray.md 19.2 c. The task view's `relaxed` block names one
failure label, a grid of position tolerances (m) and the yaw tolerance (deg), and through
`relaxed.signal` the two final measures of the K1 outcome it compares: the distance to the
target (the name in `_m`) and the yaw error (the name in `_deg`, compared by its absolute
value). For a tolerance t of the grid, a rollout counts as a relaxed success when

    the scores say it succeeded, or
    the scores give it the relaxed label and its outcome has distance <= t and
    |yaw error| <= the yaw tolerance.

Other failure labels are never relaxed. Success and label are the scores' (the clusters
of the round are built from them); the outcomes give the measures, paired by
`episode_id`. Counts are given per run, for every level of the run and for all its
levels together (`{run}_relaxed_{all|l<level>}_pos<k>_successes`, k = 1 for the first grid
value); each grid value is a fact itself (`relaxed_position_<k>`, m), so no number is
left for a model to write.

The first grid value is the scorer's own tolerance: its count must equal the scorer's
successes. `{run}_relaxed_first_grid_matches_scorer` says whether it does, and
`{run}_relaxed_scorer_mismatch` counts the relaxed-label failures that the measures put
within the scorer's tolerances: a scorer that disagrees with the measures is a finding,
not an error.

Per failure cluster of the relaxed label (the key and slug of `failure_clusters`):
the median and largest distance (`{run}_cluster_{slug}_relaxed_distance_median|max`, m),
how many members fall within each grid value with the yaw kept (`..._relaxed_within_pos<k>`)
and within the widest one (`..._relaxed_within_widest`), and `..._near_miss`: true when
the members within the WIDEST grid tolerance (the largest value of the grid) are a
MAJORITY of the cluster (more than half of its members; half is not a majority).

Pairing is reported, never silent: `{run}_outcomes_matched`, `{run}_outcomes_without_score`,
`{run}_scores_without_outcome`, `{run}_outcome_verdict_disagrees` (the outcome's verdict
gives another success or label than the scores). A run without outcomes, a relaxed-label
failure without outcome or without one of the two measures, leaves the run's sweep not
judged (`relaxed_sweep_<run>_not_judged`, with the reason); outcomes of a run that has no
scores entry are reported the same way.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from statistics import median

from flywheel.contracts.entities import Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import (
    Row,
    RunOutcomes,
    RunScores,
    ToolResult,
    merge,
    not_judged,
)
from flywheel.eval.agentqa.tools.clusters import keys_of, slug
from flywheel.eval.agentqa.tools.task import RelaxedSpec, TaskView

TOOL = "relaxed_sweep"
ROLLOUTS = "rollouts"


def _disagrees(score: Score, outcome: RolloutOutcome) -> bool:
    verdict = outcome.verdict
    if (score.success is True) != verdict.success:
        return True
    return score.success is not True and score.failure_kind != verdict.failure_label


def _pairing(book: FactBook, run: RunScores, held: RunOutcomes) -> list[str]:
    by_episode = held.by_episode()
    scored = {s.episode_id for s in run.scores}
    matched = [s for s in run.scores if s.episode_id in by_episode]
    return [
        book.add(f"{run.run}_outcomes_matched", len(matched), held.ref, ROLLOUTS),
        book.add(f"{run.run}_outcomes_without_score",
                 sum(1 for e in by_episode if e not in scored), held.ref, ROLLOUTS),
        book.add(f"{run.run}_scores_without_outcome", len(run.scores) - len(matched),
                 held.ref, ROLLOUTS),
        book.add(f"{run.run}_outcome_verdict_disagrees",
                 sum(1 for s in matched if _disagrees(s, by_episode[s.episode_id])),
                 held.ref, ROLLOUTS),
    ]


def _within(d: float, yaw: float, tol: float, spec: RelaxedSpec) -> bool:
    return d <= tol and abs(yaw) <= spec.yaw_deg


def _grid_facts(book: FactBook, task: TaskView, spec: RelaxedSpec) -> list[str]:
    ref = task.source_ref
    facts = [book.add("relaxed_label", spec.label, ref),
             book.add("relaxed_yaw_tolerance", float(spec.yaw_deg), ref, "deg")]
    facts += [book.add(f"relaxed_position_{k}", float(t), ref, "m")
              for k, t in enumerate(spec.position_m, start=1)]
    facts.append(book.add("relaxed_position_widest", float(max(spec.position_m)), ref, "m"))
    return facts


def _sweep_run(book: FactBook, task: TaskView, spec: RelaxedSpec, run: RunScores,
               held: RunOutcomes | None) -> ToolResult:
    if held is None:
        return not_judged(book, TOOL, f"run {run.run}: no outcomes entry in the pack, so no "
                          "final measure to relax", run.ref, run.run)
    pairing = _pairing(book, run, held)
    dist_name, yaw_name = task.relaxed_measures()
    by_episode = held.by_episode()
    relaxed = [s for s in run.scores if s.success is not True and s.failure_kind == spec.label]
    measured: dict[str, tuple[float, float]] = {}
    no_outcome, lacking = 0, set()
    for s in relaxed:
        found = by_episode.get(s.episode_id)
        if found is None:
            no_outcome += 1
            continue
        d, yaw = found.final.get(dist_name), found.final.get(yaw_name)
        for name, value in ((dist_name, d), (yaw_name, yaw)):
            if not isinstance(value, float) or isinstance(value, bool):
                lacking.add(name)
        if isinstance(d, float) and isinstance(yaw, float):
            measured[s.episode_id] = (d, yaw)
    if no_outcome or lacking:
        why = []
        if no_outcome:
            why.append(f"{no_outcome} failures of {spec.label} have no outcome")
        if lacking:
            why.append(f"failures of {spec.label} lack final.{', final.'.join(sorted(lacking))}")
        result = not_judged(book, TOOL, f"run {run.run}: {'; '.join(why)}", held.ref, run.run)
        return ToolResult(TOOL, (*pairing, *result.facts), (), result.not_judged)

    facts = list(pairing)
    rows: list[Row] = []
    levels = sorted({s.level for s in run.scores if s.level is not None})
    scopes: list[tuple[str, list[Score]]] = [("all", list(run.scores))]
    scopes += [(f"l{lv}", [s for s in run.scores if s.level == lv]) for lv in levels]
    for part, scores in scopes:
        name = f"{run.run}_relaxed_{part}"
        successes = sum(1 for s in scores if s.success is True)
        facts.append(book.add(f"{name}_rollouts", len(scores), run.ref, ROLLOUTS))
        facts.append(book.add(f"{name}_successes", successes, run.ref, ROLLOUTS))
        for k, tol in enumerate(spec.position_m, start=1):
            within = sum(1 for s in scores if s.episode_id in measured
                         and _within(*measured[s.episode_id], tol, spec))
            facts.append(book.add(f"{name}_pos{k}_successes", successes + within, held.ref,
                                  ROLLOUTS))
            rows.append({"run": run.run, "part": part, "position_m": float(tol),
                         "yaw_deg": float(spec.yaw_deg), "rollouts": len(scores),
                         "scorer_successes": successes, "relaxed_successes": successes + within})
    first = spec.position_m[0]
    mismatch = sum(1 for d, yaw in measured.values() if _within(d, yaw, first, spec))
    facts.append(book.add(f"{run.run}_relaxed_first_grid_matches_scorer", mismatch == 0,
                          held.ref))
    facts.append(book.add(f"{run.run}_relaxed_scorer_mismatch", mismatch, held.ref, ROLLOUTS))

    widest = max(spec.position_m)
    for key, members in sorted(keys_of(task, run).items(),
                               key=lambda kv: (slug(kv[0]), len(kv[1]))):
        if key[1] != spec.label:
            continue
        name = f"{run.run}_cluster_{slug(key)}"
        values = [measured[s.episode_id] for s in members]
        distances = [d for d, _ in values]
        facts.append(book.add(f"{name}_relaxed_distance_median", float(median(distances)),
                              held.ref, "m"))
        facts.append(book.add(f"{name}_relaxed_distance_max", float(max(distances)), held.ref,
                              "m"))
        for k, tol in enumerate(spec.position_m, start=1):
            within = sum(1 for d, yaw in values if _within(d, yaw, tol, spec))
            facts.append(book.add(f"{name}_relaxed_within_pos{k}", within, held.ref, ROLLOUTS))
            rows.append({"run": run.run, "part": f"cluster {slug(key)}",
                         "position_m": float(tol), "yaw_deg": float(spec.yaw_deg),
                         "rollouts": len(members), "scorer_successes": 0,
                         "relaxed_successes": within})
        near = sum(1 for d, yaw in values if _within(d, yaw, widest, spec))
        facts.append(book.add(f"{name}_relaxed_within_widest", near, held.ref, ROLLOUTS))
        facts.append(book.add(f"{name}_near_miss", 2 * near > len(members), held.ref))
    return ToolResult(TOOL, tuple(facts), tuple(rows))


def relaxed_sweep(book: FactBook, task: TaskView, runs: Sequence[RunScores],
                  outcomes: Mapping[str, RunOutcomes],
                  scored: Iterable[str] | None = None) -> ToolResult:
    """The sweep of each run of `runs`.

    `outcomes`: run -> its K1 outcomes, for any run of the pack; `scored`: every run with
    a scores entry in the pack (default: `runs`), so outcomes that pair with no scores
    entry are reported whatever runs the call names.
    """
    spec = task.relaxed
    if spec is None:
        return not_judged(book, TOOL, f"the task view of {task.task_id} declares no relaxed "
                          "block", task.source_ref)
    if not runs:
        return not_judged(book, TOOL, "no run given", "-")
    parts = [ToolResult(TOOL, tuple(_grid_facts(book, task, spec)))]
    parts += [_sweep_run(book, task, spec, run, outcomes.get(run.run)) for run in runs]
    known = {r.run for r in runs} if scored is None else set(scored)
    parts += [not_judged(book, TOOL, f"run {name}: its outcomes entry has no scores entry in "
                         "the pack, so they pair with nothing", held.ref, name)
              for name, held in outcomes.items() if name not in known]
    return merge(TOOL, parts)
