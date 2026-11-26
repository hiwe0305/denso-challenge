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

Yaw, per such cluster (v2): `..._yaw_over_tolerance` counts the members whose |yaw error| is
above the yaw tolerance of the sweep (`relaxed_yaw_tolerance`), `..._yaw_error_median` is the
median |yaw error| (deg), and `..._yaw_miss` is true when the members over the tolerance are
a majority of the cluster.

Where the tray comes to rest (v2, when the relaxed block names `rest_signal`): the final
position (the name in `_m`, [x, y, z]) and orientation (the name in `_quat`, w x y z) of
that `signal_measures` entry. `{run}_rest_height_reference` (m) is the median final z of the
run's SUCCESSFUL rollouts (the scores' verdict) that carry the position, so the height
compared with is the run's own data; `relaxed_rest_margin` (m) is the task view's margin.
`{run}_successes_raised` counts the successes above the reference plus the margin, out of
`{run}_rest_height_reference_successes`: the base rate, since a success may rest raised too.
Per cluster, over the members that carry both measures (`..._rest_judged`):
`..._final_height_median` (m), `..._raised` (members whose final z is above the reference
plus the margin), `..._final_tilt_median` (deg; the angle between the tray's z axis and the
world's, acos(1 - 2(x^2 + y^2)) on the normalised quaternion) and `..._rests_raised`: true
when the raised members are a majority of the judged ones. No successful rollout with a
position leaves the rest facts of the run not judged (`relaxed_sweep_<run>_rest_not_judged`);
a cluster none of whose members carry both measures, the cluster's
(`relaxed_sweep_<run>_cluster_<slug>_rest_not_judged`). Missing rest measures never change
the facts above.

Pairing is reported, never silent: `{run}_outcomes_matched`, `{run}_outcomes_without_score`,
`{run}_scores_without_outcome`, `{run}_outcome_verdict_disagrees` (the outcome's verdict
gives another success or label than the scores). A run without outcomes, a relaxed-label
failure without outcome or without one of the two measures, leaves the run's sweep not
judged (`relaxed_sweep_<run>_not_judged`, with the reason); outcomes of a run that has no
scores entry are reported the same way.
"""

from __future__ import annotations

import math
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


def _numbers(value: object, size: int) -> list[float] | None:
    """`value` as a list of `size` finite floats; None when it is not one."""
    if not isinstance(value, list) or len(value) != size:
        return None
    if not all(isinstance(v, float) and math.isfinite(v) for v in value):
        return None
    return list(value)


def rest_height(outcome: RolloutOutcome, pos_name: str) -> float | None:
    """The final z (m) of the tray; None when the outcome does not carry the position."""
    pos = _numbers(outcome.final.get(pos_name), 3)
    return None if pos is None else pos[2]


def tilt_deg(quat: Sequence[float]) -> float | None:
    """Angle (deg) between the body z axis of the quaternion (w, x, y, z) and the world z.

    The zz entry of the rotation matrix is 1 - 2(x^2 + y^2) for a unit quaternion; the
    quaternion is normalised first and the cosine clamped to [-1, 1]. None for a zero one.
    """
    w, x, y, z = quat
    norm2 = w * w + x * x + y * y + z * z
    if norm2 <= 0.0:
        return None
    cos = max(-1.0, min(1.0, 1.0 - 2.0 * (x * x + y * y) / norm2))
    return math.degrees(math.acos(cos))


def rest_tilt(outcome: RolloutOutcome, quat_name: str) -> float | None:
    """The final tilt (deg) of the tray; None when the outcome does not carry the quaternion."""
    quat = _numbers(outcome.final.get(quat_name), 4)
    return None if quat is None else tilt_deg(quat)


def _within(d: float, yaw: float, tol: float, spec: RelaxedSpec) -> bool:
    return d <= tol and abs(yaw) <= spec.yaw_deg


def _grid_facts(book: FactBook, task: TaskView, spec: RelaxedSpec) -> list[str]:
    ref = task.source_ref
    facts = [book.add("relaxed_label", spec.label, ref),
             book.add("relaxed_yaw_tolerance", float(spec.yaw_deg), ref, "deg")]
    facts += [book.add(f"relaxed_position_{k}", float(t), ref, "m")
              for k, t in enumerate(spec.position_m, start=1)]
    facts.append(book.add("relaxed_position_widest", float(max(spec.position_m)), ref, "m"))
    if spec.rest_margin_m is not None:
        facts.append(book.add("relaxed_rest_margin", float(spec.rest_margin_m), ref, "m"))
    return facts


def _yaw_facts(book: FactBook, name: str, values: Sequence[tuple[float, float]],
               spec: RelaxedSpec, ref: str) -> list[str]:
    yaws = [abs(yaw) for _, yaw in values]
    over = sum(1 for yaw in yaws if yaw > spec.yaw_deg)
    return [book.add(f"{name}_yaw_over_tolerance", over, ref, ROLLOUTS),
            book.add(f"{name}_yaw_error_median", float(median(yaws)), ref, "deg"),
            book.add(f"{name}_yaw_miss", 2 * over > len(yaws), ref)]


def _rest_reference(book: FactBook, task: TaskView, run: RunScores,
                    held: RunOutcomes) -> tuple[float | None, ToolResult]:
    """The run's rest height of reference: the median final z of its successful rollouts."""
    measures = task.rest_measures()
    assert measures is not None
    by_episode = held.by_episode()
    heights = [h for s in run.scores if s.success is True and s.episode_id in by_episode
               for h in [rest_height(by_episode[s.episode_id], measures[0])] if h is not None]
    if not heights:
        return None, not_judged(book, TOOL, f"no successful rollout carries final.{measures[0]}, "
                                "so there is no rest height to compare with", held.ref,
                                f"{run.run}_rest")
    reference = float(median(heights))
    assert task.relaxed is not None and task.relaxed.rest_margin_m is not None
    raised = sum(1 for h in heights if h > reference + task.relaxed.rest_margin_m)
    return reference, ToolResult(TOOL, (
        book.add(f"{run.run}_rest_height_reference", reference, held.ref, "m"),
        book.add(f"{run.run}_rest_height_reference_successes", len(heights), held.ref,
                 ROLLOUTS),
        book.add(f"{run.run}_successes_raised", raised, held.ref, ROLLOUTS)))


def _rest_facts(book: FactBook, task: TaskView, spec: RelaxedSpec, run: str, cluster: str,
                members: Sequence[RolloutOutcome | None], reference: float,
                ref: str) -> ToolResult:
    measures = task.rest_measures()
    assert measures is not None and spec.rest_margin_m is not None
    pos_name, quat_name = measures
    judged: list[tuple[float, float]] = []
    for found in members:
        if found is None:
            continue
        height, tilt = rest_height(found, pos_name), rest_tilt(found, quat_name)
        if height is not None and tilt is not None:
            judged.append((height, tilt))
    name = f"{run}_cluster_{cluster}"
    if not judged:
        return not_judged(book, TOOL, f"no failure of the cluster carries final.{pos_name} and "
                          f"final.{quat_name}", ref, f"{run}_cluster_{cluster}_rest")
    raised = sum(1 for h, _ in judged if h > reference + spec.rest_margin_m)
    return ToolResult(TOOL, (
        book.add(f"{name}_rest_judged", len(judged), ref, ROLLOUTS),
        book.add(f"{name}_final_height_median", float(median(h for h, _ in judged)), ref, "m"),
        book.add(f"{name}_raised", raised, ref, ROLLOUTS),
        book.add(f"{name}_final_tilt_median", float(median(t for _, t in judged)), ref, "deg"),
        book.add(f"{name}_rests_raised", 2 * raised > len(judged), ref)))


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
    clusters = [(key, members) for key, members in sorted(
        keys_of(task, run).items(), key=lambda kv: (slug(kv[0]), len(kv[1])))
        if key[1] == spec.label]
    reference: float | None = None
    left_out: list[str] = []  # why a rest part was not judged; the facts keep the book's order
    if clusters and spec.rest_signal is not None:
        reference, rested = _rest_reference(book, task, run, held)
        facts += rested.facts
        left_out += rested.not_judged
    for key, members in clusters:
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
        facts += _yaw_facts(book, name, values, spec, held.ref)
        if reference is not None:
            rested = _rest_facts(book, task, spec, run.run, slug(key),
                               [by_episode.get(s.episode_id) for s in members], reference,
                               held.ref)
            facts += rested.facts
            left_out += rested.not_judged
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(left_out))


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
