"""Acceptance of the system check on injected faults and a clean control (DA-13 AC 5, 6).

Spec section 7.6 is the shape of this: an injected fault must come back as the
class it was injected as, and a clean episode must not be reported as a system
fault. Those are the two ways the check can be useless - missing the fault it
was built for, and crying fault on a healthy run - and they are tested against
each other on the same episode body so a difference can only come from the
thing that was injected.

The faults are synthesised here rather than produced by a rollout: the real
`Trace` of SIMPLE arrives with the `SimpleSim` hook (story, dependencies) and
`FaultSpec` injection belongs to the rollout side, so AC 6 asks for CPU and
synthetic traces and this is what that looks like. The thresholds are the ones
that ship in `system.yaml`, with the camera reference pinned, because an
acceptance test against thresholds invented in the test proves nothing about
the configuration the team runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.config import SystemThresholds
from flywheel.eval.diagnosis.system.check import diagnose_system
from flywheel.eval.diagnosis.system.reader import load_episode
from flywheel.eval.diagnosis.system.verdict import Diagnosis

CAMERA_REFERENCE: dict[str, Any] = {
    "mount": "head_link",
    "width": 640,
    "height": 480,
    "fx": 400.0,
    "fy": 400.0,
    "cx": 320.0,
    "cy": 240.0,
    "pose": [0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0],
}
REFERENCE_SHA = "b" * 64
DA38 = Path(__file__).parent / "data" / "da38"


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


@pytest.fixture
def cfg() -> SystemThresholds:
    """`system.yaml` as it ships, with the camera reference pinned for R5.

    The file ships unpinned on purpose (G0 has not fixed the reference), and
    R5 then skips. Pinning it here is what lets the calibration case of AC 5
    be tested at all, and everything else is the shipped number.
    """
    shipped = yaml.safe_load(
        (_repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml").read_text(
            encoding="utf-8"
        )
    )
    shipped["r5"] = {
        **shipped["r5"],
        "reference_sha256": REFERENCE_SHA,
        "cameras": {"head": CAMERA_REFERENCE},
    }
    return SystemThresholds.from_mapping(shipped)


@pytest.fixture
def episode(tmp_path: Path, clean_rows, rtc_rows, camera_entry):
    """Write a healthy episode, then let a test move one thing in it."""

    def write(
        trace_rows: list[dict[str, Any]] | None = None,
        rtc: list[dict[str, Any]] | None = None,
        camera: dict[str, Any] | list[dict[str, Any]] | None = None,
        infra_status: str = "ok",
    ) -> Path:
        folder = tmp_path / f"ep_{len(list(tmp_path.iterdir()))}"
        folder.mkdir()
        rows = trace_rows if trace_rows is not None else clean_rows
        (folder / "trace.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8"
        )
        (folder / "rtc.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in (rtc if rtc is not None else rtc_rows)),
            encoding="utf-8",
        )
        (folder / "camera_params.json").write_text(
            json.dumps(camera if camera is not None else camera_entry), encoding="utf-8"
        )
        (folder / "episode.json").write_text(
            json.dumps({"infra_status": infra_status}), encoding="utf-8"
        )
        return folder

    return write


def test_a_clean_episode_is_not_reported_as_a_system_fault(episode, cfg) -> None:
    # The control of AC 5. Nothing was injected, every code was judged, so the
    # episode is cleared and the loop may use it as evidence about the policy.
    verdict = diagnose_system(load_episode(episode()), cfg)

    assert verdict.diagnosis is Diagnosis.CLEAN
    assert verdict.findings == []
    assert verdict.skipped == []
    assert not verdict.blocks_policy_analysis


def test_an_injected_camera_delay_comes_back_as_a_sync_fault(episode, cfg, row) -> None:
    # "trễ camera ra LỖI ĐỒNG BỘ" (AC 5). The image clock lags the state clock
    # by 60 ms, over the 20 ms tau_sync of `system.yaml`.
    delayed = [row(step, t_image=0.1 * step - 0.06) for step in range(20)]

    verdict = diagnose_system(load_episode(episode(trace_rows=delayed)), cfg)

    assert verdict.diagnosis is Diagnosis.SYNC
    assert [finding.code for finding in verdict.findings] == ["R4"]
    assert verdict.findings[0].value == pytest.approx(0.06)
    assert verdict.blocks_policy_analysis


def test_an_injected_calibration_offset_comes_back_as_a_calibration_fault(
    episode, cfg, camera_entry
) -> None:
    # "lệch calibration ra LỖI CALIBRATION" (AC 5). The head camera sits 4 cm
    # higher than the reference, over the 5 mm tolerance.
    moved = {**camera_entry, "pose": [0.0, 0.0, 1.54, 1.0, 0.0, 0.0, 0.0]}

    verdict = diagnose_system(load_episode(episode(camera=moved)), cfg)

    assert verdict.diagnosis is Diagnosis.CALIBRATION
    assert [finding.code for finding in verdict.findings] == ["R5"]
    assert verdict.findings[0].where == "head"


def test_an_injected_tracking_fault_comes_back_as_a_controller_fault(episode, cfg, row) -> None:
    off = [row(step, meas_upper=[0.4, 0.2, 0.3]) for step in range(20)]

    verdict = diagnose_system(load_episode(episode(trace_rows=off)), cfg)

    assert verdict.diagnosis is Diagnosis.CONTROLLER
    assert [(f.code, f.part) for f in verdict.findings] == [("R3", "upper")]


def test_an_upper_body_fault_is_caught_when_the_lower_body_is_not_measured(
    episode, cfg, row
) -> None:
    # Raw psi-data logs no `meas_lower` (README of the #31 fixtures). Losing the
    # lower half must not cost the upper half its verdict and hide a real
    # controller fault there.
    off = [
        row(step, meas_upper=[0.6, 0.2, 0.3], meas_lower=["NaN", "NaN"]) for step in range(20)
    ]

    verdict = diagnose_system(load_episode(episode(trace_rows=off)), cfg)

    assert verdict.diagnosis is Diagnosis.CONTROLLER
    assert [(f.code, f.part) for f in verdict.findings] == [("R3", "upper")]
    assert [skip.code for skip in verdict.skipped] == ["R3/lower"]


def test_an_injected_latency_spike_comes_back_as_a_runtime_fault(episode, cfg, rtc_rows) -> None:
    slow = [
        {**record, "chunk_received_s": record["observation_sent_s"] + 0.4} for record in rtc_rows
    ]

    verdict = diagnose_system(load_episode(episode(rtc=slow)), cfg)

    assert verdict.diagnosis is Diagnosis.RUNTIME
    assert [finding.code for finding in verdict.findings] == ["R1"]


def test_a_server_fault_is_recorded_and_is_not_a_policy_fault(episode, cfg) -> None:
    verdict = diagnose_system(load_episode(episode(infra_status="rtc_unreachable")), cfg)

    assert verdict.diagnosis is Diagnosis.INFRA
    assert verdict.infra_status == "rtc_unreachable"
    assert [finding.code for finding in verdict.findings] == ["R6"]


def test_a_crashed_simulator_is_never_a_controller_fault(episode, cfg, row) -> None:
    # The PO reproduction of #71: `sim_crash` plus a tracking error came back
    # `controller`. Commands and measurements after a crash are its consequence.
    off = [row(step, meas_upper=[0.4, 0.2, 0.3]) for step in range(20)]

    verdict = diagnose_system(
        load_episode(episode(trace_rows=off, infra_status="sim_crash")), cfg
    )

    assert verdict.diagnosis is Diagnosis.INFRA
    assert [finding.code for finding in verdict.findings] == ["R6", "R3"]


def test_two_injected_faults_both_appear_and_the_first_one_is_the_label(
    episode, cfg, row, camera_entry
) -> None:
    # The label is what the engineer fixes first; the other measurement still
    # travels, so the re-run is not a surprise.
    both = [row(step, t_image=0.1 * step - 0.06, meas_upper=[0.4, 0.2, 0.3]) for step in range(20)]

    verdict = diagnose_system(load_episode(episode(trace_rows=both)), cfg)

    assert verdict.diagnosis is Diagnosis.CONTROLLER
    assert [finding.code for finding in verdict.findings] == ["R3", "R4"]


def test_an_episode_whose_trace_lacks_a_field_is_unknown_not_clean(episode, cfg, row) -> None:
    # The first step of spec section 6.4. The episode looks healthy on every
    # code that could be judged, and it is still not cleared.
    without = [row(step) for step in range(20)]
    for item in without:
        del item["t_image"]

    verdict = diagnose_system(load_episode(episode(trace_rows=without)), cfg)

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert verdict.findings == []
    assert [skip.code for skip in verdict.skipped] == ["R4"]


def _shipped() -> SystemThresholds:
    return SystemThresholds.from_mapping(
        yaml.safe_load(
            (_repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml").read_text(
                encoding="utf-8"
            )
        )
    )


def _hook_cameras() -> list[dict[str, Any]]:
    # `camera_params.json` as the SimpleSim hook (DA-38 @ f94d5bc) writes it for
    # the two-table task at SIMPLE b75c678: both head cameras, with the hash of
    # the G0 reference copied from the job spec.
    return json.loads((DA38 / "camera_params.json").read_text(encoding="utf-8"))


def test_the_shipped_config_clears_the_cameras_the_hook_writes(episode) -> None:
    # `system.yaml` as it ships, pinned at G0 for the two-table task: the
    # cameras of a SIMPLE rollout are judged, and they match.
    verdict = diagnose_system(load_episode(episode(camera=_hook_cameras())), _shipped())

    assert verdict.diagnosis is Diagnosis.CLEAN
    assert verdict.findings == []
    assert verdict.skipped == []


def test_the_shipped_config_catches_a_hook_camera_that_drifted(episode) -> None:
    cameras = _hook_cameras()
    cameras[1] = {**cameras[1], "fx": cameras[1]["fx"] + 2.0}

    verdict = diagnose_system(load_episode(episode(camera=cameras)), _shipped())

    assert verdict.diagnosis is Diagnosis.CALIBRATION
    assert [(f.code, f.where) for f in verdict.findings] == [("R5", "head_stereo_right")]


def test_an_episode_without_camera_params_is_unknown_on_the_shipped_config(episode) -> None:
    # The hook writes no `camera_params.json` when the job had no pinned hash;
    # R5 must then say CHƯA RÕ, not pass.
    folder = episode(camera=_hook_cameras())
    (folder / "camera_params.json").unlink()

    verdict = diagnose_system(load_episode(folder), _shipped())

    assert verdict.diagnosis is Diagnosis.UNKNOWN
    assert [skip.code for skip in verdict.skipped] == ["R5"]
    assert "camera_params.json" in verdict.skipped[0].reason


def test_the_same_episode_scores_the_same_twice(episode, cfg) -> None:
    # The check is a pure step: no clock, no simulator, no model (AC 6).
    folder = episode()

    first = diagnose_system(load_episode(folder), cfg)
    second = diagnose_system(load_episode(folder), cfg)

    assert first == second
