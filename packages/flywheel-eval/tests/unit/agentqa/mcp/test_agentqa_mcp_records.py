"""The record tools of the MCP server (DA-54 task 2.2, AC 3 and 7).

The pack is the small outcome pack of the investigate-verify tests (one run R, twelve
successes and two place clusters, both off the successes on `offset_m`, a measure the
scorer does not threshold), declared again with a public source so that the server opens
it. `measure_compare` really runs on it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, get_args

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
from flywheel.contracts.entities import Source  # noqa: E402
from flywheel.contracts.evidence import Diagnosis, InterventionKind  # noqa: E402
from flywheel.eval.agentqa.mcp import server as mcp_server  # noqa: E402
from flywheel.eval.agentqa.mcp.records import (  # noqa: E402
    ANSWERS_FILE,
    DROPPED_FILE,
    RECORD_FILE,
    RECORD_TOOLS,
    VERDICTS_LIVE_FILE,
    Recorder,
    RecordRefused,
)
from flywheel.eval.agentqa.mcp.server import McpServer, open_public_session  # noqa: E402
from flywheel.eval.agentqa.round.investigate import INVESTIGATION_CALLS_FILE  # noqa: E402
from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS  # noqa: E402
from flywheel.eval.agentqa.round.records import (  # noqa: E402
    FactRecord,
    InvestigatedHypothesis,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.verify import (  # noqa: E402
    INVESTIGATED_FILE,
    INVESTIGATION_FACTS_FILE,
    investigated_verdict,
    verify,
)
from flywheel.eval.agentqa.tools.registry import REGISTRY  # noqa: E402
from helpers_mcp import REPO, internal, repacked  # noqa: E402
from helpers_round import SHA, isolated_store, pack_maker  # noqa: E402, F401
from test_agentqa_round_investigate_verify import small_pack  # noqa: E402

TIMEOUT_S = 120
HEAD = "R/place/L-PLACE-POSE/l1"
OFFSET = {"cluster": HEAD, "measure": "final.offset_m", "against": "successes_same_level"}
DIST = {"cluster": HEAD, "measure": "final.place_distance_m",
        "against": "successes_same_level"}
NOW = datetime(2026, 11, 27, tzinfo=timezone.utc)
TEXT_FIELDS = {("hypothesis_propose", "statement"), ("hypothesis_propose", "data_content.text"),
               ("hypothesis_propose", "first_check.text"), ("answer_submit", "text")}


def _public(declared: dict[str, Any]) -> None:
    declared["entries"].append({"path": "sources.jsonl", "kind": "sources"})
    declared["links"] = [{"source": e["path"], "target": "sources.jsonl", "relation": "data_of"}
                         for e in declared["entries"] if e["kind"] in ("scores", "outcomes")]


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    source = Source(uri="hf://psi-data", sha256=SHA, downloaded_at="2026-11-01",
                    data_class="public").model_dump_json() + "\n"
    return repacked(small_pack(tmp_path / "raw"), "public", _public, {"sources.jsonl": source})


class Shell:
    """The server in process, with a record directory."""

    def __init__(self, pack: Path, record: Path) -> None:
        opened = open_public_session(pack)
        self.recorder = Recorder.open(record, opened.session, opened.admission.pack_id,
                                      opened.admission.pack_sha256,
                                      markers=COMPARISON_MARKERS, now=lambda: NOW)
        self.records: list[dict[str, Any]] = []
        self.server = McpServer(opened.session, log=self.records.append,
                                now=lambda: NOW, recorder=self.recorder)
        self.ids = iter(range(1, 10_000))

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        id_ = next(self.ids)
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": id_, "method": method}
        if params is not None:
            message["params"] = params
        reply = self.server.handle_line(json.dumps(message))
        assert reply is not None and reply.isascii()
        answer: dict[str, Any] = json.loads(reply)
        assert answer["id"] == id_
        return answer

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self.request(
            "tools/call", {"name": name, "arguments": arguments})["result"]
        assert [c["type"] for c in result["content"]] == ["text"]
        return result

    def facts(self, arguments: dict[str, Any]) -> dict[str, str]:
        """Fact name suffix -> id, of one measure_compare call."""
        result = self.call("measure_compare", arguments)
        assert result["isError"] is False and result["structuredContent"]["status"] == "ran"
        return {f["name"].rsplit("successes_same_level", 1)[-1] or f["name"]: f["fact_id"]
                for f in result["structuredContent"]["facts"]}


@pytest.fixture
def record(tmp_path: Path) -> Path:
    return tmp_path / "record"


@pytest.fixture
def shell(pack: Path, record: Path) -> Shell:
    return Shell(pack, record)


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text().splitlines()]


def propose(support: list[str], *, cluster: str = HEAD, statement: str | None = None,
            diagnosis: str = "coverage_gap", intervention: str = "sim_s1",
            cites: list[str] | None = None) -> dict[str, Any]:
    cited = support if cites is None else cites
    return {
        "cluster": cluster,
        "statement": statement or "The cluster lies off the successes, see {"
        + support[0] + "}.",
        "diagnosis": diagnosis, "intervention": intervention, "support": support,
        "contra": [],
        "data_content": {"text": "Teleop demos placing the tray at {" + cited[0] + "}.",
                         "cites": cited[:1]},
        "first_check": {"text": "Compare the offsets again on a new eval.", "cites": []}}


# -- the tool list -----------------------------------------------------------------------------


def test_without_record_the_list_and_the_call_are_unchanged(pack: Path) -> None:
    opened = open_public_session(pack)
    server = McpServer(opened.session)
    tools = json.loads(server.handle_line(  # type: ignore[arg-type]
        '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'))["result"]["tools"]
    assert [t["name"] for t in tools] == list(REGISTRY)
    reply = json.loads(server.handle_line(json.dumps(  # type: ignore[arg-type]
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "answer_submit", "arguments": {"text": "x", "cites": []}}})))
    assert reply["error"] == {"code": -32602, "message": "Unknown tool: answer_submit"}
    init = json.loads(server.handle_line(  # type: ignore[arg-type]
        '{"jsonrpc":"2.0","id":3,"method":"initialize","params":{}}'))["result"]
    assert init["instructions"] == mcp_server.INSTRUCTIONS


def _nodes(schema: Any, where: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(schema, dict):
        yield where, schema
        for key, value in schema.get("properties", {}).items():
            yield from _nodes(value, f"{where}.{key}" if where else key)
        for key in ("items", "anyOf"):
            sub = schema.get(key)
            for value in (sub if isinstance(sub, list) else [sub] if sub else []):
                yield from _nodes(value, where)


def test_the_record_tools_are_listed_with_closed_schemas(shell: Shell) -> None:
    tools = shell.request("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == [*REGISTRY, *RECORD_TOOLS]
    record = {t["name"]: t for t in tools if t["name"] in RECORD_TOOLS}
    for name, tool in record.items():
        assert set(tool) == {"name", "description", "inputSchema"} and tool["description"]
        for where, node in _nodes(tool["inputSchema"]):
            leaf = where.rsplit(".", 1)[-1]
            assert not any(w in leaf.lower() for w in ("path", "file", "dir")), where
            assert node.get("type") not in ("number", "integer"), (name, where)
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert node["required"] == list(node["properties"])
            if node.get("type") == "string":
                closed = "enum" in node or "pattern" in node
                assert closed or (name, where) in TEXT_FIELDS, (name, where, node)
            assert node.get("enum", [None]) != []
    props = record["hypothesis_propose"]["inputSchema"]["properties"]
    assert props["cluster"]["enum"] == [HEAD, "R/place/L-PLACE-POSE/l2"]
    assert props["diagnosis"]["enum"] == list(get_args(Diagnosis))
    assert props["intervention"]["enum"] == list(get_args(InterventionKind))
    assert props["support"]["items"]["pattern"] == "^F[0-9]+$"
    drop = record["hypothesis_drop"]["inputSchema"]["properties"]
    assert drop["hypothesis"]["pattern"] == "^H[1-9][0-9]*$"
    init = shell.request("initialize", {})["result"]
    assert "answer_submit" in init["instructions"]


# -- rejections --------------------------------------------------------------------------------


def _rejections(f: dict[str, str]) -> list[tuple[str, dict[str, Any], str]]:
    sep, median = f["_separated"], f["_median"]
    good = propose([sep])
    return [
        ("hypothesis_propose", {**good, "cluster": "R/place/NOPE/l1"}, "not a cluster"),
        ("hypothesis_propose", propose(["F999"]), "were not given"),
        ("hypothesis_propose", {**good, "statement": "The cluster is 0.05 m off."},
         "writes the number"),
        ("hypothesis_propose", {**good, "statement": "It lies off, see {" + median + "}."},
         "without citing"),
        ("hypothesis_propose", {**good, "intervention": "repair_ticket"}, "is not allowed for"),
        ("hypothesis_propose", {**good, "data_content": {"text": "Collect 30 demos.",
                                                         "cites": []}}, "writes the number"),
        ("hypothesis_propose", {**good, "extra": 1}, "extra"),
        ("hypothesis_propose", {**good, "support": ["../etc/passwd"]}, "pattern"),
        ("hypothesis_drop", {"hypothesis": "H7", "refuted_by": [sep]}, "not a hypothesis"),
        ("hypothesis_drop", {"hypothesis": "H7", "refuted_by": []}, "not a hypothesis"),
        ("answer_submit", {"text": "The cluster is 0.05 m off.", "cites": []},
         "writes the number"),
        ("answer_submit", {"text": "See {" + median + "}.", "cites": []}, "without citing"),
        ("answer_submit", {"text": "See {F999}.", "cites": ["F999"]}, "not offered"),
        ("answer_submit", {"text": "   ", "cites": []}, "empty"),
        ("answer_submit", {"text": "a" * 4001, "cites": []}, "longer than"),
        ("answer_submit", {"text": "The median {" + median + "} is higher than the {"
                           + f["_members"] + "} members.", "cites": [median, f["_members"]]},
         "compares facts of different units"),
    ]


def test_each_rejection_is_a_tool_error_and_records_nothing(shell: Shell, record: Path) -> None:
    f = shell.facts(OFFSET)
    before = _snapshot(record)
    assert set(before) == {RECORD_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE}
    for name, arguments, why in _rejections(f):
        result = shell.call(name, arguments)
        assert result["isError"] is True, (name, arguments)
        assert why in result["content"][0]["text"], (why, result["content"][0]["text"])
        assert _snapshot(record) == before, (name, arguments)
    assert {r["status"] for r in shell.records[1:]} == {"rejected"}


# -- accepted records --------------------------------------------------------------------------


def test_a_proposal_on_separation_is_kept_as_verify_would_keep_it(
        shell: Shell, record: Path, tmp_path: Path) -> None:
    f = shell.facts(OFFSET)
    result = shell.call("hypothesis_propose", propose([f["_separated"]]))
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload == result["structuredContent"]
    assert payload["hypothesis"] == "H1" and payload["verdict"] == "kept"
    lines = (record / INVESTIGATED_FILE).read_text().splitlines()
    hypothesis = InvestigatedHypothesis.model_validate_json(lines[0])
    facts = [FactRecord.model_validate_json(x)
             for x in (record / INVESTIGATION_FACTS_FILE).read_text().splitlines()]
    assert {x.tool_call_id for x in facts} == {"M1"}
    again = investigated_verdict(hypothesis, {x.name: x for x in facts}, COMPARISON_MARKERS)
    live = VerdictRecord.model_validate_json((record / VERDICTS_LIVE_FILE).read_text())
    assert again == live and again.verdict == "accepted"
    copy = tmp_path / "copy"
    shutil.copytree(record, copy)
    assert verify(copy) == [live]  # the record directory goes through verify unchanged


def test_a_proposal_on_a_thresholded_measure_has_not_enough_evidence(
        shell: Shell, record: Path) -> None:
    f = shell.facts(DIST)
    result = shell.call("hypothesis_propose", propose([f["_beyond_threshold"]]))
    assert result["isError"] is False
    payload = result["structuredContent"]
    assert payload["verdict"].startswith("not enough evidence: H1: ")
    assert payload["failed_rules"] == ["evidence"]
    hypothesis = InvestigatedHypothesis.model_validate_json(
        (record / INVESTIGATED_FILE).read_text())
    facts = [FactRecord.model_validate_json(x)
             for x in (record / INVESTIGATION_FACTS_FILE).read_text().splitlines()]
    verdict = investigated_verdict(hypothesis, {x.name: x for x in facts}, COMPARISON_MARKERS)
    assert verdict.verdict == "rejected" and verdict.failed_rules == ["evidence"]


def test_a_dropped_hypothesis_leaves_the_open_ones(shell: Shell, record: Path) -> None:
    f = shell.facts(OFFSET)
    shell.call("hypothesis_propose", propose([f["_separated"]]))
    shell.call("hypothesis_propose", propose([f["_median"]]))
    dropped = shell.call("hypothesis_drop", {"hypothesis": "H1",
                                             "refuted_by": [f["_outside_total"]]})
    assert dropped["isError"] is False
    assert [h["hypothesis_id"] for h in _jsonl(record / INVESTIGATED_FILE)] == ["H2"]
    assert [d["hypothesis_id"] for d in _jsonl(record / DROPPED_FILE)] == ["H1"]
    again = shell.call("hypothesis_drop", {"hypothesis": "H1",
                                           "refuted_by": [f["_outside_total"]]})
    assert again["isError"] is True and "already dropped" in again["content"][0]["text"]
    assert len(_jsonl(record / VERDICTS_LIVE_FILE)) == 2


def test_an_answer_comes_back_with_the_numbers_filled_in_by_code(
        shell: Shell, record: Path) -> None:
    f = shell.facts(OFFSET)
    median, members = f["_median"], f["_members"]
    text = "Offset & place: the cluster's median offset is {" + median + "} over {" \
        + members + "} <members>."
    result = shell.call("answer_submit", {"text": text, "cites": [median, members]})
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["rendered"].startswith(
        "Offset & place: the cluster's median offset is 0.05 m over 6 rollouts <members>.")
    assert f"\n- {median} R_cluster_place" in payload["rendered"]
    assert payload["facts"][0] == {"id": median, "name": payload["facts"][0]["name"],
                                   "value": 0.05, "unit": "m"}
    line = _jsonl(record / ANSWERS_FILE)[0]
    assert line["text"] == text and line["rendered"] == payload["rendered"]
    assert line["answer_id"] == "A1" and line["ts"] == NOW.isoformat()
    typed = text.replace("{" + median + "}", "0.05 m")
    refused = shell.call("answer_submit", {"text": typed, "cites": [median, members]})
    assert refused["isError"] is True and "writes the number" in refused["content"][0]["text"]
    assert len(_jsonl(record / ANSWERS_FILE)) == 1


def test_a_comparison_with_a_comparison_fact_is_accepted(shell: Shell) -> None:
    f = shell.facts(OFFSET)
    text = ("The median {" + f["_median"] + "} is higher for {" + f["_members"]
            + "} members: {" + f["_separated"] + "}.")
    result = shell.call("answer_submit",
                        {"text": text, "cites": [f["_median"], f["_members"], f["_separated"]]})
    assert result["isError"] is False


# -- restart -----------------------------------------------------------------------------------


def test_a_restart_continues_the_ids(pack: Path, record: Path) -> None:
    first = Shell(pack, record)
    f = first.facts(OFFSET)
    first.call("hypothesis_propose", propose([f["_separated"]]))
    first.call("answer_submit", {"text": "See {" + f["_median"] + "}.",
                                 "cites": [f["_median"]]})
    snapshot = _snapshot(record)
    second = Shell(pack, record)
    assert _snapshot(record) == snapshot  # opening writes nothing
    assert second.facts(OFFSET) == f  # the same call gives the same ids
    g = second.facts(DIST)
    assert int(g["_separated"][1:]) > int(f["_separated"][1:])
    result = second.call("hypothesis_propose", propose([g["_separated"]]))
    assert result["structuredContent"]["hypothesis"] == "H2"
    answer = second.call("answer_submit", {"text": "See {" + f["_median"] + "}.",
                                           "cites": [f["_median"]]})
    assert answer["structuredContent"]["answer"] == "A2"
    calls = [json.loads(x)["call_id"] for x in
             (record / INVESTIGATION_CALLS_FILE).read_text().splitlines()]
    assert calls == ["M1", "M2", "M3"]
    facts = [FactRecord.model_validate_json(x)
             for x in (record / INVESTIGATION_FACTS_FILE).read_text().splitlines()]
    assert [x.fact_id for x in facts] == [f"F{k}" for k in range(1, len(facts) + 1)]
    assert second.call("hypothesis_drop", {"hypothesis": "H1",
                                           "refuted_by": [g["_median"]]})["isError"] is False


def test_a_record_of_another_pack_or_not_a_directory_is_refused(
        pack: Path, record: Path, tmp_path: Path) -> None:
    Shell(pack, record)
    other = pack_maker(tmp_path)("other")
    opened = open_public_session(other)
    with pytest.raises(RecordRefused, match="another pack"):
        Recorder.open(record, opened.session, opened.admission.pack_id,
                      opened.admission.pack_sha256)
    a_file = tmp_path / "a_file"
    a_file.write_text("")
    with pytest.raises(RecordRefused, match="not a directory"):
        Recorder.open(a_file, opened.session, opened.admission.pack_id,
                      opened.admission.pack_sha256)
    stray = tmp_path / "stray"
    stray.mkdir()
    (stray / ANSWERS_FILE).write_text("")
    with pytest.raises(RecordRefused, match="no record.json"):
        Recorder.open(stray, opened.session, opened.admission.pack_id,
                      opened.admission.pack_sha256)
    assert sorted(p.name for p in stray.iterdir()) == [ANSWERS_FILE]
    assert mcp_server.run(other, tmp_path / "log.jsonl", record) == 2


def test_a_pack_that_is_not_public_writes_nothing_with_record(
        pack: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    refused = repacked(pack, "internal", internal)
    target = tmp_path / "never"
    assert mcp_server.run(refused, tmp_path / "log.jsonl", target) == 2
    assert not target.exists()
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1 and err[0].startswith("error: ") and "internal" in err[0]


# -- as a child process ------------------------------------------------------------------------


def _child(pack: Path, record: Path, messages: list[dict[str, Any]]
           ) -> tuple[list[dict[str, Any]], str]:
    stdin = "".join(json.dumps(m) + "\n" for m in messages)
    done = subprocess.run(
        [sys.executable, "-m", "flywheel.eval.agentqa.mcp", "--pack", str(pack),
         "--record", str(record), "--log", str(record.parent / "log.jsonl")],
        input=stdin, capture_output=True, text=True, encoding="utf-8", cwd=REPO,
        timeout=TIMEOUT_S, check=False)
    assert done.returncode == 0, done.stderr
    return [json.loads(x) for x in done.stdout.splitlines()], done.stderr


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                   "clientInfo": {"name": "probe", "version": "0"}}}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}


def test_the_record_path_over_stdio_and_a_probe_changes_nothing(
        pack: Path, record: Path) -> None:
    replies, _ = _child(pack, record, [INIT, LIST])  # the harness's first, probing start
    assert len(replies[1]["result"]["tools"]) == len(REGISTRY) + len(RECORD_TOOLS)
    assert sorted(p.name for p in record.iterdir()) == [RECORD_FILE]
    replies, _ = _child(pack, record, [INIT, LIST, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "measure_compare", "arguments": OFFSET}}])
    facts = {f["name"].rsplit("_", 1)[-1]: f["fact_id"]
             for f in replies[2]["result"]["structuredContent"]["facts"]}
    replies, _ = _child(pack, record, [INIT, {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "hypothesis_propose", "arguments": propose([facts["separated"]])}}])
    result = replies[1]["result"]
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"])["verdict"] == "kept"
    snapshot = _snapshot(record)
    assert set(snapshot) == {RECORD_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE,
                             INVESTIGATED_FILE, VERDICTS_LIVE_FILE}
    _child(pack, record, [INIT, LIST])  # a probe start of a later session
    assert _snapshot(record) == snapshot
    log = [json.loads(x) for x in (record.parent / "log.jsonl").read_text().splitlines()]
    calls = [r for r in log if r["event"] == "call"]
    assert [(r["tool"], r["status"], r.get("call_id")) for r in calls] == [
        ("measure_compare", "ran", "M1"), ("hypothesis_propose", "accepted", None)]
