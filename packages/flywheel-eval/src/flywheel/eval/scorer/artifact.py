"""The record one scoring run leaves behind (DA-36 AC 1, 5).

`Score` of 03 section 4.3 is what `decide` of the Vòng lane and the Agent QA/QC
of the egocentric lane read. It lives in S1-10 (#36), which has not merged, and
`ScoreRecord` below is that model field for field - `episode_id`,
`scorer_version`, `success`, `step_status`, `first_failed_step`,
`failure_kind`, `failure_class`, `level`, `balance_violated` - so that the
switch is an import change and the deletion of one class, with no field name
and no stored file changing shape. It is written here rather than added to
`flywheel.contracts` because `Score` arrives there with the whole entity layer
of #36 behind it, and a second copy of that layer would be a merge conflict
rather than a dependency. The PR records this as an R6 note for the PO.

Two fields of 03 section 4.3 are not in either model: the time each step was
entered and left. Nothing in `StageEvaluation` carries them, and a field
invented in lane code is a field no other lane can read, so they go in the
Contract change issue for Long together with a typed reason for an unknown
step (AC 1).

`meta` holds what this run measured and the next reader would otherwise have to
re-derive: the signals the trace was missing, the reason behind every unknown
step, and where the balance condition broke. The per-group tracking error and
the p99 latencies that 03 section 4.3 also lists are measured by the system
check of DA-13, not here, and are left out rather than filled with zeros.

The store is append-only. Scoring the same episode again appends a second
record; `scorer_version` and `config_sha256` are what tell them apart, so a
re-score never silently replaces a number somebody has already reported
(03 section 4.4 rule 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from flywheel.eval.scorer.score import EpisodeScore
from pydantic import BaseModel, ConfigDict, Field

STORE_RECORDS = Path("scorer") / "score.jsonl"

FailureClassName = Literal["approach", "grasp", "carry", "place", "balance"]


class ScoreRecord(BaseModel):
    """One episode as scored, in the field layout of `Score` (03 section 4.3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    scorer_version: str
    success: bool | None = None
    step_status: list[str] = Field(default_factory=list)
    first_failed_step: int | None = None
    failure_kind: str | None = None
    failure_class: FailureClassName | None = None
    level: int | None = None
    balance_violated: bool = False
    # Not in `Score`: the scorer's own provenance and measurements. `task_id`
    # and `config_sha256` are what make a record reproducible, and the artifact
    # is useless without them.
    task_id: str
    config_sha256: str
    meta: dict[str, Any] = Field(default_factory=dict)


def build_record(score: EpisodeScore, level: int | None = None) -> ScoreRecord:
    """The record of one scoring run.

    `level` is the condition level of the episode (Level 1 or Level 2 of the
    demo). The scorer does not know it from a trace, so the caller passes it
    and it stays unset otherwise rather than defaulting to a level.
    """
    return ScoreRecord(
        episode_id=score.episode_id,
        scorer_version=score.scorer_version,
        success=score.success,
        step_status=[step.status.value for step in score.steps],
        first_failed_step=score.failure.first_failed_step,
        failure_kind=score.failure.failure_kind,
        failure_class=score.failure.failure_class,
        level=level,
        balance_violated=score.balance.violated,
        task_id=score.task_id,
        config_sha256=score.config_sha256,
        meta=_meta(score),
    )


def write_record(record: ScoreRecord, store_path: Path) -> Path:
    """Append the record to the store and return the file it went into."""
    path = store_path / STORE_RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return path


def _meta(score: EpisodeScore) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "step_names": [step.name for step in score.steps],
        "missing_signals": list(score.missing_signals),
    }
    unknown = {step.name: step.reason for step in score.unknown_steps if step.reason}
    if unknown:
        meta["unknown_steps"] = unknown
    if score.failure.reason is not None:
        meta["no_kind_reason"] = score.failure.reason
    if score.balance.unknown_reason is not None:
        meta["balance_unknown"] = score.balance.unknown_reason
    if score.balance.violated:
        meta["balance"] = {
            "row": score.balance.row,
            "signal": score.balance.signal,
            "value": score.balance.value,
            "limit": score.balance.limit,
        }
    return meta
