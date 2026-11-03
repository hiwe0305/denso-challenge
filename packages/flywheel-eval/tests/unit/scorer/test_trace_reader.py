"""The reading layer of the scorer (DA-36 task 1, AC 1, 5)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from flywheel.contracts import TaskDefinition
from flywheel.eval.scorer.reader import TraceError, read_signals, read_trace

MakeRows = Callable[..., list[dict[str, object]]]


def write(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_reads_every_signal_the_task_asked_for(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    trace = read_trace(write(tmp_path / "ep.jsonl", make_rows()), task)

    assert trace.num_steps == 20
    assert trace.missing_signals == ()
    assert {signal.name for signal in task.required_signals()} <= set(trace.signals.column_names)


def test_names_the_missing_signals_instead_of_failing(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    rows = [
        {key: value for key, value in row.items() if key != "object_in_target_zone"}
        for row in make_rows()
    ]

    trace = read_trace(write(tmp_path / "ep.jsonl", rows), task)

    # A signal nobody recorded is the reason a step is unknown, not an error:
    # the read has to hand that reason on rather than swallow it (AC 2).
    assert trace.missing_signals == ("object_in_target_zone",)


def test_a_gap_in_one_signal_stays_a_gap(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    rows = make_rows()
    del rows[5]["object_height"]

    trace = read_trace(write(tmp_path / "ep.jsonl", rows), task)

    assert trace.signals["object_height"].to_pylist()[5] is None
    assert trace.missing_signals == ()


def test_a_value_that_is_not_finite_is_a_gap_not_a_number(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    # `json.loads` accepts NaN, and `nan < min_height` is false, so a NaN left
    # in place clears every limit it is checked against (FR21).
    rows = [{**row, "torso_height": float("nan")} for row in make_rows()]
    path = write(tmp_path / "ep.jsonl", rows)

    trace = read_trace(path, task)

    assert trace.signals["torso_height"].to_pylist() == [None] * 20
    assert trace.missing_signals == ()


def test_the_trace_hash_names_the_bytes_that_were_read(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    # `Score.id` of 03 section 4.3 is built from it, so it has to be the hash of
    # the file this score was computed from, not of the rows after parsing.
    path = write(tmp_path / "ep.jsonl", make_rows())

    first = read_trace(path, task).trace_sha256

    assert len(first) == 64
    assert read_trace(path, task).trace_sha256 == first
    other = write(tmp_path / "other.jsonl", make_rows(steps=3))
    assert read_trace(other, task).trace_sha256 != first


def test_takes_the_episode_id_from_the_rows(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    trace = read_trace(write(tmp_path / "ep.jsonl", make_rows()), task)

    assert trace.episode_id == "ep_test"
    assert "episode_id" not in trace.signals.column_names


def test_falls_back_to_the_file_name_then_the_override(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    rows = [
        {key: value for key, value in row.items() if key != "episode_id"} for row in make_rows()
    ]
    path = write(tmp_path / "ep_0042.jsonl", rows)

    assert read_trace(path, task).episode_id == "ep_0042"
    assert read_trace(path, task, episode_id="ep_given").episode_id == "ep_given"


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("{not json}", "không phải JSON"),
        ("[1, 2]", "đối tượng JSON"),
        ('{"t": "soon"}', "phải là số"),
    ],
)
def test_a_trace_that_cannot_be_read_raises(
    tmp_path: Path, task: TaskDefinition, text: str, fragment: str
) -> None:
    path = tmp_path / "ep.jsonl"
    path.write_text(text, encoding="utf-8")

    # Nothing was measured, so this must not come back as an episode that
    # simply has no signals - that would score as a run with no faults.
    with pytest.raises(TraceError, match=fragment):
        read_trace(path, task)


def test_a_missing_file_raises(tmp_path: Path, task: TaskDefinition) -> None:
    with pytest.raises(TraceError, match="không đọc được"):
        read_trace(tmp_path / "absent.jsonl", task)


def test_rows_already_in_memory_read_the_same_way(make_rows: MakeRows) -> None:
    table = read_signals(make_rows(steps=3))

    assert table.num_rows == 3
    assert table["t"].to_pylist() == [0.0, 0.1, 0.2]
