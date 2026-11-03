"""Read a recorded trace and a task definition for the scorer (DA-36 AC 1, 5).

Reading is kept away from judging on purpose. This module turns bytes on disk
into a signal table and says what the table is missing; it never decides
whether a step passed. The scoring modules take the table and never touch a
file. That split is what makes AC 5 testable: the judging half has no clock, no
file system and no simulator in it, so the same table always scores the same.

A trace here is the per-step task signals of one episode - object pose, hand
contact, body height and tilt (03 section 4.2, row V7) - one flat JSON object
per line. It is not the `TraceStep` log of the system check (DA-13), which
records joint commands and timestamps for a different question.

A signal the task asked for and the file does not have is not an error. It is
the reason a step comes back "unknown", and it has to survive the read in a
form the scorer can quote back, which is what `Trace.missing_signals` carries.
A file that cannot be parsed at all is different: nothing was measured, so it
raises rather than scoring as an episode with no signals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
from flywheel.contracts import TaskDefinition


class TraceError(ValueError):
    """A trace file the scorer must not score."""


@dataclass(frozen=True)
class Trace:
    """One episode's signals, plus what the task asked for and did not get."""

    episode_id: str
    signals: pa.Table
    missing_signals: tuple[str, ...]

    @property
    def num_steps(self) -> int:
        return int(self.signals.num_rows)


def read_trace(path: Path, task: TaskDefinition, episode_id: str | None = None) -> Trace:
    """Read a JSONL trace and check it against `task.required_signals()`.

    `episode_id` overrides the id in the file; a file that names no episode and
    is given no id falls back to the file stem, because a `Score` without an
    episode cannot be joined to anything later.
    """
    rows = _read_rows(path)
    columns = _columns(rows, path)
    required = tuple(signal.name for signal in task.required_signals())
    missing = tuple(name for name in required if name not in columns)
    return Trace(
        episode_id=episode_id or _episode_id(rows) or path.stem,
        signals=pa.table(columns) if columns else pa.table({}),
        missing_signals=missing,
    )


def read_signals(rows: list[dict[str, Any]]) -> pa.Table:
    """Build the signal table from rows already in memory, for tests and callers
    that hold a synthetic trace rather than a file (AC 6)."""
    return pa.table(_columns(rows, Path("<memory>")))


def _read_rows(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise TraceError(f"`{path}` không đọc được: {error}") from error
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise TraceError(f"`{path}` dòng {number} không phải JSON: {error}") from error
        if not isinstance(row, dict):
            raise TraceError(f"`{path}` dòng {number} phải là một đối tượng JSON")
        rows.append(row)
    return rows


def _columns(rows: list[dict[str, Any]], path: Path) -> dict[str, list[Any]]:
    # A signal present on some steps and absent on others is padded with null
    # rather than carried forward: a held value would be a measurement nobody
    # took, and the scorer reads a null as a gap.
    names = [
        name for name in dict.fromkeys(key for row in rows for key in row) if name != "episode_id"
    ]
    columns: dict[str, list[Any]] = {}
    for name in names:
        values = [_number(row.get(name), name, path) for row in rows]
        columns[name] = values
    return columns


def _number(value: Any, name: str, path: Path) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    raise TraceError(f"`{path}`: tín hiệu `{name}` phải là số hoặc null, gặp {value!r}")


def _episode_id(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        value = row.get("episode_id")
        if isinstance(value, str) and value:
            return value
    return None
