"""Unit tests for StorePaths and store directory layout (AC 5)."""

from pathlib import Path

import pytest
from flywheel.store.paths import StorePaths, get_fw_root


def test_default_fw_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FW_ROOT", raising=False)
    assert get_fw_root() == Path("./fwdata").resolve()

    monkeypatch.setenv("FW_ROOT", str(tmp_path / "custom"))
    assert get_fw_root() == (tmp_path / "custom").resolve()


def test_store_paths_layout(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path, site="local")
    assert paths.site_dir == tmp_path / "sites" / "local"
    assert paths.objects_dir == tmp_path / "sites" / "local" / "objects" / "sha256"
    assert paths.catalog_dir == tmp_path / "sites" / "local" / "catalog"
    assert paths.runs_dir == tmp_path / "sites" / "local" / "runs"
    assert paths.index_path == tmp_path / "index" / "fw.duckdb"

    sha = "abcdef0123456789" + "0" * 48
    expected_blob = paths.objects_dir / "ab" / "cd" / sha
    assert paths.blob_path(sha) == expected_blob

    expected_table = paths.catalog_dir / "episode"
    assert paths.table_dir("episode") == expected_table

    part_path = paths.new_part_path("episode")
    assert part_path.parent == expected_table
    assert part_path.name.startswith("part-")
    assert part_path.name.endswith(".jsonl")

    expected_job = paths.runs_dir / "rp_1" / "job_1"
    assert paths.job_dir("rp_1", "job_1") == expected_job
    assert paths.job_ledger_path("rp_1", "job_1") == expected_job / "ledger.jsonl"


def test_paths_rejects_path_traversal(tmp_path: Path) -> None:
    """Feedback item 3: Prevent .. and / in job_dir and table_dir."""
    paths = StorePaths(root=tmp_path)

    with pytest.raises(ValueError, match="Invalid path segment"):
        paths.job_dir("../../../escape", "job_1")

    with pytest.raises(ValueError, match="Invalid path segment"):
        paths.job_dir("rp_1", "../escape")

    with pytest.raises(ValueError, match="Invalid path segment"):
        paths.job_dir("nested/slash", "job_1")

    with pytest.raises(ValueError, match="Invalid path segment"):
        paths.table_dir("../escape")
