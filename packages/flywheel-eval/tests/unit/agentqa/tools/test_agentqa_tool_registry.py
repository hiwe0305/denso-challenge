"""The registry of plan tools and the closed domains of their parameters (DA-43 task 4.2)."""

from __future__ import annotations

from typing import Any

import pytest
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunScores
from flywheel.eval.agentqa.tools.registry import REGISTRY, MeasureContext, check_params
from flywheel.eval.agentqa.tools.task import TaskView
from helpers_tools import job_of, metric

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
}


@pytest.fixture
def ctx(runs: dict[str, RunScores], tray: TaskView) -> MeasureContext:
    return MeasureContext(tray, runs, frozenset({"scores"}))


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
