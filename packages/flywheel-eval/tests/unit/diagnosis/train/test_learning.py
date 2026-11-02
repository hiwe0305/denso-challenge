"""T2 and T3 - no learning, and overfitting (DA-08 task 2, AC 1)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.learning import detect_t2, detect_t3
from flywheel.eval.diagnosis.train.reader import TrainSeries

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]


def falling_train(to: int = 3000) -> dict[int, float]:
    return {step: 1.0 - 0.0002 * step for step in range(0, to + 1, 10)}


def test_t2_flags_a_val_loss_that_never_dropped(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # train.yaml: n_steps = 2000, min_relative_drop = 0.05
    series = series_from(
        train=falling_train(),
        val={step: 1.0 for step in range(0, 3001, 500)},
    )
    result = detect_t2(series, cfg)
    assert codes(result) == ["T2"]
    assert result.findings[0].start_step == 2000
    assert result.findings[0].value == pytest.approx(0.0)
    assert result.findings[0].threshold == pytest.approx(0.05)


def test_t2_flags_a_flat_run_behind_one_noisy_first_measurement(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # The first val measurement is 9.9 and the job is flat at 1.0 after it. The
    # baseline is the median of the first three measurements, so it is 1.0 and
    # the run is caught; the first measurement alone would have made the
    # baseline 9.9 and a flat job look like a 90% drop (issue #5, 29/10/2026).
    series = series_from(
        train=falling_train(),
        val={0: 9.9, 500: 1.0, 1000: 1.0, 1500: 1.0, 2000: 1.0},
    )
    assert codes(detect_t2(series, cfg)) == ["T2"]


def test_t2_is_silent_when_the_val_loss_dropped(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    series = series_from(
        train=falling_train(),
        val={step: 1.0 - 0.0002 * step for step in range(0, 3001, 500)},
    )
    assert codes(detect_t2(series, cfg)) == []


def test_t2_skips_a_job_that_stopped_before_n_steps(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    # A job that died at step 800 is not a job that failed to learn. Saying so
    # is the point: an empty findings list would have read as clean (FR21).
    series = series_from(
        train=falling_train(to=800),
        val={step: 1.0 for step in range(0, 801, 100)},
    )
    result = detect_t2(series, cfg)
    assert codes(result) == [] and skipped_codes(result) == ["T2"]
    assert "step 800" in result.skipped[0].reason


def test_t2_skips_when_there_are_too_few_measurements_for_a_baseline(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    # baseline_val_count = 3 and this job logged val twice
    series = series_from(train=falling_train(), val={0: 1.0, 2500: 1.0})
    result = detect_t2(series, cfg)
    assert codes(result) == [] and skipped_codes(result) == ["T2"]


def test_t3_flags_a_rising_val_loss_while_the_train_loss_falls(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # train.yaml: m_measurements = 3. Val falls to step 600 and rises after it,
    # so the run of measurements that disagree with the train loss starts there.
    val = {0: 1.0, 200: 0.8, 400: 0.7, 600: 0.6, 800: 0.65, 1000: 0.7, 1200: 0.78}
    result = detect_t3(series_from(train=falling_train(), val=val), cfg)
    assert codes(result) == ["T3"]
    assert result.findings[0].start_step == 600
    assert result.findings[0].value == pytest.approx(3.0)
    assert result.findings[0].threshold == pytest.approx(3.0)


def test_t3_is_silent_on_a_jagged_but_healthy_train_loss(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # Batch-to-batch jitter of 0.3 on a train loss that is falling. T3 reads the
    # median between two val measurements, not single records, so the jitter
    # cannot make the train loss look stuck (plan, review point 3).
    jagged = {
        step: 1.0 - 0.0002 * step + (0.3 if (step // 10) % 2 else -0.3)
        for step in range(0, 3001, 10)
    }
    val = {step: 1.05 - 0.0002 * step for step in range(0, 3001, 200)}
    assert codes(detect_t3(series_from(train=jagged, val=val), cfg)) == []


def test_t3_is_silent_when_the_val_loss_rises_fewer_times_than_m(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
) -> None:
    # two rising measurements, then it falls again: a bump, not overfitting
    val = {0: 1.0, 200: 0.8, 400: 0.7, 600: 0.75, 800: 0.8, 1000: 0.6, 1200: 0.55}
    assert codes(detect_t3(series_from(train=falling_train(), val=val), cfg)) == []


def test_t3_skips_when_no_train_record_lines_up_with_the_val_measurements(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    val = {0: 1.0, 200: 1.1, 400: 1.2, 600: 1.3}
    result = detect_t3(series_from(val=val), cfg)
    assert codes(result) == [] and skipped_codes(result) == ["T3"]


def test_t3_skips_a_job_with_too_few_val_measurements(
    series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    # m_measurements = 3 needs four consecutive measurements to see a run
    series = series_from(train=falling_train(to=300), val={0: 1.0, 100: 1.1, 200: 1.2})
    result = detect_t3(series, cfg)
    assert codes(result) == [] and skipped_codes(result) == ["T3"]


def test_a_clean_job_is_silent_without_skipping_anything(
    clean_series: TrainSeries, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
) -> None:
    # The control the PO review asked for: a clean verdict has to come from
    # having judged the job, not from having skipped it.
    for result in (detect_t2(clean_series, cfg), detect_t3(clean_series, cfg)):
        assert codes(result) == [] and skipped_codes(result) == []
