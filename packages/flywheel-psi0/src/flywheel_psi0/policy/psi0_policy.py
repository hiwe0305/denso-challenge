"""`PolicyAdapter` for a Psi0 checkpoint served by the author's `serve_psi0_simple` (DA-19 AC 4).

`serve` starts `serve_psi0_simple --rtc` from the Psi0 repo root in Psi0's own
environment (it asserts `load_dotenv()`, so `.env` must exist there, as for
training), waits for `/health`, and yields a `PolicyEndpoint` whose `uri` is the
server's base URL; leaving the context stops the server. `client` builds the
`RTCClient` a rollout uses against that endpoint, logging to `rtc.jsonl`.

A `CheckpointRef` names a fine-tuned Psi0 run: `checkpoints` maps its id to the run
directory (the one holding `run_config.json`, `argv.txt` and `checkpoints/`) and
the `ckpt_<step>` to serve.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts import AdapterInfo, CheckpointRef, PolicyEndpoint, PolicySpec
from flywheel.contracts.artifacts import ActionLayout
from numpy.typing import NDArray

from flywheel_psi0.policy import wire
from flywheel_psi0.policy.rtc import RTCClient, RTCLog, Transport

# The two-table data in psi-data is recorded at 50 fps (meta/info.json).
SIMPLE_HZ = 50.0
OBSERVATION_KEYS = ("observation.images.egocentric", "states")


@dataclass(frozen=True)
class ServedCheckpoint:
    run_dir: Path
    step: int | str = "latest"


def http_transport(uri: str, timeout_s: float = 60.0) -> Transport:
    """`POST {uri}/act` with a `wire.request` body; the decoded `(Ta, Da)` actions back."""

    def post(body: dict[str, Any]) -> NDArray[np.float64]:
        request = urllib.request.Request(
            f"{uri}/act",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return wire.response_actions(json.loads(response.read()))

    return post


class Psi0Policy:
    """Serve Psi0 checkpoints with the author's server and talk RTC to them."""

    def __init__(
        self,
        psi0_root: Path,
        checkpoints: Mapping[str, ServedCheckpoint],
        layout: ActionLayout,
        psi0_commit: str,
        exec_horizon: int = 30,
        hz: float = SIMPLE_HZ,
        port: int = 22085,
        python_bin: Path | None = None,
        startup_timeout_s: float = 600.0,
    ) -> None:
        self.psi0_root = psi0_root
        self.checkpoints = dict(checkpoints)
        self.layout = layout
        self.psi0_commit = psi0_commit
        self.exec_horizon = exec_horizon
        self.hz = hz
        self.port = port
        self.python_bin = python_bin or psi0_root / ".venv-psi" / "bin"
        self.startup_timeout_s = startup_timeout_s

    def info(self) -> AdapterInfo:
        return AdapterInfo(
            name="psi0-serve-simple-rtc", version=self.psi0_commit, nondeterminism=("cuda",)
        )

    def describe(self, ckpt: CheckpointRef) -> PolicySpec:
        self._served(ckpt)
        return PolicySpec(
            embodiment="g1",
            observation_keys=OBSERVATION_KEYS,
            action_schema=tuple(dim.name for dim in self.layout.dimensions),
            chunk_size=self.exec_horizon,
            hz=self.hz,
        )

    def command(self, ckpt: CheckpointRef, device: str) -> list[str]:
        served = self._served(ckpt)
        return [
            str(self.python_bin / "serve_psi0_simple"),
            "--host=127.0.0.1",
            f"--port={self.port}",
            f"--device={device}",
            "--policy=psi",
            "--rtc",
            f"--action_exec_horizon={self.exec_horizon}",
            f"--run-dir={served.run_dir}",
            f"--ckpt-step={served.step}",
        ]

    def serve(self, ckpt: CheckpointRef, device: str) -> AbstractContextManager[PolicyEndpoint]:
        return self._serving(ckpt, device)

    @contextmanager
    def _serving(self, ckpt: CheckpointRef, device: str) -> Iterator[PolicyEndpoint]:
        if not (self.psi0_root / ".env").exists():
            raise FileNotFoundError(f"{self.psi0_root}/.env missing: cp .env.sample .env")
        uri = f"http://127.0.0.1:{self.port}"
        process = subprocess.Popen(
            self.command(ckpt, device), cwd=self.psi0_root, start_new_session=True
        )
        try:
            self._wait_healthy(uri, process)
            yield PolicyEndpoint(endpoint_id=f"{ckpt.checkpoint_id}@{device}", uri=uri)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()

    def client(self, endpoint: PolicyEndpoint, job_dir: Path, job_id: str) -> RTCClient:
        """The RTC client of one rollout job, logging to `<job_dir>/rtc.jsonl`."""
        return RTCClient(
            http_transport(endpoint.uri), RTCLog(job_dir / "rtc.jsonl", job_id), hz=self.hz
        )

    def _served(self, ckpt: CheckpointRef) -> ServedCheckpoint:
        if ckpt.checkpoint_id not in self.checkpoints:
            known = sorted(self.checkpoints)
            raise KeyError(f"checkpoint {ckpt.checkpoint_id!r} not served here: {known}")
        return self.checkpoints[ckpt.checkpoint_id]

    def _wait_healthy(self, uri: str, process: subprocess.Popen[bytes]) -> None:
        deadline = time.monotonic() + self.startup_timeout_s
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"psi0 server exited with {process.returncode} while starting")
            try:
                with urllib.request.urlopen(f"{uri}/health", timeout=5) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                pass
            time.sleep(1.0)
        raise TimeoutError(f"psi0 server not healthy at {uri} after {self.startup_timeout_s} s")
