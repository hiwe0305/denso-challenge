"""T8 - gradient faults (DA-08 task 3, AC 1, 6).

The two branches are tested apart because they fail apart: a log can answer
one and not the other, and the artifact has to say which half went unmeasured.
Branch (a) skips as `T8a` and branch (b) as `T8b`, while a finding is always
`T8` - the only code the contract accepts (`FindingCode`).

Branch (a) has no tolerance to tune. A job that declares the VLM frozen and
puts gradient through it is not slightly wrong; it trained a different model
than the one its config describes, so every comparison against it is void.
"""

from __future__ import annotations

from collections.abc import Callable

from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.gradients import detect_t8
from flywheel.eval.diagnosis.train.reader import TrainSeries

STEPS = range(0, 1001, 10)

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]


def losses() -> dict[int, float]:
    return {step: 1.0 - 0.0002 * step for step in STEPS}


class TestFrozenVlm:
    def test_gradient_through_a_frozen_vlm_is_caught(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        result = detect_t8(
            series_from(
                train=losses(),
                grad_vlm={step: 0.0 if step < 500 else 0.01 for step in STEPS},
                grad_action=0.1,
                vlm_frozen=True,
            ),
            cfg,
        )

        assert codes(result) == ["T8"]
        assert result.findings[0].start_step == 500
        assert result.findings[0].threshold == cfg.t8.frozen_tolerance

    def test_a_frozen_vlm_at_exactly_zero_is_clean(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.0, grad_action=0.1, vlm_frozen=True), cfg
        )

        assert result.findings == []
        assert result.skipped == []

    def test_an_unfrozen_vlm_may_have_gradient(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        """Nothing to report and nothing to skip: the job never claimed otherwise."""
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.5, grad_action=0.1, vlm_frozen=False), cfg
        )

        assert result.findings == []
        assert result.skipped == []

    def test_a_log_that_does_not_say_whether_the_vlm_was_frozen(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t8(series_from(train=losses(), grad_action=0.1), cfg)

        assert [skip.code for skip in result.skipped] == ["T8a"]
        assert "vlm_frozen" in result.skipped[0].reason

    def test_a_frozen_claim_with_no_gradient_logged_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        """ "Frozen" cannot be confirmed from a log that never measured it."""
        result = detect_t8(series_from(train=losses(), grad_action=0.1, vlm_frozen=True), cfg)

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["T8a"]
        assert "grad_norm_vlm" in result.skipped[0].reason


class TestActionHeadSpikes:
    def test_repeated_spikes_are_caught_at_the_first_one(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        over = cfg.t8.max_grad_norm * 2
        spiking = {
            step: over if 200 <= step <= 200 + 10 * cfg.t8.max_exceedances else 0.1
            for step in STEPS
        }
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.0, grad_action=spiking, vlm_frozen=True), cfg
        )

        assert codes(result) == ["T8"]
        assert result.findings[0].start_step == 200
        assert result.findings[0].threshold == cfg.t8.max_grad_norm

    def test_a_single_spike_is_a_batch_not_a_fault(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        one = {step: cfg.t8.max_grad_norm * 5 if step == 300 else 0.1 for step in STEPS}
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.0, grad_action=one, vlm_frozen=True), cfg
        )

        assert result.findings == []
        assert result.skipped == []

    def test_exactly_the_allowed_number_of_spikes_is_still_clean(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        over = cfg.t8.max_grad_norm * 2
        allowed = {step: over if step < 10 * cfg.t8.max_exceedances else 0.1 for step in STEPS}
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.0, grad_action=allowed, vlm_frozen=True), cfg
        )

        assert result.findings == []

    def test_a_log_without_the_action_gradient_skips(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t8(series_from(train=losses(), grad_vlm=0.0, vlm_frozen=True), cfg)

        assert [skip.code for skip in result.skipped] == ["T8b"]
        assert "grad_norm_action" in result.skipped[0].reason


class TestBothBranches:
    def test_the_clean_job_is_neither_flagged_nor_skipped(
        self, clean_series: TrainSeries, cfg: TrainThresholds
    ) -> None:
        result = detect_t8(clean_series, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_both_faults_at_once_report_twice(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        over = cfg.t8.max_grad_norm * 2
        result = detect_t8(
            series_from(train=losses(), grad_vlm=0.01, grad_action=over, vlm_frozen=True), cfg
        )

        assert codes(result) == ["T8", "T8"]

    def test_one_branch_judged_and_one_skipped(
        self, series_from: SeriesBuilder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        """A finding on one branch must not swallow the other branch's skip."""
        result = detect_t8(series_from(train=losses(), grad_vlm=0.01, vlm_frozen=True), cfg)

        assert codes(result) == ["T8"]
        assert [skip.code for skip in result.skipped] == ["T8b"]

    def test_an_empty_log_skips_under_the_bare_code(
        self, series_from: SeriesBuilder, cfg: TrainThresholds
    ) -> None:
        result = detect_t8(series_from(), cfg)

        assert [skip.code for skip in result.skipped] == ["T8"]
