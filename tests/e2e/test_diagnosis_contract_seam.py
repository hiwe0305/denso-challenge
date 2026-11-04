"""DA-13's lane records can cross into the shared contracts without data loss."""

from flywheel.contracts.diagnosis import StageAttribution, SystemDiagnosis
from flywheel.eval.diagnosis.stage.artifact import (
    EvidenceRecord,
    StageAttributionRecord,
    StageHypothesisRecord,
)
from flywheel.eval.diagnosis.system.artifact import (
    SystemDiagnosisRecord,
    SystemFindingRecord,
    SystemSkipRecord,
)


def test_system_record_matches_shared_contract() -> None:
    lane = SystemDiagnosisRecord(
        episode_id="ep_1",
        diagnosis="controller",
        config_sha256="a" * 64,
        trace_sha256="b" * 64,
        rtc_sha256="c" * 64,
        camera_sha256="d" * 64,
        infra_sha256="e" * 64,
        infra_status="ok",
        findings=[SystemFindingRecord(code="R3", value=0.2, threshold=0.1, part="upper")],
        skipped=[SystemSkipRecord(code="R5", reason="missing reference")],
    )
    shared = SystemDiagnosis.model_validate_json(lane.model_dump_json())
    assert shared.model_dump(mode="json") == lane.model_dump(mode="json")


def test_stage_record_matches_shared_contract() -> None:
    lane = StageAttributionRecord(
        episode_id="ep_1",
        table_sha256="a" * 64,
        failed_step=2,
        hypotheses=[
            StageHypothesisRecord(
                row_id="stage3_action_group",
                attribute_to="stage3",
                intervention="collect",
                consumes_budget=True,
                evidence=[EvidenceRecord(probe="P3", where="arm", value=0.9, threshold=0.5)],
            )
        ],
        unavailable=[SystemSkipRecord(code="stage1_perception", reason="P1 missing")],
    )
    shared = StageAttribution.model_validate_json(lane.model_dump_json())
    assert shared.model_dump(mode="json") == lane.model_dump(mode="json")
