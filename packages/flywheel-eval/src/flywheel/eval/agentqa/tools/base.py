"""What every tool returns, and the inputs the eval tools share (DA-43 task 2.1)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from flywheel.contracts.entities import Score
from flywheel.eval.agentqa.facts import FactBook, FactValue

Row = Mapping[str, FactValue]


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
    """A result that says, as a fact, why the tool (or `part` of it) judged nothing."""
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
