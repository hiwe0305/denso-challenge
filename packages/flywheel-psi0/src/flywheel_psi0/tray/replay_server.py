"""A stand-in Psi0 server that answers with recorded actions: the eval replay gate (DA-34).

SIMPLE's `eval-decoupled-wbc` with policy `psi0_decoupled_wbc` sends observations to a
Psi0 server over HTTP (`POST /act`) and unpacks each returned 36-dim action into WBC
goals. This server ignores the observation and returns the next `chunk` frames of a
release episode's exported `action` column, the target Psi0 is trained on. Replaying
S1 episodes through the eval client this way checks, before any fine-tune, that the
export layout, the agent's unpacking, the scene rebuilt from `environment_config` and
the scorer agree: an episode the planner solved must still succeed (review of PR #73,
point 3).

The wire format mirrors `simple.baselines.client` (numpy arrays as base64 with dtype
and shape) without importing SIMPLE. SIMPLE writes the dtype with numpy's
`dtype_to_descr`, which for the unstructured dtypes it sends is `dtype.str` ("<f4",
"|u1"); `np.dtype` reads that back. A request whose `history` has `reset` starts the
next episode of the queue; after the last recorded frame the last action is held.

    python -m flywheel_psi0.tray.replay_server --release <release dir> \
        --seed 1003 --seed 1003 --port 22190 --log requests.jsonl
"""

from __future__ import annotations

import argparse
import json
import threading
from base64 import b64decode, b64encode
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_psi0.tray.demo_sets import EXPORT_META

CHUNK = 24  # = action_exec_horizon of the Psi0 SIMPLE server


def encode(value: Any) -> Any:
    """JSON form of nested dicts and lists with numpy arrays, as SIMPLE's client sends."""
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, (np.ndarray, np.generic)):
        array = np.asarray(value)  # keeps a scalar 0-d; tobytes() is C order
        return {
            "__numpy__": b64encode(array.tobytes()).decode(),
            "dtype": array.dtype.str,  # = SIMPLE's dtype_to_descr for unstructured dtypes
            "shape": list(array.shape),
        }
    return value


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        if "__numpy__" in value:
            flat = np.frombuffer(b64decode(value["__numpy__"]), np.dtype(value["dtype"]))
            return flat.reshape(value["shape"]) if value["shape"] else flat[0]
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def release_actions(release: Path, seed: int) -> NDArray[np.float32]:
    """The exported (T, 36) `action` of the release episode recorded with this seed."""
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    rows = json.loads((release / EXPORT_META).read_text(encoding="utf-8"))["episodes"]
    index = next((r["episode_index"] for r in rows if r["seed"] == seed), None)
    if index is None:
        raise ValueError(f"seed {seed} is not in {release}")
    path = release / "data" / f"chunk-{index // 1000:03d}" / f"episode_{index:06d}.parquet"
    column = pq.read_table(path, columns=["action"]).column("action").to_pylist()
    return np.asarray(column, dtype=np.float32)


class Replay:
    """The queue of episodes to serve and the position in the current one."""

    def __init__(self, episodes: Sequence[NDArray[np.float32]], chunk: int = CHUNK) -> None:
        self.episodes = list(episodes)
        self.chunk = chunk
        self.current = -1
        self.position = 0
        self.lock = threading.Lock()

    def act(self, request: dict[str, Any]) -> tuple[NDArray[np.float32], dict[str, Any]]:
        with self.lock:
            if (request.get("history") or {}).get("reset"):
                self.current += 1
                self.position = 0
            if not 0 <= self.current < len(self.episodes):
                raise IndexError(f"no episode {self.current} in a queue of {len(self.episodes)}")
            actions = self.episodes[self.current]
            take = np.arange(self.position, self.position + self.chunk)
            out = actions[np.minimum(take, len(actions) - 1)]  # hold the last frame
            record = {"episode": self.current, "start": self.position, "frames": len(actions)}
            self.position += self.chunk
            return out, record


def make_server(replay: Replay, port: int, log: Path | None = None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: Any) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            self._send({"policy": "replay", "timestamp": "release-actions"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            request = decode(json.loads(self.rfile.read(length)))
            try:
                action, record = replay.act(request)
            except IndexError as error:
                self.send_error(500, str(error))
                return
            if log is not None:
                with log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            empty = np.zeros((1, 1, 3), dtype=np.uint8)
            self._send(encode({"action": action, "err": 0.0, "traj_image": empty}))

        def log_message(self, *args: Any) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--seed", type=int, action="append", required=True, help="in eval order")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--chunk", type=int, default=CHUNK)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args(argv)
    replay = Replay([release_actions(args.release, s) for s in args.seed], args.chunk)
    print(f"serving {len(replay.episodes)} episodes on 127.0.0.1:{args.port}", flush=True)
    make_server(replay, args.port, args.log).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
