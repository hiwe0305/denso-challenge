"""Calibrated replay thresholds and configs/data/replay.yaml (DA-17 task 3, AC 3)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from flywheel.data.ingest.lerobot import iter_episodes
from flywheel.data.replay_check.cli import app
from flywheel.data.replay_check.dynamic import ReplayOutcome, report_from_outcome
from flywheel.data.replay_check.kinematic import check_kinematic
from flywheel.data.replay_check.thresholds import (
    _round,
    calibrate,
    dump_thresholds,
    load_thresholds,
)
from replay_data import FPS, REPLAY_YAML, clean_frames, g1_layout, outcome_line, write_dataset
from typer.testing import CliRunner

LAYOUT = g1_layout()


@pytest.fixture(autouse=True)
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FW_ROOT", str(tmp_path / "store"))
    return tmp_path / "store"


def outcomes(count: int) -> list[ReplayOutcome]:
    return [ReplayOutcome.from_json(outcome_line(i)) for i in range(count)]


def test_calibration_passes_every_clean_episode_it_saw() -> None:
    frames = [clean_frames(i) for i in range(12)]
    th = calibrate(outcomes(12), frames=frames, layout=LAYOUT)
    for f in frames:
        assert check_kinematic(f, LAYOUT, th, episode_id="e", fps=FPS).issues == []
    assert th.kinematic_quantile == 1.0 and th.dynamic_quantile == 0.99
    assert set(th.mapping_correlation) == {d.name for d in LAYOUT.dimensions[:31]}
    assert max(th.mapping_correlation.values()) == 0.5  # the ceiling, not the clean ~1.0
    assert th.limit_tolerance == {"action": 1e-5, "states": 1e-5}  # the floor


def test_dynamic_thresholds_are_the_p99_of_successful_replays() -> None:
    lines = [ReplayOutcome.from_json(outcome_line(i)) for i in range(100)]
    lines.append(ReplayOutcome.from_json(outcome_line(100, success=False,
                                                      state_error_by_group={"hand": 9.0})))
    th = calibrate(lines, frames=[clean_frames(0)], layout=LAYOUT)
    assert th.state_error["hand"] == pytest.approx(0.05 + 0.001 * 98.01)
    assert th.hand_event_offset_steps == 1
    over = ReplayOutcome.from_json(outcome_line(99))
    assert [i.code for i in report_from_outcome("e", over, th).issues] == ["state_error"]


def test_few_episodes_give_no_mapping_threshold() -> None:
    th = calibrate(outcomes(3), frames=[clean_frames(i) for i in range(3)], layout=LAYOUT)
    assert th.mapping_correlation == {}


def test_calibration_without_a_successful_replay_raises() -> None:
    failed = [ReplayOutcome.from_json(outcome_line(0, success=False))]
    with pytest.raises(ValueError, match="successful replays"):
        calibrate(failed, frames=[clean_frames(0)], layout=LAYOUT)


def test_dump_reads_back_with_a_hash(tmp_path: Path) -> None:
    th = calibrate(outcomes(12), frames=[clean_frames(i) for i in range(12)], layout=LAYOUT)
    path = tmp_path / "replay.yaml"
    path.write_text(dump_thresholds(th, "test set"))
    loaded = load_thresholds(path)
    assert loaded.version.startswith("replay-1@") and len(loaded.version) == len("replay-1@") + 12
    for name in ("unit_ratio", "state_error", "limit_tolerance"):
        for key, value in getattr(th, name).items():
            assert value <= getattr(loaded, name)[key] <= value * (1 + 1e-5)
    for key, value in th.mapping_correlation.items():
        assert value - 1e-5 <= loaded.mapping_correlation[key] <= value


@pytest.mark.parametrize("value", [0.0634000003, 1.23456789, -0.40567891, 7.8e-7])
def test_rounding_goes_away_from_the_clean_data(value: float) -> None:
    assert _round(value, up=True) >= value and _round(value, up=False) <= value
    assert math.isclose(_round(value, up=True), value, rel_tol=1e-5)


def test_the_committed_thresholds_load() -> None:
    th = load_thresholds(REPLAY_YAML)
    assert th.version.startswith("replay-1@") and th.dynamic_quantile == 0.99
    assert set(th.state_error) == {"hand", "arm", "torso_rpy"}


def test_calibrate_command_writes_the_file_and_a_ledger_pair(tmp_path: Path, store: Path) -> None:
    root = write_dataset(tmp_path / "psi", [clean_frames(i) for i in range(12)])
    lines = tmp_path / "replay_outcomes.jsonl"
    lines.write_text("".join(outcome_line(f.episode_index) + "\n" for f in iter_episodes(root)))
    out = tmp_path / "replay.yaml"
    args = ["calibrate", str(root), "--outcomes", str(lines), "--out", str(out),
            "--calibration", "12 clean test episodes"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "12/12 replays succeeded" in result.output
    assert load_thresholds(out).version in result.output
    assert out.read_text().startswith("# Thresholds of the replay checks")
    rows = list(store.glob("sites/*/runs/g0-DA-17-*/job_replay_calibrate_*/ledger.jsonl"))
    assert len(rows) == 1 and len(rows[0].read_text().splitlines()) == 2


def test_calibrate_command_refuses_an_episode_without_outcome(tmp_path: Path) -> None:
    root = write_dataset(tmp_path / "psi", [clean_frames(i) for i in range(2)])
    lines = tmp_path / "replay_outcomes.jsonl"
    lines.write_text(outcome_line(0) + "\n")
    args = ["calibrate", str(root), "--outcomes", str(lines), "--out", str(tmp_path / "r.yaml"),
            "--calibration", "x"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2 and "no outcome for episodes [1]" in result.output
