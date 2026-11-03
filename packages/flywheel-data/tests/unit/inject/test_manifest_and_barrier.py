"""Unit tests for DefectManifest, clean dataset, and release barrier (AC 3, AC 4, AC 5)."""

from pathlib import Path

import pytest
from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.data.inject.config import InjectConfig, load_inject_config
from flywheel.data.inject.data_defects import EpisodeData
from flywheel.data.inject.dataset import (
    create_clean_dataset,
    create_defect_dataset,
    get_dataset_refs,
    verify_release_barrier,
)
from flywheel.data.inject.manifest import (
    ManifestLock,
    load_manifest,
    manifest_sha256,
    seal_manifest,
)


def _make_episodes(n: int = 15) -> list[EpisodeData]:
    return [
        EpisodeData(
            episode_id=f"ep_{i:03d}",
            timestamps_state=[0.0, 0.05, 0.10],
            timestamps_image=[0.0, 0.05, 0.10],
            states=[[0.1, 0.2] for _ in range(3)],
            actions=[[0.05, 0.15] for _ in range(3)],
            images=["f0.jpg", "f1.jpg", "f2.jpg"],
            sim_success=True,
            seed=2000 + i,
        )
        for i in range(n)
    ]


def test_manifest_serialization_and_lock(tmp_path: Path) -> None:
    manifest = DefectManifest(
        dataset_id="test_ds",
        seed=42,
        defects=[Defect(target_ref="ep_001", code="joint_jump", parameters={"dim": 0})],
    )
    manifest_file = tmp_path / "defects.json"
    h = seal_manifest(manifest, manifest_file)
    assert len(h) == 64
    assert (tmp_path / "defects.sha256").read_text(encoding="utf-8") == h
    assert manifest_sha256(load_manifest(manifest_file)) == h

    lock = ManifestLock(manifest_file)
    assert lock.verify_integrity()
    assert not lock.can_agent_read("eval_agent")
    assert not lock.can_agent_read("qa_agent")
    assert lock.can_agent_read("admin")


def test_create_defect_and_clean_dataset() -> None:
    episodes = _make_episodes(20)
    cfg = InjectConfig(injection_rate=0.10)
    injected, manifest = create_defect_dataset(episodes, config=cfg)

    assert len(injected) == 20
    assert len(manifest.defects) >= 2
    # Check that injected episodes have metadata record
    injected_count = sum(1 for ep in injected if ep.meta.injected_defect is not None)
    assert injected_count == len(manifest.defects)

    # Clean dataset has same size, no defect metadata
    clean = create_clean_dataset(injected)
    assert len(clean) == 20
    assert all(ep.meta.injected_defect is None for ep in clean)


def test_release_barrier_blocks_injected_episodes() -> None:
    episodes = _make_episodes(10)
    injected, _ = create_defect_dataset(episodes)

    # Injected dataset must be rejected by release barrier
    with pytest.raises(ValueError, match="Release train barrier violation"):
        verify_release_barrier(injected)

    # Clean dataset passes through barrier
    clean = create_clean_dataset(injected)
    passed = verify_release_barrier(clean)
    assert len(passed) == 10


def test_dataset_ref_handoff() -> None:
    manifest = DefectManifest(dataset_id="ds_eval", seed=100, defects=[])
    ref, hash_str = get_dataset_refs("ds_eval", manifest)
    assert ref.dataset_id == "ds_eval"
    assert len(hash_str) == 64


def test_every_data_defect_fits_the_contract() -> None:
    # 200 episodes at 10% cycle through all 11 injectors at least once.
    _, manifest = create_defect_dataset(
        _make_episodes(200), config=InjectConfig(injection_rate=0.10)
    )
    assert len(manifest.defects) == 20
    assert DefectManifest.model_validate(manifest.model_dump()) == manifest


def test_injected_episode_carries_its_manifest_entry() -> None:
    injected, manifest = create_defect_dataset(_make_episodes(40))
    by_id = {ep.episode_id: ep for ep in injected}
    for defect in manifest.defects:
        mark = by_id[defect.target_ref].meta.injected_defect
        assert mark is not None
        assert (mark.code, mark.parameters) == (defect.code, defect.parameters)


def test_config_loader() -> None:
    cfg = load_inject_config()
    assert cfg.version == "1.0.0"
    assert 0.05 <= cfg.injection_rate <= 0.10
    assert cfg.data.timestamp_offset_seconds > 0.033
