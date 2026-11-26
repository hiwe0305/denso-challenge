"""The bridge between the tool registry and a tool-calling shell (DA-49 task 2.1).

The pack is the round tests' (`helpers_round.pack_maker`: four 60k runs, scores only);
the builders of `helpers_round` and `helpers_tools` are imported from their directories,
as `tests/contract/agentqa/test_agentqa_cases.py` does for `agentqa_build`.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, get_args

import pytest
import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
sys.path.insert(0, str(_HERE.parent / "tools"))
from flywheel.contracts.agentqa import AgentFact  # noqa: E402
from flywheel.contracts.evidence import InterventionKind  # noqa: E402
from flywheel.eval.agentqa.mcp import bridge  # noqa: E402
from flywheel.eval.agentqa.mcp.bridge import (  # noqa: E402
    DESCRIPTIONS,
    MAX_STEP_ENUM,
    CallOutcome,
    ToolSession,
    UnknownTool,
    param_schema,
)
from flywheel.eval.agentqa.round.admit import Admitted, admit  # noqa: E402
from flywheel.eval.agentqa.round.measure import measure  # noqa: E402
from flywheel.eval.agentqa.round.pack import read_pack  # noqa: E402
from flywheel.eval.agentqa.round.records import Pack  # noqa: E402
from flywheel.eval.agentqa.tools.cost import check_costs  # noqa: E402
from flywheel.eval.agentqa.tools.registry import (  # noqa: E402
    REGISTRY,
    MeasureContext,
    check_params,
)
from flywheel.eval.agentqa.tools.task import load_task  # noqa: E402
from helpers_round import (  # noqa: E402, F401  (isolated_store is an autouse fixture)
    PLAN,
    isolated_store,
    pack_maker,
)
from helpers_tools import job_of, metric  # noqa: E402

RUNS = ["B_ALL", "C_ALL", "B_70", "C_70"]  # pack order, as the pack's entries list them
PLAN_CALLS: list[dict[str, Any]] = yaml.safe_load(PLAN.read_text())["calls"]


@pytest.fixture
def opened(tmp_path: Path) -> tuple[Pack, Admitted]:
    path = pack_maker(tmp_path)()
    return read_pack(path), admit(path)


@pytest.fixture
def session(opened: tuple[Pack, Admitted]) -> ToolSession:
    return ToolSession.from_admitted(*opened)


def _nodes(schema: Any) -> Iterator[dict[str, Any]]:
    if isinstance(schema, dict):
        yield schema
        for value in schema.values():
            yield from _nodes(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _nodes(value)


def _props(session: ToolSession) -> dict[str, dict[str, Any]]:
    return {t.name: t.input_schema["properties"] for t in session.tools()}


def test_tools_are_the_registry_in_its_order(session: ToolSession) -> None:
    tools = session.tools()
    assert [t.name for t in tools] == list(REGISTRY)
    assert len(tools) == len(REGISTRY)
    assert set(DESCRIPTIONS) == set(REGISTRY)
    assert [t.version for t in tools] == [s.version for s in REGISTRY.values()]
    assert session.tools() == tools  # computed once, the same each time
    trace = next(t for t in tools if t.name == "trace_stats")
    assert trace.missing == ("trace",) and trace.needs == ("scores", "trace")
    assert trace.description.endswith(" Not available on this pack: no entry of kind trace.")
    task = next(t for t in tools if t.name == "task_lookup")
    assert task.missing == () and task.description == DESCRIPTIONS["task_lookup"]


def test_each_parameter_has_its_closed_domain_from_the_pack(session: ToolSession) -> None:
    props = _props(session)
    tray = load_task("tray")
    runs = props["step_pass_table"]["runs"]
    assert runs["anyOf"] == [
        {"type": "string", "enum": ["all"]},
        {"type": "array", "minItems": 1, "items": {"type": "string", "enum": RUNS}}]
    pairs = props["paired_compare"]["pairs"]["anyOf"][1]
    assert pairs["items"] == {"type": "array", "minItems": 2, "maxItems": 2,
                              "items": {"type": "string", "enum": RUNS}}
    levels = props["paired_compare"]["levels"]["anyOf"][1]
    assert levels["items"] == {"type": "integer", "enum": [1, 2]}
    assert "runs the call concerns" in props["paired_compare"]["levels"]["description"]
    step = props["task_lookup"]["step"]
    assert step["type"] == "string" and step["enum"] == list(tray.steps)
    assert step["enum"][0] == "approach_a" and "place" in step["enum"]
    labels = props["signal_presence"]["labels"]["anyOf"]
    assert labels[0]["enum"] == ["seen", "all"]
    assert labels[1]["items"]["enum"] == sorted(tray.labels)
    assert {"L-PLACE-POSE", "L-TRAY-TILT"} <= set(labels[1]["items"]["enum"])
    # no job in the pack: only the words remain
    assert props["train_window"]["jobs"]["enum"] == ["all"]
    assert props["train_window"]["window"]["enum"] == ["all", "last"]
    assert props["cost_lookup"]["checks"]["anyOf"][1]["items"]["enum"] == list(check_costs())
    assert props["history_lookup"]["interventions"]["anyOf"][1]["items"]["enum"] == list(
        get_args(InterventionKind))
    for tool in session.tools():
        for node in _nodes(tool.input_schema):
            assert node.get("enum", [None]) != [], (tool.name, node)
        assert tool.input_schema["required"] == [
            p for p in REGISTRY[tool.name].params if p not in ("levels", "step")]


def test_no_schema_takes_a_free_string_or_a_path(session: ToolSession) -> None:
    for tool in session.tools():
        schema = tool.input_schema
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        for name, prop in schema["properties"].items():
            assert not any(w in name.lower() for w in ("path", "file", "dir", "ref")), name
            assert prop["description"]
        for node in _nodes(schema):
            if node.get("type") == "string":
                assert "enum" in node, (tool.name, node)


def test_an_empty_domain_leaves_no_empty_enum() -> None:
    ctx = MeasureContext(load_task("tray"), {}, frozenset())
    assert param_schema("runs", ctx) == {"description": param_schema("runs", ctx)["description"],
                                         "type": "string", "enum": ["all"]}
    assert param_schema("run", ctx)["not"] == {}
    assert param_schema("levels", ctx)["enum"] == ["all"]
    assert param_schema("pairs", ctx)["enum"] == ["all"]
    with pytest.raises(ValueError, match="nope"):
        param_schema("nope", ctx)


@pytest.mark.parametrize("params", [
    {"runs": ["C_70", "NOPE"]},
    {"runs": "all", "extra": 1},
    {},
    {"runs": "C_70"},
], ids=["unknown-run", "unknown-param", "missing-param", "not-a-list"])
def test_out_of_domain_params_are_refused_and_write_nothing(
        session: ToolSession, params: dict[str, Any]) -> None:
    session.call("task_lookup", {})
    before = len(session.book.facts)
    outcome = session.call("step_pass_table", params)
    assert outcome.status == "refused" and outcome.is_error
    assert list(outcome.problems) == check_params(REGISTRY["step_pass_table"], params,
                                                  session.ctx)
    assert outcome.problems and outcome.facts == () and outcome.rows == ()
    assert len(session.book.facts) == before
    assert outcome.payload()["problems"] == list(outcome.problems)


def _measured(opened: tuple[Pack, Admitted], tmp_path: Path, call: dict[str, Any]
              ) -> tuple[list[dict[str, Any]], str, list[str], str | None]:
    """Facts, status, not_judged and table text of one call run by step B2."""
    plan = tmp_path / "one.yaml"
    plan.write_text(yaml.safe_dump({"task_id": "tray", "calls": [call]}))
    out = tmp_path / "measured"
    result = measure(*opened, plan, out)
    record = result.calls[0]
    by_id = {f.fact_id: f for f in result.facts}
    facts = [{"fact_id": i, "name": by_id[i].name, "value": by_id[i].value,
              "unit": by_id[i].unit, "source_ref": by_id[i].source_ref}
             for i in record.fact_ids]
    table = out / "tables" / f"T1-{call['tool']}.json"
    return (facts, record.status, list(record.not_judged),
            table.read_text() if table.exists() else None)


@pytest.mark.parametrize("call", PLAN_CALLS, ids=[c["tool"] for c in PLAN_CALLS])
def test_a_call_gives_the_facts_of_the_round_measure_step(
        opened: tuple[Pack, Admitted], tmp_path: Path, call: dict[str, Any]) -> None:
    facts, status, reasons, table = _measured(opened, tmp_path, call)
    outcome = ToolSession.from_admitted(*opened).call(call["tool"], call["params"])
    assert outcome.status == status
    assert [{"fact_id": f.fact_id, "name": f.name, "value": f.value, "unit": f.unit,
             "source_ref": f.source_ref} for f in outcome.facts] == facts
    assert list(outcome.not_judged) == reasons
    if table is None:
        assert outcome.rows == ()
    else:
        assert json.dumps([dict(r) for r in outcome.rows], indent=2) + "\n" == table
    json.dumps(outcome.payload(), allow_nan=False)


def test_the_plan_covers_ran_and_skipped_calls(session: ToolSession) -> None:
    statuses = {c["tool"]: session.call(c["tool"], c["params"]).status for c in PLAN_CALLS}
    assert statuses["paired_compare"] == "ran" and statuses["trace_stats"] == "skipped"
    assert set(statuses.values()) == {"ran", "skipped"}


def test_the_same_call_twice_gives_the_same_facts(session: ToolSession) -> None:
    params = {"pairs": [["C_70", "B_70"]], "levels": [1]}
    first = session.call("paired_compare", params)
    size = len(session.book.facts)
    second = session.call("paired_compare", params)
    assert first.facts and second.facts == first.facts and second.fact_ids == first.fact_ids
    assert len(session.book.facts) == size
    skipped = session.call("trace_stats", {"runs": "all"})
    again = session.call("trace_stats", {"runs": ["C_70"]})
    assert skipped.status == again.status == "skipped" and again.facts == skipped.facts


def test_an_unknown_tool_raises(session: ToolSession) -> None:
    with pytest.raises(UnknownTool):
        session.call("read_file", {"path": "/etc/passwd"})
    with pytest.raises(KeyError):
        session.call("nope", {})


def test_payload_is_strict_json() -> None:
    fact = AgentFact(fact_id="F1", name="x_ratio", value="nan", unit="", source_ref="a.jsonl")
    outcome = CallOutcome("step_pass_table", 1, {"runs": "all"}, "ran", facts=(fact,),
                          rows=({"run": "C_70", "ratio": float("nan"), "n": 3,
                                 "inf": float("inf")},))
    payload = outcome.payload()
    text = json.dumps(payload, allow_nan=False)
    assert json.loads(text) == payload
    assert payload["rows"] == [{"run": "C_70", "ratio": "nan", "n": 3, "inf": "inf"}]
    assert payload["facts"] == [{"fact_id": "F1", "name": "x_ratio", "value": "nan",
                                 "unit": "", "source_ref": "a.jsonl"}]
    assert set(payload) == {"tool", "version", "status", "problems", "facts", "rows",
                            "not_judged"}
    assert not outcome.is_error and outcome.fact_ids == ("F1",)


def _window(steps_by_job: dict[str, list[int]]) -> dict[str, Any]:
    jobs = {job: job_of(job, [metric(job, s, 1.0) for s in steps])
            for job, steps in steps_by_job.items()}
    ctx = MeasureContext(load_task("tray"), {}, frozenset({"metrics"}), jobs=jobs)
    session = ToolSession(ctx)
    props: dict[str, Any] = {t.name: t for t in session.tools()}["train_window"].input_schema[
        "properties"]
    return props


def test_window_enumerates_few_steps() -> None:
    props = _window({"j1": [10, 20, 30], "j2": [5, 20]})
    assert props["jobs"]["anyOf"][1]["items"]["enum"] == ["j1", "j2"]
    window = props["window"]["anyOf"]
    assert window == [{"type": "string", "enum": ["all", "last"]},
                      {"type": "integer", "enum": [5, 10, 20, 30]}]


def test_window_bounds_many_steps() -> None:
    props = _window({"j1": list(range(1, MAX_STEP_ENUM + 2))})
    integer = props["window"]["anyOf"][1]
    assert integer["type"] == "integer" and "enum" not in integer
    assert (integer["minimum"], integer["maximum"]) == (1, MAX_STEP_ENUM + 1)
    assert "logged step" in integer["description"]


def test_every_registered_tool_and_domain_is_written_up() -> None:
    """A tool or a domain added to the registry fails here, not when a server starts."""
    assert set(DESCRIPTIONS) == set(REGISTRY)
    domains = {d for spec in REGISTRY.values() for d in spec.params.values()}
    assert domains <= set(bridge.DOMAIN_SCHEMAS)
    assert set(bridge.DOMAIN_SCHEMAS) == set(bridge._PARAM_HELP)


def test_a_tool_without_a_text_is_still_described() -> None:
    spec = dataclasses.replace(REGISTRY["lineage"], name="new_tool", version=4)
    assert bridge.describe(spec) == "new_tool (version 4)."
    assert bridge.describe(REGISTRY["lineage"]) == DESCRIPTIONS["lineage"]
