"""The record one scoring run leaves behind (DA-36 AC 1, 5).

The record is `Score` of `flywheel.contracts.entities` (03 section 4.3), the
artifact `decide` of the Vòng lane and the Agent QA/QC of the egocentric lane
read. Until S1-10 (#36) merged it was a lane-local `ScoreRecord` with the same
fields; task 7 replaced it with the contract model and deleted the copy, so no
field name and no stored line changed shape. `Score` is content-addressed: its
`id` is `sc_<hash>` of everything else in the record, `trace_sha256` and
`scorer_version` included, so a re-score of the same trace under the same
scorer and config gets the same id and a changed one does not.

Since #101 (issue #59) the record carries the typed reason of every unknown
step in `unknown_reason` and the time each step was entered and left in
`step_enter_s` and `step_exit_s`, the fields DA-36 had kept out of the record
until the contract held them. Adding them changed the record's shape, so the
scorer version went from 0.1.0 to 0.2.0 (task 8.4); records already in the
store keep their version and are not rewritten.

`meta` holds what this run measured and the next reader would otherwise have to
re-derive: the signals the trace was missing or had only as nulls, and where
the balance condition broke. The PO review of 3/11/2026 asks
for whatever has to survive to be named as a typed field in #62 instead. The
per-group tracking error and the p99 latencies that 03 section 4.3 also lists
are measured by the system check of DA-13, not here, and are left out rather
than filled with zeros.

The store is append-only. Scoring the same episode again appends a second
record; `scorer_version` and `config_sha256` are what tell them apart, so a
re-score never silently replaces a number somebody has already reported
(03 section 4.4 rule 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flywheel.contracts.entities import Score
from flywheel.eval.scorer.score import EpisodeScore

STORE_RECORDS = Path("scorer") / "score.jsonl"


def build_record(score: EpisodeScore, level: int | None = None) -> Score:
    """The record of one scoring run.

    `level` is the condition level of the episode (Level 1 or Level 2 of the
    demo). The scorer does not know it from a trace, so the caller passes it
    and it stays unset otherwise rather than defaulting to a level.
    """
    return Score(
        episode_id=score.episode_id,
        scorer_version=score.scorer_version,
        success=score.success,
        step_status=[step.status for step in score.steps],
        unknown_reason=[step.reason for step in score.steps],
        step_enter_s=_listed(score.step_enter_s),
        step_exit_s=_listed(score.step_exit_s),
        first_failed_step=score.failure.first_failed_step,
        failure_kind=score.failure.failure_kind,
        failure_class=score.failure.failure_class,
        level=level,
        balance_violated=score.balance.violated,
        task_id=score.task_id,
        config_sha256=score.config_sha256,
        trace_sha256=score.trace_sha256,
        meta=_meta(score),
    )


def write_record(record: Score, store_path: Path) -> Path:
    """Append the record to the store and return the file it went into."""
    path = store_path / STORE_RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return path


def _listed(values: tuple[float | None, ...] | None) -> list[float | None] | None:
    return None if values is None else list(values)


def _meta(score: EpisodeScore) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "step_names": [step.name for step in score.steps],
        "missing_signals": list(score.missing_signals),
    }
    if score.null_signals:
        meta["null_signals"] = list(score.null_signals)
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
