"""Path resolution and layout for local store (03 §7.2)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from flywheel.contracts.base import new_ulid

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
# One directory name: ids, table and site names. No leading dot, so neither "."
# nor ".." nor a hidden directory; no separators, spaces or drive letters.
PATH_SEGMENT_REGEX = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")


def get_fw_root() -> Path:
    """Return root directory for flywheel storage, defaulting to ./fwdata."""
    env_root = os.environ.get("FW_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path("./fwdata").resolve()


def _validate_path_segment(value: str, name: str) -> str:
    """Validate that a path segment names one directory inside the store."""
    if not PATH_SEGMENT_REGEX.fullmatch(value) or ".." in value:
        raise ValueError(
            f"Invalid path segment for {name}: {value!r} must be letters, digits, "
            f"'_', '-' or '.', must not start with '.' and must not contain '..'"
        )
    return value


class StorePaths:
    """Store layout under $FW_ROOT using pathlib."""

    def __init__(self, root: Path | str | None = None, site: str = "local") -> None:
        self.root = Path(root).resolve() if root is not None else get_fw_root()
        self.site = _validate_path_segment(site, "site")
        self.site_dir = self.root / "sites" / self.site
        self.objects_dir = self.site_dir / "objects" / "sha256"
        self.catalog_dir = self.site_dir / "catalog"
        self.runs_dir = self.site_dir / "runs"
        self.index_path = self.root / "index" / "fw.duckdb"

    def blob_path(self, sha256_hash: str) -> Path:
        """Return blob file path: objects/sha256/ab/cd/<hash>."""
        # The hash comes from callers of get_blob/has_blob; anything but 64 hex
        # characters could name a path outside the store ("/." resets the root).
        if not SHA256_REGEX.fullmatch(sha256_hash):
            raise ValueError(f"Invalid sha256 hash {sha256_hash!r}: expected 64 lowercase hex")
        ab = sha256_hash[:2]
        cd = sha256_hash[2:4]
        return self.objects_dir / ab / cd / sha256_hash

    def table_dir(self, table_name: str) -> Path:
        """Return catalog table directory: catalog/<bảng>/."""
        _validate_path_segment(table_name, "table_name")
        return self.catalog_dir / table_name

    def new_part_path(self, table_name: str) -> Path:
        """Return a new partition file path: catalog/<bảng>/part-<ulid>.jsonl."""
        return self.table_dir(table_name) / f"part-{new_ulid()}.jsonl"

    def job_dir(self, run_plan_id: str, job_id: str) -> Path:
        """Return job run directory: runs/<run_plan_id>/<job_id>/."""
        _validate_path_segment(run_plan_id, "run_plan_id")
        _validate_path_segment(job_id, "job_id")
        path = self.runs_dir / run_plan_id / job_id
        if not path.resolve().is_relative_to(self.runs_dir.resolve()):
            raise ValueError(
                f"Path escape detected for run_plan_id='{run_plan_id}', job_id='{job_id}'"
            )
        return path

    def job_ledger_path(self, run_plan_id: str, job_id: str) -> Path:
        """Return job cost ledger path: runs/<run_plan_id>/<job_id>/ledger.jsonl."""
        return self.job_dir(run_plan_id, job_id) / "ledger.jsonl"

    def ensure_dirs(self) -> None:
        """Ensure standard directories exist on disk."""
        self.site_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
