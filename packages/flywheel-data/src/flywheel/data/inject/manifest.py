"""Hashing, sealing and access barrier for the shared DefectManifest contract."""

import hashlib
import json
from pathlib import Path

from flywheel.contracts.artifacts import DefectManifest


def manifest_sha256(manifest: DefectManifest) -> str:
    """Hash the manifest content independently of key order and file formatting."""
    serialized = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def seal_manifest(manifest: DefectManifest, path: Path) -> str:
    """Write the manifest and its companion `.sha256` lock file; return the hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    digest = manifest_sha256(manifest)
    path.with_suffix(".sha256").write_text(digest, encoding="utf-8")
    return digest


def load_manifest(path: Path) -> DefectManifest:
    return DefectManifest.model_validate_json(path.read_text(encoding="utf-8"))


class ManifestLock:
    """Barrier to prevent benchmark evaluation agents from inspecting the answer key."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path

    def verify_integrity(self) -> bool:
        hash_file = self.manifest_path.with_suffix(".sha256")
        if not self.manifest_path.exists() or not hash_file.exists():
            return False
        expected = hash_file.read_text(encoding="utf-8").strip()
        return manifest_sha256(load_manifest(self.manifest_path)) == expected

    def can_agent_read(self, caller_role: str) -> bool:
        """Deny reading of the defect manifest if caller is an automated eval agent."""
        if caller_role in ("eval_agent", "qa_agent", "judge_agent"):
            return False
        return True
