"""What the code checks catch, and what Agent QA/QC adds on top (DA-31 AC 3).

Design 27/10/2026 section 9.2 keeps the two apart so that the agent is not given
credit for what code already found. Per defect kind:

    by code      caught by the code layer
    agent adds   caught by the agent and not by code
    together     caught by either

and, for the agent alone, how good its reports are:

- **Ranking.** Within each report, every pair of a true finding and a false one
  (natural findings left out, as in `score`): right when the true one has the
  better rank (smaller number).
- **Explanation and suggestion.** The engineer's `AgentReview` (fw review): agree
  means the insight and the suggestion stood, override means they did not. The
  contract holds one decision per finding, so the two are judged together; a
  finding nobody reviewed is counted as unreviewed, never as right.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from flywheel.contracts.agentqa import AgentReview
from flywheel.eval.agentqa.bench.detections import Detection
from flywheel.eval.agentqa.bench.score import GroupScore, Rate, kind_of
from flywheel.eval.agentqa.bench.session import GroupResult

UNREVIEWED = "unreviewed"


@dataclass(frozen=True)
class KindSplit:
    kind: str
    code: str
    injected: int
    by_code: int
    agent_adds: int
    agent_alone: int

    @property
    def together(self) -> int:
        return self.by_code + self.agent_adds


@dataclass(frozen=True)
class FindingJudgement:
    """One agent finding, its label against the key and the engineer's decision."""

    dataset_id: str
    report_id: str
    finding_id: str
    rank: int
    target: str
    code: str
    label: str  # "hit", "false", "natural" on the copy with defects; "clean" on the clean one
    review: str  # "agree", "override" or "unreviewed"
    reason: str = ""


@dataclass(frozen=True)
class AgentQuality:
    ranking: Rate
    reviews: Mapping[str, Mapping[str, int]]  # label -> decision -> count
    findings: tuple[FindingJudgement, ...]


def split_by_layer(score: GroupScore) -> tuple[KindSplit, ...]:
    code, agent = score.layers["code"].caught, score.layers["agent"].caught
    rows = []
    for kind, defect_code in score.kinds:
        mine = [i for i, d in enumerate(score.defects) if kind_of(d) == kind]
        rows.append(
            KindSplit(
                kind=kind,
                code=defect_code,
                injected=len(mine),
                by_code=sum(1 for i in mine if i in code),
                agent_adds=sum(1 for i in mine if i in agent and i not in code),
                agent_alone=sum(1 for i in mine if i in agent),
            )
        )
    return tuple(rows)


def agent_quality(
    group: GroupResult, score: GroupScore, reviews: Sequence[AgentReview]
) -> AgentQuality:
    decisions = {
        (review.report_id, d.finding_id): (d.decision, d.reason)
        for review in reviews
        for d in review.decisions
    }
    judged: list[FindingJudgement] = []
    for verdict in score.layers["agent"].verdicts:
        judged.append(_judgement(group.injected.dataset_id, verdict.detection, verdict.label,
                                 decisions))
    for detection in group.clean.runs["agent"].detections:
        judged.append(_judgement(group.clean.dataset_id, detection, "clean", decisions))
    tally: dict[str, Counter[str]] = {}
    for item in judged:
        tally.setdefault(item.label, Counter())[item.review] += 1
    return AgentQuality(
        ranking=_ranking(j for j in judged if j.dataset_id == group.injected.dataset_id),
        reviews={label: dict(counts) for label, counts in sorted(tally.items())},
        findings=tuple(judged),
    )


def _judgement(
    dataset_id: str,
    detection: Detection,
    label: str,
    decisions: Mapping[tuple[str, str], tuple[str, str]],
) -> FindingJudgement:
    report_id, finding_id = detection.report_id or "", detection.finding_id or ""
    review, reason = decisions.get((report_id, finding_id), (UNREVIEWED, ""))
    return FindingJudgement(
        dataset_id=dataset_id,
        report_id=report_id,
        finding_id=finding_id,
        rank=detection.rank or 0,
        target=detection.target,
        code=detection.code,
        label=label,
        review=review,
        reason=reason,
    )


def _ranking(judged: Iterable[FindingJudgement]) -> Rate:
    by_report: dict[str, list[FindingJudgement]] = {}
    for item in judged:
        by_report.setdefault(item.report_id, []).append(item)
    right = total = 0
    for items in by_report.values():
        hits = [i.rank for i in items if i.label == "hit"]
        false = [i.rank for i in items if i.label == "false"]
        for h in hits:
            for f in false:
                total += 1
                right += h < f
    return Rate(right, total)
