"""T1 - divergence, on the loss curve of one job (DA-08 task 2, AC 1)."""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.divergence import detect_t1
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import TrainSeries

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]


def flat(value: float, *, to: int = 1000, every: int = 10) -> dict[int, float]:
    return {step: value for step in range(0, to + 1, every)}


def test_t1_flags_a_loss_that_is_not_finite_and_marks_the_job_to_stop(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    series = series_from(train=flat(0.5) | {500: float("nan")})
    result = detect_t1(series, cfg)
    assert codes(result) == ["T1"]
    finding = result.findings[0]
    assert finding.start_step == 500 and finding.stop_job
    # nothing was compared against a number, so there is no threshold to record
    assert finding.threshold is None and math.isnan(finding.value)


@pytest.mark.parametrize("loss", [float("inf"), float("-inf")])
def test_t1_flags_an_infinite_loss_as_well_as_a_nan(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, loss: float
) -> None:
    assert codes(detect_t1(series_from(train=flat(0.5) | {700: loss}), cfg)) == ["T1"]


def test_t1_flags_a_loss_over_k_times_the_window_minimum(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # train.yaml: k = 10, window_steps = 500. The window of step 600 holds only
    # 0.5 losses, so the limit is 5.0 and a loss of 8.0 is over it.
    result = detect_t1(series_from(train=flat(0.5) | {600: 8.0}), cfg)
    assert codes(result) == ["T1"]
    assert result.findings[0].start_step == 600
    assert result.findings[0].value == pytest.approx(8.0)
    assert result.findings[0].threshold == pytest.approx(5.0)
    assert result.findings[0].stop_job


def test_t1_is_silent_on_a_rise_that_stays_under_k_times(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # 4.0 is eight times the window minimum: a bad batch, not divergence
    assert codes(detect_t1(series_from(train=flat(0.5) | {600: 4.0}), cfg)) == []


def test_t1_reaches_the_same_verdict_at_two_logging_rates(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # the same job written every 10 steps and every 50 steps: the window is 500
    # steps either way, so the spike at 600 is the same spike (plan, review point 2)
    dense = detect_t1(series_from(train=flat(0.5, every=10) | {600: 8.0}), cfg)
    sparse = detect_t1(series_from(train=flat(0.5, every=50) | {600: 8.0}), cfg)
    assert codes(dense) == codes(sparse) == ["T1"]
    assert dense.findings[0].start_step == sparse.findings[0].start_step == 600
    assert dense.findings[0].threshold == sparse.findings[0].threshold == pytest.approx(5.0)


def test_t1_forgets_a_low_loss_from_before_the_window(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # 0.5 early on, then the job settles at 2.0 and takes an 8.0 batch at step
    # 1000. Against the 500 steps before it the limit is 20.0, so there is no
    # divergence; against the whole history it would have been 5.0 and flagged.
    early = {step: 0.5 for step in range(0, 101, 10)}
    settled = {step: 2.0 for step in range(110, 1001, 10)}
    assert codes(detect_t1(series_from(train=early | settled | {1000: 8.0}), cfg)) == []


def test_t1_reports_only_the_first_divergence(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # a spike at 300 and a NaN at 500: the job was already stopping at 300, and
    # no measurement after that point was going to be trusted
    result = detect_t1(series_from(train=flat(0.5) | {300: 8.0, 500: float("nan")}), cfg)
    assert codes(result) == ["T1"]
    assert result.findings[0].start_step == 300


def test_t1_is_silent_and_skips_nothing_on_a_clean_run(
    clean_series: TrainSeries, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    result = detect_t1(clean_series, cfg)
    assert codes(result) == [] and skipped_codes(result) == []


def test_t1_skips_a_log_with_no_train_record(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    result = detect_t1(series_from(val={0: 1.0}), cfg)
    assert codes(result) == [] and skipped_codes(result) == ["T1"]
