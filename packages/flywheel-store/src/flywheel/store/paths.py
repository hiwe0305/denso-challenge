"""Path resolution and layout for local store (03 §7.2)."""

from __future__ import annotations

import os
from pathlib import Path

from flywheel.contracts.base import new_ulid


def get_fw_root() -> Path:
    """Return root directory for flywheel storage, defaulting to ./fwdata."""
    env_root = os.environ.get("FW_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path("./fwdata").resolve()


class StorePaths:
    """Store layout under $FW_ROOT using pathlib."""

    def __init__(self, root: Path | str | None = None, site: str = "local") -> None:
        self.root = Path(root).resolve() if root is not None else get_fw_root()
        self.site = site
        self.site_dir = self.root / "sites" / self.site
        self.objects_dir = self.site_dir / "objects" / "sha256"
        self.catalog_dir = self.site_dir / "catalog"
        self.runs_dir = self.site_dir / "runs"
        self.index_path = self.root / "index" / "fw.duckdb"

    def blob_path(self, sha256_hash: str) -> Path:
        """Return blob file path: objects/sha256/ab/cd/<hash>."""
        if len(sha256_hash) < 4:
            raise ValueError(f"Invalid sha256 hash length: {len(sha256_hash)}")
        ab = sha256_hash[:2]
        cd = sha256_hash[2:4]
        return self.objects_dir / ab / cd / sha256_hash

    def table_dir(self, table_name: str) -> Path:
        """Return catalog table directory: catalog/<bảng>/."""
        return self.catalog_dir / table_name

    def new_part_path(self, table_name: str) -> Path:
        """Return a new partition file path: catalog/<bảng>/part-<ulid>.jsonl."""
        return self.table_dir(table_name) / f"part-{new_ulid()}.jsonl"

    def job_dir(self, run_plan_id: str, job_id: str) -> Path:
        """Return job run directory: runs/<run_plan_id>/<job_id>/."""
        return self.runs_dir / run_plan_id / job_id

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
