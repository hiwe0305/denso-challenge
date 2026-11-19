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


def risen(cfg: TrainThresholds) -> float:
    """A loss level well past `k` times the 0.5 baseline of `flat`."""
    return 0.5 * cfg.t1.k * 1.6


def test_t1_flags_a_loss_that_stays_over_k_times_the_window_minimum(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # From step 600 the loss sits at 1.6 k times the 0.5 it had. The trailing
    # median over smooth_steps = 100 (ten records here) crosses once more than
    # half the window is high: at step 650. The window minimum of the smoothed
    # loss is 0.5, so the threshold is k * 0.5.
    train = flat(0.5) | {step: risen(cfg) for step in range(600, 1001, 10)}
    result = detect_t1(series_from(train=train), cfg)
    assert codes(result) == ["T1"]
    assert result.findings[0].start_step == 650
    assert result.findings[0].value == pytest.approx(risen(cfg))
    assert result.findings[0].threshold == pytest.approx(cfg.t1.k * 0.5)
    assert result.findings[0].stop_job


def test_t1_is_silent_on_one_bad_batch_however_high(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # One batch at 200 times the window minimum. Healthy Psi0 fine-tunes do
    # this thousands of times per job (DA-44), so a batch alone is not divergence.
    assert codes(detect_t1(series_from(train=flat(0.5) | {600: 100.0}), cfg)) == []


def test_t1_is_silent_on_a_rise_that_stays_under_k_times(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    under = 0.5 * cfg.t1.k * 0.8
    train = flat(0.5) | {step: under for step in range(600, 1001, 10)}
    assert codes(detect_t1(series_from(train=train), cfg)) == []


def test_t1_reaches_the_same_verdict_at_two_logging_rates(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # the same job written every 10 steps and every 50 steps: both windows
    # count steps, so the rise from step 600 is caught at the same step
    # (plan, review point 2)
    def job(every: int) -> TrainSeries:
        high = {step: risen(cfg) for step in range(600, 1001, every)}
        return series_from(train=flat(0.5, every=every) | high)

    dense, sparse = detect_t1(job(10), cfg), detect_t1(job(50), cfg)
    assert codes(dense) == codes(sparse) == ["T1"]
    assert dense.findings[0].start_step == sparse.findings[0].start_step == 650
    assert (
        dense.findings[0].threshold == sparse.findings[0].threshold == pytest.approx(cfg.t1.k * 0.5)
    )


def test_t1_forgets_a_low_loss_from_before_the_window(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # 0.5 early on, then the job settles at 2.0 and rises to 1.6 k times 0.5 at
    # step 1000. Against the 500 steps before it the limit is k * 2.0, so there
    # is no divergence; against the whole history it would have been k * 0.5.
    early = {step: 0.5 for step in range(0, 101, 10)}
    settled = {step: 2.0 for step in range(110, 1001, 10)}
    high = {step: risen(cfg) for step in range(1000, 1201, 10)}
    assert codes(detect_t1(series_from(train=early | settled | high), cfg)) == []


def test_t1_reports_only_the_first_divergence(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # a rise from 300 and a NaN at 500: the job was already stopping at 350,
    # and no measurement after that point was going to be trusted
    train = flat(0.5) | {step: risen(cfg) for step in range(300, 1001, 10)} | {500: float("nan")}
    result = detect_t1(series_from(train=train), cfg)
    assert codes(result) == ["T1"]
    assert result.findings[0].start_step == 350


def test_t1_smoothing_skips_a_nan_rather_than_spreading_it(
    series_from: SeriesBuilder, cfg: TrainThresholds
) -> None:
    # branch (a) reports the NaN; the median beside it must stay a number
    result = detect_t1(series_from(train=flat(0.5) | {500: float("nan")}), cfg)
    assert [finding.start_step for finding in result.findings] == [500]
    assert result.findings[0].threshold is None


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
