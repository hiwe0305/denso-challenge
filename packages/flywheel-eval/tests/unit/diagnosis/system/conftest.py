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
    """An RTC log whose chunks arrive quickly and keep the buffer full."""
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


@pytest.fixture
def inputs_from(write_trace: Rows) -> Inputs:
    """Rows as `SystemInputs` carrying the trace alone, for the trace-only checks."""

    def build(rows: list[dict[str, Any]]) -> SystemInputs:
        return SystemInputs(trace=read_trace_log(write_trace(rows)))

    return build
