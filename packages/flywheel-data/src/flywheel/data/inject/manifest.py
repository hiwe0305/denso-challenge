"""Hashing, sealing and access barrier for the shared DefectManifest contract.

Only the scorer (DA-31) reads the sealed manifest; the agent and the QA checks never
import this module (tests/unit/inject/test_read_barrier.py).
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from flywheel.contracts.artifacts import DefectManifest

MANIFEST_FILENAME = "defect_manifest.json"


def manifest_sha256(manifest: DefectManifest) -> str:
    """Hash the manifest content independently of key order and file formatting."""
    serialized = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def seal_manifest(manifest: DefectManifest, path: Path, copy_roots: Sequence[Path] = ()) -> str:
    """Write the manifest and its companion `.sha256` lock file; return the hash.

    The agent reads the benchmark copies, so the answer must not land inside any of
    `copy_roots`.
    """
    target = path.resolve()
    for root in copy_roots:
        if target.is_relative_to(root.resolve()):
            raise ValueError(f"{path} is inside the benchmark copy {root}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    digest = manifest_sha256(manifest)
    path.with_suffix(".sha256").write_text(digest, encoding="utf-8")
    return digest


def load_manifest(path: Path) -> DefectManifest:
    return DefectManifest.model_validate_json(path.read_text(encoding="utf-8"))


class ManifestLock:
    """Integrity check of a sealed manifest against its `.sha256` lock file."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path

    def verify_integrity(self) -> bool:
        hash_file = self.manifest_path.with_suffix(".sha256")
        if not self.manifest_path.exists() or not hash_file.exists():
            return False
        expected = hash_file.read_text(encoding="utf-8").strip()
        return manifest_sha256(load_manifest(self.manifest_path)) == expected
