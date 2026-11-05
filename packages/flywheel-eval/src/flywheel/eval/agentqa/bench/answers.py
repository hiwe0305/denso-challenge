"""The sealed answer key of a benchmark copy (design 27/10/2026 section 9.2).

DA-27 seals one `DefectManifest` per copy at `answers/<dataset_id>/defect_manifest.json`
with its hash in `defect_manifest.sha256`, outside every copy. Only this package
opens it, and only through `BenchSession.open_answers`, once both layers have run
on every copy (DA-31 AC 1). The clean copy is the one whose manifest has no defect.

The hash is the one DA-27 writes (`flywheel.data.inject.manifest.manifest_sha256`):
sha256 of the manifest dumped as JSON with sorted keys. It is computed again here
rather than imported, since a lane does not import another (03 section 7.3).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from flywheel.contracts.artifacts import DefectManifest

MANIFEST = "defect_manifest.json"
LOCK = "defect_manifest.sha256"


class AnswerKeyError(ValueError):
    """An answer key that is missing, ambiguous or does not match its seal."""


def manifest_sha256(manifest: DefectManifest) -> str:
    """The seal of a manifest, independent of key order and file formatting."""
    text = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_answer_dir(answer_roots: Sequence[Path], dataset_id: str) -> Path:
    """The one `answers/<dataset_id>/` dir among `answer_roots` (data and log copies
    are sealed under different roots)."""
    found = [root / dataset_id for root in answer_roots if (root / dataset_id / MANIFEST).is_file()]
    if len(found) != 1:
        where = ", ".join(str(r) for r in answer_roots) or "no root"
        raise AnswerKeyError(f"{len(found)} answer keys for {dataset_id} under {where}")
    return found[0]


def open_sealed(answer_dir: Path, dataset_id: str) -> DefectManifest:
    """Read and verify one sealed manifest; refuse it if its seal or id is wrong."""
    path, lock = answer_dir / MANIFEST, answer_dir / LOCK
    if not lock.is_file():
        raise AnswerKeyError(f"{answer_dir}: {MANIFEST} has no {LOCK}; the key is not sealed")
    manifest = DefectManifest.model_validate_json(path.read_text(encoding="utf-8"))
    expected = lock.read_text(encoding="utf-8").strip()
    actual = manifest_sha256(manifest)
    if actual != expected:
        raise AnswerKeyError(f"{path}: sha256 {actual} does not match its seal {expected}")
    if manifest.dataset_id != dataset_id:
        raise AnswerKeyError(f"{path}: manifest of {manifest.dataset_id}, not {dataset_id}")
    return manifest
