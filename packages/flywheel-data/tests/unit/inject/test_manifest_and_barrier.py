"""Unit tests for DefectManifest, clean dataset, and release barrier (AC 3, AC 4, AC 5)."""

import re
from collections import Counter
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.data.inject.applied import defect_applied
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.config import InjectConfig, load_inject_config
from flywheel.data.inject.data_defects import EpisodeData
from flywheel.data.inject.dataset import (
    copy_ids,
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
            # 36-D G1 action; hands (0-13) at zero, the rest moves.
            actions=[[0.0] * 14 + [0.05 * (j + 1) + 0.001 * i] * 22 for j in range(3)],
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
        defects=[
            Defect(
                target_ref="ep_001", code="D3", parameters={"kind": "joint_jump", "dimension": 0}
            )
        ],
    )
    manifest_file = tmp_path / "defects.json"
    h = seal_manifest(manifest, manifest_file)
    assert len(h) == 64
    assert (tmp_path / "defects.sha256").read_text(encoding="utf-8") == h
    assert manifest_sha256(load_manifest(manifest_file)) == h

    lock = ManifestLock(manifest_file)
    assert lock.verify_integrity()
    manifest_file.write_text(manifest_file.read_text().replace("ep_001", "ep_002"))
    assert not lock.verify_integrity()


def test_create_defect_and_clean_dataset() -> None:
    episodes = _make_episodes(20)
    cfg = InjectConfig(episodes_per_kind=1)
    injected, manifest = create_defect_dataset(episodes, config=cfg)

    assert len(injected) == 20
    assert len(manifest.defects) == 11
    # Check that injected episodes have metadata record
    injected_count = sum(1 for ep in injected if ep.meta.injected_defect is not None)
    assert injected_count == len(manifest.defects)

    # Clean dataset is a fresh copy of the originals, same size, no defect metadata
    clean, clean_manifest = create_clean_dataset(episodes)
    assert len(clean) == 20
    assert clean_manifest.defects == []
    assert all(ep.meta.injected_defect is None for ep in clean)


def test_release_barrier_blocks_injected_episodes() -> None:
    episodes = _make_episodes(40)
    injected, _ = create_defect_dataset(episodes)

    # Injected dataset must be rejected by release barrier
    with pytest.raises(ValueError, match="Release train barrier violation"):
        verify_release_barrier(injected)

    # Clean dataset passes through barrier
    clean, _ = create_clean_dataset(episodes)
    passed = verify_release_barrier(clean)
    assert len(passed) == 40


def test_dataset_ref_handoff() -> None:
    manifest = DefectManifest(dataset_id="ds_eval", seed=100, defects=[])
    ref, hash_str = get_dataset_refs("ds_eval", manifest)
    assert ref.dataset_id == "ds_eval"
    assert len(hash_str) == 64


def test_every_data_defect_fits_the_contract() -> None:
    _, manifest = create_defect_dataset(_make_episodes(99))
    assert len({d.parameters["kind"] for d in manifest.defects}) == 11
    assert {d.code for d in manifest.defects} == {"D1", "D2", "D3", "D5", "D6", "D7"}
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
    assert cfg.episodes_per_kind == 3
    assert cfg.data.timestamp_offset_seconds > 0.033


def test_three_distinct_episodes_per_kind() -> None:
    # PO decision 3/11/2026: 3 episodes per kind, 33 of 99, one defect per episode at most.
    injected, manifest = create_defect_dataset(_make_episodes(99))
    assert len(injected) == 99
    assert Counter(d.parameters["kind"] for d in manifest.defects) == {
        kind: 3 for kind in DATA_DEFECT_CODES
    }
    assert len({d.target_ref for d in manifest.defects}) == 33
    assert sum(ep.meta.injected_defect is not None for ep in injected) == 33


def test_same_seed_gives_same_manifest() -> None:
    episodes = _make_episodes(99)
    _, first = create_defect_dataset(episodes, config=InjectConfig(seed=7))
    _, again = create_defect_dataset(episodes, config=InjectConfig(seed=7))
    _, other = create_defect_dataset(episodes, config=InjectConfig(seed=8))
    assert manifest_sha256(first) == manifest_sha256(again)
    assert first.seed == 7
    assert manifest_sha256(first) != manifest_sha256(other)


def test_duplicate_copies_a_clean_episode_and_keeps_the_original() -> None:
    episodes = _make_episodes(99)
    injected, manifest = create_defect_dataset(episodes)
    by_id = {ep.episode_id: ep for ep in injected}
    dups = [d for d in manifest.defects if d.parameters["kind"] == "duplicate_episode"]
    assert len(dups) == 3
    for d in dups:
        copy, source = by_id[d.target_ref], by_id[str(d.parameters["original_id"])]
        assert source.meta.injected_defect is None
        assert (copy.seed, copy.states, copy.actions) == (
            source.seed,
            source.states,
            source.actions,
        )
    assert [ep.episode_id for ep in injected] == [ep.episode_id for ep in episodes]


def test_too_few_episodes_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs more than 33 episodes"):
        create_defect_dataset(_make_episodes(33))


def test_every_manifest_entry_was_applied() -> None:
    # Recall per kind is computed from the manifest, so no entry may be listed only.
    episodes = _make_episodes(99)
    injected, manifest = create_defect_dataset(episodes)
    before = {ep.episode_id: ep for ep in episodes}
    after = {ep.episode_id: ep for ep in injected}
    for d in manifest.defects:
        source = before.get(str(d.parameters.get("original_id", "")))
        assert defect_applied(before[d.target_ref], after[d.target_ref], d, source), d


def test_episodes_without_signal_are_skipped_for_action_kinds() -> None:
    # 70 episodes with all-zero actions cannot take unit_deg_rad or action_sign_flip.
    episodes = _make_episodes(99)
    for ep in episodes[:70]:
        ep.actions = [[0.0] * 36 for _ in ep.actions]
    _, manifest = create_defect_dataset(episodes)
    action_kinds = {"unit_deg_rad", "action_sign_flip"}
    targets = {d.target_ref for d in manifest.defects if d.parameters["kind"] in action_kinds}
    assert len(targets) == 6
    assert targets <= {ep.episode_id for ep in episodes[70:]}


def test_too_few_eligible_episodes_names_the_kind() -> None:
    episodes = _make_episodes(99)
    for ep in episodes:
        ep.actions = [[0.0] * 36 for _ in ep.actions]
    with pytest.raises(ValueError, match="unit_deg_rad"):
        create_defect_dataset(episodes)


NEUTRAL_ID = re.compile(r"^bench-[0-9a-f]{12}$")


def test_copy_ids_are_neutral_and_share_one_format() -> None:
    defect_id, clean_id = copy_ids(42)
    assert NEUTRAL_ID.match(defect_id) and NEUTRAL_ID.match(clean_id)
    assert defect_id != clean_id
    assert copy_ids(42) == (defect_id, clean_id)
    assert copy_ids(43) != (defect_id, clean_id)


def test_only_the_manifests_tell_the_copies_apart() -> None:
    # The agent sees dataset ids; only the scorer reads which manifest has defects.
    episodes = _make_episodes(40)
    _, defect_manifest = create_defect_dataset(episodes)
    _, clean_manifest = create_clean_dataset(episodes)
    assert {defect_manifest.dataset_id, clean_manifest.dataset_id} == set(copy_ids(42))
    assert defect_manifest.defects and not clean_manifest.defects
    assert defect_manifest.seed == clean_manifest.seed == 42


def test_revealing_dataset_ids_are_rejected() -> None:
    episodes = _make_episodes(40)
    for name in ("ds_psi_data_injected", "bench-Defect-1"):
        with pytest.raises(ValueError, match="reveals"):
            create_defect_dataset(episodes, dataset_id=name)
    with pytest.raises(ValueError, match="reveals"):
        create_clean_dataset(episodes, dataset_id="ds_psi_data_clean")


def test_dataset_passes_the_layout_to_the_injector() -> None:
    from flywheel.contracts.artifacts import ActionDimension, ActionLayout

    layout = ActionLayout(
        dimensions=[
            ActionDimension(
                name=f"a{d}",
                group="g",
                masked=d < 25,
                limit_low=-1.0 if d < 31 else None,
                limit_high=1.0 if d < 31 else None,
            )
            for d in range(36)
        ]
    )
    _, manifest = create_defect_dataset(_make_episodes(99), layout=layout)
    dims = [int(d.parameters["dimension"]) for d in manifest.defects if "dimension" in d.parameters]
    assert dims and all(d >= 25 for d in dims)
