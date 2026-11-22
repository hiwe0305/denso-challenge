"""Dataset cards (``schema: dataset-card/1``) kept next to the data under ``$FW_ROOT/datasets``.

A card describes one release or cut: its status, counts, quality, lineage and where copies
live. Two layouts are read:

* store cards ``datasets/<store>/cards/<id>.yaml``: ``locations[].root`` is the store root,
  the LeRobot folder is ``<root>/<files.release>``;
* loose cards ``datasets/_cards/<id>.yaml``: the root is the release folder
  (``files.release: .``), a cut root (LeRobot folder ``<root>/<files.cut>``) or a plain
  dataset folder.

Laptop roots are written relative to the repo (``fwdata/...``); the leading ``fwdata/`` is
replaced by ``fw_root``. Nothing here writes files.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "dataset-card/1"
CARD_GLOBS = ("datasets/*/cards/*.yaml", "datasets/_cards/*.yaml")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
STATUSES = ("current", "superseded", "benchmark", "archived", "reference")
KINDS = ("egocentric", "teleop", "synthetic_s1", "synthetic_s2", "cut")
DATA_CLASSES = ("public", "internal", "restricted")


class CardError(ValueError):
    """A card file that does not follow ``dataset-card/1``; the message names file and field."""


@dataclass(frozen=True)
class Card:
    """One parsed, validated card and the file it came from."""

    data: dict[str, Any]
    path: Path

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def files(self) -> dict[str, Any]:
        f = self.data.get("files")
        return f if isinstance(f, dict) else {}

    @property
    def parents(self) -> list[str]:
        lin = self.data.get("lineage") or {}
        return list(lin.get("parents") or [])

    def laptop_roots(self, fw_root: Path) -> list[Path]:
        """Roots of the laptop copies (not deleted), as paths under ``fw_root``."""
        out: list[Path] = []
        for loc in self.data["locations"]:
            if loc["host"] != "laptop" or str(loc.get("role") or "").startswith("deleted"):
                continue
            out.append(fw_root / str(loc["root"]).removeprefix("fwdata/"))
        return out

    def lerobot_dirs(self, fw_root: Path) -> list[Path]:
        """LeRobot folders on the laptop: ``root/files.release`` or ``root/files.cut`` when the
        card names one (a store root or cut root is not itself a dataset), else the root."""
        subs = [
            s for s in (self.files.get("release"), self.files.get("cut"))
            if isinstance(s, str) and s and s != "."
        ]  # fmt: skip
        out: list[Path] = []
        for root in self.laptop_roots(fw_root):
            out.extend([root / s for s in subs] or [root])
        return out


def _fail(path: Path, field: str, why: str) -> CardError:
    return CardError(f"{path}: field '{field}': {why}")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _str_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _check(path: Path, data: Any) -> Card:
    """Validate one parsed card; raise ``CardError`` naming the first bad field."""
    if not isinstance(data, dict):
        raise _fail(path, "<root>", "expected a mapping")
    if data.get("schema") != SCHEMA:
        raise _fail(path, "schema", f"expected '{SCHEMA}', got {data.get('schema')!r}")
    cid = data.get("id")
    if not isinstance(cid, str) or not ID_RE.match(cid):
        raise _fail(path, "id", f"not a valid id: {cid!r}")
    if cid != path.stem:
        raise _fail(path, "id", f"'{cid}' differs from the file name '{path.stem}'")
    for key, allowed in (("status", STATUSES), ("kind", KINDS), ("data_class", DATA_CLASSES)):
        if data.get(key) not in allowed:
            raise _fail(path, key, f"{data.get(key)!r} is not one of {', '.join(allowed)}")
    for key in ("task", "license"):
        v = data.get(key)
        if not isinstance(v, str) or not v.strip():
            raise _fail(path, key, "expected a non-empty string")
    if not isinstance(data.get("alias"), str):
        raise _fail(path, "alias", "expected a string")
    for key in ("format", "source_detail"):
        if data.get(key) is not None and not isinstance(data[key], str):
            raise _fail(path, key, "expected a string or null")
    counts = data.get("counts")
    if not isinstance(counts, dict):
        raise _fail(path, "counts", "expected a mapping")
    for key in ("episodes", "frames"):
        if counts.get(key) is not None and not _is_int(counts[key]):
            raise _fail(path, f"counts.{key}", "expected an integer or null")
    if counts.get("hours") is not None and not _is_num(counts["hours"]):
        raise _fail(path, "counts.hours", "expected a number or null")
    locs = data.get("locations")
    if not isinstance(locs, list):
        raise _fail(path, "locations", "expected a list")
    for k, loc in enumerate(locs):
        if not isinstance(loc, dict):
            raise _fail(path, f"locations[{k}]", "expected a mapping")
        for key in ("host", "root"):
            if not isinstance(loc.get(key), str) or not loc[key]:
                raise _fail(path, f"locations[{k}].{key}", "expected a non-empty string")
        if loc.get("role") is not None and not isinstance(loc["role"], str):
            raise _fail(path, f"locations[{k}].role", "expected a string or null")
    lin = data.get("lineage")
    if lin is not None:
        if not isinstance(lin, dict):
            raise _fail(path, "lineage", "expected a mapping or null")
        if lin.get("parents") is not None and not _str_list(lin["parents"]):
            raise _fail(path, "lineage.parents", "expected a list of strings or null")
    for key in ("scene", "files", "quality"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            raise _fail(path, key, "expected a mapping or null")
    if data.get("superseded_by") is not None and not _str_list(data["superseded_by"]):
        raise _fail(path, "superseded_by", "expected a list of strings or null")
    q = data.get("quality") or {}
    dec = q.get("qa_decisions")
    if dec is not None and not (
        isinstance(dec, dict) and all(_is_int(v) or v is None for v in dec.values())
    ):
        raise _fail(path, "quality.qa_decisions", "expected a mapping of counts or null")
    if q.get("known_issues") is not None and not _str_list(q["known_issues"]):
        raise _fail(path, "quality.known_issues", "expected a list of strings or null")
    if q.get("replay_qa") is not None and not isinstance(q["replay_qa"], str):
        raise _fail(path, "quality.replay_qa", "expected a string or null")
    return Card(data=data, path=path)


def card_files(fw_root: Path) -> list[Path]:
    """Card files under ``fw_root`` (both layouts), sorted; none when ``datasets/`` is absent."""
    if not (fw_root / "datasets").is_dir():
        return []
    found: set[Path] = set()
    for pat in CARD_GLOBS:
        found.update(p for p in fw_root.glob(pat) if p.is_file())
    return sorted(found)


def _parse(path: Path) -> Card:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise _fail(path, "<file>", f"cannot read YAML: {e}") from e
    return _check(path, data)


def load_cards(fw_root: Path) -> list[Card]:
    """Every card under ``fw_root``; the first invalid file or duplicate id raises ``CardError``."""
    cards: list[Card] = []
    seen: dict[str, Path] = {}
    for f in card_files(fw_root):
        c = _parse(f)
        if c.id in seen:
            raise _fail(f, "id", f"'{c.id}' is also the id of {seen[c.id]}")
        seen[c.id] = f
        cards.append(c)
    return cards


def load_cards_lenient(fw_root: Path) -> list[Card]:
    """Like ``load_cards`` but an invalid card, or every card of a duplicated id, is skipped.

    For live server paths: one bad card must not take the server down."""
    cards: list[Card] = []
    for f in card_files(fw_root):
        try:
            cards.append(_parse(f))
        except CardError:
            continue
    ids = [c.id for c in cards]
    return [c for c in cards if ids.count(c.id) == 1]


def cards_stamp(fw_root: Path) -> tuple[int, float]:
    """Number of card files and their latest mtime: a cheap cache key."""
    mt = 0.0
    files = card_files(fw_root)
    for f in files:
        try:
            mt = max(mt, f.stat().st_mtime)
        except OSError:
            continue
    return len(files), mt


def _resolved(p: Path) -> Path | None:
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return None


def card_for_path(cards: Iterable[Card], fw_root: Path, dataset_dir: Path) -> Card | None:
    """The card whose laptop LeRobot folder is ``dataset_dir``, else ``None``."""
    target = _resolved(Path(dataset_dir))
    if target is None:
        return None
    for c in cards:
        if any(_resolved(d) == target for d in c.lerobot_dirs(fw_root)):
            return c
    return None
