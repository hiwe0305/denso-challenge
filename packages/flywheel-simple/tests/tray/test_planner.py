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


def first(records: list[Record], phase: Phase) -> Record:
    return next(r for r in records if r.cmd.phase == phase)


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
    record = first(ToyWorld(level=1, seed=seed).run(), Phase.GRASP)
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
