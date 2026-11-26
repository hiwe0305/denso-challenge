"""How the tray was held when a carrying label was raised: part of `signal_presence` v3.

The task view's `carry` block names one failure label and four of its signals (tilt,
hands' contacts, table, time; their measures come from `signal_measures`, so no name is
written here). For each failure cluster of that label (the key and slug of
`failure_clusters`) in a run with K1 outcomes, over the members whose outcome carries every
measure (`{run}_cluster_{slug}_carried_judged`, rollouts):

    `..._both_hands_at_failure`   members with every contact measure true
    `..._off_table_at_failure`    members whose table measure is the view's `off_table`
    `..._carried_at_failure`      members with both, i.e. still held off the tables
    `..._tilt_at_failure_median`  deg
    `..._failure_time_median`     s
    `..._tilted_while_carried`    true when the carried members are a MAJORITY of the
                                  judged ones (more than half; half is not a majority)

A member counts only when every measure is there with its type (a number for the tilt and
the time, a boolean per contact, a string for the table). A cluster whose members carry
none is not judged (`signal_presence_<run>_cluster_<slug>_carry_not_judged`); a run with a
cluster of the label and no outcomes entry, the run's part
(`signal_presence_<run>_carry_not_judged`). The reasons depend on the task view only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import median

from flywheel.contracts.outcome import MeasureValue, RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunOutcomes, RunScores, ToolResult, not_judged
from flywheel.eval.agentqa.tools.clusters import keys_of, slug
from flywheel.eval.agentqa.tools.task import TaskView

TOOL = "signal_presence"
ROLLOUTS = "rollouts"


def measure_value(outcome: RolloutOutcome, where: str, name: str) -> MeasureValue:
    """The value of one measure of the outcome; None when it is not there."""
    if where == "verdict":
        value: MeasureValue = getattr(outcome.verdict, name, None)
        return value
    if where == "at_failure":
        return (outcome.verdict.at_failure or {}).get(name)
    held = outcome.final if where == "final" else outcome.extrema
    return held.get(name)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _held(outcome: RolloutOutcome,
          roles: Mapping[str, tuple[str, list[str]]]) -> tuple[float, bool, str, float] | None:
    """(tilt, both hands, table, time) of a member; None when a measure is missing."""
    where, names = roles["tilt"]
    tilt = _number(measure_value(outcome, where, names[0]))
    where, names = roles["contact"]
    contacts = [measure_value(outcome, where, n) for n in names]
    where, names = roles["table"]
    table = measure_value(outcome, where, names[0])
    where, names = roles["time"]
    time = _number(measure_value(outcome, where, names[0]))
    if (tilt is None or time is None or not isinstance(table, str)
            or not all(isinstance(c, bool) for c in contacts)):
        return None
    return tilt, all(c is True for c in contacts), table, time


def _spelled(roles: Mapping[str, tuple[str, list[str]]]) -> str:
    return ", ".join(f"{where}.{n}" for where, names in roles.values() for n in names)


def carry_at_failure(book: FactBook, task: TaskView, labels: Sequence[str],
                     runs: Sequence[RunScores],
                     outcomes: Mapping[str, RunOutcomes]) -> ToolResult:
    """The carry facts of every cluster of the `carry` label, when `labels` holds it."""
    spec = task.carry
    if spec is None or spec.label not in labels:
        return ToolResult(TOOL)
    roles = task.carry_measures()
    facts: list[str] = []
    left_out: list[str] = []
    for run in runs:
        clusters = [(key, members) for key, members in sorted(
            keys_of(task, run).items(), key=lambda kv: (slug(kv[0]), len(kv[1])))
            if key[1] == spec.label]
        if not clusters:
            continue
        held = outcomes.get(run.run)
        if held is None:
            part = not_judged(book, TOOL, f"no outcomes entry for the run, so {spec.label} "
                              "has no measure at the failure", run.ref, f"{run.run}_carry")
            facts += part.facts
            left_out += part.not_judged
            continue
        by_episode = held.by_episode()
        for key, members in clusters:
            name = f"{run.run}_cluster_{slug(key)}"
            judged = [v for s in members if s.episode_id in by_episode
                      for v in [_held(by_episode[s.episode_id], roles)] if v is not None]
            if not judged:
                part = not_judged(book, TOOL, f"no failure of the cluster carries "
                                  f"{_spelled(roles)}", held.ref, f"{name}_carry")
                facts += part.facts
                left_out += part.not_judged
                continue
            both = sum(1 for _, hands, _, _ in judged if hands)
            off = sum(1 for _, _, table, _ in judged if table == spec.off_table)
            carried = sum(1 for _, hands, table, _ in judged
                          if hands and table == spec.off_table)
            facts += [
                book.add(f"{name}_carried_judged", len(judged), held.ref, ROLLOUTS),
                book.add(f"{name}_both_hands_at_failure", both, held.ref, ROLLOUTS),
                book.add(f"{name}_off_table_at_failure", off, held.ref, ROLLOUTS),
                book.add(f"{name}_carried_at_failure", carried, held.ref, ROLLOUTS),
                book.add(f"{name}_tilt_at_failure_median",
                         float(median(t for t, _, _, _ in judged)), held.ref, "deg"),
                book.add(f"{name}_failure_time_median",
                         float(median(t for _, _, _, t in judged)), held.ref, "s"),
                book.add(f"{name}_tilted_while_carried", 2 * carried > len(judged), held.ref),
            ]
    return ToolResult(TOOL, tuple(facts), (), tuple(left_out))
