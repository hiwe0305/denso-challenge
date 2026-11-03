"""Nested demo sets of the tray experiment on CPU (DA-34 AC 1)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from flywheel_psi0.tray.demo_sets import (
    EXPORT_META,
    MANIFEST,
    DemoSets,
    ReleaseEpisode,
    main,
    nested_sets,
    rank,
    read_release,
    set_hash,
)

HASH = "0d84cc87b1e5e55db91cd13ca40bf07d24a560b83a4c8ebbd2111952dcdc18d6"
SIZES = {"A": 80, "C": 40}


def _episodes(n: int = 102, first_seed: int = 1000) -> list[ReleaseEpisode]:
    # Seeds with gaps, like a release that dropped its failed attempts.
    return [ReleaseEpisode(episode_index=i, seed=first_seed + i + i // 4) for i in range(n)]


def _write_release(root: Path, episodes: list[ReleaseEpisode]) -> str:
    """A release directory laid out like flywheel_simple.tray.release writes it."""
    (root / "meta").mkdir(parents=True)
    rows = [e.model_dump() for e in episodes]
    (root / EXPORT_META).write_text(json.dumps({"episodes": rows}, indent=2))
    (root / "data.bin").write_bytes(b"frames")
    files = [
        {
            "path": p.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "size": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    release_hash = hashlib.sha256(canonical).hexdigest()
    (root / MANIFEST).write_text(json.dumps({"release_hash": release_hash, "files": files}))
    return release_hash


def test_same_input_gives_same_sets_and_hashes() -> None:
    first = nested_sets("r", HASH, _episodes(), SIZES)
    second = nested_sets("r", HASH, _episodes(), SIZES)
    assert first == second
    assert first.sets["A"].set_hash == second.sets["A"].set_hash


def test_small_set_is_inside_the_large_one() -> None:
    sets = nested_sets("r", HASH, _episodes(), SIZES).sets
    assert len(sets["A"].seeds) == 80 and len(sets["C"].seeds) == 40
    assert set(sets["C"].seeds) < set(sets["A"].seeds)
    assert set(sets["C"].episode_indices) < set(sets["A"].episode_indices)


def test_input_order_does_not_matter() -> None:
    episodes = _episodes()
    assert nested_sets("r", HASH, episodes, SIZES) == nested_sets(
        "r", HASH, list(reversed(episodes)), SIZES
    )


def test_another_release_or_salt_gives_another_draw() -> None:
    base = nested_sets("r", HASH, _episodes(), SIZES).sets["C"]
    other_release = nested_sets("r", "f" * 64, _episodes(), SIZES).sets["C"]
    other_salt = nested_sets("r", HASH, _episodes(), SIZES, salt="other").sets["C"]
    assert other_release.seeds != base.seeds and other_release.set_hash != base.set_hash
    assert other_salt.seeds != base.seeds


def test_hash_names_the_content_not_the_draw() -> None:
    sets = nested_sets("r", HASH, _episodes(), SIZES).sets
    assert sets["C"].set_hash == set_hash(HASH, list(reversed(sets["C"].seeds)))
    assert sets["C"].set_hash != set_hash(HASH, sets["C"].seeds[1:])


def test_draw_is_not_the_first_seeds() -> None:
    # The release's seeds run in shard order; taking a prefix of them is not a random set.
    seeds = sorted(e.seed for e in _episodes())
    assert nested_sets("r", HASH, _episodes(), SIZES).sets["C"].seeds != seeds[:40]


def test_rejects_duplicate_seed_and_oversized_set() -> None:
    episodes = _episodes(3)
    with pytest.raises(ValueError, match="share a seed"):
        rank(HASH, [*episodes, ReleaseEpisode(episode_index=9, seed=episodes[0].seed)])
    with pytest.raises(ValueError, match="3 episodes"):
        nested_sets("r", HASH, episodes, {"A": 4})


def test_read_release_checks_the_manifest(tmp_path: Path) -> None:
    root = tmp_path / "tray_s1_test"
    release_hash = _write_release(root, _episodes())
    got_hash, episodes = read_release(root)
    assert got_hash == release_hash and episodes == _episodes()

    (root / EXPORT_META).write_text(json.dumps({"episodes": []}))
    with pytest.raises(ValueError, match="not the file the manifest lists"):
        read_release(root)


def test_read_release_rejects_an_edited_file_list(tmp_path: Path) -> None:
    root = tmp_path / "tray_s1_test"
    _write_release(root, _episodes())
    manifest = json.loads((root / MANIFEST).read_text())
    manifest["files"] = manifest["files"][:1]
    (root / MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="does not hash"):
        read_release(root)


def test_cli_writes_then_checks(tmp_path: Path) -> None:
    root = tmp_path / "tray_s1_test"
    release_hash = _write_release(root, _episodes())
    out = tmp_path / "demo_sets.json"
    argv = ["--release", str(root), "--size", "A=80", "--size", "C=40"]
    assert main([*argv, "--out", str(out)]) == 0
    written = DemoSets.model_validate_json(out.read_text())
    assert written.release_id == "tray_s1_test" and written.release_hash == release_hash
    assert main([*argv, "--check", str(out)]) == 0
    other = ["--release", str(root), "--size", "A=80", "--size", "C=41"]
    assert main([*other, "--check", str(out)]) == 1
