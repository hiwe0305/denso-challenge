"""Unit tests for the 11 data defect injection methods (AC 1)."""

import math
import statistics
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.data.inject.applied import defect_applied
from flywheel.data.inject.config import DataDefectConfig, InjectConfig, load_inject_config
from flywheel.data.inject.data_defects import (
    ANGLE_ACTION_DIMS,
    JOINT_ACTION_DIMS,
    DataDefectInjector,
    EpisodeData,
    NotApplicable,
)

REPO = Path(__file__).resolve().parents[5]


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
    assert len(modified.images) < 5


def test_injectors_never_write_the_answer_on_the_episode() -> None:
    # Design 9.2 (3/11/2026): the answer lives only in DefectManifest.
    injector = DataDefectInjector()
    for name in dir(injector):
        if name.startswith("inject_"):
            original = _make_dummy_episode()
            modified, _ = getattr(injector, name)(original)
            assert modified.meta == original.meta


def test_inject_drop_frames() -> None:
    # LeRobot keeps images in the video, so a dropped frame is a missing row: every
    # per-frame list loses the same frames and frame_index gets a gap.
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(drop_frames_rate=0.5))
    mod, defect = injector.inject_drop_frames(ep)
    assert defect.code == "D2"
    assert defect.parameters["kind"] == "drop_frames"
    kept = [ep.images.index(i) for i in mod.images]
    assert 0 < len(kept) < len(ep.images) and kept == sorted(kept)
    for field in ("timestamps_state", "timestamps_image", "states", "actions"):
        assert getattr(mod, field) == [getattr(ep, field)[k] for k in kept], field


def test_inject_timestamp_sync_offset() -> None:
    # The video fixes the image times; the state timestamp column is what moves.
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(timestamp_offset_seconds=0.10))
    mod, defect = injector.inject_timestamp_sync_offset(ep)
    assert defect.code == "D2"
    assert defect.parameters["kind"] == "timestamp_sync_offset"
    assert mod.timestamps_state == [t + 0.10 for t in ep.timestamps_state]
    assert mod.timestamps_image == ep.timestamps_image


def test_inject_joint_jump() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_jump_magnitude=2.0))
    mod, defect = injector.inject_joint_jump(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "joint_jump"
    step, dim = int(defect.parameters["step"]), int(defect.parameters["dimension"])
    assert dim in JOINT_ACTION_DIMS
    assert mod.actions[step][dim] == ep.actions[step][dim] + 2.0


def test_inject_joint_limit_exceeded() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(joint_limit_excess_factor=1.3))
    mod, defect = injector.inject_joint_limit_exceeded(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "joint_limit_exceeded"
    dim = int(defect.parameters["dimension"])
    assert dim in JOINT_ACTION_DIMS
    assert all(a[dim] > math.pi for a in mod.actions)


def test_inject_nan_values() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_nan_values(ep)
    assert defect.code == "D1"
    assert defect.parameters["kind"] == "nan_values"
    step = defect.parameters["step"]
    assert math.isnan(mod.actions[step][int(defect.parameters["dimension"])])


def test_inject_unit_deg_rad() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_unit_deg_rad(ep)
    assert defect.code == "D3"
    assert defect.parameters["kind"] == "unit_deg_rad"
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
    for field in ("timestamps_state", "timestamps_image", "states", "actions", "images"):
        setattr(ep, field, getattr(ep, field)[:2])
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
    # Design 9.2: a broken episode still labelled a success. The robot halts at the cut
    # (action and state held) while the recording and the label go on, so the episode
    # keeps its length and its video's frame count.
    ep = _make_dummy_episode()
    injector = DataDefectInjector(DataDefectConfig(success_label_keep_fraction=0.4))
    mod, defect = injector.inject_corrupted_success_label(ep)
    assert defect.code == "D6"
    assert defect.parameters["kind"] == "corrupted_success_label"
    assert mod.sim_success is True
    assert (defect.parameters["frozen_from"], defect.parameters["frames"]) == (2, 5)
    assert mod.actions == ep.actions[:2] + [ep.actions[1]] * 3
    assert mod.states == ep.states[:2] + [ep.states[1]] * 3
    for field in ("timestamps_state", "timestamps_image", "images"):
        assert getattr(mod, field) == getattr(ep, field), field


def test_corrupted_success_label_needs_a_success_label() -> None:
    ep = _make_dummy_episode()
    ep.sim_success = False
    with pytest.raises(NotApplicable):
        DataDefectInjector().inject_corrupted_success_label(ep)


def test_inject_wrong_task_instruction() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_wrong_task_instruction(ep)
    assert defect.code == "D6"
    assert defect.parameters["kind"] == "wrong_task_instruction"
    assert mod.instruction != ep.instruction


def test_inject_duplicate_episode() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_duplicate_episode(ep)
    assert defect.code == "D5"
    assert defect.parameters["kind"] == "duplicate_episode"
    assert mod.episode_id.endswith("_dup")


def test_inject_holdout_seed_leak() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector()
    mod, defect = injector.inject_holdout_seed_leak(ep)
    assert defect.code == "D5"
    assert defect.parameters["kind"] == "holdout_seed_leak"
    assert mod.seed is not None and 2_000_000 <= mod.seed <= 2_000_999


def test_holdout_seed_leak_works_on_an_episode_without_a_seed() -> None:
    # psi-data records no seed at all (S1-07); the leak gives it one from holdout.
    ep = _make_dummy_episode()
    ep.seed = None
    mod, _ = DataDefectInjector().inject_holdout_seed_leak(ep)
    assert mod.seed is not None and mod.seed >= 2_000_000


def test_holdout_range_is_the_split_plan_holdout() -> None:
    plan = yaml.safe_load((REPO / "configs/splits/default.yaml").read_text(encoding="utf-8"))
    holdout = plan["seed_ranges"]["holdout"]
    expected = (holdout["start"], holdout["stop"] - 1)
    assert DataDefectConfig().holdout_seed_range == expected
    assert load_inject_config().data.holdout_seed_range == expected
    train = plan["seed_ranges"]["train"]
    assert DataDefectConfig().scaffold_seed_range == (train["start"], train["stop"] - 1)


def _layout() -> ActionLayout:
    # Arms 14-20 masked; joint limits only on 21-30; other dims unbounded.
    dims = []
    for d in range(36):
        limited = 21 <= d <= 30
        dims.append(
            ActionDimension(
                name=f"a{d}",
                group="arm" if 14 <= d <= 27 else "other",
                masked=14 <= d <= 20,
                limit_low=-2.0 if limited else None,
                limit_high=2.0 if limited else None,
            )
        )
    return ActionLayout(dimensions=dims)


def test_joint_limit_uses_the_layout_limit_of_the_chosen_dim() -> None:
    ep = _make_dummy_episode()
    injector = DataDefectInjector(
        DataDefectConfig(joint_limit_excess_factor=1.25), layout=_layout()
    )
    mod, defect = injector.inject_joint_limit_exceeded(ep)
    dim = int(defect.parameters["dimension"])
    assert 21 <= dim <= 30
    assert (defect.parameters["limit_low"], defect.parameters["limit_high"]) == (-2.0, 2.0)
    # 25% of the joint range past the high limit
    assert all(a[dim] == 2.0 + 0.25 * 4.0 for a in mod.actions)
    assert defect_applied(ep, mod, defect)


def test_joint_limit_without_layout_falls_back_to_pi() -> None:
    ep = _make_dummy_episode()
    _, defect = DataDefectInjector().inject_joint_limit_exceeded(ep)
    assert (defect.parameters["limit_low"], defect.parameters["limit_high"]) == (-math.pi, math.pi)


def test_action_defects_skip_masked_dims_of_the_layout() -> None:
    for seed in range(30):
        injector = DataDefectInjector(rng_seed=seed, layout=_layout())
        for name in ("joint_jump", "unit_deg_rad", "action_sign_flip"):
            _, defect = getattr(injector, f"inject_{name}")(_make_dummy_episode())
            assert not 14 <= int(defect.parameters["dimension"]) <= 20, (seed, name)


def test_layout_without_limited_joints_makes_joint_limit_not_applicable() -> None:
    layout = ActionLayout(
        dimensions=[ActionDimension(name=f"a{d}", group="g", masked=False) for d in range(36)]
    )
    with pytest.raises(NotApplicable):
        DataDefectInjector(layout=layout).inject_joint_limit_exceeded(_make_dummy_episode())


def test_default_config_path_is_the_repo_file() -> None:
    # parents[5] pointed at packages/, so the loader silently fell back to defaults.
    assert InjectConfig.default_path() == REPO / "configs/data/inject.yaml"
    assert InjectConfig.default_path().is_file()
