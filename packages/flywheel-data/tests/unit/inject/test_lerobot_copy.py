"""Inject into a copy of a LeRobot dataset through the DA-03 reader and writer (task 8)."""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts.artifacts import DefectManifest
from flywheel.data.ingest.lerobot import EpisodeFrames, iter_episodes, read_episode_rows
from flywheel.data.inject.applied import defect_applied
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.lerobot_copy import (
    COPY_MARKER,
    episode_ref,
    frames_to_data,
    inject_copy,
    row_seed,
)
from lerobot_data import FPS, make_dataset, tree_hashes, video_path


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, DefectManifest]:
    base = tmp_path_factory.mktemp("lerobot")
    src = base / "psi"
    make_dataset(src)
    before = tree_hashes(src)
    out = base / "copies" / copy_ids(42)[0]
    manifest = inject_copy(src, out)
    assert tree_hashes(src) == before, "the source must not change"
    return src, out, manifest


def _episodes(root: Path) -> dict[str, EpisodeFrames]:
    return {episode_ref(f.episode_index): f for f in iter_episodes(root)}


def _seeds(root: Path) -> dict[str, int | None]:
    return {episode_ref(int(r["episode_index"])): row_seed(r) for r in read_episode_rows(root)}


def test_copy_holds_three_episodes_per_kind(built: tuple[Path, Path, DefectManifest]) -> None:
    _, out, manifest = built
    assert manifest.dataset_id == copy_ids(42)[0]
    assert Counter(d.parameters["kind"] for d in manifest.defects) == {
        kind: 3 for kind in DATA_DEFECT_CODES
    }
    assert len({d.target_ref for d in manifest.defects}) == 33
    assert len(list(iter_episodes(out))) == 40


def test_every_defect_is_in_the_files_written(built: tuple[Path, Path, DefectManifest]) -> None:
    # Read both datasets back from disk: the defect must be in what was written.
    src, out, manifest = built
    before, after = _episodes(src), _episodes(out)
    seeds_before, seeds_after = _seeds(src), _seeds(out)
    for d in manifest.defects:
        ref = d.target_ref
        old = frames_to_data(before[ref], FPS, seeds_before[ref])
        new = frames_to_data(after[ref], FPS, seeds_after[ref])
        source = None
        if d.parameters["kind"] == "duplicate_episode":
            orig = str(d.parameters["original_id"])
            source = frames_to_data(before[orig], FPS, seeds_before[orig])
        assert defect_applied(old, new, d, source), d


def test_untouched_episodes_keep_their_data(built: tuple[Path, Path, DefectManifest]) -> None:
    src, out, manifest = built
    targets = {d.target_ref for d in manifest.defects}
    before, after = _episodes(src), _episodes(out)
    untouched = [ref for ref in before if ref not in targets]
    assert len(untouched) == 7
    for ref in untouched:
        a, b = before[ref], after[ref]
        assert a.task == b.task
        for name in ("timestamp", "frame_index", "states", "action"):
            assert np.array_equal(getattr(a, name), getattr(b, name)), (ref, name)


def test_duplicate_copies_parquet_and_video_of_its_source(
    built: tuple[Path, Path, DefectManifest],
) -> None:
    src, out, manifest = built
    for d in manifest.defects:
        if d.parameters["kind"] != "duplicate_episode":
            continue
        slot = int(d.target_ref.removeprefix("episode_"))
        orig = int(str(d.parameters["original_id"]).removeprefix("episode_"))
        assert video_path(out, slot).read_bytes() == video_path(src, orig).read_bytes()
        assert video_path(out, orig).read_bytes() == video_path(src, orig).read_bytes()
        # A real duplicate carries its source's meta row too, scene layout included.
        rows = {int(r["episode_index"]): r for r in read_episode_rows(out)}
        source_rows = {int(r["episode_index"]): r for r in read_episode_rows(src)}
        assert rows[slot]["environment_config"] == source_rows[orig]["environment_config"]


def test_leaked_seed_is_in_the_episode_flywheel_block(
    built: tuple[Path, Path, DefectManifest],
) -> None:
    _, out, manifest = built
    seeds = _seeds(out)
    leaked = {d.target_ref for d in manifest.defects if d.parameters["kind"] == "holdout_seed_leak"}
    for ref, seed in seeds.items():
        if ref in leaked:
            assert seed is not None and 2_000_000 <= seed <= 2_000_999
        else:
            assert seed is None


def test_copy_carries_its_neutral_marker(built: tuple[Path, Path, DefectManifest]) -> None:
    _, out, manifest = built
    marker = json.loads((out / "meta" / COPY_MARKER).read_text())
    assert marker == {"benchmark_copy_id": manifest.dataset_id}


def test_every_episode_is_rewritten_so_none_stands_out(
    built: tuple[Path, Path, DefectManifest],
) -> None:
    # The writer renumbers `index` per LeRobot's rule; rewriting only the injected
    # episodes would make them the only ones renumbered.
    _, out, _ = built
    rows = read_episode_rows(out)
    start = 0
    for row in rows:
        assert row["dataset_from_index"] == start
        start += int(row["length"])


def test_refuses_to_overwrite_an_existing_copy(tmp_path: Path) -> None:
    src = tmp_path / "psi"
    make_dataset(src, count=40, length=6)
    out = tmp_path / "copy"
    out.mkdir()
    with pytest.raises(FileExistsError):
        inject_copy(src, out)
