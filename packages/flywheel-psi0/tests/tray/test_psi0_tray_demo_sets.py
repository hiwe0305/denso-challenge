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
    apply_qa,
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


# DA-03 QA rejects left out of the demo sets (decision of 5/11/2026).
REJECTED = {3: "replay_kinematic (D7): joint_mapping", 7: "replay_kinematic (D7): joint_limit"}


def _write_qa_work(work: Path, release: Path, episodes: list[ReleaseEpisode]) -> None:
    """A `fw data ingest` work directory of `release` after `fw data qa`, as DA-03 writes it."""
    (work / "qa").mkdir(parents=True)
    export_sha = hashlib.sha256((release / EXPORT_META).read_bytes()).hexdigest()
    (work / "source.json").write_text(json.dumps({"files": {EXPORT_META: export_sha}}))
    index = {f"ep_{e.episode_index:04d}": e.episode_index for e in episodes}
    (work / "episode_index.json").write_text(json.dumps(index))
    rows = [
        {
            "episode_id": episode_id,
            "threshold_version": "qa-1@test",
            "decision": "reject" if i in REJECTED else "pass",
            "reasons": [REJECTED[i]] if i in REJECTED else [],
        }
        for episode_id, i in index.items()
    ]
    (work / "qa" / "reports.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def release(tmp_path: Path) -> tuple[Path, Path, list[ReleaseEpisode]]:
    episodes = _episodes()
    root = tmp_path / "tray_s1_test"
    _write_release(root, episodes)
    work = tmp_path / "work"
    _write_qa_work(work, root, episodes)
    return root, work, episodes


def test_rejects_are_left_out_and_listed(release: tuple[Path, Path, list[ReleaseEpisode]]) -> None:
    root, work, episodes = release
    kept, pin = apply_qa(episodes, work, root)
    rejected_seeds = {episodes[i].seed for i in REJECTED}
    assert {e.seed for e in kept} == {e.seed for e in episodes} - rejected_seeds
    assert [x.seed for x in pin.excluded] == sorted(rejected_seeds)
    assert pin.excluded[0].reasons == [REJECTED[3]] and pin.threshold_version == "qa-1@test"
    reports = (work / "qa" / "reports.jsonl").read_bytes()
    assert pin.reports_sha256 == hashlib.sha256(reports).hexdigest()


def test_dropping_a_reject_keeps_the_order_of_the_rest(
    release: tuple[Path, Path, list[ReleaseEpisode]],
) -> None:
    root, work, episodes = release
    kept, _ = apply_qa(episodes, work, root)
    full = [s for s in rank("h", episodes) if s in {e.seed for e in kept}]
    assert rank("h", kept) == full


def test_a_missing_report_fails_closed(release: tuple[Path, Path, list[ReleaseEpisode]]) -> None:
    root, work, episodes = release
    reports = work / "qa" / "reports.jsonl"
    reports.write_text("".join(reports.read_text().splitlines(keepends=True)[1:]))
    with pytest.raises(ValueError, match="no DA-03 QA report"):
        apply_qa(episodes, work, root)


def test_qa_of_another_export_is_refused(
    release: tuple[Path, Path, list[ReleaseEpisode]],
) -> None:
    root, work, episodes = release
    (work / "source.json").write_text(json.dumps({"files": {EXPORT_META: "0" * 64}}))
    with pytest.raises(ValueError, match="another export"):
        apply_qa(episodes, work, root)


def test_mixed_qa_versions_are_refused(release: tuple[Path, Path, list[ReleaseEpisode]]) -> None:
    root, work, episodes = release
    reports = work / "qa" / "reports.jsonl"
    rows = [json.loads(line) for line in reports.read_text().splitlines()]
    rows[0]["threshold_version"] = "qa-0@old"
    reports.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="threshold versions"):
        apply_qa(episodes, work, root)


def test_cli_records_the_qa_exclusions(
    tmp_path: Path, release: tuple[Path, Path, list[ReleaseEpisode]]
) -> None:
    root, work, episodes = release
    out = tmp_path / "demo_sets.json"
    argv = ["--release", str(root), "--qa-work", str(work), "--size", "A=80", "--size", "C=40"]
    assert main([*argv, "--out", str(out)]) == 0
    sets = DemoSets.model_validate_json(out.read_text())
    rejected = {episodes[i].seed for i in REJECTED}
    assert sets.qa is not None and {x.seed for x in sets.qa.excluded} == rejected
    assert not rejected & set(sets.sets["A"].seeds)
    assert main([*argv, "--check", str(out)]) == 0
    release_hash, all_episodes = read_release(root)
    assert sets.sets["A"] != nested_sets("r", release_hash, all_episodes, {"A": 80}).sets["A"]
