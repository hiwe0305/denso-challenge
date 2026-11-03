"""Where an evidence card is written, and why the Cluster never names it (DA-39, PO P1)."""

import json
from pathlib import Path

import pytest
from flywheel.contracts.entities import Cluster
from flywheel.contracts.evidence import EvidenceCard
from flywheel.store.paths import StorePaths

ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = (
    ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/EvidenceCard.json"
)


def cluster() -> Cluster:
    return Cluster(
        task_id="g1_locomotion_pick_between_tables",
        run_plan_id="rp_7d2306b437d7fbbf",
        first_failed_step=2,
        failure_kind="L-GRASP",
        level=1,
        member_episode_ids=["ep_01M6HXNZ010000000000000001"],
    )


def test_card_path_is_derived_from_the_cluster_id(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    expected = paths.runs_dir / "rp_1" / "cards" / "clu_8406056e72ff77ac"
    assert paths.card_dir("rp_1", "clu_8406056e72ff77ac") == expected
    assert paths.card_path("rp_1", "clu_8406056e72ff77ac") == expected / "card.json"
    for bad in ("../clu_1", "clu/1", ".hidden"):
        with pytest.raises(ValueError):
            paths.card_path("rp_1", bad)


def test_writing_the_card_leaves_the_cluster_id_unchanged(tmp_path: Path) -> None:
    before = cluster()
    card = EvidenceCard.model_validate(
        {**json.loads(EXAMPLE.read_text(encoding="utf-8")), "cluster_id": before.id}
    )
    path = StorePaths(root=tmp_path).card_path(before.run_plan_id, card.cluster_id)
    path.parent.mkdir(parents=True)
    path.write_text(card.model_dump_json(), encoding="utf-8")

    after = Cluster.model_validate_json(before.model_dump_json())
    assert after.id == before.id and after.card_uri is None
    assert EvidenceCard.model_validate_json(path.read_text(encoding="utf-8")).cluster_id == after.id
    # What P1 avoids: naming the card in the Cluster gives it another id.
    named = Cluster.model_validate({**before.model_dump(exclude={"id"}), "card_uri": str(path)})
    assert named.id.startswith("clu_") and named.id != before.id
