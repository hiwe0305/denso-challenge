"""What build_release writes is what other lanes read (seam 3-ReleaseManifest, 03 section 7.3).

Châu and the Psi0 export read `release_manifest.json` as the v0 `ReleaseManifest`;
the catalog reads `release.json` as the `Release` entity. Both parse back to the
same record, and the shared testkit example has the shape the writer writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.contracts.entities import Release
from flywheel.contracts.v0 import ReleaseManifest
from flywheel.data.release.build import build_release

ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
SPLITS = ROOT / "configs/splits/default.yaml"


def test_the_release_files_parse_as_their_contracts(tmp_path: Path) -> None:
    episode = Episode.model_validate_json((FIXTURES / "Episode.json").read_text())
    report = QAReport.model_validate_json((FIXTURES / "QAReport.json").read_text())
    manifest = build_release([episode], [report], SPLITS, tmp_path / "rel")

    written = (tmp_path / "rel/release_manifest.json").read_text()
    assert ReleaseManifest.model_validate_json(written) == manifest
    release = Release.model_validate_json((tmp_path / "rel/release.json").read_text())
    assert release.id == manifest.release_id and release.status == "frozen"
    assert Release.model_validate_json(release.to_canonical_json()) == release

    example = json.loads((FIXTURES / "ReleaseManifest.json").read_text())
    assert set(example) == set(json.loads(written))
    ReleaseManifest.model_validate(example)
