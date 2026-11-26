"""Builders of the MCP tests: copies of the round tests' pack declared again.

A plain module (not a conftest), as `helpers_round`: mypy refuses two `conftest` modules.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from flywheel.eval.agentqa.round.pack import build_pack, write_pack

REPO = Path(__file__).resolve().parents[6]  # the tools read configs/ from the repo root
Edit = Callable[[dict[str, Any]], None]


def repacked(pack: Path, name: str, edit: Edit, files: dict[str, str] | None = None) -> Path:
    """A copy of `pack`'s files (plus `files`, ref -> text), declared again after `edit`."""
    root = pack.parent.parent / name
    shutil.copytree(pack.parent, root, ignore=shutil.ignore_patterns("pack.json"))
    for ref, text in (files or {}).items():
        (root / ref).write_text(text)
    decl = root / "round.yaml"
    declared = yaml.safe_load(decl.read_text())
    edit(declared)
    decl.write_text(yaml.safe_dump(declared))
    return write_pack(build_pack(decl), root)


def internal(declared: dict[str, Any]) -> None:
    declared["data_class"] = "internal"


def unlinked(declared: dict[str, Any]) -> None:
    declared["links"] = []  # public as declared, but no source record vouches for the scores


NOTES = "notes.txt"


def with_notes(declared: dict[str, Any]) -> None:
    """Declare `notes.txt` (write it with `files`) as a kind admit has no contract for."""
    declared["entries"].append({"path": NOTES, "kind": "notes"})
