"""The stage attribution table, one case per row (DA-13 AC 3, 4).

Each row of spec section 6.4 gets the evidence that makes it apply and must
come back naming that row and nothing else. Two further things are tested
because getting them wrong would be worse than getting a row wrong: a
hypothesis with no probe behind it must be reported as unjudged rather than
silently dropped, and nothing this module produces may be marked confirmed.
"""

from __future__ import annotations

import pytest
from flywheel.eval.config import ConfigError, StageTable, load_stage_table
from flywheel.eval.diagnosis.stage.attribute import (
    EVIDENCE_RULES,
    attribute_stage,
    related_groups,
)
from flywheel.eval.diagnosis.system.reader import StageInputs


def _rows(attribution) -> list[str]:
    return [hypothesis.row_id for hypothesis in attribution.hypotheses]


def test_the_shipped_table_has_every_row_of_the_spec(table: StageTable) -> None:
    assert [row.row_id for row in table.rows] == [
        "stage1_perception",
        "stage3_action_group",
        "runtime_distribution_shift",
        "stage3_forgetting",
        "out_of_domain",
    ]


def test_p1_wrong_on_the_failure_frames_is_blamed_on_perception(
    table, p1_from, p3_from
) -> None:
    p1 = p1_from(accuracy=0.4)
    inputs = StageInputs(p1=p1, p3=p3_from({"arm": 0.05}), failed_step=2, action_groups=("arm",))

    attribution = attribute_stage(inputs, table)

    assert _rows(attribution) == ["stage1_perception"]
    hypothesis = attribution.hypotheses[0]
    assert hypothesis.attribute_to == "Stage 1 · nhận thức"
    assert [(item.probe, item.value) for item in hypothesis.evidence] == [("P1", 0.4)]


def test_p1_evidence_names_the_probe_set_not_the_failure_frames(table, p1_from, p3_from) -> None:
    # `ProbeP1` is a score over the whole probe set (`dataset_sha256`), not
    # over the frames of this failure; the evidence must say which set it was
    # and must not claim the probe ran on frames it never saw.
    p1 = p1_from(accuracy=0.4)
    inputs = StageInputs(p1=p1, p3=p3_from({"arm": 0.05}), action_groups=("arm",))

    where = attribute_stage(inputs, table).hypotheses[0].evidence[0].where

    assert p1.dataset_sha256 in where
    assert "khung hình" not in where


def test_the_perception_row_consumes_no_budget(table, p1_from, p3_from) -> None:
    # Decision of 30/10/2026: spec section 7.3 fixes visual augmentation for
    # every branch, so this row has no data intervention left to ask for.
    inputs = StageInputs(p1=p1_from(accuracy=0.4), p3=p3_from(), action_groups=("arm",))

    assert attribute_stage(inputs, table).hypotheses[0].consumes_budget is False


def test_p1_right_and_p3_high_is_blamed_on_learning_that_group(table, p1_from, p3_from) -> None:
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.8, "leg": 0.02}),
        failed_step=3,
        action_groups=("arm",),
    )

    attribution = attribute_stage(inputs, table)

    assert _rows(attribution) == ["stage3_action_group"]
    evidence = attribution.hypotheses[0].evidence[0]
    assert evidence.probe == "P3"
    assert "arm" in evidence.where
    assert evidence.value == pytest.approx(0.8)


def test_only_the_groups_behind_the_failed_step_are_looked_at(table, p1_from, p3_from) -> None:
    # The leg group is far over the threshold and has nothing to do with the
    # step that broke; blaming it would send the engineer to collect the wrong
    # data.
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.05, "leg": 0.9}),
        failed_step=2,
        action_groups=("arm",),
    )

    assert "stage3_action_group" not in _rows(attribute_stage(inputs, table))


def test_p1_right_p3_low_and_a_closed_loop_failure_is_a_run_time_shift(
    table, p1_from, p3_from
) -> None:
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.02}),
        failed_step=4,
        action_groups=("arm",),
        closed_loop_failed=True,
    )

    attribution = attribute_stage(inputs, table)

    assert _rows(attribution) == ["runtime_distribution_shift"]
    assert attribution.hypotheses[0].evidence[0].where == "bước 4"


def test_a_failure_offline_as_well_is_not_a_run_time_shift(table, p1_from, p3_from) -> None:
    # P3 is high, so the offline error already explains it: the row exists for
    # the case where offline looked fine and the closed loop still broke.
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.8}),
        action_groups=("arm",),
        closed_loop_failed=True,
    )

    assert "runtime_distribution_shift" not in _rows(attribute_stage(inputs, table))


def test_t7_after_finetune_is_blamed_on_forgetting(table, p1_from, p3_from, p4_from) -> None:
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.05}),
        p4=p4_from(),
        t7=True,
        action_groups=("arm",),
    )

    attribution = attribute_stage(inputs, table)

    assert "stage3_forgetting" in _rows(attribution)
    forgetting = next(h for h in attribution.hypotheses if h.row_id == "stage3_forgetting")
    assert forgetting.evidence[0].probe == "P4"
    assert "ckpt_0" in forgetting.evidence[0].where


def test_p4_without_the_t7_finding_is_not_forgetting(table, p1_from, p3_from, p4_from) -> None:
    # DA-08 owns the forgetting rule; this story reads its verdict and does not
    # recompute it, so two stories cannot disagree about one checkpoint.
    inputs = StageInputs(
        p1=p1_from(), p3=p3_from({"arm": 0.8}), p4=p4_from(), t7=False, action_groups=("arm",)
    )

    assert "stage3_forgetting" not in _rows(attribute_stage(inputs, table))


def test_a_caller_that_has_not_run_t7_gets_unavailable_not_inapplicable(
    table, p1_from, p3_from, p4_from
) -> None:
    # Without DA-08's T7 verdict nobody knows whether the checkpoint forgot;
    # reading the absence as "did not forget" is the silent pass FR21 forbids.
    inputs = StageInputs(
        p1=p1_from(), p3=p3_from({"arm": 0.05}), p4=p4_from(), action_groups=("arm",)
    )

    attribution = attribute_stage(inputs, table)

    assert "stage3_forgetting" not in _rows(attribution)
    reasons = {item.row_id: item.reason for item in attribution.unavailable}
    assert "T7" in reasons["stage3_forgetting"]


def test_out_of_domain_is_not_blamed_on_any_stage(table, p1_from, p3_from) -> None:
    # The row exists to stop exactly that: a condition outside the train domain
    # is reported, not attributed (spec section 6.8).
    inputs = StageInputs(
        p1=p1_from(accuracy=0.2),
        p3=p3_from({"arm": 0.9}),
        action_groups=("arm",),
        out_of_domain=True,
        failed_step=1,
    )

    attribution = attribute_stage(inputs, table)

    assert _rows(attribution) == ["out_of_domain"]
    assert attribution.hypotheses[0].attribute_to == "Không phải lỗi stage"
    assert attribution.hypotheses[0].consumes_budget is False


def test_a_row_with_no_probe_behind_it_is_reported_as_unjudged(table) -> None:
    attribution = attribute_stage(StageInputs(), table)

    assert attribution.hypotheses == []
    assert {item.row_id for item in attribution.unavailable} == {
        "stage1_perception",
        "stage3_action_group",
        "runtime_distribution_shift",
        "stage3_forgetting",
    }
    assert all("probe" in item.reason for item in attribution.unavailable)


def test_a_missing_group_mapping_is_unjudged_not_a_clean_answer(table, p1_from, p3_from) -> None:
    inputs = StageInputs(p1=p1_from(), p3=p3_from({"arm": 0.9}), action_groups=())

    attribution = attribute_stage(inputs, table)

    assert _rows(attribution) == []
    assert "nhóm action" in next(
        item.reason for item in attribution.unavailable if item.row_id == "stage3_action_group"
    )


def test_nothing_this_module_produces_is_confirmed(table, p1_from, p3_from) -> None:
    # AC 4: the hypothesis is a proposal the engineer confirms on the evidence
    # card, so nothing here may mark itself confirmed.
    inputs = StageInputs(p1=p1_from(accuracy=0.3), p3=p3_from(), action_groups=("arm",))

    assert all(not h.confirmed for h in attribute_stage(inputs, table).hypotheses)


def test_every_evidence_rule_in_the_table_is_implemented(table: StageTable) -> None:
    assert {row.evidence for row in table.rows} <= set(EVIDENCE_RULES)


def test_a_row_naming_a_rule_nobody_implements_is_refused(tmp_path, stage_config) -> None:
    source = stage_config.read_text(encoding="utf-8")
    broken = tmp_path / "stage.yaml"
    swapped = source.replace("evidence: out_of_domain", "evidence: p2_token_loss_high")
    broken.write_text(swapped, encoding="utf-8")

    with pytest.raises(ConfigError, match="không có luật nào"):
        load_stage_table(broken, EVIDENCE_RULES)


def test_the_table_hash_names_the_file_that_was_read(tmp_path, stage_config) -> None:
    source = stage_config.read_text(encoding="utf-8")
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    first.write_text(source, encoding="utf-8")
    moved = source.replace("p1_min_accuracy: 0.9", "p1_min_accuracy: 0.8")
    second.write_text(moved, encoding="utf-8")

    assert load_stage_table(first, EVIDENCE_RULES)[1] != load_stage_table(second, EVIDENCE_RULES)[1]


def test_related_groups_is_a_fallback_over_every_group_p3_carries(p3_from) -> None:
    assert related_groups(p3_from({"leg": 0.1, "arm": 0.2})) == ("arm", "leg")
