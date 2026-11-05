from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from flywheel.contracts.segments import SEGMENT_SCHEMA, Segment, read_segments, write_segments
from pydantic import ValidationError


def test_parquet_round_trip_and_empty_bundle(tmp_path: Path) -> None:
    path = tmp_path / "segments.parquet"
    segments = [
        Segment(t_start=0, t_end=1.5, step_id="grasp", description="Pick up", label_source="human")
    ]
    write_segments(path, segments)
    assert pq.read_table(path).schema.equals(SEGMENT_SCHEMA)
    assert read_segments(path) == segments
    write_segments(path, [])
    assert read_segments(path) == []
    assert pq.read_table(path).schema.equals(SEGMENT_SCHEMA)


def test_reject_invalid_interval_and_schema(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Segment(t_start=1, t_end=1, step_id="x", description="x", label_source="rule")
    path = tmp_path / "segments.parquet"
    pq.write_table(pa.table({"t_start": [0.0]}), path)
    with pytest.raises(ValueError, match="schema"):
        read_segments(path)


def test_reject_invalid_parquet_values(tmp_path: Path) -> None:
    path = tmp_path / "segments.parquet"
    row = {
        "t_start": 0.0,
        "t_end": 1.0,
        "step_id": "x",
        "description": "x",
        "label_source": "unknown",
    }
    pq.write_table(pa.Table.from_pylist([row], schema=SEGMENT_SCHEMA), path)
    with pytest.raises(ValidationError):
        read_segments(path)
