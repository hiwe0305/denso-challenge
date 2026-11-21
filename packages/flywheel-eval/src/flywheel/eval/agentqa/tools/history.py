"""`history_lookup`: what past interventions of a kind fixed (task 3.4).

From the `FixRateEvent` rows of the site catalog, read through `flywheel.store`: per
intervention kind, how many events, how many conditions they measured, how many were fixed,
and the fixed share. Evidence cards are read nowhere: a card sits under its run plan in the
store and is not an admitted kind of the pack, so `EvidenceCard.result` is out of reach
here. A kind with no event is `not_judged` (one fact for the call, naming the kinds), so a
kind nobody tried is never read as one that did not work.
"""

from __future__ import annotations

from collections.abc import Sequence

from flywheel.contracts.entities import FixRateEvent
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, ToolResult
from flywheel.store.paths import StorePaths
from flywheel.store.tables import read_table_records
from pydantic import ValidationError

TOOL = "history_lookup"
TABLE = "fix_rate_event"


def read_events(paths: StorePaths) -> tuple[list[FixRateEvent], int]:
    """The fix-rate events of the site, and how many rows did not parse."""
    events: list[FixRateEvent] = []
    bad = 0
    for record in read_table_records(TABLE, paths):
        try:
            events.append(FixRateEvent.model_validate(record))
        except ValidationError:
            bad += 1
    return events, bad


def history_lookup(book: FactBook, kinds: Sequence[str], events: Sequence[FixRateEvent],
                   unreadable: int) -> ToolResult:
    ref = f"catalog/{TABLE}"
    facts = [book.add("history_unreadable_rows", unreadable, ref, "rows")]
    rows: list[Row] = []
    untried: list[str] = []
    for kind in kinds:
        mine = [e for e in events if e.intervention_type == kind]
        facts.append(book.add(f"history_{kind}_events", len(mine), ref, "events"))
        if not mine:
            untried.append(kind)
            continue
        conditions = sum(e.n_conditions for e in mine)
        fixed = sum(e.fixed for e in mine)
        facts += [book.add(f"history_{kind}_conditions", conditions, ref, "conditions"),
                  book.add(f"history_{kind}_fixed", fixed, ref, "conditions")]
        if conditions:
            facts.append(book.add(f"history_{kind}_fix_rate", fixed / conditions, ref))
        rows.append({"kind": kind, "events": len(mine), "conditions": conditions,
                     "fixed": fixed})
    reasons: list[str] = []
    if untried:
        reason = f"{', '.join(untried)}: no FixRateEvent of the kind in the store"
        facts.append(book.add(f"{TOOL}_not_judged", reason, ref))
        reasons.append(reason)
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))
