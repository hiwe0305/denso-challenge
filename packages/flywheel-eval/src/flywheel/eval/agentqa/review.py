"""The engineer's answer to an AgentReport, as an `AgentReview` (DA-20 AC 5, issue #34).

`fw agentqa review` writes one review per report: `agree` or `override` with a
reason for each finding. A review names every finding of its report exactly once;
a review of a finding the report does not have is refused, so DA-31 never scores
an explanation against the wrong finding.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from flywheel.contracts.agentqa import AgentReport, AgentReview, FindingDecision


class ReviewError(ValueError):
    """A review that does not answer its report."""


def make_review(
    report: AgentReport,
    reviewer: str,
    decisions: Mapping[str, tuple[str, str]],
    *,
    now: datetime | None = None,
) -> AgentReview:
    """`decisions` maps finding_id -> (decision, reason); every finding needs one."""
    ids = [f.finding_id for f in report.findings]
    unknown = sorted(set(decisions) - set(ids))
    if unknown:
        raise ReviewError(f"report {report.report_id} has no finding {unknown}")
    missing = [i for i in ids if i not in decisions]
    if missing:
        raise ReviewError(f"no decision for {missing}")
    return AgentReview(
        report_id=report.report_id,
        reviewer=reviewer,
        decided_at=now or datetime.now(timezone.utc),
        decisions=[
            FindingDecision(finding_id=i, decision=decisions[i][0], reason=decisions[i][1])  # type: ignore[arg-type]
            for i in ids
        ],
    )


def write_review(review: AgentReview, out: Path) -> Path:
    """Write `<report_id>.review.json` under `out`; an existing review is never replaced."""
    path = out / f"{review.report_id}.review.json"
    if path.exists():
        raise ReviewError(f"{path} exists: a review is append-only, write a new report")
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
