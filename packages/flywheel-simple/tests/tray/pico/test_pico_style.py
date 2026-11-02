"""Motion-style metrics measured on teleop trajectories (DA-35 task 3)."""

from __future__ import annotations

import numpy as np
import pytest
from flywheel_simple.tray.pico.style import (
    band_fraction,
    jerk_rms,
    movement_segments,
    pauses,
    percentiles,
    segment_shape,
    speeds,
)

DT = 0.02


def min_jerk(n: int) -> np.ndarray:
    s = np.linspace(0.0, 1.0, n)
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def reach(length: float = 0.3, seconds: float = 1.0, rest: float = 0.5) -> np.ndarray:
    """Rest, a straight min-jerk reach along x, rest."""
    n, r = int(seconds / DT), int(rest / DT)
    x = np.r_[np.zeros(r), length * min_jerk(n), np.full(r, length)]
    return np.c_[x, np.zeros_like(x), np.zeros_like(x)]


def test_speed_of_a_uniform_motion() -> None:
    t = np.arange(100) * DT
    pos = np.c_[0.2 * t, np.zeros(100), np.zeros(100)]
    np.testing.assert_allclose(speeds(pos, DT, smooth=1)[5:-5], 0.2, atol=1e-9)


def test_one_reach_is_one_segment_with_a_centred_peak() -> None:
    pos = reach()
    v = speeds(pos, DT)
    (seg,) = movement_segments(v, DT)
    shape = segment_shape(pos, v, seg, DT)
    assert shape["peak_time_frac"] == pytest.approx(0.5, abs=0.06)
    assert shape["length"] == pytest.approx(0.3, rel=0.1)
    assert shape["curvature"] < 0.02
    assert shape["peak_speed"] == pytest.approx(1.875 * 0.3 / 1.0, rel=0.1)  # min-jerk peak


def test_curved_path_has_curvature() -> None:
    n = 50
    s = min_jerk(n)
    pos = np.c_[0.3 * s, 0.06 * np.sin(np.pi * s), np.zeros(n)]
    pos = np.r_[np.repeat(pos[:1], 25, 0), pos, np.repeat(pos[-1:], 25, 0)]
    v = speeds(pos, DT)
    (seg,) = movement_segments(v, DT)
    assert segment_shape(pos, v, seg, DT)["curvature"] == pytest.approx(0.2, abs=0.04)


def test_short_twitches_are_not_segments() -> None:
    v = np.zeros(200)
    v[50:55] = 0.3  # 0.1 s
    assert movement_segments(v, DT, min_s=0.2) == []


def test_hysteresis_keeps_one_segment_through_a_dip() -> None:
    v = np.zeros(200)
    v[20:120] = 0.2
    v[60:63] = 0.04  # between off (0.03) and on (0.05)
    assert movement_segments(v, DT) == [(20, 120)]


def test_pauses() -> None:
    still = np.ones(300, bool)
    still[:50] = False
    still[80:200] = False  # pause 50..80 is 0.6 s, tail 200..300 is 2.0 s
    still[60:62] = False  # breaks the first pause into 0.2 s and 0.36 s
    assert pauses(still, DT, min_s=0.3) == pytest.approx([0.36, 2.0])


def test_jerk_is_zero_for_uniform_motion_and_grows_with_speed() -> None:
    t = np.arange(200) * DT
    line = np.c_[0.2 * t, np.zeros(200), np.zeros(200)]
    assert jerk_rms(line, DT) < 1e-6
    assert jerk_rms(reach(seconds=0.5), DT) > jerk_rms(reach(seconds=1.0), DT)


def test_band_fraction_finds_a_tremor() -> None:
    t = np.arange(500) * DT
    slow = np.sin(2 * np.pi * 0.3 * t)
    tremor = 0.05 * np.sin(2 * np.pi * 8.0 * t)
    assert band_fraction(slow, DT, 4.0, 12.0) < 0.01
    assert band_fraction(tremor, DT, 4.0, 12.0) > 0.95
    assert band_fraction(np.zeros(500), DT, 4.0, 12.0) == 0.0


def test_percentiles() -> None:
    out = percentiles(list(range(1, 101)))
    assert out["n"] == 100
    assert out["p50"] == pytest.approx(50.5)
    assert out["p10"] < out["p50"] < out["p90"]
    assert percentiles([])["n"] == 0
