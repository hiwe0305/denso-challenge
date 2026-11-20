"""Step B0, pack: freeze what a round gives the agent into `pack.json`.

An engineer writes `round.yaml` next to the artifacts: the task, each file with its
kind, data class and subject (run, checkpoint, job, release), and the links between
them. `build_pack` checks every file is there, hashes it and writes the manifest. The
agent never guesses what a file is from its name, and never infers which checkpoint a
run evaluated: both are declared here (architecture 20/11 section 6, B0).

    task_id: tray
    declared_by: hieu
    data_class: public            # default for entries that give none; absent = restricted
    entries:
      - {path: C_70/scores.jsonl, kind: scores, subject: {run: C_70, checkpoint: ckpt-1}}
      - {path: release/sources.jsonl, kind: sources}
    links:
      - {source: C_70/scores.jsonl, target: release/sources.jsonl, relation: data_of}

Paths are relative to the directory of `round.yaml`, which is the pack root, and stay
inside it. A pack is immutable: change a file and it is a new pack with a new id.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from flywheel.eval.agentqa.inputs import forbidden_part
from flywheel.eval.agentqa.round.records import DataClass, Pack, PackEntry, PackLink, Record
from pydantic import Field, ValidationError

PACK_FILE = "pack.json"
# Besides vault/ and answers/ (inputs.FORBIDDEN_PARTS): the team's written diagnoses
# live under docs/ and are the answers of the case bench (design 19/11 section 11.2).
FORBIDDEN_IN_PACK = ("docs",)


class PackRefused(ValueError):
    """The declaration or the pack cannot be used at all; nothing is read further."""


class DeclaredEntry(Record):
    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    data_class: DataClass | None = None
    subject: dict[str, str] = Field(default_factory=dict)


class Declaration(Record):
    """`round.yaml`, as the engineer wrote it."""

    task_id: str = Field(min_length=1)
    declared_by: str = Field(min_length=1)
    data_class: DataClass | None = None
    entries: list[DeclaredEntry] = Field(min_length=1)
    links: list[PackLink] = Field(default_factory=list)


def refused_path(root: Path, ref: str) -> str | None:
    """Why `ref` may not be part of a pack rooted at `root`, or None.

    Checked as written and with links resolved: a link out of the root, or into a
    forbidden directory, is refused like the directory itself.
    """
    pure = PurePosixPath(ref)
    if pure.is_absolute() or ".." in pure.parts:
        return "the path must be relative to the pack root and stay inside it"
    path = root / pure
    part = forbidden_part(path)
    if part is not None:
        return f"the agent does not read {part}/"
    try:
        inside = path.resolve().relative_to(root.resolve())
    except ValueError:
        return "the path leaves the pack root through a link"
    for parts in (pure.parts, inside.parts):
        for name in FORBIDDEN_IN_PACK:
            if name in (p.lower() for p in parts):
                return f"the agent does not read {name}/"
    return None


def read_declaration(path: Path) -> Declaration:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Declaration.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise PackRefused(f"{path}: {error}") from error


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_pack(declaration: Path, now: datetime | None = None) -> Pack:
    """Read `round.yaml`, check and hash every file it names, return the manifest."""
    decl = read_declaration(declaration)
    root = declaration.parent
    entries: list[PackEntry] = []
    for item in decl.entries:
        ref = PurePosixPath(item.path).as_posix()
        reason = refused_path(root, ref)
        if reason is not None:
            raise PackRefused(f"{ref}: {reason}")
        path = root / ref
        if not path.is_file():
            raise PackRefused(f"{ref}: no such file under {root}")
        entries.append(PackEntry(
            ref=ref, kind=item.kind, sha256=sha256_of(path), bytes=path.stat().st_size,
            # N2: a file nobody classified is restricted, the default of the contracts
            data_class=item.data_class or decl.data_class or "restricted",
            subject=item.subject,
        ))
    refs = [e.ref for e in entries]
    if len(set(refs)) != len(refs):
        raise PackRefused("an entry is declared twice")
    for link in decl.links:
        for end in (link.source, link.target):
            if end not in refs:
                raise PackRefused(f"link {link.relation}: {end} is not an entry")
    body = json.dumps([e.model_dump() for e in entries] + [li.model_dump() for li in decl.links],
                      sort_keys=True)
    pack_id = "pack_" + hashlib.sha256((decl.task_id + body).encode()).hexdigest()[:16]
    return Pack(pack_id=pack_id, task_id=decl.task_id, created_at=now or datetime.now(timezone.utc),
                declared_by=decl.declared_by, entries=entries, links=decl.links)


def write_pack(pack: Pack, root: Path) -> Path:
    out = root / PACK_FILE
    if out.exists():
        raise PackRefused(f"{out} exists: a pack is immutable, declare the round in a new "
                          "directory or remove the old manifest yourself")
    out.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return out


def read_pack(path: Path) -> Pack:
    try:
        return Pack.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise PackRefused(f"{path}: {error}") from error
