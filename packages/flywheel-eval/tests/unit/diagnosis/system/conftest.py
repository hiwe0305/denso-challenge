"""Synthetic traces for the F-SYS checks (DA-13 AC 6).

Every trace here is built in the test, not recorded: the real `Trace` of SIMPLE
arrives with the `SimpleSim` hook around 8/11/2026 and the checks must be
testable on CPU before then (story, dependencies). The field names are those of
`TraceStep` in Contract change #31, so a trace written by the hook reads
without changing a test.

`clean_rows` is the control: a trace that tracks its commands, answers in time,
keeps its timestamps together and carries every field. Each fault fixture is
that same trace with one thing wrong, so a check that fires on a fault and not
on the control is a check that caught the fault and not the fixture.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from flywheel.eval.diagnosis.system.reader import SystemInputs, read_trace_log

Row = Callable[..., dict[str, Any]]
Rows = Callable[..., Path]
Inputs = Callable[[list[dict[str, Any]]], SystemInputs]


def _row(step: int, **overrides: Any) -> dict[str, Any]:
    """One control cycle that tracks its commands, with named fields replaced."""
    base: dict[str, Any] = {
        "trace_id": "trace_1",
        "episode_id": "ep_1",
        "run_plan_id": "rp_1",
        "step": step,
        "t_state": 0.1 * step,
        "t_image": 0.1 * step + 0.002,
        "cmd_upper": [0.1, 0.2, 0.3],
        "meas_upper": [0.1, 0.2, 0.3],
        "cmd_lower": [0.5, 0.0],
        "meas_lower": [0.5, 0.0],
        "dropped_frames": 0,
    }
    base.update(overrides)
    return base


@pytest.fixture
def row() -> Row:
    """One control cycle, named fields replaced; the building block of every fault."""
    return _row


@pytest.fixture
def clean_rows() -> list[dict[str, Any]]:
    return [_row(step) for step in range(20)]


@pytest.fixture
def write_trace(tmp_path: Path) -> Rows:
    """Write rows as a JSONL trace and return the path."""

    def write(rows: list[dict[str, Any]], name: str = "trace.jsonl") -> Path:
        path = tmp_path / name
        path.write_text(
            "".join(json.dumps(item) + "\n" for item in rows),
            encoding="utf-8",
        )
        return path

    return write


@pytest.fixture
def rtc_rows() -> list[dict[str, Any]]:
    """An RTC log whose chunks arrive well inside the delay RTC covers (1 step)."""
    return [
        {
            "job_id": "job_1",
            "trace_id": "trace_1",
            "chunk_index": index,
            "observation_sent_s": 0.5 * index,
            "chunk_received_s": 0.5 * index + 0.02,
            "delay_steps": 1,
            "buffer_level": 6,
            "boundary_jump": 0.01,
        }
        for index in range(10)
    ]


@pytest.fixture
def camera_entry() -> dict[str, Any]:
    """Camera parameters matching the reference of `system.yaml` in the tests."""
    return {
        "episode_id": "ep_1",
        "uid": "head",
        "mount": "head_link",
        "width": 640,
        "height": 480,
        "fx": 400.0,
        "fy": 400.0,
        "cx": 320.0,
        "cy": 240.0,
        "pose": [0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0],
        "reference_sha256": "b" * 64,
    }


def _rollout_result(infra_status: str = "ok", trace_id: str = "trace_1") -> dict[str, Any]:
    """`episode.json` as the SimpleSim hook (DA-38 @ f94d5bc) writes it: a v0 RolloutResult."""
    return {
        "job_id": "job_1",
        "trace_ref": {"trace_id": trace_id, "uri": "ep_1/trace.jsonl", "sha256": None},
        "sim_success": infra_status == "ok",
        "infra_status": infra_status,
        "usage": {"wall_seconds": 12.0, "gpu_seconds": 0.0},
        "camera_params_hash": "b" * 64,
        "adapter_info": {"name": "flywheel-simple.trace", "version": "0.1.0"},
    }


Result = Callable[..., dict[str, Any]]
WriteJob = Callable[..., Path]


@pytest.fixture
def rollout_result() -> Result:
    """`episode.json` of one episode, `infra_status` and `trace_id` replaced."""
    return _rollout_result


def write_job_episode(
    job: Path,
    trace_rows: list[dict[str, Any]],
    rtc: list[dict[str, Any]] | None = None,
    camera: dict[str, Any] | list[dict[str, Any]] | None = None,
    result: dict[str, Any] | None = None,
    episode_id: str = "ep_1",
) -> Path:
    """Write one episode in the layout of the SimpleSim hook; return the episode dir.

    <job>/rtc.jsonl is the job-wide RTC log of DA-19; <job>/<episode_id>/ holds
    trace.jsonl, camera_params.json and episode.json. A file passed as None
    is not written.
    """
    folder = job / episode_id
    folder.mkdir(parents=True)
    (folder / "trace.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in trace_rows), encoding="utf-8"
    )
    if rtc is not None:
        (job / "rtc.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in rtc), encoding="utf-8"
        )
    if camera is not None:
        (folder / "camera_params.json").write_text(json.dumps(camera), encoding="utf-8")
    if result is not None:
        (folder / "episode.json").write_text(json.dumps(result), encoding="utf-8")
    return folder


@pytest.fixture
def write_job(tmp_path: Path) -> WriteJob:
    """`write_job_episode` under a fresh job directory of this test."""

    def write(trace_rows: list[dict[str, Any]], **files: Any) -> Path:
        job = tmp_path / f"job_{len(list(tmp_path.glob('job_*')))}"
        return write_job_episode(job, trace_rows, **files)

    return write


@pytest.fixture
def inputs_from(write_trace: Rows) -> Inputs:
    """Rows as `SystemInputs` carrying the trace alone, for the trace-only checks."""

    def build(rows: list[dict[str, Any]]) -> SystemInputs:
        return SystemInputs(trace=read_trace_log(write_trace(rows)))

    return build
