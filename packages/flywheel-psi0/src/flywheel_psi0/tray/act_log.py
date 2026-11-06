"""Log every request between SIMPLE's eval client and a Psi0 server (DA-34 task 3).

`eval-decoupled-wbc` talks to one host and port; this proxy sits there, forwards each
request unchanged to the real server and appends one JSON line per request to `--log`:
time, request number, episode number (the n-th `history.reset`), the episode seed the
client sent with the reset (`flywheel_simple.tray.run`), HTTP status, latency, sizes and
the sha256 of the reply body and of each request field (image, state, history, ...).
The reply hash is what the determinism check of
docs/he/tray.md 8.5 compares: two runs of one condition got the same actions exactly
when their per-episode hash sequences match. Images are not logged (the videos hold
them).

    python -m flywheel_psi0.tray.act_log --listen 22186 --upstream 127.0.0.1:22185 \
        --log requests.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import threading
import time
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def episode_seed(body: bytes) -> tuple[bool, int | None]:
    """(is a reset, seed sent with it) of an /act body; (False, None) if it does not parse."""
    try:
        history = json.loads(body).get("history")
    except (ValueError, AttributeError):
        return False, None
    if not isinstance(history, dict) or "reset" not in history:
        return False, None
    seed = history.get("seed")
    return True, None if seed is None else int(seed)


def input_hashes(body: bytes) -> dict[str, str]:
    """sha256 (first 16 hex) of each top-level field of an /act body, to see which input moved."""
    try:
        payload = json.loads(body)
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        key: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]
        for key, value in payload.items()
    }


class ActLog:
    """Request counter, episode counter and the log file, shared by the handler threads."""

    def __init__(self, upstream: tuple[str, int], log: Path, timeout_s: float = 300.0) -> None:
        self.upstream, self.log, self.timeout_s = upstream, log, timeout_s
        self.lock = threading.Lock()
        self.requests, self.episode = 0, -1
        self.seed: int | None = None

    def forward(
        self, method: str, path: str, body: bytes, headers: dict[str, str]
    ) -> tuple[int, bytes, str]:
        conn = http.client.HTTPConnection(*self.upstream, timeout=self.timeout_s)
        try:
            conn.request(method, path, body=body or None, headers=headers)
            reply = conn.getresponse()
            return reply.status, reply.read(), reply.getheader("Content-Type", "application/json")
        finally:
            conn.close()

    def record(self, row: dict[str, Any]) -> None:
        with self.log.open("a") as f:
            f.write(json.dumps(row) + "\n")


def handler(state: ActLog) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _serve(self, method: str) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            reset, seed = episode_seed(body) if self.path == "/act" else (False, None)
            with state.lock:
                state.requests += 1
                n = state.requests
                if reset:
                    state.episode, state.seed = state.episode + 1, seed
                episode, ep_seed = state.episode, state.seed
            start = time.time()
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            try:
                status, reply, ctype = state.forward(method, self.path, body, headers)
            except OSError as exc:
                status, reply, ctype = (
                    502,
                    json.dumps({"error": str(exc)}).encode(),
                    "application/json",
                )
            latency = time.time() - start
            # Logged before the reply goes out: the client never acts on a reply the log lacks.
            state.record(
                {
                    "time": round(start, 3),
                    "n": n,
                    "method": method,
                    "path": self.path,
                    "episode": episode,
                    "seed": ep_seed,
                    "reset": reset,
                    "status": status,
                    "latency_s": round(latency, 4),
                    "bytes_in": len(body),
                    "bytes_out": len(reply),
                    "reply_sha256": hashlib.sha256(reply).hexdigest(),
                    "input_sha256": input_hashes(body) if self.path == "/act" else {},
                }
            )
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            self._serve("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._serve("POST")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass  # the JSON log is the record

    return Handler


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--upstream", required=True, help="host:port of the Psi0 server")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    host, port = args.upstream.rsplit(":", 1)
    state = ActLog((host, int(port)), args.log)
    ThreadingHTTPServer(("127.0.0.1", args.listen), handler(state)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
