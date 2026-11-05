"""The system check on a job written by the SimpleSim hook itself (DA-38, the seam with DA-13).

`data/da38_g1/job-g1/` was written by `EpisodeDirSink` of `flywheel_simple.trace`
at `DA-38-trace-hook-v2` @ `207e276` (not merged; read from the branch, not built
on it), with the two-table camera reference pinned at G0, and its `rtc.jsonl` by
`RTCClient` of DA-19 reset with each trace's id at 50 ms of inference and 50 Hz.
One trace ran to the end; the other was cut off, so the hook wrote
`infra_status: simulator_error`. Nothing here was written by hand, so a reader
that disagrees with the writer fails here and not on the day of the demo.

The thresholds are `system.yaml` as it ships.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from flywheel.eval.api import diagnose_episode_system
from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.check import diagnose_system
from flywheel.eval.diagnosis.system.reader import (
    ROLLOUT_NAME,
    STEPS_NAME,
    ReaderError,
    load_episode,
)
from flywheel.eval.diagnosis.system.verdict import Diagnosis

JOB = Path(__file__).parent / "data" / "da38_g1" / "job-g1"
HEALTHY = "job-g1-0123456789ab"
CRASHED = "job-g1-fedcba987654"


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


SYSTEM_YAML = _repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml"


@pytest.fixture
def shipped() -> SystemThresholds:
    return SystemThresholds.from_mapping(yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8")))


def test_a_healthy_hook_trace_is_judged_on_every_code_and_cleared(shipped) -> None:
    inputs = load_episode(JOB / HEALTHY)

    assert inputs.trace.trace_id == HEALTHY
    assert {record.trace_id for record in inputs.rtc} == {HEALTHY}
    assert [camera.uid for camera in inputs.cameras] == ["head_stereo_left", "head_stereo_right"]
    verdict = diagnose_system(inputs, shipped)
    assert verdict.diagnosis is Diagnosis.CLEAN
    assert verdict.findings == []
    assert verdict.skipped == []


def test_a_trace_the_simulator_cut_off_is_an_infra_fault(shipped) -> None:
    verdict = diagnose_system(load_episode(JOB / CRASHED), shipped)

    assert verdict.diagnosis is Diagnosis.INFRA
    assert verdict.infra_status == "simulator_error"


def test_the_rollout_result_file_is_an_input_as_good_as_the_directory() -> None:
    by_directory = diagnose_episode_system(JOB / HEALTHY, SYSTEM_YAML)
    by_result = diagnose_episode_system(JOB / HEALTHY / ROLLOUT_NAME, SYSTEM_YAML)

    assert by_result == by_directory
    assert by_result.diagnosis == "clean"


def test_steps_that_do_not_hash_to_the_trace_ref_are_refused(tmp_path: Path) -> None:
    # `trace_ref.sha256` is the hash of `steps.jsonl` as the hook wrote it; steps
    # that changed since are not the steps the rollout result is about.
    job = tmp_path / "job-g1"
    shutil.copytree(JOB, job)
    steps = job / HEALTHY / STEPS_NAME
    rows = [json.loads(line) for line in steps.read_text(encoding="utf-8").splitlines()]
    rows[3]["meas_upper"][0] = 0.5
    steps.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(ReaderError, match="sha256"):
        load_episode(job / HEALTHY)


def test_a_trace_ref_pointing_at_another_directory_is_refused(tmp_path: Path) -> None:
    job = tmp_path / "job-g1"
    shutil.copytree(JOB, job)
    result_path = job / HEALTHY / ROLLOUT_NAME
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["trace_ref"]["uri"] = f"job-g1/{CRASHED}"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ReaderError, match=CRASHED):
        load_episode(job / HEALTHY)
