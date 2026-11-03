"""Source registration and Episode records for the three robot sources (DA-03 task 2, AC 2)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
import yaml
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.ingest.sources import (
    HOLDOUT,
    SPLITS,
    SourceRecord,
    register_source,
    to_episode,
)

REPO = Path(__file__).resolve().parents[5]
Dataset = tuple[Path, list[EpisodeFrames]]
Flywheel = Callable[..., None]
Block = dict[str, object]


def s2_block(s1: Block) -> Block:
    return {**s1, "source_detail": "teleop_pico", "synthetic_tier": "S2",
            "generator_version": "da35-s2-1", "parent_episode": "ep_parent0001"}


def test_register_source_hashes_every_file(dataset: Dataset) -> None:
    root, _ = dataset
    record = register_source(root, "psi_data", "unknown", "public")
    on_disk = sorted(p for p in root.rglob("*") if p.is_file())
    assert sorted(record.files) == sorted(p.relative_to(root).as_posix() for p in on_disk)
    for path in on_disk:
        rel = path.relative_to(root).as_posix()
        assert record.files[rel] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record.total_bytes == sum(p.stat().st_size for p in on_disk)
    assert record.license == "unknown"
    assert record.data_class == "public"
    assert record.source_detail == "psi_data"
    assert record.root == str(root.resolve())


def test_source_id_is_stable_and_follows_content(dataset: Dataset) -> None:
    root, _ = dataset
    first = register_source(root, "psi_data", "unknown", "public")
    assert first.source_id.startswith("src_")
    assert register_source(root, "psi_data", "unknown", "public").source_id == first.source_id
    assert register_source(root, "psi_data", "MIT", "public").source_id != first.source_id
    assert register_source(root, "planner_wbc", "unknown", "public").source_id != first.source_id
    (root / "meta" / "tasks.jsonl").write_text("changed\n")
    assert register_source(root, "psi_data", "unknown", "public").source_id != first.source_id


def test_register_source_needs_a_lerobot_dataset(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="info.json"):
        register_source(tmp_path, "psi_data", "unknown", "public")


@pytest.mark.parametrize("detail", ["teleop_keyboard", "planner_amo", "virtual_teleop"])
def test_register_source_refuses_a_source_without_a_profile(dataset: Dataset, detail: str) -> None:
    root, _ = dataset
    with pytest.raises(ValueError, match="psi_data, planner_wbc, teleop_pico"):
        register_source(root, detail, "unknown", "public")


def test_register_source_refuses_an_unknown_data_class(dataset: Dataset) -> None:
    root, _ = dataset
    with pytest.raises(ValueError, match="data_class"):
        register_source(root, "psi_data", "unknown", "secret")  # type: ignore[arg-type]


def test_register_source_refuses_an_empty_license(dataset: Dataset) -> None:
    root, _ = dataset
    with pytest.raises(ValueError, match="license"):
        register_source(root, "psi_data", " ", "public")


def test_psi_data_episode_is_a_measured_human_teleop_root(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    episode = to_episode(written[0], source, "train")
    assert episode.source_kind == "teleop"
    assert episode.action_quality == "measured"
    assert episode.meta.source_detail == "psi_data"
    assert episode.meta.synthetic_tier is None
    assert episode.kind == "teleop_demo"
    assert episode.operator_kind == "human"
    assert episode.is_root is True
    assert episode.embodiment_id == "g1_sonic_dwbc@1"


def test_tray_s1_episode_is_a_planned_synthetic_s1(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, written = dataset
    flywheel(root, 1, s1_block)
    source = register_source(root, "planner_wbc", "internal-generated", "public")
    episode = to_episode(written[1], source, "train")
    assert episode.source_kind == "synthetic"
    assert episode.action_quality == "planned"
    assert episode.meta.synthetic_tier == "S1"
    assert episode.meta.source_detail == "planner_wbc"
    assert episode.meta.renderer == "mujoco"
    assert episode.operator_kind == "machine"
    assert episode.is_root is False
    assert episode.embodiment_id == "g1_sonic_dwbc@1"


def test_tray_s2_episode_goes_through_the_pico_pipe(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, written = dataset
    flywheel(root, 2, s2_block(s1_block))
    source = register_source(root, "teleop_pico", "internal-generated", "public")
    episode = to_episode(written[2], source, "train")
    assert episode.meta.source_detail == "teleop_pico"
    # DA-35: virtual teleop is not human data and is never recorded as teleop.
    assert episode.source_kind == "synthetic"
    assert episode.meta.synthetic_tier == "S2"
    assert episode.action_quality == "planned"
    assert episode.kind == "variant"
    assert episode.is_root is False


def test_episode_carries_source_license_class_and_split(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    episode = to_episode(written[0], source, "dev")
    assert episode.source_id == source.source_id
    assert episode.license == "unknown"
    assert episode.data_class == "public"
    assert episode.split == "dev"
    assert episode.deid_status == "raw"
    assert episode.meta.injected_defect is None


def test_episode_ids_are_stable_and_distinct(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    ids = [to_episode(f, source, "train").episode_id for f in written]
    assert len(set(ids)) == 3
    assert all(i.startswith("ep_") for i in ids)
    assert ids == [to_episode(f, source, "train").episode_id for f in written]


def test_bundle_uri_points_at_the_episode_parquet(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    uri = to_episode(written[2], source, "train").bundle_uri
    path = Path(urlparse(uri).path)
    assert path == root.resolve() / "data" / "chunk-000" / "episode_000002.parquet"
    assert path.is_file()


def test_condition_is_marked_unknown_per_episode(dataset: Dataset) -> None:
    # psi-data holds no condition seed (S1-07); the record must not invent one.
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    conditions = {to_episode(f, source, "train").condition_id for f in written}
    assert len(conditions) == 3
    assert all(c.startswith("cond_unknown_") for c in conditions)


@pytest.mark.parametrize("split", ["", "nonsense", "test", "gate"])
def test_an_unknown_split_is_refused(dataset: Dataset, split: str) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    with pytest.raises(ValueError, match="is not one of train, dev"):
        to_episode(written[0], source, split)


def test_holdout_is_never_ingested(dataset: Dataset) -> None:
    # Review #69 point 4: holdout lives only in vault/, read only by gate.
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    with pytest.raises(ValueError, match="holdout lives only in vault/"):
        to_episode(written[0], source, "holdout")


def test_a_split_other_than_the_recorded_one_is_refused(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, written = dataset
    flywheel(root, 0, s1_block)
    source = register_source(root, "planner_wbc", "internal-generated", "public")
    assert to_episode(written[0], source, "train").split == "train"
    with pytest.raises(ValueError, match="recorded in split 'train', not 'dev'"):
        to_episode(written[0], source, "dev")


def test_ingest_splits_are_the_split_plan_without_holdout() -> None:
    plan = yaml.safe_load((REPO / "configs" / "splits" / "default.yaml").read_text())
    assert set(SPLITS) == set(plan["seed_ranges"]) - {HOLDOUT}


def test_to_episode_refuses_a_hand_made_record_without_a_profile(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    forged = SourceRecord(**{**source.__dict__, "source_detail": "teleop_keyboard"})
    with pytest.raises(ValueError, match="teleop_keyboard"):
        to_episode(written[0], forged, "train")


def test_the_lane_api_exposes_ingest() -> None:
    from flywheel.data import api

    assert api.register_source is register_source
    assert api.to_episode is to_episode
    assert api.SourceRecord is SourceRecord


def test_generated_episode_keeps_seed_level_and_generator(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    # Review #69 point 3; 03 invariant 10.
    root, written = dataset
    flywheel(root, 0, s1_block)
    flywheel(root, 1, {**s1_block, "seed": 1001})
    source = register_source(root, "planner_wbc", "internal-generated", "public")
    lineage = source.lineage[0]
    assert (lineage.seed, lineage.level, lineage.split) == (1000, 1, "train")
    assert lineage.generator_version == "da33-planner-4+cfg.815b822a"
    assert lineage.task_uid == "g1_wholebody_tray_transfer_teleop"
    first, second = (to_episode(f, source, "train") for f in written[:2])
    assert first.condition_id.startswith("cond_") and "unknown" not in first.condition_id
    assert first.condition_id != second.condition_id


def test_same_scene_gives_the_same_condition_across_sources(
    tmp_path: Path, dataset_factory: Callable[[Path, list[int]], list[EpisodeFrames]],
    flywheel: Flywheel, s1_block: Block,
) -> None:
    ids = []
    for name in ("a", "b"):
        root = tmp_path / name
        frames = dataset_factory(root, [3])[0]
        flywheel(root, 0, s1_block)
        ids.append(to_episode(frames, register_source(root, "planner_wbc", "x", "public"),
                              "train").condition_id)
    assert ids[0] == ids[1]


def test_variant_keeps_parent_and_root(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, written = dataset
    flywheel(root, 2, {**s2_block(s1_block), "root_episode": "ep_root0001"})
    source = register_source(root, "teleop_pico", "internal-generated", "public")
    episode = to_episode(written[2], source, "train")
    assert episode.parent_id == "ep_parent0001"
    assert episode.root_id == "ep_root0001"


def test_variant_without_parent_is_refused(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, written = dataset
    block = s2_block(s1_block)
    del block["parent_episode"]
    flywheel(root, 2, block)
    source = register_source(root, "teleop_pico", "internal-generated", "public")
    with pytest.raises(ValueError, match="variant without parent_episode"):
        to_episode(written[2], source, "train")


@pytest.mark.parametrize("drop", ["seed", "planner_version"])
def test_machine_made_episode_without_seed_or_generator_is_refused(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block, drop: str
) -> None:
    root, written = dataset
    del s1_block[drop]
    flywheel(root, 0, s1_block)
    source = register_source(root, "planner_wbc", "internal-generated", "public")
    with pytest.raises(ValueError, match="invariant 10"):
        to_episode(written[0], source, "train")


def test_machine_made_episode_without_a_flywheel_block_is_refused(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "planner_wbc", "internal-generated", "public")
    with pytest.raises(ValueError, match="no seed and no generator version"):
        to_episode(written[0], source, "train")


@pytest.mark.parametrize(
    "label, value",
    [("source_kind", "teleop"), ("synthetic_tier", "S1"), ("data_class", "internal"),
     ("source_detail", "virtual_teleop")],
)
def test_a_recorded_label_that_disagrees_with_the_source_is_refused(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block, label: str, value: str
) -> None:
    # Review #69 point 8: real PICO data (source_kind teleop) must not be labelled synthetic.
    root, written = dataset
    flywheel(root, 2, {**s2_block(s1_block), label: value})
    source = register_source(root, "teleop_pico", "internal-generated", "public")
    with pytest.raises(ValueError, match=f"recorded {label}='{value}'"):
        to_episode(written[2], source, "train")


def test_a_non_string_parent_is_refused_at_registration(
    dataset: Dataset, flywheel: Flywheel, s1_block: Block
) -> None:
    root, _ = dataset
    flywheel(root, 2, {**s2_block(s1_block), "parent_episode": 7})
    with pytest.raises(ValueError, match="parent_episode 7 is not an episode id"):
        register_source(root, "teleop_pico", "internal-generated", "public")


def test_an_episode_of_another_dataset_is_refused(dataset: Dataset) -> None:
    root, written = dataset
    source = register_source(root, "psi_data", "unknown", "public")
    stranger = replace(written[0], episode_index=42)
    with pytest.raises(ValueError, match="episode 42 is not in source"):
        to_episode(stranger, source, "train")


def test_register_source_reports_index_findings(dataset: Dataset) -> None:
    root, _ = dataset
    assert register_source(root, "psi_data", "unknown", "public").index_findings == ()
    path = root / "data" / "chunk-000" / "episode_000001.parquet"
    table = pq.read_table(path)
    position = table.schema.get_field_index("index")
    pq.write_table(table.set_column(position, "index", pa.array(range(10, 17))), path)
    findings = register_source(root, "psi_data", "unknown", "public").index_findings
    assert [(f.episode_index, f.expected_first, f.found_first) for f in findings] == [(1, 5, 10)]
