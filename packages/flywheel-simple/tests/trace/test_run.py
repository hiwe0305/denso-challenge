"""Job spec of the trace entry module, and the copies of contract names it relies on (DA-38 3.3).

The hook runs in SIMPLE's venv, which has no flywheel package, so `files`, `signals`
and `run` hold copies of names and rules from `flywheel.contracts.trace`; these tests
keep the copies equal to the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flywheel_simple.trace import files, signals
from flywheel_simple.trace.run import G0_RUN_PLAN_ID, JobSpec

PINNED = "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"


def env(**overrides: str) -> dict[str, str]:
    base = {
        "FW_TRACE_JOB_DIR": "/tmp/job-1",
        "FW_JOB_ID": "job-1",
        "FW_RUN_PLAN_ID": "g0-DA-38-20261105",
        "FW_CAMERA_REFERENCE_SHA256": PINNED,
    }
    return {k: v for k, v in {**base, **overrides}.items() if v}


def test_job_spec_reads_the_environment() -> None:
    spec = JobSpec.from_env(env())
    assert spec == JobSpec(Path("/tmp/job-1"), "job-1", "g0-DA-38-20261105", PINNED)


def test_job_spec_without_a_camera_reference_writes_no_camera_params() -> None:
    assert JobSpec.from_env(env(FW_CAMERA_REFERENCE_SHA256="")).camera_reference_sha256 is None


@pytest.mark.parametrize("key", ["FW_TRACE_JOB_DIR", "FW_JOB_ID", "FW_RUN_PLAN_ID"])
def test_job_spec_names_what_is_missing(key: str) -> None:
    with pytest.raises(ValueError, match=key):
        JobSpec.from_env(env(**{key: ""}))


def test_a_g0_run_plan_id_must_follow_the_g2_rule() -> None:
    with pytest.raises(ValueError, match="g0-<story>-<yyyymmdd>"):
        JobSpec.from_env(env(FW_RUN_PLAN_ID="g0-DA-38-test"))
    assert JobSpec.from_env(env(FW_RUN_PLAN_ID="rp-he-tray-001")).run_plan_id == "rp-he-tray-001"


def test_copies_of_contract_names_match_the_contract() -> None:
    trace = pytest.importorskip("flywheel.contracts.trace")
    assert signals.UPPER_NAMES == trace.UPPER_BODY
    assert signals.LOWER_NAMES == trace.LOWER_BODY
    assert (files.STEPS_NAME, files.CAMERA_NAME, files.RESULT_NAME) == (
        trace.STEPS_NAME,
        trace.CAMERA_NAME,
        trace.RESULT_NAME,
    )
    assert G0_RUN_PLAN_ID.pattern == trace.G0_RUN_PLAN_ID.pattern
