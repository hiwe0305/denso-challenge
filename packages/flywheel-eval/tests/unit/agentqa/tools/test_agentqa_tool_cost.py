"""`cost_lookup` and `history_lookup` over an isolated store (DA-43 task 3.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flywheel.contracts.configs import PriceBookConfig, PriceRateConfig
from flywheel.contracts.entities import FixRateEvent
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import ToolResult
from flywheel.eval.agentqa.tools.cost import (
    Costs,
    check_costs,
    cost_lookup,
    load_costs,
    read_ledger,
)
from flywheel.eval.agentqa.tools.history import history_lookup, read_events
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import write_record
from helpers_tools import ledger_row

CHECKS = check_costs()
KINDS = ["sim_s1", "teleop_correction"]


def values(book: FactBook, result) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {book.get(f).name: book.get(f).value for f in result.facts}


@pytest.fixture
def paths(tmp_path: Path) -> StorePaths:
    return StorePaths(tmp_path / "store")


PRICED = PriceBookConfig(name="test", rates=[
    PriceRateConfig(resource_type="gpu_seconds", unit="s", usd_per_unit=0.5, is_assumption=False),
    PriceRateConfig(resource_type="teleop_episode", unit="episode", usd_per_unit=2.0,
                    human_hours_per_unit=0.05)])


def priced(book: PriceBookConfig = PRICED) -> Costs:
    return load_costs().model_copy(update={"pricebook": book})


def lookup(paths: StorePaths, names: list[str], kinds: list[str],
           costs: Costs | None = None) -> tuple[ToolResult, dict[str, object]]:
    ledger, bad = read_ledger(paths)
    book = FactBook()
    result = cost_lookup(book, costs or priced(), CHECKS, names, kinds, ledger, bad,
                         "costs.yaml")
    return result, values(book, result)


def test_the_check_catalog_and_the_cost_keys_agree() -> None:
    costs = load_costs()
    assert set(CHECKS.values()) <= set(costs.kinds)
    assert all(k in costs.kinds for k in ("sim_s1", "report_only", "recovery_data"))


def test_estimated_and_measured_rows_stay_two_sets_of_facts(paths: StorePaths) -> None:
    estimate = ledger_row("estimated", "eval", "gpu_seconds", "s", 600.0, 0.24)
    append_ledger_entry(estimate, paths)
    append_ledger_entry(ledger_row("estimated", "eval", "gpu_seconds", "s", 200.0, 0.08,
                                   job="job-2"), paths)
    append_ledger_entry(ledger_row("measured", "eval", "gpu_seconds", "s", 450.0, 0.18,
                                   estimate=estimate.id), paths)
    append_ledger_entry(ledger_row("measured", "diagnosis", "cpu_seconds", "s", 9.0, 0.0,
                                   estimate=estimate.id, job="job-3"), paths)  # another kind
    result, got = lookup(paths, ["log_missing_signals"], [])
    p = "cost_log_missing_signals"
    assert got[f"{p}_price"] == 0.5 and got[f"{p}_price_is_assumption"] is False
    assert (got[f"{p}_estimated_rows"], got[f"{p}_estimated_quantity_median"]) == (2, 400.0)
    assert got[f"{p}_estimated_usd_total"] == pytest.approx(0.32)
    assert (got[f"{p}_measured_rows"], got[f"{p}_measured_quantity_median"]) == (1, 450.0)
    assert got[f"{p}_measured_usd_total"] == pytest.approx(0.18)
    assert result.judged  # every key asked for has a measured row


def test_a_kind_with_no_measured_row_is_one_not_judged_fact_naming_it(paths: StorePaths) -> None:
    result, got = lookup(paths, ["inspect_latch_on_successes"], KINDS)
    assert got["cost_sim_s1_measured_rows"] == 0 and got["cost_sim_s1_estimated_rows"] == 0
    assert "cost_sim_s1_measured_quantity_median" not in got
    for name in ("inspect_latch_on_successes", "sim_s1", "teleop_correction"):
        assert got[f"cost_{name}_measured_not_judged"] == (
            f"no measured ledger row of the kind for {name}")
    assert got["cost_teleop_correction_human_hours_per_unit"] == 0.05
    assert got["cost_price_cpu_seconds_not_judged"] == (
        "no price in the price book for cpu_seconds")
    assert got["cost_price_sim_episode_not_judged"] == (
        "no price in the price book for sim_episode")
    assert len(result.not_judged) == 5


def test_the_shipped_price_book_holds_no_invented_rate() -> None:
    assert load_costs().pricebook.rates == []


def test_with_no_price_there_is_no_price_fact_but_the_ledger_rows_are_reported(
        paths: StorePaths) -> None:
    estimate = ledger_row("estimated", "eval", "gpu_seconds", "s", 600.0, 0.0)
    append_ledger_entry(estimate, paths)
    append_ledger_entry(ledger_row("measured", "eval", "gpu_seconds", "s", 450.0, 0.0,
                                   estimate=estimate.id), paths)
    result, got = lookup(paths, ["log_missing_signals", "inspect_latch_on_successes"], ["sim_s1"],
                         costs=priced(PriceBookConfig(name="empty")))
    assert not any(n.endswith(("_price", "_human_hours_per_unit")) for n in got)
    p = "cost_log_missing_signals"
    assert (got[f"{p}_measured_rows"], got[f"{p}_measured_quantity_median"]) == (1, 450.0)
    assert got[f"{p}_estimated_quantity_median"] == 600.0
    for rt in ("cpu_seconds", "gpu_seconds", "sim_episode"):
        assert got[f"cost_price_{rt}_not_judged"] == f"no price in the price book for {rt}"
    assert "price" in result.not_judged[0]


def test_a_key_the_cost_file_does_not_know_is_not_judged(paths: StorePaths) -> None:
    costs = load_costs()
    costs = costs.model_copy(update={"kinds": {k: v for k, v in costs.kinds.items()
                                               if k != "sim_s2"}})
    book = FactBook()
    result = cost_lookup(book, costs, CHECKS, [], ["sim_s2"], [], 0, "costs.yaml")
    got = values(book, result)
    assert got["cost_sim_s2_kind_not_judged"] == "no ledger kind in costs.yaml for sim_s2"
    assert "cost_sim_s2_measured_rows" not in got


def test_the_tool_never_writes_the_store(paths: StorePaths) -> None:
    lookup(paths, list(CHECKS), KINDS)
    history_lookup(FactBook(), KINDS, *read_events(paths))
    assert not paths.root.exists()


def event(kind: str, n: int, fixed: int) -> FixRateEvent:
    return FixRateEvent(intervention_type=kind, n_conditions=n, fixed=fixed)


def test_history_gives_the_recorded_fix_rate_of_each_kind(paths: StorePaths) -> None:
    for e in (event("sim_s1", 10, 4), event("sim_s1", 5, 1), event("sim_s2", 4, 0)):
        write_record("fix_rate_event", e, paths)
    events, bad = read_events(paths)
    book = FactBook()
    result = history_lookup(book, ["sim_s1", "sim_s3"], events, bad)
    got = values(book, result)
    assert got["history_sim_s1_events"] == 2 and got["history_sim_s1_conditions"] == 15
    assert got["history_sim_s1_fixed"] == 5
    assert got["history_sim_s1_fix_rate"] == pytest.approx(5 / 15)
    assert got["history_sim_s3_not_judged"] == "sim_s3: no FixRateEvent of the kind in the store"
    assert got["history_sim_s3_events"] == 0 and "history_sim_s3_fix_rate" not in got
    assert "history_sim_s2_events" not in got  # only the kinds asked for


def test_an_empty_store_is_not_judged_not_a_fix_rate_of_zero(paths: StorePaths) -> None:
    book = FactBook()
    result = history_lookup(book, KINDS, *read_events(paths))
    assert not result.judged and not result.rows
