"""O1-O4 - what the P3 probe says about the actions themselves (DA-08 task 4, AC 2, 6).

Each code gets a positive and a negative case, and each negative case checks
`skipped` too: a probe field the contract does not carry has to come out as a
named skip, never as a clean action head (FR21).

O4 is the code AC 2 is about. The joint limits belong to the embodiment, so
they are read off the `ActionLayout` the log was written under; the tests here
hold a layout whose third dimension is masked and limitless, and a probe that
names it must not become a finding against a number written in code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from flywheel.contracts.artifacts import ProbeP3
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.offline import (
    detect_o1,
    detect_o2,
    detect_o3,
    detect_o4,
    detect_offline,
)
from flywheel.eval.diagnosis.train.reader import LayoutView

Codes = Callable[[DetectorResult], list[str]]
P3Builder = Callable[..., ProbeP3]


class TestO1GroupError:
    def test_a_group_far_over_the_other_groups(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        """With no budget in the config, a group is judged against the group median."""
        result = detect_o1(p3_from(error_by_group={"arm": 0.10, "hand": 0.90, "waist": 0.10}), cfg)

        assert codes(result) == ["O1"]
        assert result.findings[0].group == "hand"
        assert result.findings[0].value == pytest.approx(0.90)
        assert result.findings[0].threshold == pytest.approx(0.10 * cfg.o1.max_error_ratio)

    def test_a_group_over_its_own_budget(self, p3_from: P3Builder, cfg: TrainThresholds) -> None:
        """A budget written for the group wins over the median rule."""
        thresholds = replace(cfg, o1=replace(cfg.o1, max_error_by_group={"hand": 0.05}))

        result = detect_o1(p3_from(error_by_group={"arm": 0.10, "hand": 0.10}), thresholds)

        assert [finding.group for finding in result.findings] == ["hand"]
        assert result.findings[0].threshold == pytest.approx(0.05)

    def test_the_clean_probe_is_neither_flagged_nor_skipped(
        self, clean_p3: ProbeP3, cfg: TrainThresholds
    ) -> None:
        result = detect_o1(clean_p3, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_every_group_equally_bad_is_not_one_bad_group(
        self, p3_from: P3Builder, cfg: TrainThresholds
    ) -> None:
        """A probe where everything is off is a bad checkpoint, not a bad group."""
        result = detect_o1(p3_from(error_by_group={"arm": 0.90, "hand": 0.90}), cfg)

        assert result.findings == []

    def test_a_probe_without_group_errors_skips(
        self, p3_from: P3Builder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        result = detect_o1(p3_from(error_by_group={}), cfg)

        assert skipped_codes(result) == ["O1"]
        assert "error_by_group" in result.skipped[0].reason


class TestO2ChunkPosition:
    def test_error_growing_along_the_chunk(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        result = detect_o2(p3_from(error_by_chunk_pos=[0.1, 0.2, 0.4, 0.8]), cfg)

        assert codes(result) == ["O2"]
        assert result.findings[0].value > cfg.o2.max_slope

    def test_a_flat_chunk_with_a_bad_last_position(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        """The ratio catches what a slope fitted over a long chunk flattens out."""
        flat = [0.01] * 40

        result = detect_o2(p3_from(error_by_chunk_pos=[*flat, 0.20]), cfg)

        assert codes(result) == ["O2"]
        assert result.findings[0].threshold == pytest.approx(cfg.o2.max_ratio)

    def test_one_finding_when_both_rules_fire(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        result = detect_o2(p3_from(error_by_chunk_pos=[0.05, 0.3, 0.6, 1.2]), cfg)

        assert codes(result) == ["O2"]

    def test_the_clean_probe_is_neither_flagged_nor_skipped(
        self, clean_p3: ProbeP3, cfg: TrainThresholds
    ) -> None:
        result = detect_o2(clean_p3, cfg)

        assert result.findings == []
        assert result.skipped == []

    def test_a_single_chunk_position_is_no_trend(
        self, p3_from: P3Builder, cfg: TrainThresholds, skipped_codes: Codes
    ) -> None:
        result = detect_o2(p3_from(error_by_chunk_pos=[0.5]), cfg)

        assert result.findings == []
        assert skipped_codes(result) == ["O2"]
        assert "error_by_chunk_pos" in result.skipped[0].reason


class TestO3HandEvent:
    def test_a_hand_event_off_the_demonstrated_step(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        result = detect_o3(p3_from(hand_event_offset_steps=float(cfg.o3.max_offset_steps + 3)), cfg)

        assert codes(result) == ["O3"]
        assert result.findings[0].threshold == pytest.approx(cfg.o3.max_offset_steps)

    def test_an_early_hand_event_counts_like_a_late_one(
        self, p3_from: P3Builder, cfg: TrainThresholds, codes: Codes
    ) -> None:
        offset = -float(cfg.o3.max_offset_steps + 3)

        result = detect_o3(p3_from(hand_event_offset_steps=offset), cfg)

        assert codes(result) == ["O3"]
        assert result.findings[0].value == pytest.approx(abs(offset))

    def test_the_clean_probe_is_neither_flagged_nor_skipped(
        self, clean_p3: ProbeP3, cfg: TrainThresholds
    ) -> None:
        result = detect_o3(clean_p3, cfg)

        assert result.findings == []
        assert result.skipped == []


class TestO4JointLimits:
    def test_o4_uses_the_layout_limits_not_a_number_in_code(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_o4(p3_from(out_of_limit_dims=[1]), cfg, layout)

        assert [finding.dim for finding in result.findings] == [1]
        assert result.findings[0].code == "O4"
        assert result.findings[0].group == layout.layout.dimensions[1].group

    def test_the_clean_probe_is_neither_flagged_nor_skipped(
        self, clean_p3: ProbeP3, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_o4(clean_p3, cfg, layout)

        assert result.findings == []
        assert result.skipped == []

    def test_a_masked_dimension_is_not_an_action_fault(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """The padding dimensions of G1 drive nothing, so they cannot leave a limit."""
        result = detect_o4(p3_from(out_of_limit_dims=[2]), cfg, layout)

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["O4"]
        assert "masked" in result.skipped[0].reason

    def test_a_dimension_the_layout_does_not_have_skips(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """A probe run under another action layout names dimensions this one lacks."""
        result = detect_o4(p3_from(out_of_limit_dims=[7]), cfg, layout)

        assert result.findings == []
        assert [skip.code for skip in result.skipped] == ["O4"]
        assert "action_layout" in result.skipped[0].reason

    def test_a_frame_fraction_the_probe_does_not_carry_skips(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """`max_fraction` above zero needs a per-frame count P3 does not report."""
        thresholds = replace(cfg, o4=replace(cfg.o4, max_fraction=0.01))

        result = detect_o4(p3_from(out_of_limit_dims=[1]), thresholds, layout)

        assert [skip.code for skip in result.skipped] == ["O4b"]
        assert "max_fraction" in result.skipped[0].reason


class TestAllFour:
    def test_the_clean_probe_passes_every_offline_code(
        self, clean_p3: ProbeP3, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        result = detect_offline(clean_p3, cfg, layout)

        assert result.findings == []
        assert result.skipped == []

    def test_each_code_is_judged_independently(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView, codes: Codes
    ) -> None:
        """One probe can carry more than one offline fault, and does on a bad run."""
        probe = p3_from(
            error_by_group={"arm": 0.10, "hand": 0.90, "waist": 0.10},
            error_by_chunk_pos=[0.1, 0.2, 0.4, 0.8],
            hand_event_offset_steps=float(cfg.o3.max_offset_steps + 3),
            out_of_limit_dims=[1],
        )

        result = detect_offline(probe, cfg, layout)

        assert codes(result) == ["O1", "O2", "O3", "O4"]

    def test_offline_findings_carry_no_train_step(
        self, p3_from: P3Builder, cfg: TrainThresholds, layout: LayoutView
    ) -> None:
        """A probe is measured on a checkpoint, not at a step of the train job."""
        result = detect_offline(p3_from(hand_event_offset_steps=50.0), cfg, layout)

        assert [finding.start_step for finding in result.findings] == [0]
