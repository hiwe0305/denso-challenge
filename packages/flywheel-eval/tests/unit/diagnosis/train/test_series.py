"""Pure numpy helpers shared by the F-TRAIN and F-OFF detectors (DA-08 task 1)."""

from __future__ import annotations

import numpy as np
import pytest
from flywheel.eval.diagnosis.train.series import (
    at_val_points,
    linear_slope,
    median_in_window,
    percentile_with_count,
    relative_drop,
    window_mask,
)
from numpy.typing import NDArray


def steps(*values: int) -> NDArray[np.int64]:
    return np.asarray(values, dtype=np.int64)


def values(*items: float) -> NDArray[np.float64]:
    return np.asarray(items, dtype=np.float64)


def test_window_mask_is_half_open_on_the_step_axis() -> None:
    step = steps(0, 100, 200, 300, 400)
    assert list(window_mask(step, 100, 200)) == [False, True, True, False, False]


def test_window_mask_counts_steps_not_records() -> None:
    # same 500-step window, two logging rates: the window is the same stretch of
    # training either way (plan, review point 2)
    dense = steps(*range(0, 1000, 10))
    sparse = steps(*range(0, 1000, 50))
    assert dense[window_mask(dense, 500, 500)][0] == sparse[window_mask(sparse, 500, 500)][0] == 500
    assert dense[window_mask(dense, 500, 500)][-1] == 990
    assert sparse[window_mask(sparse, 500, 500)][-1] == 950


def test_window_mask_trailing_window_includes_its_end_step() -> None:
    # the T1 idiom: the 500 steps up to and including step 600
    step = steps(0, 100, 101, 600, 601)
    assert list(window_mask(step, 600 - 500 + 1, 500)) == [False, False, True, True, False]


def test_window_mask_rejects_an_empty_width() -> None:
    with pytest.raises(ValueError):
        window_mask(steps(0, 10), 0, 0)


def test_median_in_window_uses_only_records_inside_it() -> None:
    step = steps(0, 10, 20, 30)
    assert median_in_window(step, values(9.0, 1.0, 3.0, 9.0), 10, 20) == pytest.approx(2.0)


def test_median_in_window_drops_non_finite_values() -> None:
    # T1 reports NaN and Inf; they must not poison the smoothing T3 runs on
    step = steps(0, 10, 20)
    assert median_in_window(step, values(1.0, float("nan"), 3.0), 0, 30) == pytest.approx(2.0)


def test_median_in_window_is_nan_on_an_empty_window() -> None:
    assert np.isnan(median_in_window(steps(0, 10), values(1.0, 2.0), 500, 100))


def test_at_val_points_takes_the_median_between_two_val_points() -> None:
    train_step = steps(10, 20, 30, 110, 120)
    train_value = values(5.0, 1.0, 3.0, 0.9, 0.7)
    out = at_val_points(steps(100, 200), train_step, train_value)
    assert list(out) == pytest.approx([3.0, 0.8])


def test_at_val_points_opens_the_first_window_at_the_start_of_the_job() -> None:
    out = at_val_points(steps(100), steps(0, 50), values(2.0, 4.0))
    assert out[0] == pytest.approx(3.0)


def test_at_val_points_is_nan_where_no_train_record_falls_in() -> None:
    out = at_val_points(steps(100, 200), steps(10, 20), values(1.0, 2.0))
    assert out[0] == pytest.approx(1.5) and np.isnan(out[1])


def test_at_val_points_rejects_unsorted_val_steps() -> None:
    with pytest.raises(ValueError):
        at_val_points(steps(200, 100), steps(10), values(1.0))


def test_relative_drop_is_the_share_of_the_baseline_that_went() -> None:
    assert relative_drop(0.9, 0.5) == pytest.approx(0.4444, abs=1e-4)


def test_relative_drop_without_a_baseline_scale_is_nan() -> None:
    # a zero or negative baseline carries no scale: the caller skips, it does not conclude
    assert np.isnan(relative_drop(0.0, 0.5))
    assert np.isnan(relative_drop(float("nan"), 0.5))


def test_linear_slope_recovers_the_slope_of_a_line() -> None:
    x = values(0.0, 1.0, 2.0, 3.0)
    assert linear_slope(x, values(1.0, 3.0, 5.0, 7.0)) == pytest.approx(2.0)


def test_linear_slope_is_positive_on_error_growing_along_the_chunk() -> None:
    # O2 on error_by_chunk_pos
    y = values(0.1, 0.2, 0.4, 0.8)
    assert linear_slope(values(0.0, 1.0, 2.0, 3.0), y) > 0.2


def test_linear_slope_needs_two_distinct_points() -> None:
    assert np.isnan(linear_slope(values(1.0), values(2.0)))
    assert np.isnan(linear_slope(values(2.0, 2.0, 2.0), values(1.0, 2.0, 3.0)))


def test_linear_slope_ignores_non_finite_pairs() -> None:
    x = values(0.0, 1.0, 2.0, 3.0)
    assert linear_slope(x, values(1.0, float("nan"), 5.0, 7.0)) == pytest.approx(2.0)


def test_percentile_with_count_reports_how_many_samples_it_saw() -> None:
    value, count = percentile_with_count(values(*[float(i) for i in range(101)]), 99.0)
    assert value == pytest.approx(99.0) and count == 101


def test_percentile_with_count_on_a_short_sample_is_near_the_maximum() -> None:
    # plan, review point 7: tau from under 100 samples is almost the maximum, so the
    # caller has to be able to see the sample count next to the value
    sample = values(1.0, 1.0, 1.0, 9.0)
    value, count = percentile_with_count(sample, 99.0)
    assert count == 4 and value == pytest.approx(float(sample.max()), rel=0.05)


def test_percentile_with_count_is_nan_and_zero_without_finite_values() -> None:
    value, count = percentile_with_count(values(float("nan"), float("inf")), 99.0)
    assert np.isnan(value) and count == 0
