"""Planner-independent parts of the virtual PICO operator (DA-35 task 5)."""

from __future__ import annotations

import numpy as np
import pytest
from flywheel_simple.tray.pico.style import band_fraction, movement_segments, segment_shape, speeds
from flywheel_simple.tray.pico.virtual import (
    STYLE_RANGES,
    JoystickShaper,
    Style,
    StyleFollower,
    robot_to_teleop,
    sample_style,
    style_seed_for,
    teleop_to_robot,
)

DT = 0.02


def random_pose(rng: np.random.Generator) -> np.ndarray:
    q = rng.normal(size=4)
    w, x, y, z = q / np.linalg.norm(q)
    pose = np.eye(4)
    pose[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ]
    pose[:3, 3] = rng.normal(scale=0.3, size=3)
    return pose


@pytest.mark.parametrize("scale", [1.0, 1.3, 0.7])
def test_inverse_pre_processor_round_trip(scale: float) -> None:
    rng = np.random.default_rng(0)
    for _ in range(20):
        ee0, ctrl0, ctrl, align = (random_pose(rng) for _ in range(4))
        align[:3, 3] = 0.0  # WristsPreProcessor aligns with a rotation only
        robot = teleop_to_robot(ctrl, ee0, ctrl0, scale, align)
        back = robot_to_teleop(robot, ee0, ctrl0, scale, align)
        np.testing.assert_allclose(back, ctrl, atol=1e-9)


def test_forward_matches_the_pre_processor_formula_for_pico() -> None:
    # decoupled_wbc WristsPreProcessor, control_device "pico": alignment is identity,
    # robot = ee0 @ S(inv(ctrl0) @ ctrl) with S scaling the translation.
    rng = np.random.default_rng(1)
    ee0, ctrl0, ctrl = (random_pose(rng) for _ in range(3))
    delta = np.linalg.inv(ctrl0) @ ctrl
    delta[:3, 3] *= 1.5
    np.testing.assert_allclose(teleop_to_robot(ctrl, ee0, ctrl0, 1.5), ee0 @ delta, atol=1e-12)


def test_teleop_at_the_calibration_pose_gives_the_calibration_target() -> None:
    rng = np.random.default_rng(2)
    ee0, ctrl0 = random_pose(rng), random_pose(rng)
    np.testing.assert_allclose(teleop_to_robot(ctrl0, ee0, ctrl0, 1.2), ee0, atol=1e-12)


def test_styles_are_deterministic_and_inside_the_ranges() -> None:
    a, b, c = sample_style(7), sample_style(7), sample_style(8)
    assert a == b
    assert a != c
    for seed in range(50):
        style = sample_style(seed)
        for name, (lo, hi) in STYLE_RANGES.items():
            assert lo <= getattr(style, name) <= hi, name


def run_follower(style: Style, targets: np.ndarray, seed: int = 0) -> np.ndarray:
    follower = StyleFollower(style, dt=DT, seed=seed)
    follower.reset(targets[0])
    return np.array([follower.step(t) for t in targets])


def step_targets(length: float = 0.3, seconds: float = 3.0) -> np.ndarray:
    n = int(seconds / DT)
    targets = np.zeros((n, 3))
    targets[25:, 0] = length  # the planner jumps the target after 0.5 s
    return targets


def calm(**kw: float) -> Style:
    base = dict(omega=8.0, zeta=1.0, curvature=0.0, tremor_mm=0.0, joystick_accel=1.0, arc_seed=0.0)
    base["turn_rate"] = 0.5
    base.update(kw)
    return Style(**base)


def test_follower_peaks_early_and_arrives() -> None:
    path = run_follower(calm(), step_targets())
    v = speeds(path, DT, smooth=1)
    (seg,) = movement_segments(v, DT)
    assert segment_shape(path, v, seg, DT)["peak_time_frac"] < 0.45  # min-jerk would be 0.5
    np.testing.assert_allclose(path[-1], [0.3, 0, 0], atol=2e-3)


def test_underdamped_follower_overshoots_then_corrects() -> None:
    path = run_follower(calm(zeta=0.65), step_targets())
    assert path[:, 0].max() > 0.3 + 0.005
    np.testing.assert_allclose(path[-1], [0.3, 0, 0], atol=3e-3)


def test_curvature_bows_the_path_and_vanishes_at_rest() -> None:
    straight = run_follower(calm(), step_targets())
    curved = run_follower(calm(curvature=0.3), step_targets())
    assert np.abs(straight[:, 1:]).max() < 1e-9
    assert np.linalg.norm(curved[:, 1:], axis=1).max() > 0.02  # >= 2 cm off a 30 cm chord
    np.testing.assert_allclose(curved[-1], [0.3, 0, 0], atol=3e-3)


def test_tremor_is_small_and_in_band() -> None:
    hold = np.zeros((500, 3))
    path = run_follower(calm(tremor_mm=1.5), hold)
    assert np.abs(path).max() < 0.005
    assert band_fraction(np.gradient(path, DT, axis=0), DT, 4.0, 12.0) > 0.9


def test_follower_is_deterministic_per_seed() -> None:
    style = sample_style(3)
    targets = step_targets()
    np.testing.assert_array_equal(run_follower(style, targets, 5), run_follower(style, targets, 5))
    assert not np.array_equal(run_follower(style, targets, 5), run_follower(style, targets, 6))


def test_joystick_limits_acceleration() -> None:
    shaper = JoystickShaper(accel=0.5, dt=DT)
    out = [shaper.step(0.5) for _ in range(100)]
    assert np.max(np.diff(out)) <= 0.5 * DT + 1e-12
    assert out[-1] == pytest.approx(0.5)
    stop = [shaper.step(0.0) for _ in range(100)]
    assert stop[-1] == pytest.approx(0.0)


def test_style_seeds_are_reproducible_and_differ_per_attempt_and_condition() -> None:
    a = style_seed_for(0, 1, 7, 1)
    assert a == style_seed_for(0, 1, 7, 1)
    others = {style_seed_for(0, 1, 7, 2), style_seed_for(0, 0, 7, 1), style_seed_for(1, 1, 7, 1)}
    assert a not in others and len(others) == 3
