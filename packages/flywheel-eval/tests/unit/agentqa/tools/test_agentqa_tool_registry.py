"""The registry of plan tools and the closed domains of their parameters (DA-43 task 4.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunScores, StoreRows
from flywheel.eval.agentqa.tools.registry import REGISTRY, MeasureContext, check_params
from flywheel.eval.agentqa.tools.task import TaskView
from helpers_tools import job_of, metric, rollout, trace_of

EMPTY_LEDGER = StoreRows("store_snapshot/ledger.jsonl", ())
EMPTY_EVENTS = StoreRows("store_snapshot/fix_rate.jsonl", ())
PARAMS: dict[str, dict[str, Any]] = {
    "task_lookup": {},
    "step_pass_table": {"runs": "all"},
    "failure_clusters": {"runs": "all"},
    "latch_consistency": {"runs": "all"},
    "signal_presence": {"labels": "seen"},
    "paired_compare": {"pairs": "all", "levels": "all"},
    "trace_stats": {"runs": "all"},
    "train_window": {"jobs": "all", "window": "last"},
    "lineage": {},
    "coverage_distance": {"runs": "all"},
    "cost_lookup": {"checks": "all", "interventions": "all"},
    "history_lookup": {"interventions": "all"},
}


@pytest.fixture
def ctx(runs: dict[str, RunScores], tray: TaskView) -> MeasureContext:
    return MeasureContext(tray, runs, frozenset({"scores", "ledger", "fix_rate"}),
                          ledger=EMPTY_LEDGER, fix_rate=EMPTY_EVENTS)


def test_every_tool_is_registered() -> None:
    assert sorted(REGISTRY) == sorted(PARAMS)


@pytest.mark.parametrize("name", sorted(PARAMS))
def test_every_tool_runs_through_its_spec(name: str, ctx: MeasureContext) -> None:
    spec = REGISTRY[name]
    assert check_params(spec, PARAMS[name], ctx) == []
    result = spec.run(FactBook(), ctx, PARAMS[name])
    assert result.tool == name and result.facts


def test_pairs_all_on_four_runs_gives_six_comparisons(ctx: MeasureContext) -> None:
    result = REGISTRY["paired_compare"].run(FactBook(), ctx, PARAMS["paired_compare"])
    assert len(result.rows) == 6
    assert (result.rows[0]["a"], result.rows[0]["b"]) == tuple(list(ctx.runs)[:2])


def test_a_list_of_runs_and_levels_restricts_the_call(ctx: MeasureContext) -> None:
    runs = list(ctx.runs)[:2]
    spec = REGISTRY["paired_compare"]
    params = {"pairs": [runs], "levels": [1]}
    assert check_params(spec, params, ctx) == []
    assert len(spec.run(FactBook(), ctx, params).rows) == 1


@pytest.mark.parametrize(("name", "params", "text"), [
    ("step_pass_table", {"runs": ["NOPE"]}, "not in the pack"),
    ("step_pass_table", {"runs": 60}, "list of run names"),
    ("step_pass_table", {"runs": []}, "list of run names"),
    ("step_pass_table", {}, "missing"),
    ("step_pass_table", {"runs": "all", "limit": 5}, "unknown parameter"),
    ("paired_compare", {"pairs": "all", "levels": [7]}, "does not occur"),
    ("paired_compare", {"pairs": "all", "levels": [0.5]}, "integer levels"),
    ("paired_compare", {"pairs": [["B_ALL", "B_ALL"]]}, "with itself"),
    ("paired_compare", {"pairs": [["B_ALL"]]}, "not a pair"),
    ("signal_presence", {"labels": ["L-NOPE"]}, "not a label"),
    ("signal_presence", {"labels": 0.3}, "list of labels"),
    ("task_lookup", {"step": "teleport"}, "not a step"),
])
def test_check_params_refuses(name: str, params: dict[str, Any], text: str,
                              ctx: MeasureContext) -> None:
    problems = check_params(REGISTRY[name], params, ctx)
    assert problems and any(text in p for p in problems), problems


def test_check_params_lists_every_problem(ctx: MeasureContext) -> None:
    problems = check_params(REGISTRY["paired_compare"], {"levels": [9], "x": 1}, ctx)
    assert len(problems) >= 3  # missing pairs, unknown x, level 9


@pytest.fixture
def ctx_jobs(ctx: MeasureContext) -> MeasureContext:
    return MeasureContext(ctx.task, ctx.runs, frozenset({"scores", "metrics"}),
                          jobs={"J": job_of("J", [metric("J", 10, 1.0),
                                                  metric("J", 20, 2.0, split="val")])})


@pytest.mark.parametrize(("params", "text"), [
    ({"jobs": ["NOPE"], "window": "all"}, "job 'NOPE' is not in the pack"),
    ({"jobs": 3, "window": "all"}, "list of job ids"),
    ({"jobs": "all", "window": 15}, "not a logged step of job J"),
    ({"jobs": "all", "window": 0.5}, "logged step"),
    ({"jobs": "all", "window": "first"}, "logged step"),
    ({"jobs": "all", "window": True}, "logged step"),
    ({"jobs": "all"}, "'window' is missing"),
    ({"jobs": [["J"]], "window": 20}, "list of job ids"),
])
def test_train_window_refuses_what_is_outside_its_domains(
        params: dict[str, Any], text: str, ctx_jobs: MeasureContext) -> None:
    problems = check_params(REGISTRY["train_window"], params, ctx_jobs)
    assert problems and any(text in p for p in problems), problems


def test_train_window_accepts_a_logged_step_and_runs(ctx_jobs: MeasureContext) -> None:
    params = {"jobs": ["J"], "window": 20}
    assert check_params(REGISTRY["train_window"], params, ctx_jobs) == []
    result = REGISTRY["train_window"].run(FactBook(), ctx_jobs, params)
    assert result.judged is False and result.rows[0]["window"] == "s20"


def test_trace_stats_refuses_a_run_that_is_not_in_the_pack(ctx: MeasureContext) -> None:
    problems = check_params(REGISTRY["trace_stats"], {"runs": ["NOPE"]}, ctx)
    assert any("not in the pack" in p for p in problems)
    assert any("unknown parameter" in p
               for p in check_params(REGISTRY["lineage"], {"depth": 3}, ctx))


@pytest.mark.parametrize(("name", "params", "text"), [
    ("cost_lookup", {"checks": ["rm -rf"], "interventions": "all"}, "'rm -rf' is not one of"),
    ("cost_lookup", {"checks": "all", "interventions": ["sim_s9"]}, "'sim_s9' is not one of"),
    ("cost_lookup", {"checks": "some", "interventions": "all"}, "list of checks"),
    ("cost_lookup", {"interventions": "all"}, "'checks' is missing"),
    ("history_lookup", {"interventions": 3}, "list of interventions"),
    ("history_lookup", {"interventions": ["report_only", "free text"]}, "'free text' is not"),
    ("coverage_distance", {"runs": ["NOPE"]}, "not in the pack"),
])
def test_cost_history_and_coverage_refuse_what_is_outside_their_domains(
        name: str, params: dict[str, Any], text: str, ctx: MeasureContext) -> None:
    problems = check_params(REGISTRY[name], params, ctx)
    assert problems and any(text in p for p in problems), problems


def test_cost_and_history_take_the_closed_domains(ctx: MeasureContext) -> None:
    for name, params in (("cost_lookup", {"checks": ["cpu_analysis_x"], "interventions": "all"}),):
        assert check_params(REGISTRY[name], params, ctx)  # a cost key is not a check id
    good = {"checks": ["log_missing_signals"], "interventions": ["sim_s1", "report_only"]}
    assert check_params(REGISTRY["cost_lookup"], good, ctx) == []


# a fact's name fixes its value within a round, whatever the parameters of a call --------

def _full(ctx: MeasureContext) -> MeasureContext:
    runs = list(ctx.runs)
    traces = {r: trace_of(r, [step for e in ("l1-s0", "l1-s1") for step in rollout(r, e)])
              for r in runs}
    jobs = {j: job_of(j, [metric(j, 10, 1.0), metric(j, 20, 2.0, split="val")])
            for j in ("J", "K")}
    return MeasureContext(ctx.task, ctx.runs, ctx.kinds | {"trace", "metrics"},
                          traces=traces, jobs=jobs, ledger=EMPTY_LEDGER, fix_rate=EMPTY_EVENTS)


def _param_sets(ctx: MeasureContext) -> dict[str, list[dict[str, Any]]]:
    first, second = list(ctx.runs)[:2]
    step = ctx.task.steps[0]
    return {
        "task_lookup": [{}, {"step": step}],
        "step_pass_table": [{"runs": "all"}, {"runs": [first]}],
        "failure_clusters": [{"runs": "all"}, {"runs": [first]}],
        "latch_consistency": [{"runs": "all"}, {"runs": [second]}],
        "signal_presence": [{"labels": "seen"}, {"labels": "all"}],
        "paired_compare": [{"pairs": "all", "levels": "all"},
                           {"pairs": [[first, second]], "levels": [1]},
                           {"pairs": [[second, first]], "levels": [2]}],
        "trace_stats": [{"runs": "all"}, {"runs": [first]}],
        "train_window": [{"jobs": "all", "window": "last"}, {"jobs": ["J"], "window": "all"},
                         {"jobs": "all", "window": 20}],
        "lineage": [{}, {}],
        "coverage_distance": [{"runs": "all"}, {"runs": [first]}],
        "cost_lookup": [{"checks": "all", "interventions": "all"},
                        {"checks": ["log_missing_signals"], "interventions": ["sim_s1"]},
                        {"checks": ["inspect_latch_on_successes"], "interventions": ["sim_s2"]}],
        "history_lookup": [{"interventions": "all"}, {"interventions": ["sim_s1"]},
                           {"interventions": ["sim_s2", "sim_s3"]}],
    }


@pytest.mark.parametrize("name", sorted(PARAMS))
def test_a_tool_run_twice_with_other_parameters_never_clashes_in_one_book(
        name: str, ctx: MeasureContext) -> None:
    full = _full(ctx)
    book = FactBook()
    for params in _param_sets(full)[name]:
        assert check_params(REGISTRY[name], params, full) == [], params
        REGISTRY[name].run(book, full, params)  # FactClash would raise here
    assert book.facts


def test_the_param_sets_cover_every_registered_tool(ctx: MeasureContext) -> None:
    assert sorted(_param_sets(ctx)) == sorted(REGISTRY)


# the tools read the pack, never the live store ----------------------------------------------

def test_no_tool_module_imports_the_store() -> None:
    import flywheel.eval.agentqa.tools as tools

    for path in Path(tools.__file__).parent.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "flywheel.store" not in text, path.name


def test_cost_and_history_need_their_snapshot_kinds() -> None:
    assert REGISTRY["cost_lookup"].needs == ("ledger",)
    assert REGISTRY["history_lookup"].needs == ("fix_rate",)
