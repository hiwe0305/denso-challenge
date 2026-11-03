"""Unit tests for the 11 data defect injection methods (AC 1)."""

import math
import statistics

import pytest
from flywheel.contracts.artifacts import InjectedDefect
from flywheel.data.inject.applied import defect_applied
from flywheel.data.inject.config import DataDefectConfig
from flywheel.data.inject.data_defects import (
    ANGLE_ACTION_DIMS,
    JOINT_ACTION_DIMS,
    DataDefectInjector,
    EpisodeData,
    NotApplicable,
)


def _make_dummy_episode() -> EpisodeData:
    return EpisodeData(
        episode_id="ep_test_001",
        timestamps_state=[0.0, 0.05, 0.10, 0.15, 0.20],
        timestamps_image=[0.0, 0.05, 0.10, 0.15, 0.20],
        states=[[0.1, 0.2, 0.3] for _ in range(5)],
        # 36-D action like G1 in SIMPLE: hands (0-13) stay at zero on the two-table task.
        actions=[[0.0] * 14 + [0.05 * (i + 1)] * 22 for i in range(5)],
        images=["frame_0.jpg", "frame_1.jpg", "frame_2.jpg", "frame_3.jpg", "frame_4.jpg"],
        instruction="pick object from table 1 and place on table 2",
        sim_success=True,
        seed=1000,
    )


def test_injector_preserves_original() -> None:
    original = _make_dummy_episode()
    injector = DataDefectInjector()
    modified, _ = injector.inject_drop_frames(original)
    assert len(original.images) == 5
    assert original.meta.injected_defect is None
    assert modified.meta.injected_defect is not None


def test_inject_drop_frames() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(drop_frames_rate=0.5))
    mod, defect = injector.inject_drop_frames(ep)
    assert defect.code == "D2"
    assert defect.parameters["kind"] == "drop_frames"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert len(mod.images) < len(ep.images)
    assert len(mod.timestamps_image) == len(mod.images)


def test_inject_timestamp_sync_offset() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(timestamp_offset_seconds=0.10))
    mod, defect = injector.inject_timestamp_sync_offset(ep)
    assert defect.code == "D2"
    assert defect.parameters["kind"] == "timestamp_sync_offset"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert mod.timestamps_image[0] == 0.10
    assert mod.timestamps_state[0] == 0.0


def test_inject_joint_jump() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_jump_magnitude=2.0))
    mod, defect = injector.inject_joint_jump(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "joint_jump"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    step, dim = int(defect.parameters["step"]), int(defect.parameters["dimension"])
    assert dim in JOINT_ACTION_DIMS
    assert mod.actions[step][dim] == ep.actions[step][dim] + 2.0


def test_inject_joint_limit_exceeded() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_limit_excess_factor=1.3))
    mod, defect = injector.inject_joint_limit_exceeded(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "joint_limit_exceeded"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    dim = int(defect.parameters["dimension"])
    assert dim in JOINT_ACTION_DIMS
    assert all(a[dim] > math.pi for a in mod.actions)


def test_inject_nan_values() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_nan_values(ep)
    assert defect.code == "D1"
    assert defect.parameters["kind"] == "nan_values"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    step = defect.parameters["step"]
    assert math.isnan(mod.actions[step][0])


def test_inject_unit_deg_rad() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_unit_deg_rad(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "unit_deg_rad"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    dim = int(defect.parameters["dimension"])
    # Design 9.2: only angle dims, and only one that is not all zero, so the scaling shows.
    assert dim in ANGLE_ACTION_DIMS and dim >= 14
    scale = injector.config.unit_deg_rad_scale
    assert [a[dim] for a in mod.actions] == [a[dim] * scale for a in ep.actions]


def test_unit_deg_rad_needs_a_nonzero_angle_dim() -> None:
    ep = _make_dummy_episode()
    # Only dims 31-34 (height, velocities, turn flag) move: no angle to scale.
    ep.actions = [[0.0] * 31 + [0.7 + i, 0.1, 0.2, 1.0, 0.0] for i in range(5)]
    with pytest.raises(NotApplicable):
        DataDefectInjector().inject_unit_deg_rad(ep)


def test_inject_action_sign_flip() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_action_sign_flip(ep)
    assert defect.code == "D7"
    assert defect.parameters["kind"] == "action_sign_flip"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    dim = int(defect.parameters["dimension"])
    # Design 9.2: one dim whose std is not zero on this episode.
    assert statistics.pstdev(a[dim] for a in ep.actions) > 0
    assert [a[dim] for a in mod.actions] == [-a[dim] for a in ep.actions]
    other = [d for d in range(36) if d != dim]
    assert [[a[d] for d in other] for a in mod.actions] == [
        [a[d] for d in other] for a in ep.actions
    ]


def test_action_sign_flip_needs_a_moving_dim() -> None:
    ep = _make_dummy_episode()
    ep.actions = [[0.0] * 14 + [0.3] * 22 for _ in range(5)]
    with pytest.raises(NotApplicable):
        DataDefectInjector().inject_action_sign_flip(ep)


def test_drop_frames_needs_more_than_two_images() -> None:
    ep = _make_dummy_episode()
    ep.images, ep.timestamps_image = ep.images[:2], ep.timestamps_image[:2]
    with pytest.raises(NotApplicable):
        DataDefectInjector(DataDefectConfig(drop_frames_rate=0.0)).inject_drop_frames(ep)


def test_every_injector_changes_what_it_lists() -> None:
    injector = DataDefectInjector()
    for name in sorted(n for n in dir(injector) if n.startswith("inject_")):
        if name == "inject_duplicate_episode":
            continue  # needs a source episode; covered in test_manifest_and_barrier
        before = _make_dummy_episode()
        after, defect = getattr(injector, name)(before)
        assert defect_applied(before, after, defect), name


def test_defect_applied_rejects_a_listed_but_unapplied_defect() -> None:
    before = _make_dummy_episode()
    _, defect = DataDefectInjector().inject_unit_deg_rad(before)
    assert not defect_applied(before, before, defect)


def test_inject_corrupted_success_label() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_corrupted_success_label(ep)
    assert defect.code == "D6"
    assert defect.parameters["kind"] == "corrupted_success_label"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert mod.sim_success is False


def test_inject_wrong_task_instruction() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_wrong_task_instruction(ep)
    assert defect.code == "D6"
    assert defect.parameters["kind"] == "wrong_task_instruction"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert mod.instruction != ep.instruction


def test_inject_duplicate_episode() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_duplicate_episode(ep)
    assert defect.code == "D5"
    assert defect.parameters["kind"] == "duplicate_episode"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert mod.episode_id.endswith("_dup")


def test_inject_holdout_seed_leak() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_holdout_seed_leak(ep)
    assert defect.code == "D5"
    assert defect.parameters["kind"] == "holdout_seed_leak"
    assert mod.meta.injected_defect == InjectedDefect(
        code=defect.code, parameters=defect.parameters
    )
    assert 9000 <= mod.seed <= 9999
