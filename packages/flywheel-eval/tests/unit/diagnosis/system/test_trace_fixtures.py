"""The system check on the trace fixtures of Contract change #31 (PR #48).

The traces in `data/trace_pr48/` are copied byte for byte from
`flywheel/testkit/fixtures/trace/` of PR #48 at `5b373e2`, the fixtures the
writer side of `TraceStep` is built against. They are copied rather than read
from testkit because #48 has not merged; when it does, this test reads them
from testkit and the copies go.

They matter because they follow the writer's conventions rather than this
lane's: the camera runs at 25 Hz against a 50 Hz control loop, so `t_image` is
null on every other cycle, and raw psi-data carries no lower-body measurement.
A test on traces built in this lane cannot catch a reader that disagrees with
the writer; these can.

The thresholds are the ones that ship in `system.yaml`, with the camera
reference pinned to `camera_clean.json`, the same way `test_injected_faults.py`
pins it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.check import diagnose_system
from flywheel.eval.diagnosis.system.reader import load_episode
from flywheel.eval.diagnosis.system.verdict import Diagnosis, SystemVerdict

DATA = Path(__file__).parent / "data" / "trace_pr48"
REFERENCE_KEYS = ("mount", "width", "height", "fx", "fy", "cx", "cy", "pose")


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


@pytest.fixture
def cfg() -> SystemThresholds:
    """`system.yaml` as it ships, with the reference pinned to `camera_clean.json`."""
    shipped = yaml.safe_load(
        (_repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml").read_text(
            encoding="utf-8"
        )
    )
    camera: dict[str, Any] = json.loads((DATA / "camera_clean.json").read_text(encoding="utf-8"))
    shipped["r5"] = {
        **shipped["r5"],
        "reference_sha256": camera["reference_sha256"],
        "cameras": {
            camera["uid"]: {key: camera[key] for key in REFERENCE_KEYS}
        },
    }
    return SystemThresholds.from_mapping(shipped)


def _check(tmp_path: Path, trace: str, camera: str, cfg: SystemThresholds) -> SystemVerdict:
    episode = tmp_path / Path(trace).stem
    episode.mkdir()
    shutil.copyfile(DATA / trace, episode / "trace.jsonl")
    shutil.copyfile(DATA / camera, episode / "camera_params.json")
    return diagnose_system(load_episode(episode), cfg)


def _skipped(verdict: SystemVerdict) -> set[str]:
    return {skip.code for skip in verdict.skipped}


def test_the_clean_fixture_judges_tracking_and_sync(tmp_path: Path, cfg) -> None:
    # `t_image: null` on the 50 cycles with no new frame is the writer's
    # convention, not a gap; only the codes with no input at all are skipped
    # (no RTC log, no `infra_status`).
    verdict = _check(tmp_path, "clean.jsonl", "camera_clean.json", cfg)

    assert verdict.findings == []
    assert _skipped(verdict) == {"R1", "R2", "R6"}


def test_the_sync_delay_fixture_comes_back_as_a_sync_fault(tmp_path: Path, cfg) -> None:
    verdict = _check(tmp_path, "r4_sync_delay.jsonl", "camera_clean.json", cfg)

    assert verdict.diagnosis is Diagnosis.SYNC
    assert [finding.code for finding in verdict.findings] == ["R4"]
    assert verdict.findings[0].value == pytest.approx(0.12)


def test_the_calibration_offset_fixture_comes_back_as_a_calibration_fault(
    tmp_path: Path, cfg
) -> None:
    verdict = _check(tmp_path, "r5_calibration_offset.jsonl", "camera_offset.json", cfg)

    assert verdict.diagnosis is Diagnosis.CALIBRATION
    assert {finding.code for finding in verdict.findings} == {"R5"}


def test_the_missing_signals_fixture_is_unknown(tmp_path: Path, cfg) -> None:
    verdict = _check(tmp_path, "missing_signals.jsonl", "camera_clean.json", cfg)

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert verdict.findings == []
    assert "R4" in _skipped(verdict)
    # raw psi-data has no lower-body measurement; the upper half is still judged
    assert "R3/lower" in _skipped(verdict)
    assert "R3/upper" not in _skipped(verdict)
