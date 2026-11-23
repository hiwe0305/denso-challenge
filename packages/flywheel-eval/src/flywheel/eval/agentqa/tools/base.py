"""What every tool returns, and the inputs the eval tools share (DA-43 task 2.1)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from flywheel.contracts.entities import Condition, Score
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.contracts.trace import TraceStep
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.facts import FactBook, FactValue

Row = Mapping[str, FactValue]


@dataclass(frozen=True)
class StoreRows:
    """The rows of a store snapshot entry of the pack, and the rows it could not parse."""

    ref: str
    rows: tuple[Any, ...]
    unreadable: int = 0


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
class RunOutcomes:
    """The K1 outcomes of one run (`RolloutOutcome`, one per rollout), from one pack entry.

    They pair with the run's scores by `episode_id`; small (one line per rollout), so held.
    """

    run: str
    ref: str  # the `outcomes` entry they came from, as recorded in facts
    outcomes: tuple[RolloutOutcome, ...]

    def by_episode(self) -> dict[str, RolloutOutcome]:
        return {o.episode_id: o for o in self.outcomes}


@dataclass(frozen=True)
class TraceFile:
    """One `trace` entry of the pack: its ref, the sha256 the pack records, its cycles.

    The cycles are either `held` or read by `load` each time they are asked for (step B2:
    a real trace is too large to keep, so a tool reads one file at a time).
    """

    ref: str
    sha256: str
    held: tuple[TraceStep, ...] = ()
    load: Callable[[], Iterable[TraceStep]] | None = field(default=None, compare=False)

    def read(self) -> list[TraceStep]:
        """The cycles of the file, in file order; nothing keeps them but the caller."""
        return list(self.held if self.load is None else self.load())

    @property
    def steps(self) -> tuple[TraceStep, ...]:
        return tuple(self.read())


@dataclass(frozen=True)
class RunTrace:
    """The trace files of one run, in pack order (real data: one file per rollout)."""

    run: str
    files: tuple[TraceFile, ...]


@dataclass(frozen=True)
class JobMetrics:
    """The training log of one job (`TrainingMetric.job_id`), in file order.

    The rows are either `held` or read by `load` each time they are asked for (a real log
    is 60k rows): a tool iterates `iter_rows` and keeps only what it reduces them to.
    """

    job: str
    ref: str
    held: tuple[TrainingMetric, ...] = ()
    load: Callable[[], Iterable[TrainingMetric]] | None = field(default=None, compare=False)

    def iter_rows(self) -> Iterator[TrainingMetric]:
        return iter(self.held if self.load is None else self.load())

    @property
    def rows(self) -> tuple[TrainingMetric, ...]:
        return tuple(self.iter_rows())


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
    run: str = ""  # subject.run: the run of the pack the entry belongs to; "" when not declared
