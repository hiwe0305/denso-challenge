"""The score of one episode and the record it leaves (DA-36 task 5, AC 5)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from flywheel.contracts import TaskDefinition
from flywheel.eval.api import SCORER_CONFIG_DIR, score_record, score_trace, store_score
from flywheel.eval.scorer.artifact import STORE_RECORDS, build_record
from flywheel.eval.scorer.status import ScorerError

MakeRows = Callable[..., list[dict[str, object]]]
CONFIG = SCORER_CONFIG_DIR / "two-table.yaml"


def write(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_a_clean_episode_scores_as_a_pass(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    score = score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG)

    assert score.success is True
    assert [step.status.value for step in score.steps] == ["pass"] * 6
    # The control of AC 6: no failure *and* nothing unknown.
    assert score.unknown_steps == ()
    assert score.failure.failure_kind is None


def test_the_same_trace_always_scores_the_same(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: object
) -> None:
    path = write(tmp_path / "ep.jsonl", make_rows(hand_object_contact=sig.const(0.0)))  # type: ignore[attr-defined]

    first = score_record(score_trace(path, task, CONFIG))
    second = score_record(score_trace(path, task, CONFIG))

    # AC 5: a pure step, so the record is identical byte for byte, hash and all.
    assert first.model_dump_json() == second.model_dump_json()


def test_the_config_hash_travels_with_the_score(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    score = score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG)

    assert len(score.config_sha256) == 64
    assert score_record(score).config_sha256 == score.config_sha256


def test_a_config_for_another_task_is_refused(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    other = tmp_path / "tray.yaml"
    other.write_text(
        "task_id: tray\nscorer_version: '0.1.0'\nthresholds: {r_reach: 0.08}\n"
        "balance: {min_height: 0.6, max_tilt: 0.3, height_signal: torso_height, "
        "tilt_signal: torso_tilt}\n",
        encoding="utf-8",
    )

    # The thresholds of another task are not approximately right, they are the
    # wrong numbers, and scoring with them would look like a result.
    with pytest.raises(ScorerError, match="task `tray`"):
        score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, other)


def test_the_record_carries_the_fields_score_has(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: object
) -> None:
    rows = make_rows(object_in_target_zone=sig.const(0.0))  # type: ignore[attr-defined]

    record = build_record(score_trace(write(tmp_path / "ep.jsonl", rows), task, CONFIG), level=2)

    assert record.episode_id == "ep_test"
    assert record.step_status[:4] == ["pass", "pass", "pass", "pass"]
    assert record.first_failed_step == 4
    assert record.failure_kind == "L-PLACE"
    assert record.failure_class == "place"
    assert record.level == 2
    assert record.balance_violated is False
    assert record.meta["step_names"][4] == "place"


def test_an_unknown_step_reaches_the_record_with_its_reason(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    rows = [
        {key: value for key, value in row.items() if key != "object_height"} for row in make_rows()
    ]

    record = build_record(score_trace(write(tmp_path / "ep.jsonl", rows), task, CONFIG))

    assert record.success is None
    assert record.failure_kind == "L-UNKNOWN"
    assert record.meta["missing_signals"] == ["object_height"]
    assert "object_height" in record.meta["unknown_steps"]["approach"]


def test_a_balance_violation_reaches_the_record(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: object
) -> None:
    rows = make_rows(torso_tilt=sig.switch(12, 0.05, 0.8))  # type: ignore[attr-defined]

    record = build_record(score_trace(write(tmp_path / "ep.jsonl", rows), task, CONFIG))

    assert record.balance_violated is True
    assert record.failure_kind == "L-BALANCE"
    assert record.failure_class == "balance"
    assert record.meta["balance"]["row"] == 12


def test_the_store_is_append_only(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    score = score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG)
    store = tmp_path / "store"

    first = store_score(score, store)
    second = store_score(score, store)

    assert first == second == store / STORE_RECORDS
    lines = first.read_text(encoding="utf-8").strip().splitlines()
    # Scoring again adds a record beside the first; nothing is rewritten.
    assert len(lines) == 2
    assert json.loads(lines[0])["episode_id"] == "ep_test"


def test_the_record_rejects_a_field_nobody_declared(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    record = build_record(score_trace(write(tmp_path / "ep.jsonl", make_rows()), task, CONFIG))

    # `Score` is a contract record; a lane that could bolt a field onto it
    # would be a lane the other two cannot read (AC 1).
    with pytest.raises(ValueError, match="extra"):
        record.model_copy(update={"nhan_xet": "tốt"}).model_validate(
            {**record.model_dump(), "nhan_xet": "tốt"}
        )
