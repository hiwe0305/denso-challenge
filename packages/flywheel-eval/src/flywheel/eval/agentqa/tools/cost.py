"""`cost_lookup`: what a check or an intervention costs, estimated and measured (task 3.4).

For each check of `configs/eval/agentqa/checks.yaml` (by its `cost_key`) and each
`InterventionKind`, from `configs/eval/agentqa/costs.yaml` and the site ledger:

- the unit price of the rate of its kind, when the price book has one;
- the rows of past jobs of the same kind, `estimated` and `measured` apart, never merged:
  how many, the median quantity, the USD they add up to. A measured figure is never a
  stand-in for the estimate or the other way round.

The ledger is read, never written, through `flywheel.store`. The price book may be empty:
a resource_type with no rate has no price fact (nothing is invented), is `not_judged` once
for the call, and its ledger rows are still reported. A kind with no measured row is
`not_judged` too, one fact for the call that names the kinds, so silence is not read as 0.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from statistics import median

import yaml
from flywheel.contracts.configs import PriceBookConfig
from flywheel.contracts.entities import LedgerEntry
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ToolResult, not_judged
from flywheel.store.paths import StorePaths
from flywheel.store.tables import complete_lines
from pydantic import BaseModel, ConfigDict, ValidationError

TOOL = "cost_lookup"
COSTS_FILE = Path("configs") / "eval" / "agentqa" / "costs.yaml"
CHECKS_FILE = Path("configs") / "eval" / "agentqa" / "checks.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KindSpec(_Frozen):
    activity: str
    resource_type: str


class Costs(_Frozen):
    pricebook: PriceBookConfig
    kinds: dict[str, KindSpec]


def load_costs(path: Path = COSTS_FILE) -> Costs:
    return Costs.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def check_costs(path: Path = CHECKS_FILE) -> dict[str, str]:
    """check id -> cost key, from the check catalog."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {c["id"]: c["cost_key"] for c in raw["checks"]}


def read_ledger(paths: StorePaths) -> tuple[list[LedgerEntry], int]:
    """Every ledger row of the site, and how many lines did not parse."""
    rows: list[LedgerEntry] = []
    bad = 0
    for file in sorted(paths.runs_dir.glob("**/ledger*.jsonl")):
        for line in complete_lines(file):
            try:
                rows.append(LedgerEntry.model_validate(json.loads(line)))
            except (ValueError, ValidationError):
                bad += 1
    return rows, bad


def _figures(book: FactBook, name: str, kind: str, rows: Sequence[LedgerEntry],
             unit: str, ref: str) -> list[str]:
    facts = [book.add(f"cost_{name}_{kind}_rows", len(rows), ref, "rows")]
    if rows:
        facts += [book.add(f"cost_{name}_{kind}_quantity_median",
                           float(median(r.quantity for r in rows)), ref, unit),
                  book.add(f"cost_{name}_{kind}_usd_total",
                           float(sum(r.usd_amount for r in rows)), ref, "usd")]
    return facts


def cost_lookup(book: FactBook, costs: Costs, checks: dict[str, str], names: Sequence[str],
                kinds: Sequence[str], ledger: Sequence[LedgerEntry], unreadable: int,
                ref: str) -> ToolResult:
    """`names`: check ids; `kinds`: intervention kinds (both from closed domains)."""
    rates = {r.resource_type: r for r in costs.pricebook.rates}
    facts = [book.add("cost_ledger_unreadable_rows", unreadable, "store", "rows"),
             book.add("cost_pricebook_hash", costs.pricebook.cfg_hash(), ref)]
    unpriced: set[str] = set()
    unkeyed: list[str] = []
    mixed: list[str] = []
    unmeasured: list[str] = []
    keyed = [(n, checks[n]) for n in names] + [(k, k) for k in kinds]
    for name, key in keyed:
        kind = costs.kinds.get(key)
        if kind is None:
            unkeyed.append(name)
            continue
        rate = rates.get(kind.resource_type)
        same = [r for r in ledger if r.activity == kind.activity
                and r.resource_type == kind.resource_type]
        if rate is None:
            unpriced.add(kind.resource_type)
            units = {r.unit for r in same}
            if len(units) > 1:
                mixed.append(name)
                same = []
            unit = next(iter(units)) if len(units) == 1 else ""
        else:
            unit = rate.unit
            same = [r for r in same if r.unit == unit]
            facts += [book.add(f"cost_{name}_price", rate.usd_per_unit, ref, f"usd/{unit}"),
                      book.add(f"cost_{name}_human_hours_per_unit", rate.human_hours_per_unit,
                               ref, f"h/{unit}"),
                      book.add(f"cost_{name}_price_is_assumption", rate.is_assumption, ref)]
        for measure in ("estimated", "measured"):
            rows = [r for r in same if r.measure_kind == measure]
            facts += _figures(book, name, measure, rows, unit, "store")
            if measure == "measured" and not rows:
                unmeasured.append(name)
    reasons: list[str] = []
    for part, missing, why in (
            ("price", sorted(unpriced), "no price in the price book for "),
            ("kind", unkeyed, "no ledger kind in costs.yaml for "),
            ("units", mixed, "ledger rows in more than one unit, so not added up, for "),
            ("measured", unmeasured, "no measured ledger row of the kind for ")):
        if missing:
            reason = why + ", ".join(missing)
            facts.append(book.add(f"{TOOL}_{part}_not_judged", reason, ref))
            reasons.append(reason)
    return ToolResult(TOOL, tuple(facts), (), tuple(reasons))


def no_costs(book: FactBook, reason: str) -> ToolResult:
    return not_judged(book, TOOL, reason, str(COSTS_FILE))
