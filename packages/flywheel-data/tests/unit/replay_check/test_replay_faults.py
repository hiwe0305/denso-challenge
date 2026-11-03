"""Three injected faults are caught and reach QA; clean episodes are not flagged (DA-17 task 4).

The story's faults - one joint's sign flipped, a joint in degrees instead of
radians, the state clock two frames off the video - go into copies of clean G1
episodes written in the test. The dynamic side runs on `fake_replay`, a stand-in
for the SIMPLE adapter with the same output: testkit's FakeSim2D is a 2-D point
gripper and has no G1 joints to replay. Then the real pipeline: `fw data ingest`,
`replay_check reports`, `fw data qa --replay` (AC 4).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.data.cli import app as data_app
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.replay_check.cli import app as replay_app
from flywheel.data.replay_check.kinematic import DEG_PER_RAD, joint_dims
from replay_data import FPS, LEAD, clean_frames, g1_layout, write_dataset
from typer.testing import CliRunner

LAYOUT = g1_layout()
ELBOW = [d.name for d in LAYOUT.dimensions].index("right_elbow_joint")
GROUPS = {"hand": range(0, 14), "arm": range(14, 28), "torso_rpy": range(28, 31)}
CLEAN = 12


def sign_flip(f: EpisodeFrames) -> EpisodeFrames:
    action = f.action.copy()
    action[:, ELBOW] = -action[:, ELBOW]
    return dataclasses.replace(f, action=action)


def degrees(f: EpisodeFrames) -> EpisodeFrames:
    action = f.action.copy()
    action[:, ELBOW] *= DEG_PER_RAD
    return dataclasses.replace(f, action=action)


def two_frames_late(f: EpisodeFrames) -> EpisodeFrames:
    return dataclasses.replace(f, timestamp=f.timestamp + 2 / FPS)


FAULTS = {"sign_flip": sign_flip, "unit_deg_rad": degrees, "timestamp_2_frames": two_frames_late}


def fake_replay(f: EpisodeFrames) -> dict[str, Any]:
    """A WBC that tracks the commanded joints LEAD frames late, clipped to the limits,
    read through 0.01 rad encoders; the outcome line as the adapter writes it
    (compare.outcome). The encoders make every clean replay show the same error, so
    a p99 threshold calibrated on them flags none of them."""
    dims = joint_dims(LAYOUT, 32)
    low = np.array([LAYOUT.dimensions[i].limit_low for i in dims])
    high = np.array([LAYOUT.dimensions[i].limit_high for i in dims])
    reached = np.clip(f.action[:, dims].astype(np.float64), low, high)
    replayed = np.concatenate([f.states[:LEAD, dims], reached])  # before the first command
    gap = np.abs(replayed[1 : len(f.states)] - f.states[1:, dims])
    errors = {g: float(np.ceil(gap[:, list(r)].max() / 0.01) * 0.01) for g, r in GROUPS.items()}
    return {
        "episode_index": f.episode_index,
        "success": max(errors.values()) < 0.5,
        "state_error_by_group": errors,
        "hand_event_offset_steps": 0,
    }


@pytest.fixture
def pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Clean episodes 0..CLEAN-1, then one copy of episode 0 per fault; ingested."""
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    clean = [clean_frames(i) for i in range(CLEAN)]
    faulty = [
        dataclasses.replace(fault(clean_frames(0)), episode_index=CLEAN + k)
        for k, fault in enumerate(FAULTS.values())
    ]
    calib = write_dataset(tmp_path / "calib", clean)
    root = write_dataset(tmp_path / "psi", clean + faulty)
    runner = CliRunner()
    for name, dataset in (("calib", calib), ("psi", root)):
        lines = "".join(json.dumps(fake_replay(f)) + "\n" for f in clean + faulty)
        (tmp_path / f"{name}.jsonl").write_text(lines)
    yaml_path = tmp_path / "replay.yaml"
    result = runner.invoke(replay_app, [
        "calibrate", str(calib), "--outcomes", str(tmp_path / "calib.jsonl"),
        "--out", str(yaml_path), "--calibration", "clean test episodes"])
    assert result.exit_code == 0, result.output
    work = tmp_path / "work"
    result = runner.invoke(data_app, [
        "ingest", str(root), "--source-detail", "psi_data", "--license", "test",
        "--data-class", "public", "--work", str(work)])
    assert result.exit_code == 0, result.output
    ids = {i: e for e, i in json.loads((work / "episode_index.json").read_text()).items()}
    return {"root": root, "work": work, "yaml": yaml_path, "ids": ids, "tmp": tmp_path}


def run_reports(p: dict[str, Any]) -> Path:
    out = p["tmp"] / "replay-reports"
    result = CliRunner().invoke(replay_app, [
        "reports", str(p["work"]), "--out", str(out), "--outcomes",
        str(p["tmp"] / "psi.jsonl"), "--config", str(p["yaml"])])
    assert result.exit_code == 0, result.output
    return out


def issues(out: Path, episode_id: str, mode: str) -> set[str]:
    report = json.loads((out / f"{episode_id}.{mode}.json").read_text())
    assert report["mode"] == mode and report["episode_id"] == episode_id
    return {i["code"] for i in report["issues"]}


def test_each_fault_is_caught_and_clean_episodes_are_not(pipeline: dict[str, Any]) -> None:
    out = run_reports(pipeline)
    ids = pipeline["ids"]
    for index in range(CLEAN):
        assert issues(out, ids[index], "kinematic") == set()
        assert issues(out, ids[index], "dynamic") == set()
    sign, deg, late = (ids[CLEAN + k] for k in range(3))
    assert issues(out, sign, "kinematic") == {"joint_mapping"}
    assert issues(out, sign, "dynamic") == {"state_error", "replay_failed"}
    assert issues(out, deg, "kinematic") == {"unit_deg_rad", "joint_limit"}
    assert issues(out, late, "kinematic") == {"timestamp_offset"}
    assert issues(out, late, "dynamic") == set()  # the clock is no joint: kinematic only


def test_qa_rejects_the_faults_and_passes_the_clean(pipeline: dict[str, Any]) -> None:
    out = run_reports(pipeline)
    work = pipeline["work"]
    result = CliRunner().invoke(data_app, ["qa", str(work), "--replay", str(out)])
    assert result.exit_code == 0, result.output
    lines = (work / "qa" / "reports.jsonl").read_text().splitlines()
    reports = [json.loads(line) for line in lines]
    by_id = {r["episode_id"]: r for r in reports}
    ids = pipeline["ids"]
    for index in range(CLEAN):
        assert by_id[ids[index]]["decision"] == "pass", by_id[ids[index]]
    for k in range(3):
        report = by_id[ids[CLEAN + k]]
        assert report["decision"] == "reject"
        failed = {c["name"] for c in report["checks"] if not c["passed"]}
        assert "replay_kinematic" in failed


def test_reports_refuse_a_used_directory(pipeline: dict[str, Any]) -> None:
    out = run_reports(pipeline)
    result = CliRunner().invoke(replay_app, [
        "reports", str(pipeline["work"]), "--out", str(out), "--config", str(pipeline["yaml"])])
    assert result.exit_code == 2 and "not empty" in result.output
