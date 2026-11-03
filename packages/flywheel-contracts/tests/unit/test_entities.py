"""Unit tests for the 12 L0-lite catalog entities (AC 1, AC 3, AC 4)."""

import json
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import EpisodeMetadata
from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Condition,
    Decision,
    Episode,
    FixRateEvent,
    LedgerEntry,
    QACheck,
    QAReport,
    Release,
    RunPlan,
    Score,
    Source,
)
from pydantic import ValidationError


def test_all_12_entities_can_be_instantiated_with_defaults() -> None:
    """Verify all 12 entities instantiate and have correct default columns and ID formats."""
    # 1. Source (content)
    src = Source(
        uri="https://huggingface.co/datasets/unitree/psi-data",
        sha256="a" * 64,
        downloaded_at="2026-11-02T12:00:00Z",
        provenance={"clean_for_main_task": "true"},
    )
    assert src.id.startswith("src_")
    assert src.site_id == "local"
    assert src.task_id == "default"
    assert src.embodiment_id == "default"
    assert src.schema_version == "1.0.0"
    assert src.provenance == {"clean_for_main_task": "true"}

    # 2. Condition (content)
    cond = Condition(
        condition_seed=42,
        layout_hash="b" * 64,
        values={"box_x": 0.5},
    )
    assert cond.id.startswith("cond_")
    assert cond.split == "train"

    # 3. Episode (event, reused from artifacts.py)
    ep = Episode(
        kind="teleop_demo",
        operator_kind="human",
        is_root=True,
        condition_id="cond_1",
        run_plan_id="rp_1",
        bundle_uri="sites/local/episodes/ep_01H...",
        license="MIT",
        data_class="public",
        split="train",
        source_kind="teleop",
        action_quality="measured",
        embodiment_id="g1",
        meta=EpisodeMetadata(),
    )
    assert ep.id.startswith("ep_")
    assert ep.deid_status == "raw"
    assert len(ep.id) == 3 + 26  # ep_ + 26-char ULID

    # 4. QAReport (event, reused from artifacts.py)
    qa = QAReport(
        report_id="",
        episode_id=ep.id,
        threshold_version="v1",
        decision="pass",
        reasons=[],
        checks=[QACheck(name="sync", value=0.01, threshold=0.1, passed=True)],
    )
    assert qa.id.startswith("qa_")

    # 5. Release (content)
    rel = Release(name="release-v1")
    assert rel.id.startswith("rel_")

    # 6. Checkpoint (content)
    ckpt = Checkpoint(
        weights_sha256="c" * 64,
        uri="sites/local/checkpoints/ckpt_1",
    )
    assert ckpt.id.startswith("ckpt_")

    # 7. RunPlan (content)
    rp = RunPlan(name="round-1-runplan")
    assert rp.id.startswith("rp_")

    # 8. Score (content)
    sc = Score(
        episode_id=ep.id,
        task_id="two-table",
        config_sha256="d" * 64,
        trace_sha256="e" * 64,
        first_failed_step=2,
        failure_kind="L-GRASP",
        failure_class="grasp",
    )
    assert sc.id.startswith("sc_")

    # 9. Cluster (content)
    clu = Cluster(
        first_failed_step=2,
        failure_kind="L-GRASP",
        failure_class="grasp",
    )
    assert clu.id.startswith("clu_")

    # 10. FixRateEvent (event)
    fre = FixRateEvent(
        intervention_id="iv_01H...",
        failure_kind="L-GRASP",
        n_conditions=10,
        p_parent=0.2,
        p_candidate=0.8,
        fixed=6,
    )
    assert fre.id.startswith("fre_")

    # 11. LedgerEntry (event)
    led = LedgerEntry(
        activity="train",
        run_plan_id="rp_1",
        resource_type="gpu_hour_a100",
        quantity=2.5,
        unit="hour",
        usd_amount=7.50,
        measure_kind="estimated",
    )
    assert led.id.startswith("led_")

    # 12. Decision (event)
    dec = Decision(
        kind="dev_gate",
        subject_kind="eval_run",
        subject_id="eval_1",
        verdict="pass",
        signed_by="Hieu",
        reason="Success rate >= 95% on dev set",
    )
    assert dec.id.startswith("dec_")


def test_content_id_hashes_after_filling_defaults() -> None:
    """Feedback item 1: Explicit site_id='local' produces identical ID to omitting it."""
    src_implicit = Source(
        uri="https://example.com/dataset.tar",
        sha256="1" * 64,
        downloaded_at="2026-11-03T00:00:00Z",
    )
    src_explicit = Source(
        uri="https://example.com/dataset.tar",
        sha256="1" * 64,
        downloaded_at="2026-11-03T00:00:00Z",
        site_id="local",
    )
    assert src_implicit.id == src_explicit.id

    # Passing matching explicit id succeeds
    src_with_id = Source(
        id=src_implicit.id,
        uri="https://example.com/dataset.tar",
        sha256="1" * 64,
        downloaded_at="2026-11-03T00:00:00Z",
    )
    assert src_with_id.id == src_implicit.id

    # Passing mismatched explicit id raises ValueError
    with pytest.raises(ValueError, match="Content ID mismatch"):
        Source(
            id="src_0000000000000000",
            uri="https://example.com/dataset.tar",
            sha256="1" * 64,
            downloaded_at="2026-11-03T00:00:00Z",
        )


def test_condition_split_rejects_holdout() -> None:
    """Feedback item 4: Condition.split rejects 'holdout' (03 §4.3)."""
    Condition(condition_seed=1, layout_hash="1" * 64, split="train")
    Condition(condition_seed=2, layout_hash="2" * 64, split="dev")
    with pytest.raises(ValidationError):
        Condition(condition_seed=3, layout_hash="3" * 64, split="holdout")


def test_ledger_entry_measure_kind_and_estimate_id() -> None:
    """Feedback item 5: measure_kind is required; estimated cannot have estimate_entry_id."""
    # 1. Missing measure_kind raises ValidationError
    with pytest.raises(ValidationError):
        LedgerEntry(  # type: ignore[call-arg]
            activity="train",
            run_plan_id="rp_1",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=10.0,
        )

    # 2. Estimated entry with estimate_entry_id is rejected
    with pytest.raises(ValueError, match="estimated entry cannot have an estimate_entry_id"):
        LedgerEntry(
            activity="train",
            run_plan_id="rp_1",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=10.0,
            measure_kind="estimated",
            estimate_entry_id="led_01H...",
        )

    # 3. Two entries for the same job link via estimate_entry_id
    entry_est = LedgerEntry(
        activity="train",
        run_plan_id="rp_1",
        resource_type="gpu_hour_a100",
        quantity=2.0,
        unit="hour",
        usd_amount=6.0,
        measure_kind="estimated",
    )
    entry_meas = LedgerEntry(
        activity="train",
        run_plan_id="rp_1",
        job_id="job_1",
        resource_type="gpu_hour_a100",
        quantity=2.1,
        unit="hour",
        usd_amount=6.3,
        measure_kind="measured",
        estimate_entry_id=entry_est.id,
    )
    assert entry_meas.estimate_entry_id == entry_est.id

    # 4. Measured entry missing estimate_entry_id is rejected
    with pytest.raises(ValueError, match="measured entry must have an estimate_entry_id"):
        LedgerEntry(
            activity="train",
            run_plan_id="rp_1",
            job_id="job_1",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=10.0,
            measure_kind="measured",
        )

    # 5. Measured entry with invalid estimate_entry_id format is rejected
    with pytest.raises(ValueError, match="must be a valid 'led_' event ID"):
        LedgerEntry(
            activity="train",
            run_plan_id="rp_1",
            job_id="job_1",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=10.0,
            measure_kind="measured",
            estimate_entry_id="xyz",
        )

    # 6. Negative amounts rejected without reverses_entry_id
    with pytest.raises(ValueError, match="quantity cannot be negative"):
        LedgerEntry(
            activity="train",
            run_plan_id="rp_1",
            resource_type="gpu",
            quantity=-1.0,
            unit="h",
            usd_amount=10.0,
            measure_kind="estimated",
        )
    with pytest.raises(ValueError, match="usd_amount cannot be negative"):
        LedgerEntry(
            activity="train",
            run_plan_id="rp_1",
            resource_type="gpu",
            quantity=1.0,
            unit="h",
            usd_amount=-5.0,
            measure_kind="estimated",
        )

    # 7. Negative amounts accepted when reverses_entry_id is set
    rev = LedgerEntry(
        activity="train",
        run_plan_id="rp_1",
        resource_type="gpu",
        quantity=-1.0,
        unit="h",
        usd_amount=-5.0,
        measure_kind="estimated",
        reverses_entry_id=entry_est.id,
    )
    assert rev.quantity == -1.0
    assert rev.usd_amount == -5.0


def test_source_sha256_must_be_hex() -> None:
    """Feedback item 6: Source.sha256 requires 64-char lowercase hex."""
    with pytest.raises(ValidationError):
        Source(
            uri="https://example.com/dataset",
            sha256="not-a-valid-hex-sha256",
            downloaded_at="2026-11-03T00:00:00Z",
        )


def test_episode_accepts_custom_episode_id() -> None:
    """Feedback item 1 & PO decision: Catalog accepts any non-empty episode_id."""
    ep = Episode(
        episode_id="ep_1",
        kind="teleop_demo",
        operator_kind="human",
        is_root=True,
        condition_id="cond_1",
        run_plan_id="rp_1",
        bundle_uri="data/ep_1",
        license="MIT",
        data_class="public",
        split="train",
        source_kind="teleop",
        action_quality="measured",
        embodiment_id="g1",
        meta=EpisodeMetadata(),
    )
    assert ep.id == "ep_1"
    assert ep.episode_id == "ep_1"


def test_score_requires_task_id() -> None:
    """PO review 3/11 item 1: a Score without task_id must not fall back to "default"."""
    with pytest.raises(ValidationError, match="task_id"):
        Score(  # type: ignore[call-arg]
            episode_id="ep_1",
            config_sha256="d" * 64,
            trace_sha256="e" * 64,
        )
    with pytest.raises(ValidationError, match="task_id"):
        Score(
            episode_id="ep_1",
            task_id="",
            config_sha256="d" * 64,
            trace_sha256="e" * 64,
        )


def test_score_carries_trace_sha256() -> None:
    """PO review 3/11 item 2: Score keeps the trace hash DA-36's ScoreRecord records."""
    base = {"episode_id": "ep_1", "task_id": "two-table", "config_sha256": "d" * 64}
    with pytest.raises(ValidationError, match="trace_sha256"):
        Score.model_validate(base)
    with pytest.raises(ValidationError, match="trace_sha256"):
        Score.model_validate({**base, "trace_sha256": "nothex"})

    first = Score.model_validate({**base, "trace_sha256": "e" * 64})
    rescored = Score.model_validate({**base, "trace_sha256": "f" * 64})
    assert first.trace_sha256 == "e" * 64
    assert first.id != rescored.id


FIXTURES = (
    Path(__file__).resolve().parents[4]
    / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
)


@pytest.mark.parametrize("model", [Score, Cluster, Decision, LedgerEntry])
def test_shared_entity_example_round_trips(
    model: type[Score | Cluster | Decision | LedgerEntry],
) -> None:
    """PO review 3/11: tests/e2e/test_demo_seams.py reads these four shared examples."""
    example = (FIXTURES / f"{model.__name__}.json").read_text(encoding="utf-8")
    value = model.model_validate_json(example)
    assert model.model_validate_json(value.model_dump_json()) == value
    # The id is in the file, so a reader sees the id the store will hold.
    assert value.id == json.loads(example)["id"]


def test_ledger_entry_requires_run_plan_id_and_a_measured_job_id() -> None:
    """PO decision D4 (3/11): every row names its run plan; a measurement names its job."""
    base = {
        "activity": "eval",
        "resource_type": "gpu_hour_rtx3060",
        "quantity": 1.0,
        "unit": "hour",
        "usd_amount": 0.2,
    }
    with pytest.raises(ValidationError, match="run_plan_id"):
        LedgerEntry.model_validate({**base, "measure_kind": "estimated"})
    with pytest.raises(ValidationError, match="run_plan_id"):
        LedgerEntry.model_validate({**base, "measure_kind": "estimated", "run_plan_id": ""})

    estimate = LedgerEntry.model_validate(
        {**base, "measure_kind": "estimated", "run_plan_id": "rp_1"}
    )
    assert estimate.job_id is None  # an estimate may be made for the whole run plan
    with pytest.raises(ValidationError, match="job_id"):
        LedgerEntry.model_validate(
            {
                **base,
                "measure_kind": "measured",
                "run_plan_id": "rp_1",
                "estimate_entry_id": estimate.id,
            }
        )
