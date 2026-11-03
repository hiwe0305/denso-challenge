"""Content hash of a tray release directory (DA-33 Task 9, AC 4).

The manifest lists every file under the release root (posix path relative to
the root, sha256, size in bytes), sorted by path; `release_hash` is the sha256
of that list as canonical JSON. The manifest file itself is not listed, so
writing it does not change the hash, and any changed byte in any file does.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST = "release_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(release_root: Path) -> dict[str, Any]:
    paths = {p.relative_to(release_root).as_posix(): p for p in release_root.rglob("*")}
    files = [
        {"path": rel, "sha256": _sha256(p), "size": p.stat().st_size}
        for rel, p in sorted(paths.items())
        if p.is_file() and rel != MANIFEST
    ]
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"release_hash": hashlib.sha256(canonical).hexdigest(), "files": files}


def write_manifest(release_root: Path) -> str:
    """Write release_root/release_manifest.json; returns release_hash."""
    manifest = build_manifest(release_root)
    (release_root / MANIFEST).write_text(json.dumps(manifest, indent=1) + "\n")
    return str(manifest["release_hash"])


def verify_manifest(release_root: Path) -> bool:
    """True when the files under release_root still match its manifest."""
    recorded = json.loads((release_root / MANIFEST).read_text())
    return bool(build_manifest(release_root) == recorded)
