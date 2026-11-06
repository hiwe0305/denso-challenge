"""The request log between the eval client and a Psi0 server, over real HTTP on CPU (DA-34)."""

from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray.act_log import ActLog, episode_seed, handler, input_hashes


class Upstream(BaseHTTPRequestHandler):
    """Answers /act with the request's own `n`, /info with a fixed body, the rest with 404."""

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._reply(200, {"action": body["n"]})

    def do_GET(self) -> None:  # noqa: N802
        self._reply(200, {"policy": "psi0"}) if self.path == "/info" else self._reply(404, {})

    def _reply(self, status: int, value: Any) -> None:
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def serve(server: ThreadingHTTPServer) -> Iterator[int]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


@pytest.fixture
def proxy(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    for up_port in serve(upstream):
        log = tmp_path / "requests.jsonl"
        front = ThreadingHTTPServer(("127.0.0.1", 0), handler(ActLog(("127.0.0.1", up_port), log)))
        for port in serve(front):
            yield port, log


def post(port: int, payload: dict[str, Any]) -> bytes:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/act",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as reply:
        return reply.read()


def test_episode_seed_reads_the_reset_of_simples_client() -> None:
    assert episode_seed(b'{"history": {"reset": true, "seed": 1000101}}') == (True, 1000101)
    assert episode_seed(b'{"history": {"reset": true}}') == (True, None)
    assert episode_seed(b'{"history": {}}') == (False, None)
    assert episode_seed(b'{"history": null}') == (False, None)
    assert episode_seed(b"not json") == (False, None)


def test_input_hashes_show_which_field_moved() -> None:
    a = input_hashes(b'{"image": [1, 2], "state": {"q": 0.5, "v": 1}}')
    b = input_hashes(b'{"state": {"v": 1, "q": 0.5}, "image": [1, 3]}')
    assert set(a) == {"image", "state"} and all(len(h) == 16 for h in a.values())
    assert a["state"] == b["state"]  # key order does not matter
    assert a["image"] != b["image"]
    assert input_hashes(b"not json") == {} and input_hashes(b"[1, 2]") == {}


def test_every_request_is_forwarded_and_logged_with_its_episode(proxy: tuple[int, Path]) -> None:
    port, log = proxy
    replies = [
        post(port, {"n": 1, "history": {"reset": True, "seed": 1000100}}),
        post(port, {"n": 2, "history": {}}),
        post(port, {"n": 3, "history": {"reset": True, "seed": 1000101}}),
        post(port, {"n": 4, "history": {}}),
    ]
    assert [json.loads(r)["action"] for r in replies] == [1, 2, 3, 4]  # unchanged both ways
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(r["n"], r["episode"], r["seed"], r["reset"]) for r in rows] == [
        (1, 0, 1000100, True),
        (2, 0, 1000100, False),
        (3, 1, 1000101, True),
        (4, 1, 1000101, False),
    ]
    assert [r["reply_sha256"] for r in rows] == [hashlib.sha256(r).hexdigest() for r in replies]
    assert all(r["status"] == 200 and r["path"] == "/act" and r["latency_s"] >= 0 for r in rows)


def test_get_passes_through_and_errors_keep_their_status(proxy: tuple[int, Path]) -> None:
    port, log = proxy
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/info") as reply:
        assert json.loads(reply.read()) == {"policy": "psi0"}
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
    assert err.value.code == 404
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(r["method"], r["path"], r["status"], r["episode"]) for r in rows] == [
        ("GET", "/info", 200, -1),
        ("GET", "/nope", 404, -1),
    ]


def test_a_dead_upstream_is_a_logged_502(tmp_path: Path) -> None:
    log = tmp_path / "requests.jsonl"
    front = ThreadingHTTPServer(
        ("127.0.0.1", 0), handler(ActLog(("127.0.0.1", 1), log, timeout_s=2))
    )
    for port in serve(front):
        with pytest.raises(urllib.error.HTTPError) as err:
            post(port, {"n": 1, "history": {"reset": True, "seed": 5}})
        assert err.value.code == 502
    row = json.loads(log.read_text())
    assert (row["status"], row["episode"], row["seed"]) == (502, 0, 5)
