"""T4 - group imbalance (DA-08 task 3, AC 1, 6).

One positive and one negative per code is the AC 6 floor. The cases past that
are the ones that decide whether T4 means anything: a job where *every* group
is slow must not be reported as imbalanced, because that is T2's fault and
calling it T4 would send whoever reads the artifact after the wrong data.
"""

from __future__ import annotations

from collections.abc import Callable

from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.groups import detect_t4
from flywheel.eval.diagnosis.train.reader import TrainSeries

STEPS = range(0, 6001, 10)

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]


def falling(rate: float) -> dict[int, float]:
    return {step: 1.0 - rate * step for step in STEPS}


def flat() -> dict[int, float]:
    return {step: 1.0 for step in STEPS}


class TestCaught:
    def test_one_flat_group_beside_a_learning_one(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t4(
            series_from(train=falling(0.0001), groups={"arm": falling(0.00012), "hand": flat()}),
            cfg,
        )

        assert [finding.group for finding in result.findings] == ["hand"]
        assert result.findings[0].code == "T4"
        assert result.findings[0].value < cfg.t4.min_group_drop
        assert result.findings[0].threshold == cfg.t4.min_group_drop

    def test_two_flat_groups_are_both_reported(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t4(
            series_from(
                train=falling(0.0001),
                groups={"arm": falling(0.00012), "hand": flat(), "waist": flat()},
            ),
            cfg,
        )

        assert sorted(finding.group or "" for finding in result.findings) == ["hand", "waist"]


class TestClean:
    def test_the_clean_job_is_neither_flagged_nor_skipped(
        self, clean_series: TrainSeries, cfg: TrainThresholds
    ) -> None:
        result = detect_t4(clean_series, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_every_group_slow_is_not_an_imbalance(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        """A job that learns nothing anywhere is T2, not T4."""
        result = detect_t4(series_from(train=flat(), groups={"arm": flat(), "hand": flat()}), cfg)

        assert result.findings == []

    def test_both_groups_learning_is_clean(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t4(
            series_from(
                train=falling(0.0001),
                groups={"arm": falling(0.00012), "hand": falling(0.00011)},
            ),
            cfg,
        )

        assert result.findings == []
        assert result.skipped == []


class TestCannotJudge:
    def test_a_log_without_group_losses_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        result = detect_t4(series_from(train=falling(0.0001)), cfg)

        assert skipped_codes(result) == ["T4"]
        assert "loss_by_group" in result.skipped[0].reason

    def test_a_job_shorter_than_the_window_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        short = {step: 1.0 - 0.0001 * step for step in range(0, 100, 10)}
        result = detect_t4(series_from(train=short, groups={"arm": short}), cfg)

        assert skipped_codes(result) == ["T4"]
        assert str(cfg.t4.window_steps) in result.skipped[0].reason

    def test_a_group_with_no_usable_measurements_skips_without_hiding_the_rest(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        """The judgeable groups are still judged; the unjudgeable one is named."""
        result = detect_t4(
            series_from(
                train=falling(0.0001),
                groups={
                    "arm": falling(0.00012),
                    "hand": flat(),
                    "head": {0: float("nan")},
                },
            ),
            cfg,
        )

        assert [finding.group for finding in result.findings] == ["hand"]
        assert [skip.code for skip in result.skipped] == ["T4"]
        assert "head" in result.skipped[0].reason

    def test_a_zero_baseline_carries_no_scale(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        """A group whose loss starts at zero cannot have a relative drop."""
        result = detect_t4(
            series_from(
                train=falling(0.0001),
                groups={"arm": falling(0.00012), "hand": {step: 0.0 for step in STEPS}},
            ),
            cfg,
        )

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["T4"]
        assert "hand" in result.skipped[0].reason
