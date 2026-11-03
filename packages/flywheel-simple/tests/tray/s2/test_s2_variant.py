"""A parent moved onto a new condition, and its closed-loop replay (DA-35 task 10, AC 5)."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.pico.operator import OperatorConfig
from flywheel_simple.tray.pico.virtual import teleop_to_robot
from flywheel_simple.tray.randomize import EpisodeSample, sample_episode
from flywheel_simple.tray.s2.config import S2Config
from flywheel_simple.tray.s2.jobs import sample_jobs
from flywheel_simple.tray.s2.parents import ParentDemo
from flywheel_simple.tray.s2.replay import ReplayOperator, eef_matrices
from flywheel_simple.tray.s2.segments import segment
from flywheel_simple.tray.s2.variant import (
    Planar,
    VariantPlan,
    base_frame,
    plan_variant,
    pose_matrix,
    stitch_for,
    yaw_of,
)
from test_s2_replay import DT, calibration, recorded


def walking_parent() -> ParentDemo:
    """The replay test's demo with a base that walks to table A, back and to table B."""
    demo = recorded()
    x = 0.4 + np.cumsum(demo.navigate[:, 0]) * DT * np.where(np.arange(demo.frames) < 523, 1, -1)
    pose = demo.base_pose.copy()
    pose[:, 0] = x
    turn = np.zeros(demo.frames)
    turn[600:760] = np.linspace(0, math.pi, 160)
    turn[760:] = math.pi
    pose[:, 3], pose[:, 6] = np.cos(turn / 2), np.sin(turn / 2)
    nav = demo.navigate.copy()
    nav[600:760, 2] = 0.6
    return replace(demo, base_pose=pose, navigate=nav)


def samples() -> tuple[EpisodeSample, EpisodeSample]:
    parent = sample_episode(TrayConfig.load(), 0, 0)
    moved = replace(
        parent,
        level=1,
        seed=7,
        tray_pose=Pose2D(parent.tray_pose.x - 0.03, 0.04, math.radians(8.0)),
        target_pose=Pose2D(parent.target_pose.x + 0.02, -0.05, math.radians(-6.0)),
    )
    return parent, moved


def plan(new: EpisodeSample | None = None, stitch_s: float = 0.5) -> VariantPlan:
    parent = walking_parent()
    old, moved = samples()
    return plan_variant(parent, segment(parent), old, moved if new is None else new, stitch_s)


def test_planar_between_takes_old_to_new() -> None:
    old, new = Pose2D(1.1, 0.0, 0.0), Pose2D(1.05, 0.04, 0.2)
    m = Planar.between(old, new).matrix() @ pose_matrix(np.array([1.1, 0, 0.85, 1, 0, 0, 0]))
    np.testing.assert_allclose(m[:2, 3], [new.x, new.y], atol=1e-12)
    assert math.isclose(math.atan2(m[1, 0], m[0, 0]), new.yaw)


def test_same_scene_is_the_identity() -> None:
    old, _ = samples()
    p = plan(new=old)
    assert all(abs(t.dx) + abs(t.dy) + abs(t.yaw) < 1e-12 for t in p.transforms)
    assert all(a == Planar() for a in p.anchors)
    parent = p.parent
    np.testing.assert_allclose(p.base_ref[:, :2], parent.base_pose[:, :2], atol=1e-12)
    for i in (300, 1500):  # tray and target anchors
        robot = np.linalg.inv(base_frame(parent.base_pose[i])) @ p.wrist_world[i, 0]
        np.testing.assert_allclose(robot, eef_matrices(parent.eef[i])[0], atol=1e-12)


def test_the_carried_tray_lands_on_the_moved_target() -> None:
    """A tray held T_K off the parent's grip, carried on the moved base path, ends at T_P."""
    p = plan()
    i, lift = p.cut.place_start, int(p.cut.step_frames[2])
    parent = p.parent
    base = p.transforms[i].matrix() @ base_frame(parent.base_pose[i])
    tray_new = base @ np.linalg.inv(base_frame(parent.base_pose[lift])) @ p.t_k.matrix()
    tray_new = tray_new @ pose_matrix(parent.tray_pose[lift])
    want = (
        p.t_p.matrix()
        @ base_frame(parent.base_pose[i])
        @ np.linalg.inv(base_frame(parent.base_pose[lift]))
        @ pose_matrix(parent.tray_pose[lift])
    )
    np.testing.assert_allclose(tray_new[:2, 3], want[:2, 3], atol=1e-9)


def test_hands_follow_the_tray_in_k_and_the_target_in_p() -> None:
    p = plan()
    old, new = samples()
    parent, cut = p.parent, p.cut

    def frame(pose: Pose2D) -> np.ndarray:
        return Planar.between(Pose2D(0, 0, 0), pose).matrix()

    cases = {
        cut.walk_a_end + 50: (old.tray_pose, new.tray_pose),
        cut.place_start + 50: (old.target_pose, new.target_pose),
    }
    assert cut.reach_start <= cut.walk_a_end + 50 < cut.grasp_end
    for i, (before, after) in cases.items():
        parent_world = base_frame(parent.base_pose[i]) @ eef_matrices(parent.eef[i])[1]
        rel_parent = np.linalg.inv(frame(before)) @ parent_world
        rel_variant = np.linalg.inv(frame(after)) @ p.wrist_world[i, 1]
        np.testing.assert_allclose(rel_variant, rel_parent, atol=1e-9)


def test_transform_changes_smoothly() -> None:
    p = plan()
    steps = [
        (abs(b.dx - a.dx) + abs(b.dy - a.dy), abs(b.yaw - a.yaw))
        for a, b in zip(p.transforms, p.transforms[1:])
    ]
    assert max(s[0] for s in steps) < 3e-3 and max(s[1] for s in steps) < 3e-3
    # The base keeps the parent's path through K and is moved during the carry only.
    assert all(t == Planar() for t in p.transforms[: p.cut.k_end])
    assert p.anchors[p.cut.walk_a_end] == p.t_k and p.anchors[-1] == p.t_p


def test_world_weight_ramps_at_anchor_switches() -> None:
    p = plan(stitch_s=0.5)
    cut = p.cut
    w = p.world_weight
    assert cut.reach_start > 0
    assert w[: cut.reach_start].max() == 0.0
    assert w[cut.reach_start + 24] == 1.0 and 0.0 < w[cut.reach_start + 10] < 1.0
    assert w[cut.grasp_end + 25 : cut.place_start].max() == 0.0
    assert w[cut.place_start + 24 :].min() == 1.0


def test_the_base_turn_is_spread_over_the_carry() -> None:
    p = plan()
    total = float(np.sum(p.yaw_rate)) / 50
    assert math.isclose(total, p.t_p.yaw - p.t_k.yaw, abs_tol=1e-9)
    assert not p.yaw_rate[: p.cut.k_end].any()  # the base turns only while carrying


def test_variant_is_deterministic() -> None:
    a, b = plan(), plan()
    np.testing.assert_array_equal(a.wrist_world, b.wrist_world)
    np.testing.assert_array_equal(a.base_ref, b.base_ref)
    assert stitch_for(5, 0.4, 0.6) == stitch_for(5, 0.4, 0.6) != stitch_for(6, 0.4, 0.6)
    assert 0.4 <= stitch_for(5, 0.4, 0.6) <= 0.6


def operator(p: VariantPlan) -> ReplayOperator:
    cfg = OperatorConfig.load()
    op = ReplayOperator(cfg.ctrl0(), cfg.done_wait_s, cfg=S2Config.load())
    op.reset(p, joystick_accel=100.0)  # no rate limit: compare sticks directly
    return op


def ref_pose(p: VariantPlan, i: int, dx: float = 0.0) -> np.ndarray:
    x, y, yaw = p.base_ref[i]
    return np.array([x + dx, y, 0.75, math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)])


def test_on_reference_the_hands_get_the_parent_targets() -> None:
    p, cal = plan(), calibration()
    op = operator(p)
    op.step(0.0, None, ref_pose(p, 0))
    t = 0.0
    while op.ref < p.cut.walk_a_end + 60:
        t += DT
        s = op.step(t, cal, ref_pose(p, min(op.ref + 1, p.frames - 1)))
    i = op.ref
    want = np.linalg.inv(base_frame(ref_pose(p, i))) @ p.wrist_world[i, 0]
    got = teleop_to_robot(s.controllers[0], cal.ee0[0], op.ctrl0[0], cal.scale)
    np.testing.assert_allclose(got, want, atol=1e-9)
    assert op.gate_waits == []  # no gate at table A: the base keeps the parent's path


def test_a_gate_holds_and_steps_onto_the_reference() -> None:
    p, cal = plan(), calibration()
    op = operator(p)
    cfg = S2Config.load()
    op.step(0.0, None, ref_pose(p, 0))
    t, gate = 0.0, p.gates[0]
    while op.ref < gate:
        t += DT
        op.step(t, cal, ref_pose(p, min(op.ref + 1, p.frames - 1)))
    held = []
    for _ in range(round(cfg.gate_max_s / DT) + 5):
        t += DT
        s = op.step(t, cal, ref_pose(p, gate, dx=-0.10))  # 10 cm behind
        held.append((op.ref, s.navigate_cmd[0], s.stage, math.hypot(*s.navigate_cmd[:2])))
    assert all(h[0] == gate for h in held[:-10])
    assert held[0][2] == "gate"
    heading = p.base_ref[gate, 2]
    assert math.copysign(1, held[5][1]) == math.copysign(1, math.cos(heading))
    assert held[5][3] >= cfg.step_speed_min - 1e-9
    (wait,) = op.gate_waits
    assert wait[:3] == (gate, pytest.approx(cfg.gate_max_s, abs=0.03), False)
    assert wait[5] == pytest.approx(0.10, abs=0.01)  # still 10 cm off when it gave up


def jobs_parents() -> list[dict[str, object]]:
    return [{"parent_id": f"b/shard-00/{i}", "level": i % 2} for i in range(6)]


def test_jobs_are_drawn_from_their_base() -> None:
    cfg = S2Config.load()
    seeds = (cfg.cond_seed_min, cfg.cond_seed_max)
    a = sample_jobs(jobs_parents(), 40, 0, cfg.level1_share, seeds)
    assert a == sample_jobs(jobs_parents(), 40, 0, cfg.level1_share, seeds)
    assert a != sample_jobs(jobs_parents(), 40, 1, cfg.level1_share, seeds)
    level = {p["parent_id"]: p["level"] for p in jobs_parents()}
    assert not any(j.level == 0 and level[j.parent_id] == 0 for j in a)
    scenes = [(j.parent_id, j.level, j.seed if j.level else 0) for j in a]
    assert len(set(scenes)) == len(scenes)
    assert all(cfg.cond_seed_min <= j.seed <= cfg.cond_seed_max for j in a)


def test_too_few_distinct_scenes_is_an_error() -> None:
    only_level0 = [{"parent_id": "b/shard-00/0", "level": 0}]
    with pytest.raises(RuntimeError, match="distinct"):
        sample_jobs(only_level0, 5, 0, 0.0, (200000, 200001))


def test_yaw_of_reads_the_quaternion() -> None:
    p = plan()
    assert math.isclose(yaw_of(ref_pose(p, 600)), p.base_ref[600, 2])


def test_an_identity_variant_sends_the_parent_sticks() -> None:
    old, _ = samples()
    p, cal = plan(new=old), calibration()
    op = operator(p)
    op.step(0.0, None, ref_pose(p, 0))
    t, integral = 0.0, 0.0
    while op.ref < p.cut.k_end + 300:
        t += DT
        s = op.step(t, cal, ref_pose(p, min(op.ref + 1, p.frames - 1)))
        if s.stage == "gate":
            integral = s.navigate_cmd[3]
            continue
        sent = op._lead(p, op.ref)
        np.testing.assert_allclose(s.navigate_cmd[:3], sent[:3], atol=1e-12)
        integral = math.atan2(math.sin(integral + sent[2] * DT), math.cos(integral + sent[2] * DT))
        assert math.isclose(s.navigate_cmd[3], integral, abs_tol=1e-12)


def expected_tray(p: VariantPlan, i: int) -> np.ndarray:
    m = p.anchors[i].matrix() @ pose_matrix(p.parent.tray_pose[i])
    yaw = math.atan2(m[1, 0], m[0, 0])
    return np.array([m[0, 3], m[1, 3], m[2, 3], math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)])


def play_to_place(p: VariantPlan, tray_offset: tuple[float, float]) -> ReplayOperator:
    """Steps on the base reference up to place_start, the tray held `tray_offset` off."""
    op, cal = operator(p), calibration()
    op.step(0.0, None, ref_pose(p, 0))
    t = 0.0
    while op.ref < p.cut.place_start:
        t += DT
        i = min(op.ref + 1, p.frames - 1)
        tray = expected_tray(p, i)
        tray[:2] += tray_offset
        op.step(t, cal, ref_pose(p, i), tray)
    return op


def test_placing_hands_take_up_where_the_held_tray_is_off() -> None:
    p = plan()
    op = play_to_place(p, (0.02, -0.01))
    assert op.place_fix is not None
    assert (op.place_fix.dx, op.place_fix.dy) == (pytest.approx(-0.02), pytest.approx(0.01))
    far = play_to_place(p, (0.30, 0.0)).place_fix
    assert far is not None and math.hypot(far.dx, far.dy) == pytest.approx(0.05)
