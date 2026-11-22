"""The report record of one scored case."""

from __future__ import annotations

from typing import Literal

from flywheel.eval.agentqa.casebench.answers import Kind, Strict
from pydantic import Field

Verdict = Literal["reached", "missed", "clean", "wrong_rank1", "wrong_top3"]


class PointResult(Strict):
    id: str
    kind: Kind
    must: bool
    verdict: Verdict
    reason: str = ""
    rank: int | None = Field(default=None, description="Final rank of the right diagnosis.")


class KindCount(Strict):
    reached: int
    total: int


class Counts(Strict):
    a1_reached: int
    a1_total: int
    a1_must_reached: int
    a1_must_total: int
    a1_by_kind: dict[str, KindCount]
    a2_rank1: int
    a2_top3: int
    a2_total: int
    a3_wrong_rank1: int
    a3_wrong_top3: int
    a4_reached: int
    a4_total: int
    a5_reached: int
    a5_total: int


class Delta(Strict):
    """D1: the agent run against the code-floor run of the same pack."""

    floor_run_id: str
    added_right: list[str]
    added_wrong: list[str]
    rank_improved: list[str]
    rank_worsened: list[str]


class CaseReport(Strict):
    case_id: str
    set: str
    answer_sha256: str
    run_id: str
    agent_hash: str
    status: str
    pack_id: str
    points: list[PointResult]
    counts: Counts
    d1: Delta | None = None

    def summary(self) -> str:
        c = self.counts
        line = (f"{self.case_id} [{self.set}] A1 {c.a1_reached}/{c.a1_total} "
                f"(must {c.a1_must_reached}/{c.a1_must_total}) "
                f"A2 rank1 {c.a2_rank1} top3 {c.a2_top3} of {c.a2_total} "
                f"A3 rank1 {c.a3_wrong_rank1} top3 {c.a3_wrong_top3} "
                f"A4 {c.a4_reached}/{c.a4_total} A5 {c.a5_reached}/{c.a5_total}")
        if self.d1 is not None:
            d = self.d1
            line += (f" D1 +right {len(d.added_right)} +wrong {len(d.added_wrong)} "
                     f"up {len(d.rank_improved)} down {len(d.rank_worsened)}")
        return line
