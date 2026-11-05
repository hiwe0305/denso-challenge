"""Per-cycle command and measurement vectors of the trace hook (DA-38 AC 2). Pure logic, CPU."""

from __future__ import annotations

import math

import numpy as np
import pytest
from flywheel_simple.trace.signals import (
    LOWER_NAMES,
    encode,
    image_time,
    measured_signals,
    split_command,
    yaw_of,
)


def psi0_action() -> np.ndarray:
    return np.arange(36, dtype=np.float64) / 10.0


def g1_joint_qpos() -> np.ndarray:
    """43 robot joints in SIMPLE's g1_sonic order; value = index, so slices are readable."""
    return np.arange(43, dtype=np.float64)


def test_command_upper_is_the_first_28_action_dims() -> None:
    upper, _ = split_command(psi0_action())
    assert upper == pytest.approx(psi0_action()[:28].tolist())


def test_command_lower_drops_dim_34() -> None:
    _, lower = split_command(psi0_action())
    a = psi0_action()
    assert lower == pytest.approx([a[28], a[29], a[30], a[31], a[32], a[33], a[35]])
    assert len(lower) == len(LOWER_NAMES) == 7


def test_command_rejects_a_non_36d_action() -> None:
    with pytest.raises(ValueError, match="36"):
        split_command(np.zeros(32))


def test_measured_upper_follows_the_psi0_state_slices() -> None:
    upper, _ = measured_signals(g1_joint_qpos(), np.array([0, 0, 0.74, 1, 0, 0, 0]), np.zeros(6))
    expected = (
        [29, 30, 31]  # left thumb
        + [34, 35]  # left middle (D-26: dims 3:5 are middle)
        + [32, 33]  # left index
        + list(range(36, 43))  # right hand
        + list(range(15, 22))  # left arm
        + list(range(22, 29))  # right arm
    )
    assert upper == pytest.approx([float(i) for i in expected])


def test_measured_lower_reads_waist_as_roll_pitch_yaw_and_base_height() -> None:
    _, lower = measured_signals(g1_joint_qpos(), np.array([0, 0, 0.74, 1, 0, 0, 0]), np.zeros(6))
    assert lower[:3] == pytest.approx([13.0, 14.0, 12.0])  # waist roll, pitch, yaw joints
    assert lower[3] == pytest.approx(0.74)


def test_measured_velocity_is_rotated_into_the_heading_frame() -> None:
    yaw = math.pi / 2  # robot faces world +y
    quat = [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]
    qvel = np.array([0.0, 0.5, 0.0, 0.0, 0.0, 0.0])  # moving along world +y = forward
    _, lower = measured_signals(g1_joint_qpos(), np.array([1.0, 2.0, 0.7, *quat]), qvel)
    vx, vy, measured_yaw = lower[4], lower[5], lower[6]
    assert vx == pytest.approx(0.5)
    assert vy == pytest.approx(0.0, abs=1e-12)
    assert measured_yaw == pytest.approx(yaw)


def test_yaw_of_identity_is_zero_and_handles_negative_yaw() -> None:
    assert yaw_of(np.array([1.0, 0.0, 0.0, 0.0])) == pytest.approx(0.0)
    q = [math.cos(-0.3), 0.0, 0.0, math.sin(-0.3)]  # yaw -0.6 rad
    assert yaw_of(np.array(q)) == pytest.approx(-0.6)


def test_image_time_only_on_cycles_where_the_policy_received_a_frame() -> None:
    assert image_time(1.24, frame_sent=True) == pytest.approx(1.24)
    assert image_time(1.24, frame_sent=False) is None


def test_encode_keeps_finite_floats_and_names_non_finite_ones() -> None:
    assert encode(0.25) == 0.25
    assert encode(float("nan")) == "NaN"
    assert encode(float("inf")) == "Infinity"
    assert encode(float("-inf")) == "-Infinity"
    assert isinstance(encode(np.float32(1.5)), float)
