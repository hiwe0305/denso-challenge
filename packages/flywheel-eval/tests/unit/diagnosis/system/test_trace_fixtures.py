"""The system check on the trace fixtures of Contract change #31 (merged as PR #79).

The traces are read where they live, in `flywheel/testkit/fixtures/trace/`: the
fixtures the writer side of `TraceStep` is built against, in the layout of
decisions G1 and G1b - `<trace_id>/` with `steps.jsonl`, `camera_params.jsonl`
and `rollout_result.json`. They are read as they are, not copied, so a change
to them on master reaches this test the day it lands.

They matter because they follow the writer's conventions rather than this
lane's: the camera runs at 25 Hz against a 50 Hz control loop, so `t_image` is
null on every other cycle, and raw psi-data carries no lower-body measurement,
written as "NaN". A test on traces built in this lane cannot catch a reader
that disagrees with the writer; these can.

The thresholds are `system.yaml` as it ships. The fixtures' cameras carry the
G0 reference of the two-table task that `system.yaml` pins (testkit README), so
nothing here is pinned by the test.
"""

from __future__ import annotations

from pathlib import Path

import flywheel.testkit
import pytest
import yaml
from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.check import diagnose_system
from flywheel.eval.diagnosis.system.reader import load_episode
from flywheel.eval.diagnosis.system.verdict import Diagnosis, SystemVerdict

FIXTURES = Path(flywheel.testkit.__file__).parent / "fixtures" / "trace"


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


@pytest.fixture
def cfg() -> SystemThresholds:
    """`system.yaml` as it ships."""
    return SystemThresholds.from_mapping(
        yaml.safe_load(
            (_repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml").read_text(
                encoding="utf-8"
            )
        )
    )


def _check(trace_id: str, cfg: SystemThresholds) -> SystemVerdict:
    return diagnose_system(load_episode(FIXTURES / trace_id), cfg)


def _skipped(verdict: SystemVerdict) -> set[str]:
    return {skip.code for skip in verdict.skipped}


def test_the_clean_fixture_is_judged_on_every_code_it_has_input_for(cfg) -> None:
    # `t_image: null` on the 50 cycles with no new frame is the writer's
    # convention, not a gap; only R1 and R2 are skipped, because testkit ships
    # no `rtc.jsonl`. R5 and R6 are judged, on the real G0 reference and the
    # RolloutResult beside the steps.
    verdict = _check("tr_clean", cfg)

    assert verdict.findings == []
    assert _skipped(verdict) == {"R1", "R2"}
    assert verdict.infra_status == "ok"


def test_the_sync_delay_fixture_comes_back_as_a_sync_fault(cfg) -> None:
    verdict = _check("tr_sync_delay", cfg)

    assert verdict.diagnosis is Diagnosis.SYNC
    assert [finding.code for finding in verdict.findings] == ["R4"]
    assert verdict.findings[0].value == pytest.approx(0.12)


def test_the_calibration_offset_fixture_comes_back_on_the_camera_that_moved(cfg) -> None:
    # `head_stereo_left` has fx, fy 10% high and 15° of pitch; the right one is
    # the reference, and must not be reported with it.
    verdict = _check("tr_calib_offset", cfg)

    assert verdict.diagnosis is Diagnosis.CALIBRATION
    assert {finding.code for finding in verdict.findings} == {"R5"}
    assert {finding.where for finding in verdict.findings} == {"head_stereo_left"}


def test_the_missing_signals_fixture_is_unknown(cfg) -> None:
    verdict = _check("tr_missing", cfg)

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert verdict.findings == []
    assert "R4" in _skipped(verdict)
    # raw psi-data has no lower-body measurement; the upper half is still judged
    assert "R3/lower" in _skipped(verdict)
    assert "R3/upper" not in _skipped(verdict)
