"""DA-04 task 1: ingest of a pinned EgoDex subset, hashes, licence, data_class (AC 1)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from ego_data import CONFIG, FRAMES, config_for, write_hdf5
from flywheel.data.api import ConfigError
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.config import EgoConfig, load_config
from flywheel.data.ingest.egocentric.egodex import instruction_of, read_meta
from flywheel.data.ingest.egocentric.episodes import read_bundle, read_episodes
from flywheel.data.ingest.egocentric.source import (
    changed_files,
    load_record,
    register_egodex,
    select_egodex,
)


def test_the_repo_config_pins_a_pick_and_place_subset() -> None:
    cfg = load_config(CONFIG)
    egodex = cfg.sources["egodex"]
    assert egodex.data_class == "public" and egodex.license == "CC-BY-NC-ND-4.0"
    assert egodex.episodes_per_task == 2 and len(egodex.tasks) == 10
    assert "basic_pick_place" in egodex.tasks
    assert cfg.threshold_version.startswith("ego-1@")


def test_an_unknown_or_missing_key_is_a_config_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(CONFIG.read_text().replace("review:", "extra: 1\nreview:"))
    with pytest.raises(ConfigError, match="unknown"):
        load_config(bad)
    missing = tmp_path / "missing.yaml"
    missing.write_text(CONFIG.read_text().replace("  hand_out_of_frame:", "  hand_out_of:"))
    with pytest.raises(ConfigError):
        load_config(missing)


def test_selection_takes_the_lowest_complete_episodes_per_task(store: Path) -> None:
    split = store / "egodex" / "part1"
    (split / "stack_cups" / "0.mp4").unlink()  # episode 0 is incomplete now
    chosen = select_egodex(split, ("stack_cups", "basic_pick_place"), 2)
    assert [(e.task, e.index) for e in chosen] == [
        ("basic_pick_place", 0), ("basic_pick_place", 1), ("stack_cups", 1), ("stack_cups", 2)]
    with pytest.raises(ValueError, match="not in the sample"):
        select_egodex(split, ("no_such_task",), 1)
    with pytest.raises(ValueError, match="complete episodes"):
        select_egodex(split, ("stack_cups",), 3)


def test_register_hashes_every_chosen_file_and_names_the_waiver(store: Path,
                                                                cfg: EgoConfig) -> None:
    record = register_egodex(store, cfg)
    assert len(record.episodes) == 4 and len(record.files) == 8
    name = "part1/basic_pick_place/0.hdf5"
    expected = hashlib.sha256((store / "egodex" / name).read_bytes()).hexdigest()
    assert record.files[name] == expected
    assert record.license == "CC-BY-NC-ND-4.0" and record.data_class == "public"
    assert record.deid_waiver is not None and "D2" in record.deid_waiver
    assert record.source_id == register_egodex(store, cfg).source_id
    assert changed_files(record) == []
    write_hdf5(store / "egodex" / name, frames=FRAMES + 1)
    assert changed_files(record) == [name]
    assert register_egodex(store, cfg).source_id != record.source_id


def test_ingest_writes_egocentric_episodes_and_bundles(store: Path, cfg: EgoConfig) -> None:
    record = register_egodex(store, cfg)
    work = store / "pipeline" / record.source_id
    episodes = api.ingest(record, work, cfg, store)
    assert load_record((work / "source.json").read_text()) == record
    assert read_episodes(work) == episodes
    for e in episodes:
        assert (e.source_kind, e.kind, e.operator_kind, e.is_root) == (
            "egocentric", "teleop_demo", "human", True)
        assert (e.deid_status, e.action_quality, e.data_class) == ("raw", "retargeted", "public")
        assert e.embodiment_id == "human_hands@egodex" and e.source_id == record.source_id
        assert e.bundle_uri.startswith(f"pipeline/{record.source_id}/egocentric/")
        bundle = read_bundle(work, e.episode_id)
        assert (bundle.frames, bundle.video_frames, bundle.fps) == (FRAMES, FRAMES, 30.0)
        assert bundle.pose_source == "E-B" and bundle.objects == ("cup",)
        assert bundle.instruction == "Pick up the cup and place it on the plate."
    again = api.ingest(register_egodex(store, cfg), work, cfg, store)
    assert [e.episode_id for e in again] == [e.episode_id for e in episodes]


def test_holdout_is_never_ingested(store: Path, cfg: EgoConfig) -> None:
    record = register_egodex(store, cfg)
    with pytest.raises(ValueError, match="holdout"):
        api.ingest(record, store / "w", cfg, store, split="holdout")


def test_the_instruction_follows_which_llm_description() -> None:
    attrs = {"llm_description": "first", "llm_description2": "second",
             "which_llm_description": 2, "description": "annotator"}
    assert instruction_of(attrs) == "second"
    assert instruction_of({**attrs, "which_llm_description": 1}) == "first"
    assert instruction_of({"llm_description": "None", "description": "annotator"}) == "annotator"


def test_read_meta(tmp_path: Path) -> None:
    path = tmp_path / "t" / "0.hdf5"
    write_hdf5(path)
    meta = read_meta(path)
    assert meta.frames == FRAMES and meta.intrinsic.shape == (3, 3) and meta.task == "t"


def test_a_config_with_another_subset(tmp_path: Path, store: Path) -> None:
    cfg = load_config(config_for(tmp_path, tasks=("stack_cups",), per_task=3))
    assert len(register_egodex(store, cfg).episodes) == 3
