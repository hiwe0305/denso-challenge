"""QA of one episode: each check catches an episode made wrong on purpose (DA-03 AC 3)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts.artifacts import QAReport, ReplayIssue, ReplayReport
from flywheel.data.config import QAConfig
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.qa.checks import (
    calibrate_action_jump,
    dataset_checks,
    episode_action_jumps,
    run_qa,
)
from numpy.typing import NDArray
from qa_data import FPS, clean_frames, episode_of, lineage_of

S1 = "planner_wbc"


def qa(frames: EpisodeFrames, cfg: QAConfig, source: str = "psi_data", **kw: object) -> QAReport:
    episode = episode_of(source)
    lineage = kw.pop("lineage", lineage_of() if source != "psi_data" else None)
    replay = kw.pop("replay", None)
    report = run_qa(frames, episode, replay, cfg, fps=FPS, lineage=lineage)  # type: ignore[arg-type]
    assert QAReport.model_validate_json(report.model_dump_json()) == report
    return report


def failed(report: QAReport) -> set[str]:
    return {c.name for c in report.checks if not c.passed}


def with_(frames: EpisodeFrames, **change: object) -> EpisodeFrames:
    return dataclasses.replace(frames, **change)  # type: ignore[arg-type]


@pytest.mark.parametrize("source", ["psi_data", S1, "teleop_pico"])
def test_a_clean_episode_passes_every_check(qa_config: QAConfig, source: str) -> None:
    report = qa(clean_frames(), qa_config, source)

    assert report.decision == "pass" and report.reasons == [] and not failed(report)
    names = {c.name for c in report.checks}
    assert {"timestamp_step", "finite_values", "joint_limits", "lineage"} <= names
    assert "action_jump.arm" in names
    assert ("split_seed" in names) == (source != "psi_data")  # psi-data records no seed
    assert ("video_rows_match" in names) == (source == "psi_data")
    assert report.threshold_version.startswith("qa-1@")
    assert report == qa(clean_frames(), qa_config, source)  # same input, same report_id


@pytest.mark.parametrize("length", [0, 1])
def test_an_episode_of_0_or_1_frame_is_rejected_with_its_reason(
    qa_config: QAConfig, length: int
) -> None:
    report = qa(clean_frames(length=length), qa_config)
    assert report.decision == "reject"
    assert report.reasons == [f"min_frames: episode has {length} frame(s), QA needs at least 2"]


def broken(name: str) -> EpisodeFrames:
    """An episode that only the check `name` fails."""
    frames = clean_frames()
    ts, action = frames.timestamp.copy(), frames.action.copy()
    if name == "timestamp_monotonic":
        ts[5] = ts[4]  # also a step of 1 period off, which the step check still allows
        return with_(frames, timestamp=ts)
    if name == "timestamp_step":
        ts[10:] += 2.5 / FPS
        return with_(frames, timestamp=ts)
    if name == "frame_index_contiguous":
        return with_(frames, frame_index=np.r_[np.arange(10), np.arange(11, 21)].astype(np.int64))
    if name == "finite_values":
        action[3, 20] = np.nan
        return with_(frames, action=action)
    if name == "joint_limits":
        action[:, 17] = 2.1  # left_elbow_joint limit_high 2.0944
        return with_(frames, action=action)
    if name == "action_jump.arm":
        action[8:, 20] = 0.2  # one step of 0.2 rad on left_wrist_yaw; p99.9 is 0.087
        return with_(frames, action=action)
    if name == "task_instruction":
        return with_(frames, task=" ")
    raise AssertionError(name)


@pytest.mark.parametrize(
    ("name", "code", "decision"),
    [
        ("timestamp_monotonic", "D2", "reject"),
        ("timestamp_step", "D2", "reject"),
        ("frame_index_contiguous", "D2", "quarantine"),
        ("finite_values", "D1", "reject"),
        ("joint_limits", "D3", "reject"),
        ("action_jump.arm", "D3", "flag"),
        ("task_instruction", "D6", "flag"),
    ],
)
def test_each_check_catches_its_defect(
    qa_config: QAConfig, name: str, code: str, decision: str
) -> None:
    report = qa(broken(name), qa_config)
    assert failed(report) == {name}
    assert report.decision == decision
    assert len(report.reasons) == 1 and report.reasons[0].startswith(f"{name} ({code}): ")


@pytest.mark.parametrize(
    ("check", "kind"),
    [
        ("finite_values", "nan_values"),
        ("frame_index_contiguous", "drop_frames"),
        ("joint_limits", "joint_limit_exceeded"),
        ("action_jump", "joint_jump"),
        ("split_seed", "holdout_seed_leak"),
        ("task_instruction", "wrong_task_instruction"),
        ("task_success", "corrupted_success_label"),
    ],
)
def test_a_check_reports_the_code_of_the_defect_it_catches(
    qa_config: QAConfig, check: str, kind: str
) -> None:
    # DA-31 matches a QA finding to an injected defect by code (design 9.2): a check
    # coded apart from the kind it catches would score 0 recall on that kind.
    assert qa_config.checks[check].code == DATA_DEFECT_CODES[kind]


def test_a_limit_rounded_in_the_layout_is_no_breach(qa_config: QAConfig) -> None:
    frames = clean_frames()
    action = frames.action.copy()
    action[:, 18] = -1.972222  # URDF left_wrist_roll; the layout says -1.97222
    assert qa(with_(frames, action=action), qa_config).decision == "pass"


def test_a_nan_rejects_without_judging_limits_or_jumps_on_it(qa_config: QAConfig) -> None:
    names = {c.name for c in qa(broken("finite_values"), qa_config).checks}
    assert "joint_limits" not in names and not any(n.startswith("action_jump") for n in names)


def test_video_frames_against_rows(qa_config: QAConfig) -> None:
    one_off = with_(clean_frames(), video_frames={"cam": 21})
    assert failed(qa(one_off, qa_config)) == {"video_rows_match"}  # psi-data: exactly equal
    assert failed(qa(one_off, qa_config, S1)) == set()  # generic sync allows 1 frame
    two_off = with_(clean_frames(), video_frames={"cam": 18})
    assert failed(qa(two_off, qa_config, S1)) == {"image_state_sync"}
    assert qa(two_off, qa_config, S1).decision == "reject"


def test_a_heading_crossing_pi_is_no_jump(qa_config: QAConfig) -> None:
    frames = clean_frames()
    action = frames.action.copy()
    action[:, 35] = np.where(np.arange(20) < 10, 3.14, -3.14)
    assert qa(with_(frames, action=action), qa_config).decision == "pass"
    assert episode_action_jumps(with_(frames, action=action), qa_config.groups)["target_yaw"] > 6


def test_lineage_a_generated_episode_needs(qa_config: QAConfig) -> None:
    report = qa(clean_frames(), qa_config, S1, lineage=lineage_of(seed=None, version=None))
    assert report.decision == "quarantine"
    reason = "lineage (D6): missing lineage fields = 2 > 0 (seed, generator_version)"
    assert report.reasons == [reason]


@pytest.mark.parametrize(("seed", "decision"), [(999_999, "pass"), (1_000_000, "reject"),
                                                (2_000_124, "reject")])
def test_a_seed_outside_the_train_range_is_rejected(
    qa_config: QAConfig, seed: int, decision: str
) -> None:
    report = qa(clean_frames(), qa_config, S1, lineage=lineage_of(seed=seed))
    assert report.decision == decision
    assert ("split_seed" in failed(report)) == (decision == "reject")


def replay(mode: str, issues: int = 0, success: bool | None = None) -> ReplayReport:
    found = [ReplayIssue(code="state_off", frames=[3], detail="joint 17") for _ in range(issues)]
    return ReplayReport(episode_id="ep_1", mode=mode, issues=found, sim_success=success)  # type: ignore[arg-type]


def test_replay_kinematic_off_rejects_dynamic_off_flags(qa_config: QAConfig) -> None:
    kinematic = qa(clean_frames(), qa_config, replay=replay("kinematic", 1))
    assert (kinematic.decision, failed(kinematic)) == ("reject", {"replay_kinematic"})
    dynamic = qa(clean_frames(), qa_config, replay=[replay("kinematic"), replay("dynamic", 2)])
    assert (dynamic.decision, failed(dynamic)) == ("flag", {"replay_dynamic"})


def test_a_failed_dynamic_replay_only_flags(qa_config: QAConfig) -> None:
    # DA-17 AC 3, PO 4/11/2026: open-loop replay success is no quality label.
    teleop = qa(clean_frames(), qa_config, replay=replay("dynamic", success=False))
    assert (teleop.decision, failed(teleop)) == ("flag", {"task_success"})
    generated = qa(clean_frames(), qa_config, S1, replay=replay("dynamic", success=False))
    assert (generated.decision, failed(generated)) == ("flag", {"replay_success"})
    assert generated.reasons[0].startswith("replay_success (D8)")


def test_without_a_replay_report_the_config_decides(qa_config: QAConfig) -> None:
    names = {c.name for c in qa(clean_frames(), qa_config, S1).checks}
    assert not names & {"replay_kinematic", "replay_dynamic", "replay_success"}  # skip

    rules = dict(qa_config.checks)
    rules["replay_success"] = dataclasses.replace(rules["replay_success"], when_missing="flag")
    strict = dataclasses.replace(qa_config, checks=rules)
    report = qa(clean_frames(), strict, S1)
    assert report.decision == "flag"
    assert report.reasons == ["replay_success (D8): no ReplayReport for the episode"]


def test_a_replay_report_of_another_episode_is_refused(qa_config: QAConfig) -> None:
    other = replay("dynamic").model_copy(update={"episode_id": "ep_2"})
    with pytest.raises(ValueError, match="ReplayReport of ep_2"):
        qa(clean_frames(), qa_config, replay=other)


def test_calibration_takes_the_quantile_of_each_episode_largest_jump(qa_config: QAConfig) -> None:
    episodes = []
    for i, step in enumerate([0.01, 0.02, 0.04]):
        frames = clean_frames(i)
        action = frames.action.copy()
        action[:, 14] = np.arange(20) * step
        episodes.append(with_(frames, action=action))
    thresholds = calibrate_action_jump(episodes, qa_config.groups, 0.5)
    assert thresholds["arm"] == pytest.approx(0.02)
    assert thresholds["hand"] == 0.0


def write_stats(root: Path, frames: list[EpisodeFrames], shift: float) -> None:
    def block(values: NDArray[Any]) -> dict[str, list[float]]:
        data = values.reshape(len(values), -1).astype(np.float64)
        return {"mean": (data.mean(0) + shift).tolist(), "std": data.std(0).tolist(),
                "min": data.min(0).tolist(), "max": data.max(0).tolist()}

    (root / "meta").mkdir(parents=True)
    states = np.concatenate([f.states for f in frames])
    action = np.concatenate([f.action for f in frames])
    stats = {"states": block(states), "action": block(action)}
    (root / "meta" / "stats.json").write_text(json.dumps(stats))
    rows = [{"episode_index": f.episode_index,
             "stats": {"action": block(f.action), "timestamp": block(f.timestamp)}}
            for f in frames]
    (root / "meta" / "episodes_stats.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.mark.parametrize(("shift", "passed"), [(0.0, True), (3.6e-4, False)])
def test_shipped_stats_against_the_dataset_own_frames(
    tmp_path: Path, qa_config: QAConfig, shift: float, passed: bool
) -> None:
    frames = [clean_frames(0), clean_frames(1, length=30)]
    write_stats(tmp_path, frames, shift)
    findings = {f.check.name: f for f in dataset_checks(tmp_path, frames, qa_config)}
    assert set(findings) == {"stats_json.states", "stats_json.action", "episodes_stats.action",
                             "episodes_stats.timestamp"}
    assert all(f.check.passed == passed and f.code == "D4" for f in findings.values())
    if not passed:
        assert findings["stats_json.states"].check.value == pytest.approx(3.6e-4)
        assert "at states.mean[0]" in findings["stats_json.states"].detail
        assert "at episode 0 action.mean[0]" in findings["episodes_stats.action"].detail
