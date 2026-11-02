"""Content-addressed blob storage with SHA-256 (03 §7.2, AC 5)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from flywheel.store.paths import StorePaths


def put_blob(data: bytes, paths: StorePaths | None = None) -> str:
    """Store immutable bytes under objects/sha256/ab/cd/<hash> and return the 64-hex hash."""
    if paths is None:
        paths = StorePaths()

    sha256 = hashlib.sha256(data).hexdigest()
    blob_file = paths.blob_path(sha256)

    if blob_file.is_file():
        return sha256

    blob_file.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically via temporary file in same directory
    temp_file = blob_file.with_name(f".tmp-{blob_file.name}")
    try:
        temp_file.write_bytes(data)
        temp_file.replace(blob_file)
    except Exception:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
        raise

    return sha256


def get_blob(sha256: str, paths: StorePaths | None = None) -> bytes:
    """Read blob bytes by SHA-256 hash."""
    if paths is None:
        paths = StorePaths()

    blob_file = paths.blob_path(sha256)
    if not blob_file.is_file():
        raise FileNotFoundError(f"Blob with hash {sha256} not found at {blob_file}")

    data = blob_file.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != sha256:
        raise ValueError(f"Blob integrity check failed: expected {sha256}, got {actual_hash}")

    return data


def has_blob(sha256: str, paths: StorePaths | None = None) -> bool:
    """Check if a blob exists in storage."""
    if paths is None:
        paths = StorePaths()
    return paths.blob_path(sha256).is_file()
