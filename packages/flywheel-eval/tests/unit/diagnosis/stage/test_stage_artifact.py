"""The stage attribution record: what it keeps, and what it refuses to claim (DA-13 AC 3, 4).

Two things are load-bearing. A record whose `hypotheses` and `unavailable` are
both empty has to mean "every row was judged and none applied", so what was
unjudged travels with what applied. And nothing the lane writes may be marked
confirmed, because that mark is the engineer's on the evidence card.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.eval.api import attribute_failure_stage, store_stage_attribution
from flywheel.eval.config import StageTable
from flywheel.eval.diagnosis.stage.artifact import (
    STAGE_RECORDS,
    build_stage_record,
    write_stage_record,
)
from flywheel.eval.diagnosis.stage.attribute import attribute_stage
from flywheel.eval.diagnosis.system.reader import StageInputs


def test_the_record_keeps_the_evidence_of_every_hypothesis(table, p1_from, p3_from) -> None:
    inputs = StageInputs(
        p1=p1_from(accuracy=0.95),
        p3=p3_from({"arm": 0.9}),
        failed_step=3,
        action_groups=("arm",),
    )

    record = build_stage_record(attribute_stage(inputs, table), "ep_1", "a" * 64, 3)

    assert record.episode_id == "ep_1"
    assert record.failed_step == 3
    assert [h.row_id for h in record.hypotheses] == ["stage3_action_group"]
    assert record.hypotheses[0].evidence[0].probe == "P3"
    assert record.hypotheses[0].evidence[0].value == pytest.approx(0.9)


def test_the_record_keeps_what_could_not_be_judged(table) -> None:
    record = build_stage_record(attribute_stage(StageInputs(), table), "ep_1", "a" * 64)

    assert record.hypotheses == []
    assert {item.code for item in record.unavailable} == {
        "stage1_perception",
        "stage3_action_group",
        "runtime_distribution_shift",
        "stage3_forgetting",
    }


def test_no_hypothesis_is_written_as_confirmed(table, p1_from, p3_from) -> None:
    inputs = StageInputs(p1=p1_from(accuracy=0.2), p3=p3_from(), action_groups=("arm",))

    record = build_stage_record(attribute_stage(inputs, table), "ep_1", "a" * 64)

    assert record.hypotheses
    assert all(h.confirmed is False for h in record.hypotheses)


def test_the_store_is_append_only(tmp_path: Path, table: StageTable, p1_from, p3_from) -> None:
    inputs = StageInputs(p1=p1_from(accuracy=0.2), p3=p3_from(), action_groups=("arm",))
    record = build_stage_record(attribute_stage(inputs, table), "ep_1", "a" * 64)

    first = write_stage_record(record, tmp_path)
    write_stage_record(record, tmp_path)

    assert first == tmp_path / STAGE_RECORDS
    assert len(first.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_the_api_records_the_hash_of_the_table_it_read(
    stage_config: Path, tmp_path: Path, p1_from, p3_from
) -> None:
    inputs = StageInputs(p1=p1_from(accuracy=0.2), p3=p3_from(), action_groups=("arm",))

    record = attribute_failure_stage(inputs, "ep_1", stage_config)
    written = store_stage_attribution(record, tmp_path)

    assert len(record.table_sha256) == 64
    stored = json.loads(written.read_text(encoding="utf-8").strip())
    assert stored["table_sha256"] == record.table_sha256
    assert stored["hypotheses"][0]["confirmed"] is False
