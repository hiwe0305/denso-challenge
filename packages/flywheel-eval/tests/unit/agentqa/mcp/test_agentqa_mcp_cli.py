"""`fw agentqa mcp` (DA-49 task 2.3): the command, the started record, the public check (AC 4).

Run in process with typer's `CliRunner`, which feeds stdin and keeps stdout and stderr
apart; the child-process runs are in `test_agentqa_mcp_server.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
from flywheel.eval.agentqa.cli import app  # noqa: E402
from flywheel.eval.agentqa.mcp.bridge import ToolSession  # noqa: E402
from flywheel.eval.agentqa.mcp.server import (  # noqa: E402
    PROTOCOL_VERSION,
    open_public_session,
    started_record,
)
from flywheel.eval.agentqa.round.admit import admit  # noqa: E402
from flywheel.eval.agentqa.round.pack import read_pack  # noqa: E402
from flywheel.eval.agentqa.tools.registry import REGISTRY  # noqa: E402
from helpers_mcp import NOTES, internal, repacked, unlinked, with_notes  # noqa: E402
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401

PAIRED = {"pairs": [["C_70", "B_70"]], "levels": [1]}
SCRIPT = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "paired_compare", "arguments": PAIRED}},
]
STARTED_KEYS = {"ts", "event", "pack_id", "pack_sha256", "data_class", "tools", "accepted",
                "rejected", "protocol"}
CALL_KEYS = {"ts", "event", "tool", "params", "status", "fact_ids", "seconds"}


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    made: Path = pack_maker(tmp_path)()
    return made


def _invoke(*args: str, stdin: str = "") -> Any:
    return CliRunner().invoke(app, ["mcp", *args], input=stdin)


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_the_command_serves_the_pack_and_logs_the_start_then_each_call(
        pack: Path, tmp_path: Path) -> None:
    log = tmp_path / "logs" / "mcp.log"
    log.parent.mkdir()
    stdin = "".join(json.dumps(m) + "\n" for m in SCRIPT)
    result = _invoke("--pack", str(pack), "--log", str(log), stdin=stdin)
    assert result.exit_code == 0, result.stderr
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]  # the notification made no line
    assert all(r["jsonrpc"] == "2.0" and "result" in r for r in replies)
    assert len(replies[1]["result"]["tools"]) == len(REGISTRY)
    call = replies[2]["result"]
    assert call["isError"] is False
    direct = ToolSession.from_admitted(read_pack(pack), admit(pack)).call("paired_compare",
                                                                          PAIRED)
    assert call["structuredContent"] == direct.payload()
    assert result.stderr == ""  # the log went to the file
    started, logged = _records(log)
    assert set(started) == STARTED_KEYS and started["event"] == "started"
    assert set(logged) == CALL_KEYS and logged["event"] == "call"
    assert logged["tool"] == "paired_compare" and logged["params"] == PAIRED
    assert logged["status"] == "ran" and logged["fact_ids"] == list(direct.fact_ids)


def test_without_log_the_records_go_to_stderr(pack: Path) -> None:
    ping = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
    result = _invoke("--pack", str(pack), stdin=ping)
    assert result.exit_code == 0
    assert [json.loads(x)["id"] for x in result.stdout.splitlines()] == [1]
    assert [json.loads(x)["event"] for x in result.stderr.splitlines()] == ["started"]


@pytest.mark.parametrize(("edit", "word"), [(internal, "internal"), (unlinked, "unknown")],
                         ids=["internal", "unconfirmed"])
def test_a_pack_not_confirmed_public_is_refused(
        pack: Path, tmp_path: Path, edit: Any, word: str) -> None:
    refused = repacked(pack, "refused", edit)
    log = tmp_path / "mcp.log"
    ping = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
    result = _invoke("--pack", str(refused), "--log", str(log), stdin=ping)
    assert result.exit_code == 2
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ") and word in lines[0]
    assert not log.exists()


def test_a_missing_pack_is_one_error_line(tmp_path: Path) -> None:
    log = tmp_path / "mcp.log"
    result = _invoke("--pack", str(tmp_path / "nope.json"), "--log", str(log))
    assert result.exit_code == 2 and result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ") and "nope.json" in lines[0]
    assert "Traceback" not in result.stderr and not log.exists()


def test_the_command_has_no_option_but_pack_log_and_record() -> None:
    group = typer.main.get_command(app)
    assert isinstance(group, typer.core.TyperGroup)
    command = group.commands["mcp"]
    options = {o for p in command.params for o in p.opts}
    assert options == {"--pack", "--log", "--record"}  # --record: DA-54
    pack_option = next(p for p in command.params if "--pack" in p.opts)
    assert pack_option.required


def test_the_started_record_names_the_pack_and_what_admit_let_through(pack: Path) -> None:
    opened = open_public_session(pack)
    record = started_record(opened)
    admission = opened.admission
    assert set(record) == STARTED_KEYS
    assert record["event"] == "started" and record["protocol"] == PROTOCOL_VERSION == "2025-11-25"
    assert record["pack_id"] == read_pack(pack).pack_id == admission.pack_id
    assert record["pack_sha256"] == admission.pack_sha256 and len(record["pack_sha256"]) == 64
    assert record["data_class"] == "public"
    assert record["tools"] == len(REGISTRY)
    assert record["accepted"] == 5  # sources.jsonl and the scores of four runs
    assert record["rejected"] == []
    json.dumps(record, allow_nan=False)


def test_the_started_record_lists_what_admit_rejected(pack: Path) -> None:
    noted = repacked(pack, "noted", with_notes, files={NOTES: "free text\n"})
    record = started_record(open_public_session(noted))
    assert record["accepted"] == 5 and record["data_class"] == "public"
    assert [r["ref"] for r in record["rejected"]] == [NOTES]
    assert record["rejected"][0]["reason"].startswith("kind notes has no contract here")
