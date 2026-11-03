"""Unit tests for content-addressed blob storage (AC 5)."""

import hashlib
from pathlib import Path

import pytest
from flywheel.store.blobs import get_blob, has_blob, put_blob
from flywheel.store.paths import StorePaths


def test_put_and_get_blob(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    content = b"hello physical intelligence humanoid flywheel"
    expected_hash = hashlib.sha256(content).hexdigest()

    digest = put_blob(content, paths=paths)
    assert digest == expected_hash
    assert has_blob(digest, paths=paths)

    retrieved = get_blob(digest, paths=paths)
    assert retrieved == content

    # Verify physical file location: objects/sha256/ab/cd/<hash>
    expected_dir = tmp_path / "sites" / "local" / "objects" / "sha256" / digest[:2] / digest[2:4]
    expected_path = expected_dir / digest
    assert expected_path.is_file()
    assert expected_path.read_bytes() == content


def test_blob_idempotence(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    content = b"idempotent content"
    digest1 = put_blob(content, paths=paths)
    digest2 = put_blob(content, paths=paths)
    assert digest1 == digest2


def test_get_nonexistent_blob_raises(tmp_path: Path) -> None:
    paths = StorePaths(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        get_blob("a" * 64, paths=paths)


@pytest.mark.parametrize(
    "bad_hash",
    [
        "../../../../etc/passwd",
        "/./" + "a" * 61,
        "ab/../../" + "0" * 55,
        "A" * 64,
        "a" * 63,
        "",
    ],
)
def test_blob_lookup_rejects_anything_but_a_sha256(tmp_path: Path, bad_hash: str) -> None:
    """PO review 3/11 item 5: a hash from the caller cannot reach a file outside the store."""
    paths = StorePaths(root=tmp_path)
    with pytest.raises(ValueError, match="sha256"):
        paths.blob_path(bad_hash)
    with pytest.raises(ValueError, match="sha256"):
        has_blob(bad_hash, paths=paths)
    with pytest.raises(ValueError, match="sha256"):
        get_blob(bad_hash, paths=paths)
