"""`signal_presence`: can the inputs tell a real failure from a scorer artefact? (DA-43 task 2.3)

For each failure label, the task view lists the signals an engineer needs to judge it
(`labels.<label>.signals`), and for each step check the signals it needs
(`latch_signals`). The tool compares them with what the loaded artifact kinds carry
(`provides`). A label whose signals are missing cannot be diagnosed beyond CHƯA RÕ
(thiếu tín hiệu), spec 6.4 item 1: that is how the team left the tilt failures of
`C_70` (docs/he/tray.md 20.11, H3) and asked DA-38 for `failure_t` and contacts.

With K1 outcomes in the pack (version 2), a signal the task view maps to outcome measures
(`signal_measures`) is available for a label in a run when the run has an `outcomes`
entry and every failed rollout of that label in its scores has an outcome that carries
every measure, not null. A missing one is named: `target_pose (missing:
final.target_yaw_rad)`, `outcome` for a failed rollout without outcome, `outcomes entry`
for a run without one. The facts `<label>_judgeable` and `<label>_signals_missing` keep
their names; their value (source: the task view) covers every run where the label
failed (every run when it failed nowhere): judgeable only when it is judgeable in each.
A run whose own answer differs gets the same two names with its scores file as source,
which the hypothesis rules prefer for that run's clusters. Without an `outcomes` entry in
the pack the tool reads `provides` only, as version 1 did.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, RunOutcomes, RunScores, ToolResult
from flywheel.eval.agentqa.tools.task import SignalMeasures, TaskView

TOOL = "signal_presence"


def labels_seen(runs: Sequence[RunScores]) -> list[str]:
    return sorted({s.failure_kind for r in runs for s in r.scores
                   if not s.success and s.failure_kind})


NO_OUTCOME = "outcome"
NO_ENTRY = "outcomes entry"


def missing_measures(outcome: RolloutOutcome, spec: SignalMeasures) -> list[str]:
    """`<where>.<name>` of every measure of `spec` the outcome lacks or holds null."""
    if spec.where == "verdict":
        held: Mapping[str, object] = {n: getattr(outcome.verdict, n, None) for n in spec.names}
    elif spec.where == "at_failure":
        held = outcome.verdict.at_failure or {}
    else:
        held = outcome.final if spec.where == "final" else outcome.extrema
    return [f"{spec.where}.{n}" for n in spec.names if held.get(n) is None]


def _run_missing(task: TaskView, label: str, run: RunScores | None,
                 held: RunOutcomes | None, available: set[str]) -> dict[str, set[str]]:
    """signal -> what is missing for it in `run` (an empty set: no detail to give)."""
    spec = task.labels[label]
    failed = [] if run is None else [s for s in run.scores
                                     if s.success is not True and s.failure_kind == label]
    by_episode = {} if held is None else held.by_episode()
    out: dict[str, set[str]] = {}
    for sig in spec.signals:
        if sig in available:
            continue
        measures = task.signal_measures.get(sig)
        if measures is None:
            out[sig] = set()
            continue
        if held is None:
            out[sig] = {NO_ENTRY}
            continue
        lacking: set[str] = set()
        for s in failed:
            found = by_episode.get(s.episode_id)
            lacking.update([NO_OUTCOME] if found is None else missing_measures(found, measures))
        if lacking:
            out[sig] = lacking
    return out


def _spelled(task: TaskView, label: str, missing: Mapping[str, set[str]]) -> str:
    parts = [sig if not missing[sig] else f"{sig} (missing: {', '.join(sorted(missing[sig]))})"
             for sig in task.labels[label].signals if sig in missing]
    return ", ".join(parts) or "none"


def signal_presence(book: FactBook, task: TaskView, kinds: Iterable[str],
                    labels: Sequence[str] | None = None, runs: Sequence[RunScores] = (),
                    outcomes: Mapping[str, RunOutcomes] | None = None) -> ToolResult:
    """`kinds`: the artifact kinds loaded (`scores`, `trace`, ...); `labels`: all if None.

    `runs` and `outcomes` (run -> its K1 outcomes) are read only when `kinds` holds
    `outcomes`; otherwise the result is that of `provides` alone.
    """
    ref = task.source_ref
    kinds = sorted(set(kinds))
    with_outcomes = "outcomes" in kinds
    available = {sig for kind in kinds for sig in task.provides.get(kind, [])}
    facts = [book.add("inputs_kinds", ", ".join(kinds) or "none", ref)]
    reasons: list[str] = []
    unknown_kinds = [k for k in kinds if k not in task.provides]
    if unknown_kinds:
        reason = f"kinds {unknown_kinds} are not in provides of {task.task_id}"
        facts.append(book.add(f"{TOOL}_kinds_not_judged", reason, ref))
        reasons.append(reason)
    rows: list[Row] = []
    for label in labels if labels is not None else sorted(task.labels):
        spec = task.labels.get(label)
        if spec is None:
            reason = f"label {label} is not in the task view of {task.task_id}"
            facts.append(book.add(f"{TOOL}_{label}_not_judged", reason, ref))
            reasons.append(reason)
            continue
        if not with_outcomes:
            missing = [sig for sig in spec.signals if sig not in available]
            facts.append(book.add(f"{label}_judgeable", not missing, ref))
            facts.append(book.add(f"{label}_signals_missing", ", ".join(missing) or "none",
                                  ref))
            rows.append({"check": label, "judgeable": not missing,
                         "missing": ", ".join(missing)})
            continue
        held = outcomes or {}
        failing = [r for r in runs if any(s.success is not True and s.failure_kind == label
                                          for s in r.scores)]
        concerned: list[RunScores | None] = list(failing or runs) or [None]
        per_run = [(r, _run_missing(task, label, r, None if r is None else held.get(r.run),
                                    available)) for r in concerned]
        union: dict[str, set[str]] = {}
        for _, missing_of in per_run:
            for sig, what in missing_of.items():
                union.setdefault(sig, set()).update(what)
        overall = (not union, _spelled(task, label, union))
        facts.append(book.add(f"{label}_judgeable", overall[0], ref))
        facts.append(book.add(f"{label}_signals_missing", overall[1], ref))
        rows.append({"check": label, "judgeable": overall[0],
                     "missing": "" if overall[0] else overall[1]})
        for r, missing_of in per_run:
            own = (not missing_of, _spelled(task, label, missing_of))
            if r is None or own == overall:
                continue
            facts.append(book.add(f"{label}_judgeable", own[0], r.ref))
            facts.append(book.add(f"{label}_signals_missing", own[1], r.ref))
            rows.append({"check": f"{label} in {r.run}", "judgeable": own[0],
                         "missing": "" if own[0] else own[1]})
    for step, needed in sorted(task.latch_signals.items(), key=lambda kv: task.index(kv[0])):
        missing = [sig for sig in needed if sig not in available]
        facts.append(book.add(f"latch_{step}_judgeable", not missing, ref))
        facts.append(book.add(f"latch_{step}_signals_missing", ", ".join(missing) or "none",
                              ref))
        rows.append({"check": f"latch {step}", "judgeable": not missing,
                     "missing": ", ".join(missing)})
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))
