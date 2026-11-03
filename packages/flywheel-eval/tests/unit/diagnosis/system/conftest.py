"""Synthetic traces for the F-SYS checks (DA-13 AC 6).

Every trace here is built in the test, not recorded, so the checks are
testable on CPU (story, dependencies). Each step is a whole
`flywheel.contracts.trace.TraceStep` - 28 upper-body and 7 lower-body channels -
so the reader takes it through the contract as it takes the hook's. The traces
the writer side was built against are in testkit and read in
`test_trace_fixtures.py`; the hook's own output is in `test_hook_seam.py`.

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
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY
from flywheel.eval.diagnosis.system.reader import (
    CAMERA_NAME,
    ROLLOUT_NAME,
    RTC_NAME,
    STEPS_NAME,
    SystemInputs,
    read_trace_log,
)

Row = Callable[..., dict[str, Any]]
Rows = Callable[..., Path]
Inputs = Callable[[list[dict[str, Any]]], SystemInputs]


UPPER = [0.1, 0.2, 0.3, *[0.0] * (len(UPPER_BODY) - 3)]
LOWER = [0.5, *[0.0] * (len(LOWER_BODY) - 1)]


def _row(step: int, **overrides: Any) -> dict[str, Any]:
    """One control cycle that tracks its commands, with named fields replaced.

    A vector shorter than the contract's width replaces the leading channels
    and keeps the clean values in the rest, so `meas_upper=[0.4, 0.2, 0.3]` is
    an error of 0.3 on the first upper-body joint and nothing else.
    """
    base: dict[str, Any] = {
        "trace_id": "trace_1",
        "episode_id": "ep_1",
        "run_plan_id": "rp_1",
        "step": step,
        "t_state": 0.1 * step,
        "t_image": 0.1 * step + 0.002,
        "cmd_upper": list(UPPER),
        "meas_upper": list(UPPER),
        "cmd_lower": list(LOWER),
        "meas_lower": list(LOWER),
        "dropped_frames": 0,
    }
    for name, value in overrides.items():
        clean = base.get(name)
        if isinstance(value, list) and isinstance(clean, list):
            value = [*value, *clean[len(value) :]]
        base[name] = value
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

    def write(rows: list[dict[str, Any]], name: str = STEPS_NAME) -> Path:
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
        "trace_id": "trace_1",
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
    """`rollout_result.json` of one trace: a v0 RolloutResult, as the SimpleSim hook fills it."""
    return {
        "job_id": "job_1",
        "trace_ref": {"trace_id": trace_id, "uri": trace_id, "sha256": None},
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
    """`rollout_result.json` of one trace, `infra_status` and `trace_id` replaced."""
    return _rollout_result


def _jsonl(items: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(item) + "\n" for item in items)


def write_job_episode(
    job: Path,
    trace_rows: list[dict[str, Any]],
    rtc: list[dict[str, Any]] | None = None,
    camera: dict[str, Any] | list[dict[str, Any]] | None = None,
    result: dict[str, Any] | None = None,
    trace_id: str = "trace_1",
) -> Path:
    """Write one trace in the layout of decision G1 on PR #48; return the trace dir.

    `<job>/rtc.jsonl` is the job-wide RTC log of DA-19; `<job>/<trace_id>/`
    holds the steps, one camera per line of the camera file, and the
    RolloutResult. The names are the reader's constants. A file passed as
    None is not written.
    """
    folder = job / trace_id
    folder.mkdir(parents=True)
    (folder / STEPS_NAME).write_text(_jsonl(trace_rows), encoding="utf-8")
    if rtc is not None:
        (job / RTC_NAME).write_text(_jsonl(rtc), encoding="utf-8")
    if camera is not None:
        cameras = camera if isinstance(camera, list) else [camera]
        (folder / CAMERA_NAME).write_text(_jsonl(cameras), encoding="utf-8")
    if result is not None:
        (folder / ROLLOUT_NAME).write_text(json.dumps(result), encoding="utf-8")
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
