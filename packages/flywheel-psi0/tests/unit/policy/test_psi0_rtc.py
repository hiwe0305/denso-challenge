"""The RTC client and its inference log, against a fake delayed Psi0 server (DA-19 AC 4).

`fake_server` stands where the author's `serve_psi0_simple` would: an executable
answering `/health` and `/act` over real HTTP with the same wire format, sleeping
`--latency` seconds per request and returning a ramp so chunk boundaries jump by a
known amount. Nothing here needs torch or psi.
"""

from __future__ import annotations

import base64
import itertools
import json
import socket
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts import CheckpointRef
from flywheel.contracts.artifacts import ActionDimension, ActionLayout, RTCInferenceRecord
from flywheel.contracts.protocols import PolicyAdapter
from flywheel_psi0.policy import Psi0Policy, RTCClient, RTCLog, ServedCheckpoint, wire
from numpy.typing import NDArray

DIMS, TA = 4, 30

FAKE_SERVER = r'''#!{python}
"""A stand-in for serve_psi0_simple: same routes, same wire format, a fixed latency."""
import argparse, base64, json, time
from http.server import BaseHTTPRequestHandler, HTTPServer
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int)
parser.add_argument("--action_exec_horizon", type=int)
args, _ = parser.parse_known_args()
LATENCY, DIMS, served = {latency}, {dims}, []

def encode(a):
    a = np.ascontiguousarray(a)
    return {{"__numpy__": base64.b64encode(a.tobytes()).decode(),
            "dtype": np.lib.format.dtype_to_descr(a.dtype), "shape": list(a.shape)}}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply({{"status": "ok"}})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(LATENCY)
        history = body["history"]
        start = 0 if history.get("reset") else len(served) * args.action_exec_horizon
        served.append(history)
        ramp = start + np.arange(args.action_exec_horizon, dtype=np.float32)
        actions = np.repeat(ramp[:, None], DIMS, axis=1) * 0.01
        actions[0] += 0.5  # every chunk starts 0.5 off the ramp: a known boundary jump
        image = encode(np.zeros((1, 1, 3), np.uint8))
        self.reply({{"action": encode(actions), "err": 0.0, "traj_image": image}})

HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
'''


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def layout() -> ActionLayout:
    return ActionLayout(
        dimensions=[ActionDimension(name=f"d{i}", group="arm", masked=False) for i in range(DIMS)]
    )


@pytest.fixture
def fake_psi0(tmp_path: Path) -> Path:
    root = tmp_path / "Psi0"
    bin_dir = root / ".venv-psi" / "bin"
    bin_dir.mkdir(parents=True)
    server = bin_dir / "serve_psi0_simple"
    server.write_text(FAKE_SERVER.format(python=sys.executable, latency=0.05, dims=DIMS))
    server.chmod(server.stat().st_mode | stat.S_IXUSR)
    (root / ".env").write_text("")
    return root


def policy(root: Path) -> Psi0Policy:
    return Psi0Policy(
        root,
        {"psi0-s3-smoke": ServedCheckpoint(run_dir=Path("/runs/smoke"), step=60)},
        layout(),
        psi0_commit="cda3fdf",
        exec_horizon=TA,
        port=free_port(),
        startup_timeout_s=30,
    )


def observe(trace_id: str) -> Callable[[bool], dict[str, Any]]:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    return lambda reset: wire.request(
        {"observation.images.egocentric": image},
        np.zeros(32, dtype=np.float32),
        "Pick the box and place it on the other table",
        session_id=trace_id,
        reset=reset,
    )


def read(path: Path) -> list[RTCInferenceRecord]:
    return [RTCInferenceRecord.model_validate_json(x) for x in path.read_text().splitlines()]


def test_wire_matches_the_psi_helpers_format() -> None:
    array = np.arange(6, dtype=np.float32).reshape(2, 3)
    encoded = wire.encode({"a": array, "s": np.float64(2.5), "text": "x"})

    assert encoded["a"] == {
        "__numpy__": base64.b64encode(array.tobytes()).decode(),
        "dtype": "<f4",
        "shape": [2, 3],
    }
    decoded = wire.decode(json.loads(json.dumps(encoded)))
    assert np.array_equal(decoded["a"], array) and decoded["s"] == 2.5 and decoded["text"] == "x"


def test_request_carries_the_session_and_reset() -> None:
    first = wire.request({}, np.zeros(3), "go", session_id="trace-7", reset=True)
    later = wire.request({}, np.zeros(3), "go", session_id="trace-7")

    assert first["history"] == {"session_id": "trace-7", "reset": True}
    assert later["history"] == {"session_id": "trace-7"}
    assert first["state"]["states"]["shape"] == [1, 3]


def test_server_error_string_raises() -> None:
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        wire.response_actions('{"status": "CUDA out of memory"}')


def test_delayed_policy_logs_one_valid_record_per_chunk(tmp_path: Path) -> None:
    ticks = itertools.count()
    clock = lambda: next(ticks) * 0.025  # noqa: E731 - each call is 25 ms later
    chunk = np.arange(TA * DIMS, dtype=np.float64).reshape(TA, DIMS)

    def transport(body: dict[str, Any]) -> NDArray[np.float64]:
        return chunk.copy()

    log = RTCLog(tmp_path / "rtc.jsonl", "job-rtc")
    client = RTCClient(transport, log, hz=50.0, clock=clock)
    client.reset("trace-1")
    for _ in range(2 * TA + 1):
        client.act(observe("trace-1"))

    records = read(tmp_path / "rtc.jsonl")
    assert [r.chunk_index for r in records] == [0, 1, 2]
    assert {r.trace_id for r in records} == {"trace-1"} and records[0].job_id == "job-rtc"
    # sent and received are consecutive clock reads: 25 ms at 50 Hz is 1.25 -> 2 steps
    assert {r.delay_steps for r in records} == {2}
    assert all(r.chunk_received_s > r.observation_sent_s for r in records)
    assert {r.buffer_level for r in records} == {0}
    assert records[0].boundary_jump == 0.0  # nothing executed before the first chunk
    assert records[1].boundary_jump == pytest.approx(float(np.max(np.abs(chunk[0] - chunk[-1]))))


def test_act_before_reset_is_refused(tmp_path: Path) -> None:
    client = RTCClient(lambda body: np.zeros((1, 1)), RTCLog(tmp_path / "rtc.jsonl", "j"), hz=50)
    with pytest.raises(RuntimeError, match="reset"):
        client.act(observe("t"))


def test_psi0_policy_serves_and_logs_rtc_over_http(fake_psi0: Path, tmp_path: Path) -> None:
    psi0 = policy(fake_psi0)
    assert isinstance(psi0, PolicyAdapter)
    ckpt = CheckpointRef(checkpoint_id="psi0-s3-smoke")
    assert psi0.describe(ckpt).chunk_size == TA and psi0.describe(ckpt).hz == 50.0
    assert "--rtc" in psi0.command(ckpt, "cuda:0")

    with psi0.serve(ckpt, "cuda:0") as endpoint:
        assert endpoint.uri.startswith("http://127.0.0.1:")
        client = psi0.client(endpoint, tmp_path / "job", "job-http")
        client.reset("trace-http")
        actions = [client.act(observe("trace-http")) for _ in range(2 * TA)]

    records = read(tmp_path / "job" / "rtc.jsonl")
    assert [r.chunk_index for r in records] == [0, 1]
    # 50 ms of server latency at 50 Hz: at least 3 control steps (2.5, rounded up)
    assert all(r.delay_steps >= 3 for r in records)
    # The fake starts each chunk 0.5 off its ramp: last of chunk 0 is 0.29, first of 1 is 0.80
    assert records[1].boundary_jump == pytest.approx(0.51, abs=1e-5)
    assert actions[TA][0] == pytest.approx(0.80, abs=1e-5)


def test_unknown_checkpoint_is_refused(fake_psi0: Path) -> None:
    with pytest.raises(KeyError, match="nope"):
        policy(fake_psi0).describe(CheckpointRef(checkpoint_id="nope"))
