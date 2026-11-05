"""DA-31 AC 3: what code catches, what the agent adds, and how good the agent's reports are."""

from __future__ import annotations

from datetime import timezone

from conftest import CLEAN, INJECTED, T0
from flywheel.contracts.agentqa import AgentReview, FindingDecision
from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.eval.agentqa.bench.detections import Detection, LayerRun
from flywheel.eval.agentqa.bench.layers import agent_quality, split_by_layer
from flywheel.eval.agentqa.bench.score import score_group
from flywheel.eval.agentqa.bench.session import CopyResult, GroupResult

UNITS = tuple(f"e{i}" for i in range(6))
DEFECTS = [
    Defect(target_ref="e1", code="D3", parameters={"kind": "joint_jump"}),
    Defect(target_ref="e2", code="D3", parameters={"kind": "joint_jump"}),
    Defect(target_ref="e3", code="D7", parameters={"kind": "action_sign_flip"}),
]


def _agent(report_id: str, finding: str, target: str, code: str, rank: int) -> Detection:
    return Detection(target, code, report_id=report_id, finding_id=finding, rank=rank)


def _group() -> GroupResult:
    def run(layer: str, dataset_id: str, detections: list[Detection]) -> LayerRun:
        return LayerRun(layer=layer, dataset_id=dataset_id, units=UNITS,  # type: ignore[arg-type]
                        detections=tuple(detections), reported_at=T0)

    injected_agent = [
        _agent("r1", "f1", "e4", "D3", 1),  # false, ranked first
        _agent("r1", "f2", "e3", "D7", 2),  # hit, only the agent sees the sign flip
        _agent("r1", "f3", "e1", "D3", 3),  # hit, code saw it too
        _agent("r1", "f4", "e5", "D6", 4),  # natural: on the clean copy as well
    ]
    injected = CopyResult(
        "data", INJECTED, T0,
        {"code": run("code", INJECTED, [Detection("e1", "D3"), Detection("e2", "D3")]),
         "agent": run("agent", INJECTED, injected_agent)},
        DefectManifest(dataset_id=INJECTED, seed=1, defects=DEFECTS),
    )
    clean = CopyResult(
        "data", CLEAN, T0,
        {"code": run("code", CLEAN, []),
         "agent": run("agent", CLEAN, [_agent("r2", "g1", "e5", "D6", 1)])},
        DefectManifest(dataset_id=CLEAN, seed=1, defects=[]),
    )
    return GroupResult("data", injected, clean)


def test_the_agent_gets_credit_only_for_what_code_missed() -> None:
    rows = {r.kind: r for r in split_by_layer(score_group(_group()))}
    jump, flip = rows["joint_jump"], rows["action_sign_flip"]
    assert (jump.injected, jump.by_code, jump.agent_adds, jump.agent_alone, jump.together) == (
        2, 2, 0, 1, 2)
    assert (flip.injected, flip.by_code, flip.agent_adds, flip.agent_alone, flip.together) == (
        1, 0, 1, 1, 1)


def test_ranking_counts_true_over_false_pairs_within_a_report() -> None:
    group = _group()
    quality = agent_quality(group, score_group(group), [])
    # f2 and f3 are true, f1 is false and ranked above both: 0 of 2 pairs right
    assert (quality.ranking.hit, quality.ranking.total) == (0, 2)


def test_reviews_judge_explanation_and_suggestion_and_unreviewed_is_not_right() -> None:
    group = _group()
    review = AgentReview(
        report_id="r1",
        reviewer="hieu",
        decided_at=T0.astimezone(timezone.utc),
        decisions=[
            FindingDecision(finding_id="f1", decision="override", reason="e4 is in range"),
            FindingDecision(finding_id="f2", decision="agree"),
        ],
    )
    quality = agent_quality(group, score_group(group), [review])
    assert quality.reviews == {
        "clean": {"unreviewed": 1},
        "false": {"override": 1},
        "hit": {"agree": 1, "unreviewed": 1},
        "natural": {"unreviewed": 1},
    }
    f1 = next(f for f in quality.findings if f.finding_id == "f1")
    assert (f1.label, f1.review, f1.reason) == ("false", "override", "e4 is in range")
