"""Shared representation of the segments.parquet episode bundle member."""

from pathlib import Path
from typing import Literal

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.artifacts import Artifact
from pydantic import Field, model_validator


class Segment(Artifact):
    """A task segment; timestamps are seconds relative to the episode start."""

    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    step_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    label_source: Literal["rule", "human", "model"]

    @model_validator(mode="after")
    def validate_interval(self) -> "Segment":
        if self.t_end <= self.t_start:
            raise ValueError("t_end must be later than t_start")
        return self


SEGMENT_SCHEMA = pa.schema(
    [
        pa.field("t_start", pa.float64(), nullable=False),
        pa.field("t_end", pa.float64(), nullable=False),
        pa.field("step_id", pa.string(), nullable=False),
        pa.field("description", pa.string(), nullable=False),
        pa.field("label_source", pa.string(), nullable=False),
    ]
)


def write_segments(path: Path, segments: list[Segment]) -> None:
    """Write even an empty list with the same explicit parquet schema."""
    table = pa.Table.from_pylist([s.model_dump() for s in segments], schema=SEGMENT_SCHEMA)
    pq.write_table(table, path)


def read_segments(path: Path) -> list[Segment]:
    """Reject a different schema or invalid values rather than silently coercing them."""
    table = pq.read_table(path)
    if not table.schema.equals(SEGMENT_SCHEMA, check_metadata=False):
        raise ValueError("invalid segments parquet schema")
    return [Segment.model_validate(row) for row in table.to_pylist()]
