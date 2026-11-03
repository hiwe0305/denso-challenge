"""The answer key stays out of reach of the agent and the QA checks (AC 3).

The agent under test (DA-20, flywheel.eval.agentqa) and the data checks (flywheel.data
outside inject/) must never load the DefectManifest; only the scorer
(flywheel.eval.agentqa.bench, DA-31) reads it, after both have run.
"""

from pathlib import Path

import pytest
from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.data.inject.manifest import MANIFEST_FILENAME, seal_manifest

REPO = Path(__file__).resolve().parents[5]
TOKENS = ("DefectManifest", "defect_manifest", "load_manifest", "inject.manifest")

# (package root, sub-paths allowed to touch the answer key)
GUARDED = (
    (REPO / "packages/flywheel-eval/src/flywheel/eval/agentqa", ("bench",)),
    (REPO / "packages/flywheel-data/src/flywheel/data", ("inject", "cli.py", "api.py")),
)


def references(root: Path, allowed: tuple[str, ...]) -> list[str]:
    """Python files under `root`, outside `allowed`, that mention the answer key."""
    hits = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if rel.parts[0] in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        hits += [f"{path}: {t}" for t in TOKENS if t in text]
    return hits


def test_agent_and_checks_never_reference_the_answer_key() -> None:
    for root, allowed in GUARDED:
        assert root.is_dir(), root
        assert references(root, allowed) == []


def test_the_scan_catches_a_planted_reference(tmp_path: Path) -> None:
    (tmp_path / "qa").mkdir()
    (tmp_path / "qa" / "peek.py").write_text("from flywheel.data.inject import load_manifest\n")
    (tmp_path / "inject").mkdir()
    (tmp_path / "inject" / "ok.py").write_text("DefectManifest\n")
    assert len(references(tmp_path, ("inject",))) == 1


def _manifest() -> DefectManifest:
    return DefectManifest(
        dataset_id="bench-000000000001",
        seed=1,
        defects=[Defect(target_ref="ep_1", code="D1", parameters={"kind": "nan_values"})],
    )


def test_seal_refuses_to_write_inside_a_benchmark_copy(tmp_path: Path) -> None:
    copy_root = tmp_path / "bench-000000000001"
    with pytest.raises(ValueError, match="inside the benchmark copy"):
        seal_manifest(_manifest(), copy_root / "meta" / MANIFEST_FILENAME, copy_roots=[copy_root])


def test_seal_writes_the_answer_next_to_its_hash_outside_the_copy(tmp_path: Path) -> None:
    answers = tmp_path / "answers" / "bench-000000000001"
    digest = seal_manifest(
        _manifest(), answers / MANIFEST_FILENAME, copy_roots=[tmp_path / "bench-000000000001"]
    )
    assert MANIFEST_FILENAME == "defect_manifest.json"
    assert (answers / "defect_manifest.sha256").read_text(encoding="utf-8") == digest
