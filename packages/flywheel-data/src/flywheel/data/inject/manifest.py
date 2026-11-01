"""Defect manifest model, hashing, and access barrier."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DefectRecord:
    target_ref: str
    code: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DefectManifestRecord:
    dataset_id: str
    seed: int
    defects: list[DefectRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "seed": self.seed,
            "defects": [asdict(d) for d in self.defects],
        }

    def compute_sha256(self) -> str:
        serialized = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def save_locked(self, path: Path) -> str:
        """Save manifest and return its SHA-256 hash. Enforce read-only lock."""
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        path.write_text(content, encoding="utf-8")
        h = self.compute_sha256()
        # Save companion hash lock file
        hash_file = path.with_suffix(".sha256")
        hash_file.write_text(h, encoding="utf-8")
        return h

    @classmethod
    def load(cls, path: Path) -> "DefectManifestRecord":
        data = json.loads(path.read_text(encoding="utf-8"))
        defects = [
            DefectRecord(
                target_ref=d["target_ref"],
                code=d["code"],
                parameters=d.get("parameters", {}),
            )
            for d in data.get("defects", [])
        ]
        return cls(
            dataset_id=data["dataset_id"],
            seed=data["seed"],
            defects=defects,
        )


class ManifestLock:
    """Barrier to prevent benchmark evaluation agents from inspecting the answer key."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path

    def verify_integrity(self) -> bool:
        hash_file = self.manifest_path.with_suffix(".sha256")
        if not self.manifest_path.exists() or not hash_file.exists():
            return False
        expected = hash_file.read_text(encoding="utf-8").strip()
        manifest = DefectManifestRecord.load(self.manifest_path)
        return manifest.compute_sha256() == expected

    def can_agent_read(self, caller_role: str) -> bool:
        """Deny reading of the defect manifest if caller is an automated eval agent."""
        if caller_role in ("eval_agent", "qa_agent", "judge_agent"):
            return False
        return True
