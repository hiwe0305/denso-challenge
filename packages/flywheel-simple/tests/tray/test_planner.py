"""Tray planner phase machine (DA-33 AC 2) in a toy world; pure, runs in the workspace."""

from __future__ import annotations

import math

import numpy as np
import pytest
from flywheel_simple.tray.planner import Phase, PlannerConfig, TrayPlanner, base_transform
from flywheel_simple.tray.predicates import StepTracker
from toy_world import PELVIS_Z, Record, ToyWorld

MIRROR = np.diag([1.0, -1.0, 1.0])


def ordered_unique(phases: list[Phase]) -> list[Phase]:
    out: list[Phase] = []
    for p in phases:
        if not out or out[-1] != p:
            out.append(p)
    return out


def in_tray_frame(record: Record, wrist: np.ndarray) -> np.ndarray:
    pos, quat = record.state.tray_pos, record.state.tray_quat
    yaw = 2 * math.atan2(quat[3], quat[0])
    c, s = math.cos(yaw), math.sin(yaw)
    tray = np.eye(4)
    tray[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    tray[:3, 3] = pos
    world = base_transform(record.base, PELVIS_Z) @ wrist
    return np.asarray(np.linalg.inv(tray) @ world)


def test_planner_config_loads_every_key() -> None:
    cfg = PlannerConfig.load()
    assert cfg.standoff > 0 and cfg.timeout_approach_a > 0 and cfg.turn_rate <= 1.0


def test_toy_world_episode_visits_phases_in_order_and_finishes() -> None:
    phases = [r.cmd.phase for r in ToyWorld().run()]
    assert ordered_unique(phases) == [p for p in Phase if p is not Phase.ABORT]


@pytest.mark.parametrize(("level", "seed"), [(0, 0), (1, 1), (1, 2), (1, 3)])
def test_toy_world_episode_succeeds(level: int, seed: int) -> None:
    records = ToyWorld(level=level, seed=seed).run()
    assert records[-1].cmd.phase is Phase.DONE
    assert records[-1].report.success and records[-1].report.failure is None
    assert all(records[-1].report.steps)


def test_wrists_stay_fixed_in_base_frame_while_carrying() -> None:
    cmds = [r.cmd for r in ToyWorld().run() if r.cmd.phase in (Phase.TURN, Phase.CARRY)]
    assert cmds
    for wrists in ([c.left_wrist for c in cmds], [c.right_wrist for c in cmds]):
        assert max(float(np.max(np.abs(w - wrists[0]))) for w in wrists) < 1e-9


@pytest.mark.parametrize("seed", [0, 1])
def test_grasp_targets_mirror_about_the_tray(seed: int) -> None:
    # The last GRASP command: the first still carries the decaying REACH jump (D-20).
    records = ToyWorld(level=1, seed=seed).run()
    record = [r for r in records if r.cmd.phase is Phase.GRASP][-1]
    left = in_tray_frame(record, record.cmd.left_wrist)
    right = in_tray_frame(record, record.cmd.right_wrist)
    assert np.allclose(left[:3, 3], MIRROR @ right[:3, 3], atol=1e-6)
    assert np.allclose(left[:3, :3], MIRROR @ right[:3, :3] @ MIRROR, atol=1e-6)


def test_contact_loss_while_turning_aborts() -> None:
    world = ToyWorld()
    world.drop_left_contact_at(Phase.TURN)
    records = world.run()
    assert records[-1].cmd.phase is Phase.ABORT
    assert records[-1].cmd.abort_reason == "L-ONE-HAND"
    assert Phase.CARRY not in [r.cmd.phase for r in records]


def test_phase_timeout_aborts_with_reason() -> None:
    world = ToyWorld()
    world.block_base()
    cmd = world.run()[-1].cmd
    assert cmd.phase is Phase.ABORT and cmd.abort_reason == "timeout:APPROACH_A"


def test_palm_sag_is_corrected_while_reaching_and_lifting() -> None:
    # SIMPLE's arm PD has no gravity feed-forward: palms sit 2-3 cm under the
    # commanded wrists (docs/g0/tray/upper-body.md).
    world = ToyWorld(palm_sag=0.03)
    records = world.run()
    assert records[-1].cmd.phase is Phase.DONE and records[-1].report.success
    # Grasp targets freeze while the hands close, so the gripped tray is not chased upwards.
    carried = [r.state.tray_pos[2] for r in records if r.cmd.phase is Phase.CARRY]
    top = world.cfg.table_height + world.planner_cfg.lift_height
    assert max(carried) <= top + world.planner_cfg.palm_correction_max


def test_aborted_and_done_commands_stand_still() -> None:
    records = ToyWorld().run()
    done = [r.cmd for r in records if r.cmd.phase is Phase.DONE]
    assert done and all(c.nav == (0.0, 0.0, 0.0) for c in done)


def test_reset_starts_a_new_episode() -> None:
    world = ToyWorld()
    planner = TrayPlanner(world.planner_cfg, world.cfg, world.sample)
    state = world._state()
    report = StepTracker(world.cfg, world.sample).update(state)
    planner.step(state, world.base, report)
    planner.phase = Phase.CARRY
    planner.reset()
    assert planner.step(state, world.base, report).phase is Phase.APPROACH_A


def test_hands_shift_the_tray_onto_the_target_while_lowering() -> None:
    from dataclasses import replace

    # Without sideways steps the walk ends off target in y; the arms take up the rest.
    def miss(shift_max: float) -> float:
        cfg = replace(PlannerConfig.load(), place_shift_max=shift_max)
        world = ToyWorld(level=1, seed=2, vy_scale=0.0, planner_cfg=cfg)
        world.run()
        target = world.sample.target_pose
        return math.hypot(world.tray_pos[0] - target.x, world.tray_pos[1] - target.y)

    # Seed 2 ends 5.9 cm off (tolerance 5 cm); a 5 cm shift brings it under 1.5 cm.
    assert miss(0.0) > 0.05 and miss(0.05) < 0.015


def test_pinch_grasp_closes_only_once_the_hands_are_there() -> None:
    from dataclasses import replace

    from flywheel_simple.tray.planner import grasp_palms_world, tray_yaw_of

    # A finger pinch slides in open and closes at the handles; a squeeze closes at once.
    cfg = replace(PlannerConfig.load(), hand_closure_open=0.0, squeeze=0.0, grasp_close_after=5.0)
    world = ToyWorld(planner_cfg=cfg)
    records = world.run()
    grasp = [r for r in records if r.cmd.phase is Phase.GRASP]
    assert grasp[0].cmd.hand_closure == (0.0, 0.0) and grasp[-1].cmd.hand_closure == (1.0, 1.0)
    assert records[-1].cmd.phase is Phase.DONE and records[-1].report.success
    # Closing starts only once the commanded palms have arrived, not on the way.
    closing = next(r for r in grasp if r.cmd.hand_closure[0] > 0.0)
    state = grasp[0].state
    targets = grasp_palms_world(cfg, world.cfg, state.tray_pos, tray_yaw_of(state.tray_quat))
    for palm, target in zip(commanded_palms_world(world, closing), targets):
        assert float(np.linalg.norm(palm - target)) < 0.002


def test_levelling_reads_pitch_about_the_handle_axis() -> None:
    from flywheel_simple.tray.planner import _axis_angle, _pitch

    angle = math.radians(12.0)
    about_y = np.array([math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0])
    about_x = np.array([math.cos(angle / 2), math.sin(angle / 2), 0.0, 0.0])
    assert _pitch(about_y) == pytest.approx(angle) and _pitch(about_x) == pytest.approx(0.0)
    turn = _axis_angle(np.array([0.0, 1.0, 0.0]), angle)
    assert np.allclose(turn @ np.array([1.0, 0.0, 0.0]), [math.cos(angle), 0.0, -math.sin(angle)])


def palm_path(world: ToyWorld, records: list[Record], side: int = 0) -> np.ndarray:
    """Commanded palm point per step in the base frame, starting at the start wrists."""
    offset = np.r_[world.planner_cfg.palm_offsets[side], 1.0]
    wrists = [world.start_wrists[side]] + [
        r.cmd.left_wrist if side == 0 else r.cmd.right_wrist for r in records
    ]
    return np.array([(w @ offset)[:3] for w in wrists])


def rotation_steps_deg(world: ToyWorld, records: list[Record], side: int) -> np.ndarray:
    wrists = [world.start_wrists[side]] + [
        r.cmd.left_wrist if side == 0 else r.cmd.right_wrist for r in records
    ]
    cos = [(np.trace(a[:3, :3].T @ b[:3, :3]) - 1) / 2 for a, b in zip(wrists, wrists[1:])]
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


@pytest.mark.parametrize(("level", "seed"), [(0, 0), (1, 1)])
def test_commanded_wrists_never_jump(level: int, seed: int) -> None:
    # decoupled_wbc interpolates one control step ahead, so a target step is an arm
    # lunge (11.7 cm in one 20 ms step at REACH measured on seed 22, level 1).
    world = ToyWorld(level=level, seed=seed)
    records = world.run()
    assert records[-1].cmd.phase is Phase.DONE
    for side in (0, 1):
        steps = np.linalg.norm(np.diff(palm_path(world, records, side), axis=0), axis=1)
        assert float(np.max(steps)) < 0.015  # m per 20 ms step
        assert float(np.max(rotation_steps_deg(world, records, side))) < 3.0


def test_reaching_has_a_bell_shaped_speed_profile() -> None:
    # Minimum jerk: speed zero at both ends, one peak in the middle (human reaching).
    world = ToyWorld()
    records = world.run()
    reach = [r for r in records if r.cmd.phase is Phase.APPROACH_A]
    speed = np.linalg.norm(np.diff(palm_path(world, reach), axis=0), axis=1) / 0.02
    moving = np.flatnonzero(speed > 1e-9)
    assert moving.size and moving[-1] + 1 < speed.size  # settles before APPROACH_A ends
    profile = speed[: moving[-1] + 1]
    peak = int(np.argmax(profile))
    assert profile[0] < 0.05 * profile[peak] and profile[-1] < 0.1 * profile[peak]
    assert 0.4 <= peak / (profile.size - 1) <= 0.6
    assert np.all(np.diff(profile[: peak + 1]) >= -1e-9)
    assert np.all(np.diff(profile[peak:]) <= 1e-9)
    assert profile.size * 0.02 >= world.planner_cfg.smooth_min_s - 0.02


def commanded_palms_world(world: ToyWorld, record: Record) -> list[np.ndarray]:
    offsets = world.planner_cfg.palm_offsets
    to_world = base_transform(record.base, PELVIS_Z)
    wrists = (record.cmd.left_wrist, record.cmd.right_wrist)
    return [(to_world @ w @ np.r_[o, 1.0])[:3] for w, o in zip(wrists, offsets)]


def test_reach_ends_only_once_the_hands_have_arrived() -> None:
    # Sagging arms put the measured palms within palm_tol of the pre-grasp pose while
    # the commanded ones were still on the way (seed 22, level 1: REACH ended after
    # 0.16 s and the hands cut down onto the handles). REACH waits for the end of the
    # trajectory, then for the measured palms at the final target.
    from flywheel_simple.tray.planner import grasp_palms_world, tray_yaw_of

    world = ToyWorld(level=1, seed=1)
    records = world.run()
    k = next(i for i, r in enumerate(records) if r.cmd.phase is Phase.GRASP)
    last_reach = records[k - 1]
    cfg = world.planner_cfg
    state = last_reach.state
    outside = grasp_palms_world(
        cfg, world.cfg, state.tray_pos, tray_yaw_of(state.tray_quat), cfg.pregrasp_offset
    )
    above = np.array([0.0, 0.0, cfg.pregrasp_dz])
    for palm, target in zip(commanded_palms_world(world, last_reach), outside):
        assert float(np.linalg.norm(palm - (target + above))) < 0.002
    reach_s = sum(r.cmd.phase is Phase.REACH for r in records) * 0.02
    assert reach_s >= cfg.smooth_min_s - 0.02


def test_hands_close_and_open_gradually() -> None:
    records = ToyWorld().run()
    closure = np.array([r.cmd.hand_closure[0] for r in records])
    assert float(np.max(np.abs(np.diff(closure)))) <= 0.1
    assert np.any((closure > 0.05) & (closure < 0.95))
    assert float(np.max(closure)) == 1.0 and closure[-1] == records[0].cmd.hand_closure[0]


def test_release_opens_the_hands_before_moving_them_out() -> None:
    # Hands moving out while still opening dragged the tray by a hooked thumb (level 0
    # seed 0: 9.9 deg tilt, RELEASE timed out).
    world = ToyWorld()
    records = [r for r in world.run() if r.cmd.phase is Phase.RELEASE]
    opened = next(i for i, r in enumerate(records) if r.cmd.hand_closure[0] == 0.0)
    assert opened > 0
    for side in (0, 1):
        held = palm_path(world, records[: opened + 1], side)[1:]
        assert float(np.max(np.abs(held - held[0]))) < 0.002  # LOWER's last 1 mm step
        moved = palm_path(world, records, side)[1:]
        assert float(np.linalg.norm(moved[-1] - moved[0])) > 0.05
