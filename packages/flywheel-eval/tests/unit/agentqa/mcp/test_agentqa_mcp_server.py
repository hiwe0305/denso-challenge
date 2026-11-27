"""The MCP server on stdio (DA-49 task 2.2): in process on `handle_line`, and as a child.

The pack is the round tests' (`helpers_round.pack_maker`), imported from its directory
as `test_agentqa_mcp_bridge.py` does.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
from flywheel.eval.agentqa.mcp.bridge import ToolSession  # noqa: E402
from flywheel.eval.agentqa.mcp.server import (  # noqa: E402
    PROTOCOL_VERSION,
    SERVER_NAME,
    McpServer,
    PackNotPublic,
    _writer,
    build_parser,
    open_public_session,
)
from flywheel.eval.agentqa.round.admit import admit  # noqa: E402
from flywheel.eval.agentqa.round.pack import read_pack  # noqa: E402
from flywheel.eval.agentqa.tools.registry import REGISTRY, check_params  # noqa: E402
from helpers_mcp import REPO, internal, repacked, unlinked  # noqa: E402
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401

TIMEOUT_S = 120
PAIRED = {"pairs": [["C_70", "B_70"]], "levels": [1]}


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    made: Path = pack_maker(tmp_path)()
    return made


def _session(pack: Path) -> ToolSession:
    return ToolSession.from_admitted(read_pack(pack), admit(pack))


class Harness:
    def __init__(self, pack: Path) -> None:
        self.session = _session(pack)
        self.records: list[dict[str, Any]] = []
        ticks = iter(range(10_000))
        self.server = McpServer(self.session, log=self.records.append,
                                clock=lambda: float(next(ticks)),
                                now=lambda: datetime(2026, 11, 27, tzinfo=timezone.utc))

    def raw(self, line: str | bytes) -> dict[str, Any] | None:
        reply = self.server.handle_line(line)
        if reply is None:
            return None
        assert "\n" not in reply and reply.isascii()
        message: dict[str, Any] = json.loads(reply)
        assert message["jsonrpc"] == "2.0"
        assert ("result" in message) != ("error" in message)
        return message

    def send(self, message: dict[str, Any]) -> dict[str, Any] | None:
        return self.raw(json.dumps(message))

    def request(self, method: str, params: dict[str, Any] | None = None,
                id_: str | int = 1) -> dict[str, Any]:
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": id_, "method": method}
        if params is not None:
            message["params"] = params
        reply = self.send(message)
        assert reply is not None and reply["id"] == id_
        return reply


@pytest.fixture
def h(pack: Path) -> Harness:
    return Harness(pack)


@pytest.mark.parametrize("asked", ["2025-06-18", "2099-01-01", PROTOCOL_VERSION])
def test_initialize_answers_the_pinned_version(h: Harness, asked: str) -> None:
    result = h.request("initialize", {"protocolVersion": asked, "capabilities": {},
                                      "clientInfo": {"name": "test", "version": "0"}})["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION == "2025-11-25"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == SERVER_NAME and result["serverInfo"]["version"]
    assert "fact id" in result["instructions"]


@pytest.mark.parametrize("id_", ["abc", 7, 0, -3])
def test_ping_echoes_the_id(h: Harness, id_: str | int) -> None:
    assert h.request("ping", id_=id_)["result"] == {}


def test_tools_list_is_the_registry(h: Harness) -> None:
    tools = h.request("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == list(REGISTRY) and len(tools) == len(REGISTRY)
    for tool in tools:
        assert set(tool) == {"name", "description", "inputSchema"}
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
    assert h.request("tools/list", {"cursor": None})["result"]["tools"] == tools
    error = h.request("tools/list", {"cursor": "page2"})["error"]
    assert error["code"] == -32602 and error["message"] == "Invalid cursor"


def test_a_valid_call_returns_the_facts_of_the_bridge(h: Harness, pack: Path) -> None:
    result = h.request("tools/call", {"name": "paired_compare", "arguments": PAIRED})["result"]
    assert result["isError"] is False
    direct = _session(pack).call("paired_compare", PAIRED)
    assert result["structuredContent"] == direct.payload()
    assert [c["type"] for c in result["content"]] == ["text"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert [f["fact_id"] for f in result["structuredContent"]["facts"]] == list(direct.fact_ids)
    assert h.records == [{"ts": "2026-11-27T00:00:00+00:00", "event": "call",
                          "tool": "paired_compare",
                          "params": PAIRED, "status": "ran",
                          "fact_ids": list(direct.fact_ids), "seconds": 1.0}]


def test_arguments_may_be_left_out_and_a_skipped_tool_says_why(h: Harness) -> None:
    result = h.request("tools/call", {"name": "lineage"})["result"]
    assert result["isError"] is False and result["structuredContent"]["status"] == "ran"
    skipped = h.request("tools/call", {"name": "trace_stats",
                                       "arguments": {"runs": "all"}})["result"]
    assert skipped["isError"] is False
    assert skipped["structuredContent"]["status"] == "skipped"
    assert skipped["structuredContent"]["not_judged"] == ["no entry of kind trace in the pack"]
    assert [r["status"] for r in h.records] == ["ran", "skipped"]


def test_an_out_of_domain_call_is_a_tool_error_and_writes_nothing(h: Harness) -> None:
    arguments = {"runs": ["C_70", "NOPE"]}
    result = h.request("tools/call", {"name": "step_pass_table",
                                      "arguments": arguments})["result"]
    problems = check_params(REGISTRY["step_pass_table"], arguments, h.session.ctx)
    assert result["isError"] is True
    assert result["content"][0]["text"] == "\n".join(problems) and "NOPE" in problems[0]
    assert result["structuredContent"]["status"] == "refused"
    assert h.session.book.facts == []
    assert [(r["status"], r["fact_ids"]) for r in h.records] == [("refused", [])]


@pytest.mark.parametrize(("params", "message"), [
    ({"name": "read_file", "arguments": {"path": "/etc/passwd"}}, "Unknown tool: read_file"),
    ({"name": "lineage", "arguments": ["x"]}, "Invalid params: arguments must be an object"),
    ({"arguments": {}}, "Invalid params: name must be a string"),
    ({"name": 3}, "Invalid params: name must be a string"),
])
def test_a_malformed_call_is_a_protocol_error(h: Harness, params: dict[str, Any],
                                              message: str) -> None:
    error = h.request("tools/call", params)["error"]
    assert error == {"code": -32602, "message": message}
    assert h.records == [] and h.session.book.facts == []


def test_params_that_are_not_an_object_are_refused(h: Harness) -> None:
    reply = h.send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": ["lineage"]})
    assert reply is not None and reply["error"]["code"] == -32602


def test_a_tool_that_raises_is_a_tool_error_and_the_server_goes_on(
        h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object) -> Any:
        raise RuntimeError("broken at /some/secret/path.py\nsecond line")

    monkeypatch.setitem(REGISTRY, "lineage", dataclasses.replace(REGISTRY["lineage"], run=boom))
    result = h.request("tools/call", {"name": "lineage"}, id_=9)["result"]
    assert result == {"content": [{"type": "text", "text": "tool lineage failed: RuntimeError"}],
                      "isError": True}  # no structuredContent, no message, no path
    assert h.request("ping", id_=10)["result"] == {}
    assert h.records[0]["status"] == "failed" and h.records[0]["fact_ids"] == []
    assert h.records[0]["error"] == "RuntimeError: broken at /some/secret/path.py"


def test_an_unknown_method_is_not_found(h: Harness) -> None:
    error = h.request("resources/list")["error"]
    assert error == {"code": -32601, "message": "Method not found: resources/list"}


@pytest.mark.parametrize("line", ["{not json", "NaN", '{"jsonrpc":"2.0","id":1,"method":"ping",'
                                  '"params":{"x":NaN}}'])
def test_a_line_that_is_not_json_is_a_parse_error(h: Harness, line: str) -> None:
    reply = h.raw(line)
    assert reply == {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
    assert h.request("ping")["result"] == {}


@pytest.mark.parametrize(("message", "id_"), [
    ([{"jsonrpc": "2.0", "id": 1, "method": "ping"}], None),
    ("ping", None),
    ({"jsonrpc": "1.0", "id": 5, "method": "ping"}, 5),
    ({"id": 5, "method": "ping"}, 5),
    ({"jsonrpc": "2.0", "id": None, "method": "ping"}, None),
    ({"jsonrpc": "2.0", "id": 1.5, "method": "ping"}, None),
    ({"jsonrpc": "2.0", "id": True, "method": "ping"}, None),
    ({"jsonrpc": "2.0", "id": "s", "method": 3}, "s"),
    ({"jsonrpc": "2.0", "id": 6}, 6),
], ids=["batch", "string", "jsonrpc-1.0", "no-jsonrpc", "null-id", "float-id", "bool-id",
        "method-not-string", "no-method"])
def test_an_invalid_request(h: Harness, message: object, id_: object) -> None:
    reply = h.send(message)  # type: ignore[arg-type]
    assert reply == {"jsonrpc": "2.0", "id": id_,
                     "error": {"code": -32600, "message": "Invalid Request"}}


@pytest.mark.parametrize("message", [
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "method": "notifications/whatever", "params": {"a": 1}},
    {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "lineage"}},
    {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "nope"}},
    {"jsonrpc": "1.0", "method": 5},
    {"jsonrpc": "2.0", "id": 7, "result": {}},
    {"jsonrpc": "2.0", "id": 8, "error": {"code": -1, "message": "no"}},
], ids=["initialized", "unknown", "tools-call", "unknown-tool", "invalid", "response",
        "error-response"])
def test_notifications_and_responses_get_no_answer_and_run_nothing(
        h: Harness, message: dict[str, Any]) -> None:
    assert h.send(message) is None
    assert h.session.book.facts == [] and h.records == []


def test_blank_lines_are_skipped(h: Harness) -> None:
    assert h.raw("") is None and h.raw("   \t") is None


def test_serve_writes_one_line_per_answer(h: Harness) -> None:
    class Out:
        def __init__(self) -> None:
            self.text, self.flushes = "", 0

        def write(self, s: str) -> int:
            self.text += s
            return len(s)

        def flush(self) -> None:
            self.flushes += 1

    out = Out()
    lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n",
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n",
             "\n", json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"]
    h.server.serve(lines, out)  # type: ignore[arg-type]
    assert [json.loads(x)["id"] for x in out.text.splitlines()] == [1, 2]
    assert out.flushes == 2

    class Closed(Out):
        def write(self, s: str) -> int:
            raise BrokenPipeError

    h.server.serve(lines, Closed())  # type: ignore[arg-type]


# -- the data class -------------------------------------------------------------------


def test_only_a_confirmed_public_pack_opens(pack: Path) -> None:
    assert [t.name for t in open_public_session(pack).session.tools()] == list(REGISTRY)
    with pytest.raises(PackNotPublic, match="internal"):
        open_public_session(repacked(pack, "internal", internal))
    with pytest.raises(PackNotPublic, match="unknown"):
        open_public_session(repacked(pack, "unlinked", unlinked))


def test_the_command_has_no_option_but_pack_and_log() -> None:
    options = {o for a in build_parser()._actions for o in a.option_strings}
    assert options == {"-h", "--help", "--pack", "--log"}


# -- as a child process (AC 1) -----------------------------------------------------------


def _child(pack: Path, stdin: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "flywheel.eval.agentqa.mcp", "--pack", str(pack), *extra],
        input=stdin, capture_output=True, text=True, encoding="utf-8", cwd=REPO,
        timeout=TIMEOUT_S, check=False)


def test_the_server_answers_over_stdio(pack: Path) -> None:
    script = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "method": "notifications/unknown"},
        {"jsonrpc": "2.0", "id": "p", "method": "ping"},
        "this is not json",
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "paired_compare", "arguments": PAIRED}},
        {"jsonrpc": "2.0", "id": 4, "method": "nope/nope"},
    ]
    stdin = "".join((m if isinstance(m, str) else json.dumps(m)) + "\n" for m in script)
    done = _child(pack, stdin)
    assert done.returncode == 0, done.stderr
    assert done.stdout.endswith("\n")
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    # the two notifications made no line: the reply after initialize's is the ping's
    assert [r["id"] for r in replies] == [1, "p", None, 2, 3, 4]
    assert replies[0]["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert replies[1]["result"] == {}
    assert replies[2]["error"]["code"] == -32700
    assert len(replies[3]["result"]["tools"]) == len(REGISTRY)
    call = replies[4]["result"]
    assert call["isError"] is False and call["structuredContent"]["facts"]
    assert replies[5]["error"]["code"] == -32601
    logged = [json.loads(line) for line in done.stderr.splitlines()]
    assert [r["event"] for r in logged] == ["started", "call"]
    assert logged[0]["tools"] == len(REGISTRY) and logged[0]["data_class"] == "public"
    assert logged[1]["tool"] == "paired_compare"
    assert logged[1]["fact_ids"] == [f["fact_id"] for f in call["structuredContent"]["facts"]]


def test_the_server_refuses_a_pack_that_is_not_public(pack: Path, tmp_path: Path) -> None:
    refused = repacked(pack, "internal", internal)
    done = _child(refused, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n",
                  "--log", str(tmp_path / "calls.jsonl"))
    assert done.returncode == 2
    assert done.stdout == ""
    lines = done.stderr.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ") and "internal" in lines[0]
    assert not (tmp_path / "calls.jsonl").exists()


# -- what a client can send that is not clean (review of PR 240) -------------------------


class Utf8Sink:
    """A log stream that fails, as a UTF-8 file would, on what it cannot encode."""

    def __init__(self) -> None:
        self.text = ""

    def write(self, s: str) -> int:
        s.encode("utf-8")
        self.text += s
        return len(s)

    def flush(self) -> None:
        pass


def test_a_line_that_is_not_utf8_is_a_parse_error(h: Harness) -> None:
    assert h.raw(b"\xff\xfe\n") == {"jsonrpc": "2.0", "id": None,
                                     "error": {"code": -32700, "message": "Parse error"}}
    assert h.raw(b'{"jsonrpc":"2.0","id":1,"method":"\xc3\xa9"}\n')["error"] == {  # type: ignore[index]
        "code": -32601, "message": "Method not found: \u00e9"}
    assert h.request("ping")["result"] == {}


@pytest.mark.parametrize("line", [
    '{"jsonrpc":"2.0","id":3,"method":"ping"}\r\n',
    b'{"jsonrpc":"2.0","id":3,"method":"ping"}\r\n',
    '{"jsonrpc":"2.0","id":3,"method":"ping"}',
    b'{"jsonrpc":"2.0","id":3,"method":"ping"}',
    '\ufeff{"jsonrpc":"2.0","id":3,"method":"ping"}\n',
    b'\xef\xbb\xbf{"jsonrpc":"2.0","id":3,"method":"ping"}\n',
], ids=["crlf", "crlf-bytes", "no-newline", "no-newline-bytes", "bom", "bom-bytes"])
def test_line_ends_and_a_byte_order_mark_are_served(h: Harness, line: str | bytes) -> None:
    assert h.raw(line) == {"jsonrpc": "2.0", "id": 3, "result": {}}


def test_a_long_line_is_answered(h: Harness) -> None:
    filler = "x" * 2_000_000
    reply = h.raw(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping",
                              "params": {"pad": filler}}))
    assert reply == {"jsonrpc": "2.0", "id": 1, "result": {}}


@pytest.mark.parametrize(("line", "code"), [
    ('{"jsonrpc":"2.0","id":1,"method":"\\ud800"}', -32601),
    ('{"jsonrpc":"2.0","id":"\\ud800","method":"ping"}', None),
    ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"\\udfff"}}', -32602),
    ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"step_pass_table",'
     '"arguments":{"runs":["\\ud800"]}}}', None),
    ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"step_pass_table",'
     '"arguments":{"\\ud800":1}}}', None),
], ids=["method", "id", "tool-name", "argument-value", "argument-name"])
def test_a_lone_surrogate_is_echoed_as_ascii(h: Harness, line: str, code: int | None) -> None:
    reply = h.server.handle_line(line)
    assert reply is not None and reply.isascii()
    reply.encode("utf-8")
    message = json.loads(reply)
    if code is None:
        assert "result" in message
    else:
        assert message["error"]["code"] == code
    for record in h.records:  # as `run` writes the log, it must encode
        sink = Utf8Sink()
        _writer(sink)(record)  # type: ignore[arg-type]
        assert sink.text.isascii()
    assert h.request("ping")["result"] == {}


def test_a_refused_call_with_a_surrogate_is_logged_in_ascii(h: Harness) -> None:
    line = ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"step_pass_table",'
            '"arguments":{"runs":["\\ud800"]}}}')
    result = json.loads(h.server.handle_line(line) or "{}")["result"]
    assert result["isError"] is True and "ud800" in result["content"][0]["text"]
    assert [r["status"] for r in h.records] == ["refused"]
    assert h.records[0]["params"] == {"runs": ["\ud800"]}
