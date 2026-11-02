"""T5 and T6 - dead dimension and mode collapse (DA-08 task 3, AC 1, 2, 6).

Two rules are tested here harder than the codes themselves, because breaking
either turns a verdict into a wrong one:

* A dimension the action layout marks `masked` is never reported. It is
  constant because nothing drives it, and AC 2 is what says to ask the layout
  rather than hold a list of dimensions in code.
* T6 on a dimension whose `target_std` is zero ends in a skip with that
  dimension named. Reporting nothing there would make an unjudgeable dimension
  look clean, which is the silent pass FR21 forbids and the case the contract
  owner added `DiagnosisSkip` for (issue #5, 1/11).
"""

from __future__ import annotations

from collections.abc import Callable

from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.dimensions import detect_t5, detect_t6
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import LayoutView, TrainSeries

STEPS = range(0, 3001, 10)

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]


def losses() -> dict[int, float]:
    return {step: 1.0 - 0.0002 * step for step in STEPS}


class TestT5Caught:
    def test_a_dimension_with_no_variance_left(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t5(series_from(train=losses(), pred_var=[0.2, 0.0, 0.3]), cfg, layout)

        assert [finding.dim for finding in result.findings] == [1]
        assert result.findings[0].code == "T5"
        assert result.findings[0].threshold == cfg.t5.epsilon

    def test_variance_just_under_epsilon_counts(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t5(
            series_from(train=losses(), pred_var=[0.2, cfg.t5.epsilon / 2, 0.3]), cfg, layout
        )

        assert [finding.dim for finding in result.findings] == [1]

    def test_only_the_trailing_window_decides(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """A dimension that was dead early but recovered is not a finding."""
        dead_then_alive = {step: [0.2, 0.0 if step < 1000 else 0.3, 0.3] for step in STEPS}
        result = detect_t5(series_from(train=losses(), pred_var=dead_then_alive), cfg, layout)

        assert result.findings == []


class TestT5Clean:
    def test_the_clean_job_is_neither_flagged_nor_skipped(
        self, clean_series: TrainSeries, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t5(clean_series, cfg, layout)

        assert result.findings == []
        assert result.skipped == []

    def test_a_masked_dimension_is_never_reported(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """Dimension 2 is masked in the layout, so a zero variance there is normal."""
        result = detect_t5(series_from(train=losses(), pred_var=[0.2, 0.3, 0.0]), cfg, layout)

        assert result.findings == []
        assert result.skipped == []


class TestT6Caught:
    def test_predictions_far_narrower_than_the_targets(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t6(
            series_from(train=losses(), pred_std=[0.5, 0.05, 0.5], target_std=[1.0, 1.0, 1.0]),
            cfg,
            layout,
        )

        assert [finding.dim for finding in result.findings] == [1]
        assert result.findings[0].code == "T6"
        assert result.findings[0].value < cfg.t6.min_std_ratio

    def test_the_last_record_with_both_statistics_decides(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """A job that collapsed only at the end is still a finding."""
        widening = {step: [0.5, 0.5 if step < 2000 else 0.01, 0.5] for step in STEPS}
        result = detect_t6(
            series_from(train=losses(), pred_std=widening, target_std=[1.0, 1.0, 1.0]),
            cfg,
            layout,
        )

        assert [finding.dim for finding in result.findings] == [1]
        assert result.findings[0].start_step == 3000


class TestT6Clean:
    def test_the_clean_job_is_neither_flagged_nor_skipped(
        self, clean_series: TrainSeries, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t6(clean_series, cfg, layout)

        assert result.findings == []
        assert result.skipped == []

    def test_a_masked_dimension_is_never_reported(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t6(
            series_from(train=losses(), pred_std=[0.5, 0.5, 0.0], target_std=[1.0, 1.0, 1.0]),
            cfg,
            layout,
        )

        assert result.findings == []
        assert result.skipped == []


class TestT6CannotJudge:
    def test_a_zero_target_std_is_a_named_skip(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """The case `DiagnosisSkip` was added for: no denominator, so no verdict."""
        result = detect_t6(
            series_from(train=losses(), pred_std=[0.5, 0.5, 0.5], target_std=[1.0, 0.0, 1.0]),
            cfg,
            layout,
        )

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["T6"]
        assert "arm_1" in result.skipped[0].reason
        assert "target_std" in result.skipped[0].reason

    def test_one_zero_target_does_not_hide_a_finding_on_another_dimension(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_t6(
            series_from(train=losses(), pred_std=[0.05, 0.5, 0.5], target_std=[1.0, 0.0, 1.0]),
            cfg,
            layout,
        )

        assert [finding.dim for finding in result.findings] == [0]
        assert [skip.code for skip in result.skipped] == ["T6"]


class TestSignalsThatAreMissing:
    def test_t5_without_pred_var_skips(
        self,
        series_from: SeriesBuilder,
        cfg: TrainThresholds,
        layout: LayoutView,
        skipped_codes: Codes,
    ) -> None:
        result = detect_t5(series_from(train=losses()), cfg, layout)

        assert skipped_codes(result) == ["T5"]
        assert "pred_var_by_dim" in result.skipped[0].reason

    def test_t6_without_target_std_skips(
        self,
        series_from: SeriesBuilder,
        cfg: TrainThresholds,
        layout: LayoutView,
        skipped_codes: Codes,
    ) -> None:
        result = detect_t6(series_from(train=losses(), pred_std=[0.5, 0.5, 0.5]), cfg, layout)

        assert skipped_codes(result) == ["T6"]
        assert "target_std" in result.skipped[0].reason

    def test_an_empty_log_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        assert [skip.code for skip in detect_t5(series_from(), cfg, layout).skipped] == ["T5"]
        assert [skip.code for skip in detect_t6(series_from(), cfg, layout).skipped] == ["T6"]

    def test_a_log_of_the_wrong_width_skips_rather_than_judging_wrong_joints(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """Dimension `i` of a five-dimension log is not dimension `i` of this layout."""
        result = detect_t5(
            series_from(train=losses(), pred_var=[0.2, 0.0, 0.3, 0.3, 0.3]), cfg, layout
        )

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["T5"]
        assert "action_layout" in result.skipped[0].reason

    def test_a_dimension_logged_in_no_record_of_the_window_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        early_only = {step: [0.2, 0.3, 0.3] for step in range(0, 500, 10)}
        series = series_from(train=losses(), pred_var=early_only)

        result = detect_t5(series, cfg, layout)

        assert result.findings == []
        assert {skip.code for skip in result.skipped} == {"T5"}
        assert len(result.skipped) == 2  # both unmasked dimensions, named one by one
