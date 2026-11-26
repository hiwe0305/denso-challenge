"""The MCP server as a child process on raw pipes (DA-49, review of PR 240).

Bytes that are not UTF-8 and lone surrogates must not end the server; a reply must leave
as soon as its request is answered, not at EOF; a reader that closes stdout must not turn
the exit into a failure. Every read has a timeout, so a hang fails instead of blocking.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Any

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
from helpers_mcp import REPO  # noqa: E402
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401

STARTUP_S = 120  # admit and the first imports
REPLY_S = 60
PAIRED = {"pairs": [["C_70", "B_70"]], "levels": [1]}


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    made: Path = pack_maker(tmp_path)()
    return made


def _start(pack: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "flywheel.eval.agentqa.mcp", "--pack", str(pack)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REPO)


def _line(message: dict[str, Any]) -> bytes:
    return json.dumps(message).encode() + b"\n"


def test_bad_bytes_and_surrogates_do_not_end_the_server(pack: Path) -> None:
    stdin = (b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
             b"\xff\xfe\n"
             b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
             b'{"jsonrpc":"2.0","id":3,"method":"\\ud800"}\n'
             b'{"jsonrpc":"2.0","id":"\\udfff","method":"ping"}\n'
             b'{"jsonrpc":"2.0","id":4,"method":"ping"}')  # the last line has no newline
    child = _start(pack)
    out, err = child.communicate(stdin, timeout=STARTUP_S)
    assert child.returncode == 0, err.decode(errors="replace")
    assert out.isascii()
    replies = [json.loads(line) for line in out.decode().splitlines()]
    assert [r["id"] for r in replies] == [1, None, 2, 3, "\udfff", 4]
    assert replies[1]["error"]["code"] == -32700
    assert replies[3]["error"] == {"code": -32601, "message": "Method not found: \ud800"}
    assert [r.get("result") for r in (replies[0], replies[2], replies[4], replies[5])] == [{}] * 4
    assert b"Traceback" not in err


class Reader:
    """The child's stdout, a line at a time, each wait bounded."""

    def __init__(self, stream: IO[bytes]) -> None:
        self.lines: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._pump, args=(stream,), daemon=True).start()

    def _pump(self, stream: IO[bytes]) -> None:
        for line in stream:
            self.lines.put(line)
        self.lines.put(b"")  # EOF

    def next(self, timeout: float) -> dict[str, Any]:
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"no reply within {timeout} s: the server holds it") from None
        assert line, "the server closed stdout"
        message: dict[str, Any] = json.loads(line)
        return message


def _one_line(stream: IO[bytes], timeout: float) -> bytes:
    """One line, read by a thread that then lets go of the stream (so it can be closed)."""
    got: queue.Queue[bytes] = queue.Queue()
    threading.Thread(target=lambda: got.put(stream.readline()), daemon=True).start()
    try:
        return got.get(timeout=timeout)
    except queue.Empty:
        raise AssertionError(f"no reply within {timeout} s") from None


def test_each_reply_leaves_before_the_next_request(pack: Path) -> None:
    child = _start(pack)
    assert child.stdin is not None and child.stdout is not None
    reader = Reader(child.stdout)

    def ask(message: dict[str, Any], timeout: float = REPLY_S) -> dict[str, Any]:
        assert child.stdin is not None
        child.stdin.write(_line(message))
        child.stdin.flush()
        return reader.next(timeout)

    try:
        first = ask({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                "clientInfo": {"name": "test", "version": "0"}}}, STARTUP_S)
        assert first["id"] == 1 and first["result"]["protocolVersion"] == "2025-11-25"
        child.stdin.write(_line({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        child.stdin.flush()
        assert ask({"jsonrpc": "2.0", "id": "p", "method": "ping"}) == {
            "jsonrpc": "2.0", "id": "p", "result": {}}  # the notification made no line
        tools = ask({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert tools["id"] == 2 and len(tools["result"]["tools"]) == 13
        call = ask({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "paired_compare", "arguments": PAIRED}})
        assert call["id"] == 3 and call["result"]["isError"] is False
        child.stdin.close()
        assert child.wait(timeout=REPLY_S) == 0
    finally:
        child.kill()
        child.wait()


def test_a_reader_that_closes_stdout_does_not_fail_the_exit(pack: Path) -> None:
    child = _start(pack)
    assert child.stdin is not None and child.stdout is not None and child.stderr is not None
    child.stdin.write(_line({"jsonrpc": "2.0", "id": 1, "method": "ping"}))
    child.stdin.flush()
    assert json.loads(_one_line(child.stdout, STARTUP_S))["id"] == 1
    child.stdout.close()  # the reader goes away; the next small reply cannot be written
    try:
        child.stdin.write(_line({"jsonrpc": "2.0", "id": 2, "method": "ping"}))
        child.stdin.flush()
        child.stdin.close()
    except BrokenPipeError:  # the server already left
        pass
    try:
        assert child.wait(timeout=REPLY_S) == 0  # not 120, the failed flush at exit
        err = child.stderr.read()
    finally:
        child.kill()
        child.wait()
    assert b"Exception ignored" not in err and b"Traceback" not in err
