"""Console paths and path guards. Every other module reads paths through ``active()``."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class PathDenied(ValueError):
    """Raised when a path leaves the allowed roots or touches protected data."""


@dataclass(frozen=True)
class ConsolePaths:
    repo: Path
    fw_root: Path

    @property
    def console_dir(self) -> Path:
        return self.fw_root / "console"

    @property
    def index(self) -> Path:
        return self.console_dir / "index"

    @property
    def cache(self) -> Path:
        return self.console_dir / "cache"

    @property
    def jobs(self) -> Path:
        return self.console_dir / "jobs"

    @property
    def chat(self) -> Path:
        return self.console_dir / "chat"

    @property
    def config(self) -> Path:
        return self.console_dir / "config"

    @property
    def exports(self) -> Path:
        return self.console_dir / "exports"

    @property
    def uploads(self) -> Path:
        return self.console_dir / "uploads"

    @property
    def web(self) -> Path:
        return Path(__file__).parent / "web"

    @property
    def seed(self) -> Path:
        return Path(__file__).parent / "seed"

    @classmethod
    def from_env(cls, repo: Path | None = None) -> ConsolePaths:
        root = repo if repo is not None else _find_repo(Path.cwd())
        env = os.environ.get("FW_ROOT")
        return cls(repo=root, fw_root=Path(env) if env else root / "fwdata")


def _is_workspace(pyproject: Path) -> bool:
    try:
        return "[tool.uv.workspace]" in pyproject.read_text(encoding="utf-8")
    except OSError:
        return False


def _find_repo(start: Path) -> Path:
    start = start.resolve()
    for parent in (start, *start.parents):
        pyproject = parent / "pyproject.toml"
        if pyproject.is_file() and _is_workspace(pyproject):
            return parent
    return start


_active: ConsolePaths | None = None


def set_active(p: ConsolePaths) -> None:
    global _active
    _active = p


def active() -> ConsolePaths:
    global _active
    if _active is None:
        _active = ConsolePaths.from_env()
    return _active


def guard(p: Path | str, roots: Sequence[Path]) -> Path:
    """Resolve ``p`` (following symlinks) and require it to sit under one of ``roots``."""
    resolved = Path(p).resolve()
    for part in resolved.parts:
        if part == "vault" or "holdout" in part.lower():
            raise PathDenied(f"protected path: {p}")
    for root in roots:
        if resolved.is_relative_to(root.resolve()):
            return resolved
    raise PathDenied(f"outside allowed roots: {p}")


def deid_only(p: Path) -> Path:
    if not p.name.endswith(".deid.mp4"):
        raise PathDenied(f"not a de-identified video: {p}")
    return p
