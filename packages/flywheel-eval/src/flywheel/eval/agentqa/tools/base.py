"""What every tool returns, and the inputs the eval tools share (DA-43 task 2.1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from flywheel.contracts.entities import Condition, Score
from flywheel.contracts.trace import TraceStep
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.facts import FactBook, FactValue

Row = Mapping[str, FactValue]


@dataclass(frozen=True)
class StoreRead:
    """What a store-reading tool read: the table, the rows that parsed, a hash over them.

    `sha256` is over the canonical JSON of the rows read, projected on the fields the tool
    uses (ids and timestamps are noise to it) and sorted, so it does not move with the order
    of files; `unreadable` counts the rows that did not parse and are not in the hash.
    """

    table: str
    rows: int
    sha256: str
    unreadable: int = 0


def store_read(table: str, rows: Iterable[Mapping[str, object]],
               unreadable: int = 0) -> StoreRead:
    lines = sorted(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                   for r in rows)
    return StoreRead(table, len(lines), hashlib.sha256("\n".join(lines).encode()).hexdigest(),
                     unreadable)


@dataclass(frozen=True)
class ToolResult:
    """The facts one tool call added, the table behind them, and what it could not judge.

    `facts` are ids in the book the call wrote to; `rows` is the table a figure or an
    HTML page shows (its numbers are the facts' values, never new ones); `not_judged`
    holds the reasons a part was left out, each of which is also a fact.
    """

    tool: str
    facts: tuple[str, ...] = ()
    rows: tuple[Row, ...] = ()
    not_judged: tuple[str, ...] = ()
    store_reads: tuple[StoreRead, ...] = ()  # set only by tools registered `reads_store`

    @property
    def judged(self) -> bool:
        return not self.not_judged


def not_judged(book: FactBook, tool: str, reason: str, source_ref: str,
               part: str = "") -> ToolResult:
    """A result that says, as a fact, why the tool (or `part` of it) judged nothing.

    The fact's name is `<tool>[_<part>]_not_judged` and a name fixes its value within a
    round: `reason` must depend only on the tool and on `part`, never on the parameters of
    the call. Put whatever varies (a run, a job, a pair and its levels) into `part`.
    """
    name = f"{tool}_{part}_not_judged" if part else f"{tool}_not_judged"
    return ToolResult(tool, (book.add(name, reason, source_ref),), (), (reason,))


def merge(tool: str, results: Sequence[ToolResult]) -> ToolResult:
    """One result of several parts of the same tool, in order."""
    return ToolResult(
        tool,
        tuple(f for r in results for f in r.facts),
        tuple(row for r in results for row in r.rows),
        tuple(reason for r in results for reason in r.not_judged),
        tuple(read for r in results for read in r.store_reads),
    )


def condition_of(score: Score) -> str:
    """The condition a rollout ran: `episode_id` after its run prefix.

    `export_scores` writes `<run>/l<level>-s<seed>`; two runs pair on the part after
    the run. Until the outcome contract carries the condition (design 7.2, K1), this
    is the convention every eval tool uses.
    """
    return score.episode_id.split("/", 1)[-1]


@dataclass(frozen=True)
class RunScores:
    """The scored rollouts of one run (one checkpoint on one eval set)."""

    run: str
    ref: str  # the file the scores came from, as recorded in facts
    scores: tuple[Score, ...]
    key: Callable[[Score], str] = field(default=condition_of)

    def levels(self) -> list[int]:
        return sorted({s.level for s in self.scores if s.level is not None})


@dataclass(frozen=True)
class RunTrace:
    """The control cycles of the rollouts of one run, from one `trace` entry of the pack."""

    run: str
    ref: str
    steps: tuple[TraceStep, ...]


@dataclass(frozen=True)
class JobMetrics:
    """The training log of one job (`TrainingMetric.job_id`), in file order."""

    job: str
    ref: str
    rows: tuple[TrainingMetric, ...]


@dataclass(frozen=True)
class EntryView:
    """What the pack declares about an accepted entry: its file, kind and subject."""

    ref: str
    kind: str
    subject: Mapping[str, str]


@dataclass(frozen=True)
class ConditionSet:
    """The `Condition` records of one `conditions` entry and the role the pack declares."""

    ref: str
    role: str  # subject.role: "train" or "eval"; "" when the pack does not say
    conditions: tuple[Condition, ...]
