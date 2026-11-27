"""An MCP server on stdio for the analysis tools of Agent QA/QC (DA-49 task 2.2).

JSON-RPC 2.0, one message per line, on top of `bridge.ToolSession`. It serves the tools
part of MCP only: `initialize`, `ping`, `tools/list` and `tools/call`. The protocol is
pinned to revision 2025-11-25, the last one that has `initialize` and `ping`:

- https://modelcontextprotocol.io/specification/2025-11-25/basic
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination

Stdout carries protocol messages and nothing else; the server never prints. A message
without `id` is a notification and gets no answer, whatever it says. Parameters outside
their closed domain are a tool execution error (`isError: true`) and run nothing; so is a
tool that raises (the tools page, Error Handling: such errors go in the result so the
model can correct its call), while -32603 is kept for a failure outside a tool.

Every line written, to stdout and to the call log, is pure ASCII (`ensure_ascii`): a lone
surrogate a client sent (`"\\ud800"`) is echoed escaped and can never fail an encoder.
Input is read as bytes and decoded line by line, so a line that is not UTF-8 is a parse
error (-32700) and the lines around it are served as usual.

The server only opens a pack that `admit` confirms `public`, with the same check the
model gateway applies before a hosted model (`hosted_refusal`): the server cannot know
whether the model behind the chat shell is hosted. Nothing bypasses this check.

DA-54: with `--record <dir>` it also serves the record tools of `records.py`
(`hypothesis_propose`, `hypothesis_drop`, `answer_submit`) and writes the analysis calls'
facts and the accepted records into `<dir>`. Without it nothing differs from DA-49.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, TextIO

import yaml
from flywheel.eval.agentqa.mcp.bridge import CallOutcome, ToolSession, UnknownTool
from flywheel.eval.agentqa.mcp.records import (
    INSTRUCTIONS as RECORD_INSTRUCTIONS,
)
from flywheel.eval.agentqa.mcp.records import (
    RECORD_TOOLS,
    Recorder,
    RecordRefused,
)
from flywheel.eval.agentqa.round.admit import admit
from flywheel.eval.agentqa.round.gateway import hosted_refusal
from flywheel.eval.agentqa.round.measure import PlanRefused
from flywheel.eval.agentqa.round.pack import PackRefused, read_pack
from flywheel.eval.agentqa.round.records import Admission
from flywheel.eval.agentqa.round.version import agent_version

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "flywheel-agentqa"
CallLog = Callable[[dict[str, Any]], None]
LOG_HELP = "append one JSON line per tool call here (default: stderr)"
RECORD_HELP = ("also serve the record tools (hypothesis_propose, hypothesis_drop, "
               "answer_submit) and write the facts and accepted records into this directory")

INSTRUCTIONS = (
    "These tools compute facts about one admitted eval round pack; every number in an "
    "answer must come from a fact a tool returned, cited by its fact id (F1, F2, ...). "
    "The tools only read that one pack and take no file paths. A tool whose data the pack "
    "lacks returns a not-judged fact that says why, never a guess."
)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

Id = str | int | None
BOM = "\ufeff"


class PackNotPublic(ValueError):
    """The pack is not confirmed `public`, so no chat shell may be served from it."""


class _Reply(Exception):
    """A protocol error to answer with (raised inside a request handler)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _usable_id(value: object) -> bool:
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _server_version() -> str:
    try:
        return agent_version() or "0"
    except (OSError, yaml.YAMLError):
        return "0"


def _first_line(error: BaseException) -> str:
    text = str(error).strip()
    return text.splitlines()[0][:200] if text else ""


class McpServer:
    """Answers MCP messages line by line for one `ToolSession`."""

    def __init__(self, session: ToolSession, *, log: CallLog | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 now: Callable[[], datetime] = _now,
                 recorder: Recorder | None = None) -> None:
        self._session = session if recorder is None else recorder.session
        self._recorder = recorder
        self._log = log
        self._clock = clock
        self._now = now

    # -- framing ---------------------------------------------------------------------

    @staticmethod
    def _line(message: dict[str, Any]) -> str:
        text = json.dumps(message, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        if "\n" in text:  # json.dumps escapes newlines in strings; this cannot happen
            raise ValueError("a message would hold a newline")
        return text

    def _error(self, id_: Id, code: int, message: str) -> str:
        return self._line({"jsonrpc": "2.0", "id": id_,
                           "error": {"code": code, "message": message}})

    def handle_line(self, line: str | bytes) -> str | None:
        """One input line -> one output line (no trailing newline), or None. Never raises.

        `line` may be the raw bytes of the stream: they are decoded as strict UTF-8 here,
        so a line that is not UTF-8 is answered with a parse error like any other garbage.
        A byte order mark before the message is skipped; a trailing CR LF is whitespace.
        """
        try:
            text = line.decode("utf-8") if isinstance(line, bytes) else line
        except UnicodeDecodeError:
            return self._error(None, PARSE_ERROR, "Parse error")
        text = text.removeprefix(BOM)
        if not text.strip():
            return None
        try:
            message = json.loads(text, parse_constant=_reject_constant)
        except ValueError:  # JSONDecodeError, a NaN or Infinity token
            return self._error(None, PARSE_ERROR, "Parse error")
        if not isinstance(message, dict):  # an array is a batch: not in this revision
            return self._error(None, INVALID_REQUEST, "Invalid Request")
        if "method" not in message:
            if "result" in message or "error" in message:
                return None  # a response to a request we never sent
            id_ = message.get("id")
            return self._error(id_ if _usable_id(id_) else None, INVALID_REQUEST,
                               "Invalid Request")
        if "id" not in message:
            return None  # a notification: never answered, nothing runs
        id_ = message["id"]
        if not _usable_id(id_):
            return self._error(None, INVALID_REQUEST, "Invalid Request")
        method = message["method"]
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self._error(id_, INVALID_REQUEST, "Invalid Request")
        try:
            result = self._dispatch(method, message.get("params"))
            return self._line({"jsonrpc": "2.0", "id": id_, "result": result})
        except _Reply as reply:
            return self._error(id_, reply.code, reply.message)
        except Exception as error:  # noqa: BLE001  (the server answers and goes on)
            return self._error(id_, INTERNAL_ERROR, f"Internal error: {type(error).__name__}")

    def serve(self, lines: Iterable[str] | Iterable[bytes], out: TextIO) -> bool:
        """Answer every line until EOF; False when the reader closed `out` (loop ended)."""
        for line in lines:
            reply = self.handle_line(line)
            if reply is None:
                continue
            try:
                out.write(reply + "\n")
                out.flush()
            except BrokenPipeError:
                return False
        return True

    # -- methods ---------------------------------------------------------------------

    def _dispatch(self, method: str, params: object) -> dict[str, Any]:
        if params is not None and not isinstance(params, dict):
            raise _Reply(INVALID_PARAMS, "Invalid params: params must be an object")
        given: dict[str, Any] = params or {}
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,  # the one version this server speaks
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": _server_version()},
                "instructions": INSTRUCTIONS + (
                    "" if self._recorder is None else RECORD_INSTRUCTIONS),
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            if given.get("cursor") is not None:
                raise _Reply(INVALID_PARAMS, "Invalid cursor")  # one page, no cursor issued
            tools = [{"name": t.name, "description": t.description,
                      "inputSchema": t.input_schema} for t in self._session.tools()]
            if self._recorder is not None:
                tools += self._recorder.tools()
            return {"tools": tools}
        if method == "tools/call":
            return self._call(given)
        raise _Reply(METHOD_NOT_FOUND, f"Method not found: {method}")

    def _call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise _Reply(INVALID_PARAMS, "Invalid params: name must be a string")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise _Reply(INVALID_PARAMS, "Invalid params: arguments must be an object")
        start = self._clock()
        if self._recorder is not None and name in RECORD_TOOLS:
            recorded = self._recorder.record(name, arguments)
            self._record(name, arguments, "rejected" if recorded.is_error else "accepted",
                         recorded.cites, start)
            return recorded.result()
        call_id = ""
        try:
            if self._recorder is None:
                outcome = self._session.call(name, arguments)
            else:
                outcome, call_id = self._recorder.call(name, arguments)
        except UnknownTool:
            raise _Reply(INVALID_PARAMS, f"Unknown tool: {name}") from None
        except Exception as error:  # noqa: BLE001  (the server answers and goes on)
            # A tool execution error, not a protocol error: the 2025-11-25 tools page (Error
            # Handling, server/tools) puts those in the result with isError so the model can
            # correct its call, and a tool can raise for a combination of parameters the
            # model may change (`FactClash`). Only the type is said: no message, no path.
            self._record(name, arguments, "failed", (), start,
                         f"{type(error).__name__}: {_first_line(error)}")
            return {"content": [{"type": "text",
                                 "text": f"tool {name} failed: {type(error).__name__}"}],
                    "isError": True}
        self._record(name, arguments, outcome.status, outcome.fact_ids, start, call_id=call_id)
        return self._result(outcome)

    @staticmethod
    def _result(outcome: CallOutcome) -> dict[str, Any]:
        payload = outcome.payload()
        text = ("\n".join(outcome.problems) if outcome.is_error else
                json.dumps(payload, ensure_ascii=True, allow_nan=False))
        return {"content": [{"type": "text", "text": text}], "structuredContent": payload,
                "isError": outcome.is_error}

    def _record(self, tool: str, params: dict[str, Any], status: str,
                fact_ids: Sequence[str], start: float, error: str | None = None,
                call_id: str = "") -> None:
        if self._log is None:
            return
        record: dict[str, Any] = {
            "ts": self._now().isoformat(), "event": "call", "tool": tool, "params": params,
            "status": status, "fact_ids": list(fact_ids),
            "seconds": round(self._clock() - start, 3)}
        if error is not None:
            record["error"] = error
        if call_id:  # with --record: the tool_call_id of investigation_facts.jsonl
            record["call_id"] = call_id
        self._log(record)


@dataclass(frozen=True)
class OpenPack:
    """A pack that passed the public check: the tool session and what step B1 recorded."""

    session: ToolSession
    admission: Admission


def open_public_session(pack_path: Path) -> OpenPack:
    """read_pack + admit + the hosted check; raises PackRefused / PackNotPublic / PlanRefused."""
    pack = read_pack(pack_path)
    admitted = admit(pack_path)
    reason = hosted_refusal(admitted.admission, True)
    if reason is not None:
        raise PackNotPublic(reason)
    return OpenPack(ToolSession.from_admitted(pack, admitted), admitted.admission)


def started_record(opened: OpenPack, now: datetime | None = None) -> dict[str, Any]:
    """The first line of the log: which pack is served, its class, what admit let through.

    Listing the tools here also builds their schemas once (the `window` domain streams
    the training logs), so the first `tools/list` of the shell is answered at once.
    """
    admission = opened.admission
    return {
        "ts": (now or _now()).isoformat(), "event": "started",
        "pack_id": admission.pack_id, "pack_sha256": admission.pack_sha256,
        "data_class": admission.data_class, "tools": len(opened.session.tools()),
        "accepted": len(admission.accepted),
        "rejected": [{"ref": r.ref, "reason": r.reason} for r in admission.rejected],
        "protocol": PROTOCOL_VERSION,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m flywheel.eval.agentqa.mcp", allow_abbrev=False,
        description="Serve the Agent QA/QC tools of one public round pack over MCP on stdio.")
    parser.add_argument("--pack", type=Path, required=True, help="the pack.json of the round")
    parser.add_argument("--log", type=Path, default=None, help=LOG_HELP)
    parser.add_argument("--record", type=Path, default=None, help=RECORD_HELP)
    return parser


def _writer(stream: TextIO) -> CallLog:
    def write(record: dict[str, Any]) -> None:
        stream.write(json.dumps(record, ensure_ascii=True) + "\n")
        stream.flush()

    return write


def _drop_stdout() -> None:
    """The reader closed stdout: point it at devnull so the exit flush cannot fail.

    Without this, the reply still buffered makes the interpreter's final flush raise and
    exit 120 (the idiom of the Python docs, signal module, "Note on SIGPIPE").
    """
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (OSError, ValueError):  # no real file descriptor (an in-process runner)
        pass


def run(pack: Path, log: Path | None = None, record: Path | None = None) -> int:
    """Serve `pack` on stdin and stdout until EOF; 2 (one `error:` line) when refused.

    Shared by `python -m flywheel.eval.agentqa.mcp` and `fw agentqa mcp`. The log (the
    started record, then one record per tool call) goes to `log`, appended, or to stderr.
    `record`: the record directory (DA-54); opened only after the pack passed the public
    check, so a refused pack writes nothing there.
    """
    if hasattr(sys.stdout, "reconfigure"):  # replies are ASCII; UTF-8 is the transport's
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):  # an `error:` line may hold any path: never fail
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        opened = open_public_session(pack)
    except (PackRefused, PackNotPublic, PlanRefused, OSError) as error:
        # OSError: a config the tools read from the repo root (the task view) is missing
        print(f"error: {_first_line(error)}", file=sys.stderr)
        return 2
    recorder = None
    if record is not None:
        try:
            recorder = Recorder.open(record, opened.session, opened.admission.pack_id,
                                     opened.admission.pack_sha256)
        except (RecordRefused, OSError) as error:
            print(f"error: {_first_line(error)}", file=sys.stderr)
            return 2
        opened = OpenPack(recorder.session, opened.admission)
    log_file = None if log is None else open(  # noqa: SIM115  (open for the session)
        log, "a", encoding="utf-8", buffering=1)
    try:
        write = _writer(sys.stderr if log_file is None else log_file)
        write(started_record(opened))
        # bytes, decoded line by line in handle_line: a line that is not UTF-8 is -32700
        lines: IO[bytes] | TextIO = getattr(sys.stdin, "buffer", sys.stdin)
        if not McpServer(opened.session, log=write, recorder=recorder).serve(lines, sys.stdout):
            _drop_stdout()
    finally:
        if log_file is not None:
            log_file.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args.pack, args.log, args.record)
