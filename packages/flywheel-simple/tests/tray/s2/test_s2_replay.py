"""The replay operator turns recorded frames back into PICO signals (DA-35 task 9)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from flywheel_simple.tray.pico.operator import Calibration, OperatorConfig
from flywheel_simple.tray.pico.virtual import teleop_to_robot
from flywheel_simple.tray.s2.jobs import S2Job, read_jobs
from flywheel_simple.tray.s2.parents import ParentDemo
from flywheel_simple.tray.s2.replay import (
    HAND_LEAD,
    NAV_LEAD,
    ReplayOperator,
    ReplayPlan,
    eef_matrices,
)
from flywheel_simple.tray.s2.segments import segment
from test_s2_segments import demo as cut_demo

DT = 0.02


def recorded(frames: int = 1675) -> ParentDemo:
    """The segment test's demo with wrist targets, sticks and hands that change per frame."""
    base = cut_demo(frames=frames)
    t = np.arange(frames) * DT
    eef = np.zeros((frames, 14))
    for k, side in ((0, 1.0), (7, -1.0)):
        eef[:, k] = 0.2 + 0.05 * np.sin(t)
        eef[:, k + 1] = side * (0.15 + 0.02 * np.cos(t))
        eef[:, k + 2] = 0.1 + 0.01 * t
        half = 0.3 * np.sin(0.5 * t) / 2  # rotation about z
        eef[:, k + 3], eef[:, k + 6] = np.cos(half), np.sin(half)
    eef[0] = 0.0  # the activation frame has no wrist data yet
    nav = base.navigate.copy()
    nav[:, 3] = 0.001 * np.arange(frames)
    closed = np.zeros((frames, 2), dtype=bool)
    closed[360:1592] = True
    return ParentDemo(**{**base.__dict__, "eef": eef, "navigate": nav, "hands_closed": closed})


def calibration() -> Calibration:
    ee0 = []
    for side in (1.0, -1.0):
        pose = np.eye(4)
        pose[:3, 3] = [0.2, side * 0.15, 0.1]
        ee0.append(pose)
    return Calibration(ee0=(ee0[0], ee0[1]), scale=1.2)


def operator(parent: ParentDemo) -> ReplayOperator:
    cfg = OperatorConfig.load()
    op = ReplayOperator(cfg.ctrl0(), done_wait_s=cfg.done_wait_s)
    op.reset(ReplayPlan(parent, segment(parent)))
    return op


def test_first_step_activates_at_the_activation_pose() -> None:
    op = operator(recorded())
    s = op.step(0.0, None)
    assert s.activate and not s.reset and s.stage == "activate"
    for got, want in zip(s.controllers, op.ctrl0):
        np.testing.assert_array_equal(got, want)


def test_frames_come_back_through_the_wrist_preprocessor() -> None:
    """Wrist targets on their own frame; hands and sticks ahead by what the recording lags."""
    parent, cal = recorded(), calibration()
    op = operator(parent)
    op.step(0.0, None)
    for tau in range(1, parent.frames):
        s = op.step(tau * DT, cal)
        targets = eef_matrices(parent.eef[tau])
        for k in range(2):
            back = teleop_to_robot(s.controllers[k], cal.ee0[k], op.ctrl0[k], cal.scale)
            np.testing.assert_allclose(back, targets[k], atol=1e-12)
        last = parent.frames - 1
        lead = [parent.navigate[min(tau + d, last), k] for k, d in enumerate(NAV_LEAD)]
        assert s.navigate_cmd == tuple(lead)
        assert s.closed == tuple(parent.hands_closed[min(tau + HAND_LEAD, last)])
        assert s.stage == segment(parent).segment_of(tau)


def test_after_the_last_frame_it_lets_go_then_gives_up() -> None:
    parent, cal = recorded(frames=1675), calibration()
    op = operator(parent)
    signals = [op.step(tau * DT, cal) for tau in range(parent.frames + 300)]
    end = signals[parent.frames]
    assert end.stage == "end" and end.navigate_cmd[:3] == (0.0, 0.0, 0.0)
    assert end.navigate_cmd[3] == parent.navigate[-1, 3]
    give_up = [k for k, s in enumerate(signals) if s.reset]
    assert give_up[0] == parent.frames + round(OperatorConfig.load().done_wait_s / DT)
    assert [stage for stage, _ in op.timeline] == ["activate", "K", "W", "P", "end", "give_up"]


def test_jobs_stay_in_the_train_domain(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    rows = [{"parent_id": "b/shard-00/0", "level": 1, "seed": 7, "gen_seed": 3}]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert read_jobs(path) == [S2Job(1, 7, "b/shard-00/0", 3)]
    with pytest.raises(ValueError, match="level 2"):
        S2Job(2, 7, "b/shard-00/0")
    with pytest.raises(ValueError, match="not a train seed"):
        S2Job(0, 1_000_000, "b/shard-00/0")
