"""Unit tests for the 11 data defect injection methods (AC 1)."""

import math

from flywheel.data.inject.config import DataDefectConfig
from flywheel.data.inject.data_defects import DataDefectInjector, EpisodeData


def _make_dummy_episode() -> EpisodeData:
    return EpisodeData(
        episode_id="ep_test_001",
        timestamps_state=[0.0, 0.05, 0.10, 0.15, 0.20],
        timestamps_image=[0.0, 0.05, 0.10, 0.15, 0.20],
        states=[[0.1, 0.2, 0.3] for _ in range(5)],
        actions=[[0.05, 0.15, 0.25] for _ in range(5)],
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
    assert "injected_defect" not in original.meta
    assert "injected_defect" in modified.meta


def test_inject_drop_frames() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(drop_frames_rate=0.5))
    mod, defect = injector.inject_drop_frames(ep)
    assert defect.code == "drop_frames"
    assert len(mod.images) < len(ep.images)
    assert len(mod.timestamps_image) == len(mod.images)


def test_inject_timestamp_sync_offset() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(timestamp_offset_seconds=0.10))
    mod, defect = injector.inject_timestamp_sync_offset(ep)
    assert defect.code == "timestamp_sync_offset"
    assert mod.timestamps_image[0] == 0.10
    assert mod.timestamps_state[0] == 0.0


def test_inject_joint_jump() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_jump_magnitude=2.0))
    mod, defect = injector.inject_joint_jump(ep)
    assert defect.code == "joint_jump"
    step = defect.parameters["step"]
    assert mod.states[step][0] == 0.1 + 2.0


def test_inject_joint_limit_exceeded() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_limit_excess_factor=1.3))
    mod, defect = injector.inject_joint_limit_exceeded(ep)
    assert defect.code == "joint_limit_exceeded"
    dim = defect.parameters["dimension"]
    assert mod.states[0][dim] > math.pi


def test_inject_nan_values() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_nan_values(ep)
    assert defect.code == "nan_values"
    step = defect.parameters["step"]
    assert math.isnan(mod.actions[step][0])


def test_inject_unit_deg_rad() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_unit_deg_rad(ep)
    assert defect.code == "unit_deg_rad"
    dim = defect.parameters["dimension"]
    assert mod.states[0][dim] > 10.0  # converted from 0.3 rad to ~17 deg


def test_inject_action_sign_flip() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(action_sign_flip_dims=(0,)))
    mod, defect = injector.inject_action_sign_flip(ep)
    assert defect.code == "action_sign_flip"
    assert mod.actions[0][0] == -0.05
    assert mod.actions[0][1] == 0.15


def test_inject_corrupted_success_label() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_corrupted_success_label(ep)
    assert defect.code == "corrupted_success_label"
    assert mod.sim_success is False


def test_inject_wrong_task_instruction() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_wrong_task_instruction(ep)
    assert defect.code == "wrong_task_instruction"
    assert mod.instruction != ep.instruction


def test_inject_duplicate_episode() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_duplicate_episode(ep)
    assert defect.code == "duplicate_episode"
    assert mod.episode_id.endswith("_dup")


def test_inject_holdout_seed_leak() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_holdout_seed_leak(ep)
    assert defect.code == "holdout_seed_leak"
    assert 9000 <= mod.seed <= 9999
