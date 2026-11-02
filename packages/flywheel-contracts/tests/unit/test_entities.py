"""Unit tests for the 12 L0-lite catalog entities (AC 1, AC 3, AC 4)."""

import pytest
from pydantic import ValidationError

from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Condition,
    Decision,
    Episode,
    FixRateEvent,
    LedgerEntry,
    QAReport,
    Release,
    RunPlan,
    Score,
    Source,
)


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

    # 3. Episode (event)
    ep = Episode(
        kind="teleop_demo",
        operator_kind="human",
        is_root=True,
        bundle_uri="sites/local/episodes/ep_01H...",
    )
    assert ep.id.startswith("ep_")
    assert len(ep.id) == 3 + 26  # ep_ + 26-char ULID

    # 4. QAReport (event)
    qa = QAReport(
        episode_id=ep.id,
        decision="pass",
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
        resource_type="gpu_hour_a100",
        quantity=2.5,
        unit="hour",
        usd_amount=7.50,
        measure_kind="measured",
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


def test_episode_root_invariant() -> None:
    """AC 3: is_root = true requires human operator and teleop kind."""
    # Valid root
    ep_valid = Episode(
        kind="teleop_demo",
        operator_kind="human",
        is_root=True,
        bundle_uri="uri",
    )
    assert ep_valid.is_root is True

    # Invalid: machine cannot be root
    with pytest.raises(ValidationError):
        Episode(
            kind="teleop_demo",
            operator_kind="machine",
            is_root=True,
            bundle_uri="uri",
        )

    # Invalid: sim_rollout cannot be root
    with pytest.raises(ValidationError):
        Episode(
            kind="sim_rollout",
            operator_kind="human",
            is_root=True,
            bundle_uri="uri",
        )


def test_content_id_determinism_on_entity() -> None:
    """AC 4: Two ContentEntity instances with same content receive identical ID."""
    src1 = Source(
        uri="https://example.com/data.tar",
        sha256="d" * 64,
        downloaded_at="2026-11-02T00:00:00Z",
    )
    src2 = Source(
        uri="https://example.com/data.tar",
        sha256="d" * 64,
        downloaded_at="2026-11-02T00:00:00Z",
    )
    src3 = Source(
        uri="https://example.com/data.tar",
        sha256="e" * 64,
        downloaded_at="2026-11-02T00:00:00Z",
    )
    assert src1.id == src2.id
    assert src1.id != src3.id


def test_custom_embodiment_and_task_does_not_break_schema() -> None:
    """NFR7: Custom embodiment and task can be passed without altering entity schema."""
    ep = Episode(
        kind="sim_rollout",
        operator_kind="machine",
        bundle_uri="uri",
        task_id="future_assembly_task",
        embodiment_id="custom_robot_arm@2",
        site_id="plant_yokohama",
    )
    assert ep.task_id == "future_assembly_task"
    assert ep.embodiment_id == "custom_robot_arm@2"
    assert ep.site_id == "plant_yokohama"
