"""Release manifest and content hash (DA-33 Task 9); no simulator."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from flywheel_simple.tray.release import MANIFEST, build_manifest, verify_manifest, write_manifest


def _release(root: Path) -> Path:
    files = {
        "meta/info.json": b'{"fps": 50}',
        "data/chunk-000/episode_000000.parquet": b"PAR1" + bytes(range(64)),
        "videos/chunk-000/egocentric/episode_000000.mp4": b"\x00\x00\x00\x18ftyp",
    }
    for rel, content in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(content)
    return root


def test_same_files_give_the_same_hash(tmp_path: Path) -> None:
    a = _release(tmp_path / "a")
    b = _release(tmp_path / "b")
    assert build_manifest(a) == build_manifest(b)
    assert write_manifest(a) == build_manifest(b)["release_hash"]


def test_one_changed_byte_changes_the_hash(tmp_path: Path) -> None:
    root = _release(tmp_path / "r")
    before = write_manifest(root)
    parquet = root / "data/chunk-000/episode_000000.parquet"
    data = bytearray(parquet.read_bytes())
    data[10] ^= 1
    parquet.write_bytes(bytes(data))
    assert build_manifest(root)["release_hash"] != before
    assert not verify_manifest(root)


def test_manifest_lists_every_file_but_itself(tmp_path: Path) -> None:
    root = _release(tmp_path / "r")
    write_manifest(root)
    listed = [f["path"] for f in json.loads((root / MANIFEST).read_text())["files"]]
    assert listed == sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        and p.name != MANIFEST
    )
    assert len(listed) == 3 and verify_manifest(root)


def test_hash_does_not_depend_on_the_directory_name(tmp_path: Path) -> None:
    root = _release(tmp_path / "staging")
    h = write_manifest(root)
    moved = Path(shutil.move(str(root), tmp_path / f"tray_s1_{h[:12]}"))
    assert verify_manifest(moved) and build_manifest(moved)["release_hash"] == h
