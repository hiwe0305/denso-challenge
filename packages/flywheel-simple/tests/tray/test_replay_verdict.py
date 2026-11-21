"""Replay QA verdicts from a replay outcome and the recorded final tray pose; no simulator."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from flywheel_simple.tray import replay_qa as rq
from flywheel_simple.tray.replay_qa import TRAY_TOL_M, verdict, yaw_gap_deg

RECORDED = [-1.2, 0.05, 0.85, 1.0, 0.0, 0.0, 0.0]  # pos xyz, quat wxyz (yaw 0)


def _outcome(dx: float = 0.0, yaw: float = 0.0, success: bool = True) -> dict:  # type: ignore[type-arg]
    return {
        "success": success,
        "tray_pos": [RECORDED[0] + dx, RECORDED[1], RECORDED[2]],
        "tray_quat": [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)],
    }


def test_matching_replay_passes() -> None:
    v = verdict(3, 101, RECORDED, _outcome(dx=0.005))
    assert v.passed and v.reason == "pass" and v.tray_error_m == pytest.approx(0.005)


def test_half_turn_counts_as_the_same_pose() -> None:
    assert yaw_gap_deg(math.pi, 0.0) == pytest.approx(0.0, abs=1e-9)
    assert verdict(0, 1, RECORDED, _outcome(yaw=math.pi)).passed


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (None, "not_replayed"),
        (_outcome(success=False), "not_success"),
        (_outcome(dx=TRAY_TOL_M + 0.005), "tray_moved"),
        (_outcome(yaw=math.radians(10)), "tray_moved"),
    ],
)
def test_failures_name_their_reason(outcome: dict | None, reason: str) -> None:  # type: ignore[type-arg]
    v = verdict(0, 1, RECORDED, outcome)
    assert not v.passed and v.reason == reason


def _replay(monkeypatch: pytest.MonkeyPatch, work: Path, seeds: list[int], log: str) -> None:
    """Two recorded episodes (seeds 101, 102); the replay returns outcomes for `seeds`."""

    def run_replay(raw_root: Path, work: Path) -> Path:
        work.mkdir(parents=True, exist_ok=True)
        (work / "replay.log").write_text(log)
        out = work / "replay_outcomes.jsonl"
        out.write_text("".join(json.dumps({"seed": s, **_outcome()}) + "\n" for s in seeds))
        return out

    monkeypatch.setattr(rq, "run_replay", run_replay)
    monkeypatch.setattr(rq, "recorded_finals", lambda raw: {0: (101, RECORDED), 1: (102, RECORDED)})


def test_a_crashed_replay_writes_no_verdicts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # SIMPLE's replay CLI prints the error and exits 0; the missing outcome must not
    # read as a QA miss.
    work = tmp_path / "replay"
    work.mkdir()
    (work / "replay_qa.jsonl").write_text("stale\n")
    crash = "Episodes: 0/2\nAn error occurred: Offscreen framebuffer is not complete\n"
    _replay(monkeypatch, work, [101], crash)
    with pytest.raises(rq.ReplayIncomplete, match=r"1/2 episodes \[1\].*framebuffer"):
        rq.replay_qa(tmp_path / "raw", work)
    assert not (work / "replay_qa.jsonl").exists()


def test_a_full_replay_writes_one_verdict_per_episode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _replay(monkeypatch, tmp_path / "replay", [101, 102], "")
    verdicts = rq.replay_qa(tmp_path / "raw", tmp_path / "replay")
    assert [v.reason for v in verdicts] == ["pass", "pass"]
    assert len((tmp_path / "replay" / "replay_qa.jsonl").read_text().splitlines()) == 2


def _episodes(root: Path, uids: list[str]) -> Path:
    meta = root / "meta"
    meta.mkdir(parents=True)
    rows = [
        {"episode_index": i, "environment_config": json.dumps({"uid": uid})}
        for i, uid in enumerate(uids)
    ]
    (meta / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return root


def test_jig_episodes_replay_in_the_jig_scene(tmp_path: Path) -> None:
    # DA-41: through `run` they were rebuilt in DA-33's scene (no jig, target jittered).
    raw = _episodes(tmp_path, [rq.JIG_TASK_UID, rq.JIG_TASK_UID])
    assert rq.replay_target(raw) == ("flywheel_simple.tray.jig_run", rq.JIG_ENV_ID)


def test_zone1_episodes_replay_as_before(tmp_path: Path) -> None:
    raw = _episodes(tmp_path, ["g1_wholebody_tray_transfer_teleop"])
    assert rq.replay_target(raw) == ("flywheel_simple.tray.run", rq.ENV_ID)


def test_a_batch_mixing_scenes_is_refused(tmp_path: Path) -> None:
    raw = _episodes(tmp_path, [rq.JIG_TASK_UID, "g1_wholebody_tray_transfer_teleop"])
    with pytest.raises(ValueError, match="mixes task uids"):
        rq.replay_target(raw)


def test_jig_ids_match_the_jig_task() -> None:
    # jig_task needs SIMPLE to import, so its constants are read from the source.
    source = (Path(rq.__file__).parent / "jig_task.py").read_text()
    assert f'JIG_TASK_UID = "{rq.JIG_TASK_UID}"' in source
    assert f'JIG_ENV_ID = "{rq.JIG_ENV_ID}"' in source
