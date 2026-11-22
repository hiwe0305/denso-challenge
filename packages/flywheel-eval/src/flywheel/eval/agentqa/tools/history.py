"""`history_lookup`: what past interventions of a kind fixed (task 3.4).

From the `FixRateEvent` rows of the pack's `fix_rate` entry (the store snapshot): per
intervention kind, how many events, how many conditions they measured, how many were fixed,
and the fixed share. Evidence cards are read nowhere: a card sits under its run plan in the
store and is not an admitted kind of the pack, so `EvidenceCard.result` is out of reach
here. A kind with no event is `not_judged` (`history_<kind>_not_judged`, named by the kind), so a
kind nobody tried is never read as one that did not work.
"""

from __future__ import annotations

from collections.abc import Sequence

from flywheel.contracts.entities import FixRateEvent
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, ToolResult

TOOL = "history_lookup"


def history_lookup(book: FactBook, kinds: Sequence[str], events: Sequence[FixRateEvent],
                   unreadable: int, ref: str = "store_snapshot/fix_rate.jsonl") -> ToolResult:
    """`ref`: the pack entry (the store snapshot of step B0) the events come from."""
    facts = [book.add("history_unreadable_rows", unreadable, ref, "rows")]
    rows: list[Row] = []
    reasons: list[str] = []
    for kind in kinds:
        mine = [e for e in events if e.intervention_type == kind]
        facts.append(book.add(f"history_{kind}_events", len(mine), ref, "events"))
        if not mine:
            reason = f"{kind}: no FixRateEvent of the kind in the pack"
            facts.append(book.add(f"history_{kind}_not_judged", reason, ref))
            reasons.append(reason)
            continue
        conditions = sum(e.n_conditions for e in mine)
        fixed = sum(e.fixed for e in mine)
        facts += [book.add(f"history_{kind}_conditions", conditions, ref, "conditions"),
                  book.add(f"history_{kind}_fixed", fixed, ref, "conditions")]
        if conditions:
            facts.append(book.add(f"history_{kind}_fix_rate", fixed / conditions, ref))
        rows.append({"kind": kind, "events": len(mine), "conditions": conditions,
                     "fixed": fixed})
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))
