"""T7 - the fine-tune forgot what its parent knew (DA-08 task 4, AC 2, 6).

Two things decide whether T7 means anything. It must never read a missing
parent probe as "nothing was forgotten", which is the silent pass FR21 forbids
and the reason every case here checks `skipped` as well as `findings`. And it
must know which direction is worse for each metric: a P1 accuracy falling and
a P3 error rising are the same fault, so a test for each keeps the sign honest.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from flywheel.contracts.artifacts import ProbeP4
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.forgetting import detect_t7

Codes = Callable[[DetectorResult], list[str]]
P4Builder = Callable[..., ProbeP4]


class TestCaught:
    def test_a_p1_accuracy_below_the_parent(
        self, p4_from: P4Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        child = p4_from(accuracy={"where": 0.50, "what": 0.75})
        parent = p4_from(checkpoint_id="ckpt-parent", accuracy={"where": 0.90, "what": 0.75})

        result = detect_t7(child, parent, cfg)

        assert codes(result) == ["T7"]
        assert result.findings[0].group == "p1.where"
        assert result.findings[0].value == pytest.approx(0.444, abs=1e-3)
        assert result.findings[0].threshold == cfg.t7.max_relative_drop

    def test_a_p3_group_error_above_the_parent(
        self, p4_from: P4Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        """An error that grew is forgetting too, though the subtraction flips."""
        child = p4_from(error_by_group={"arm": 0.20, "hand": 0.12})
        parent = p4_from(checkpoint_id="ckpt-parent", error_by_group={"arm": 0.10, "hand": 0.12})

        result = detect_t7(child, parent, cfg)

        assert codes(result) == ["T7"]
        assert result.findings[0].group == "p3.error_by_group.arm"
        assert result.findings[0].value == pytest.approx(1.0)

    def test_a_hand_event_drifting_further_off(
        self, p4_from: P4Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        """What counts is the distance from the demonstrated step, not its sign."""
        child = p4_from(hand_event_offset_steps=-4.0)
        parent = p4_from(checkpoint_id="ckpt-parent", hand_event_offset_steps=2.0)

        result = detect_t7(child, parent, cfg)

        assert codes(result) == ["T7"]
        assert result.findings[0].group == "p3.hand_event_offset_steps"
        assert result.findings[0].value == pytest.approx(1.0)

    def test_every_regressed_metric_is_reported_once(
        self, p4_from: P4Builder, cfg: TrainThresholds
    ) -> None:
        child = p4_from(accuracy={"where": 0.40, "what": 0.30}, error_by_group={"arm": 0.30})
        parent = p4_from(
            checkpoint_id="ckpt-parent",
            accuracy={"where": 0.90, "what": 0.80},
            error_by_group={"arm": 0.10},
        )

        result = detect_t7(child, parent, cfg)

        assert sorted(finding.group or "" for finding in result.findings) == [
            "p1.what",
            "p1.where",
            "p3.error_by_group.arm",
        ]


class TestClean:
    def test_a_fine_tune_that_improved_is_neither_flagged_nor_skipped(
        self, clean_p4_pair: tuple[ProbeP4, ProbeP4], cfg: TrainThresholds
    ) -> None:
        child, parent = clean_p4_pair

        result = detect_t7(child, parent, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_a_drop_under_the_threshold_is_not_forgetting(
        self, p4_from: P4Builder, cfg: TrainThresholds
    ) -> None:
        """Probe scores move between runs; only a drop past the threshold counts."""
        child = p4_from(accuracy={"where": 0.78}, error_by_group={"arm": 0.10})
        parent = p4_from(
            checkpoint_id="ckpt-parent", accuracy={"where": 0.80}, error_by_group={"arm": 0.10}
        )

        result = detect_t7(child, parent, cfg)

        assert result.findings == []
        assert result.skipped == []


class TestCannotJudge:
    def test_t7_needs_the_parent_probe(
        self, p4_from: P4Builder, cfg: TrainThresholds, codes: Codes, skipped_codes: Codes
    ) -> None:
        """The first fine-tune off a published checkpoint has no parent P4 at all.

        That is the case the demo runs, so the skip has to say which probe is
        missing rather than let the checkpoint pass as clean.
        """
        result = detect_t7(p4_from(accuracy={"where": 0.50}), None, cfg)

        assert codes(result) == []
        assert skipped_codes(result) == ["T7"]
        assert "cha" in result.skipped[0].reason
        assert "ckpt-parent" in result.skipped[0].reason

    def test_a_probe_of_another_checkpoint_is_not_the_parent(
        self, p4_from: P4Builder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        child = p4_from(parent_checkpoint_id="ckpt-parent", accuracy={"where": 0.50})
        other = p4_from(checkpoint_id="ckpt-somebody-else", accuracy={"where": 0.90})

        result = detect_t7(child, other, cfg)

        assert result.findings == []
        assert skipped_codes(result) == ["T7"]
        assert "ckpt-somebody-else" in result.skipped[0].reason

    def test_two_probe_sets_cannot_be_compared(
        self, p4_from: P4Builder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        """A score is only comparable against a score from the same probe data."""
        child = p4_from(accuracy={"where": 0.50}, probe_set="probe-set-1")
        parent = p4_from(
            checkpoint_id="ckpt-parent", accuracy={"where": 0.90}, probe_set="probe-set-2"
        )

        result = detect_t7(child, parent, cfg)

        assert result.findings == []
        assert skipped_codes(result) == ["T7"]
        assert "dataset_sha256" in result.skipped[0].reason

    def test_a_metric_the_parent_does_not_have_is_named_not_dropped(
        self, p4_from: P4Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        child = p4_from(accuracy={"where": 0.80, "colour": 0.20})
        parent = p4_from(checkpoint_id="ckpt-parent", accuracy={"where": 0.80})

        result = detect_t7(child, parent, cfg)

        assert codes(result) == []
        assert [skip.code for skip in result.skipped] == ["T7"]
        assert "colour" in result.skipped[0].reason

    def test_a_parent_value_of_zero_carries_no_scale(
        self, p4_from: P4Builder, cfg: TrainThresholds
    ) -> None:
        """A metric that got worse than a parent of zero has no relative amount.

        It is a regression, so reporting it clean would be wrong; there is no
        fraction to compare against the threshold, so reporting it as a finding
        would put a made-up number in the artifact. It is named as a skip.
        """
        child = p4_from(error_by_group={"arm": 0.05})
        parent = p4_from(checkpoint_id="ckpt-parent", error_by_group={"arm": 0.00})

        result = detect_t7(child, parent, cfg)

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["T7"]
        assert "arm" in result.skipped[0].reason
