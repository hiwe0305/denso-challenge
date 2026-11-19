"""`signal_presence`: can the inputs tell a real failure from a scorer artefact? (DA-43 task 2.3)

For each failure label, the task view lists the signals an engineer needs to judge it
(`labels.<label>.signals`), and for each step check the signals it needs
(`latch_signals`). The tool compares them with what the loaded artifact kinds carry
(`provides`). A label whose signals are missing cannot be diagnosed beyond CHƯA RÕ
(thiếu tín hiệu), spec 6.4 item 1: that is how the team left the tilt failures of
`C_70` (docs/he/tray.md 20.11, H3) and asked DA-38 for `failure_t` and contacts.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, RunScores, ToolResult
from flywheel.eval.agentqa.tools.task import TaskView

TOOL = "signal_presence"


def labels_seen(runs: Sequence[RunScores]) -> list[str]:
    return sorted({s.failure_kind for r in runs for s in r.scores
                   if not s.success and s.failure_kind})


def signal_presence(book: FactBook, task: TaskView, kinds: Iterable[str],
                    labels: Sequence[str] | None = None) -> ToolResult:
    """`kinds`: the artifact kinds loaded (`scores`, `trace`, ...); `labels`: all if None."""
    ref = task.source_ref
    kinds = sorted(set(kinds))
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
        missing = [sig for sig in spec.signals if sig not in available]
        facts.append(book.add(f"{label}_judgeable", not missing, ref))
        facts.append(book.add(f"{label}_signals_missing", ", ".join(missing) or "none", ref))
        rows.append({"check": label, "judgeable": not missing, "missing": ", ".join(missing)})
    for step, needed in sorted(task.latch_signals.items(), key=lambda kv: task.index(kv[0])):
        missing = [sig for sig in needed if sig not in available]
        facts.append(book.add(f"latch_{step}_judgeable", not missing, ref))
        facts.append(book.add(f"latch_{step}_signals_missing", ", ".join(missing) or "none",
                              ref))
        rows.append({"check": f"latch {step}", "judgeable": not missing,
                     "missing": ", ".join(missing)})
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))
