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
from flywheel.console.paths import ConsolePaths

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


# ------------------------------------------------------------------ overlay on the seed rows
_KIND = {
    "synthetic_s1": "release", "synthetic_s2": "release", "cut": "subset-cut",
    "teleop": "raw source", "egocentric": "raw source",
}  # fmt: skip
_DATA_TYPE = {
    "synthetic_s1": "synthetic S1", "synthetic_s2": "synthetic S2",
    "teleop": "teleop", "egocentric": "egocentric",
}  # fmt: skip
_SOURCE_TYPE = {
    "planner_wbc": "synthetic S1", "s2": "synthetic S2",
    "psi_data": "teleop", "teleop_pico": "teleop",
}  # fmt: skip
_QA_ORDER = ("pass", "flag", "reject")
_FPS_RE = re.compile(r"(\d+)\s*fps")
# Row fields a card brings; seed-only rows get them empty so every row has the same keys.
CARD_FIELDS: dict[str, Any] = {
    "scene": None, "superseded_by": [], "story": None, "replay_qa": None, "card": None,
}  # fmt: skip


def seed_doc(paths: ConsolePaths) -> dict[str, Any]:
    """The seed catalog as a mapping (``rows``, ``edges``, ...); absent file means empty."""
    p = paths.seed / "catalog.yaml"
    if not p.is_file():
        return {"rows": [], "edges": []}
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"rows": data, "edges": []}
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError(f"{p}: expected a YAML list of rows")
    return data


def _title(d: dict[str, Any]) -> str:
    """``Tray S1 · jig2 · l1 (420)`` from the alias ``task.kind.scene.level.generator.date``."""
    alias = str(d["alias"])
    seg = alias.split(".")
    if len(seg) < 4 or not all(seg[:4]):
        return alias
    task = seg[0].replace("_", " ")
    kind = seg[1].upper() if re.fullmatch(r"s\d+", seg[1]) else seg[1].capitalize()
    out = f"{task[:1].upper()}{task[1:]} {kind} · {seg[2]} · {seg[3]}"
    eps = (d.get("counts") or {}).get("episodes")
    return out + (f" ({eps})" if eps is not None else "")


def _qa(dec: dict[str, Any] | None) -> str:
    if not dec:
        return "-"
    keys = [k for k in _QA_ORDER if k in dec] + [k for k in dec if k not in _QA_ORDER]
    return ", ".join(f"{dec[k]} {k}" for k in keys if dec[k] is not None) or "-"


def _locations(card: Card) -> list[str]:
    """Seed-style location strings; copies whose ``role`` starts with ``deleted`` are dropped."""
    d = card.data
    rel = card.files.get("release")
    join = d["kind"] != "cut" and isinstance(rel, str) and rel not in ("", ".")
    out: list[str] = []
    for loc in d["locations"]:
        if str(loc.get("role") or "").startswith("deleted"):
            continue
        host, root = str(loc["host"]), str(loc["root"])
        if host == "huggingface":
            out.append(f"HF {root}")
            continue
        path = f"{root.rstrip('/')}/{rel}" if join else root
        out.append(f"{host}:{path}")
    return out


def _fw_rel(fw_root: Path, p: Path) -> str | None:
    """``p`` relative to ``fw_root`` (no ``fwdata/`` prefix), or None when outside."""
    try:
        if not p.resolve().is_relative_to(fw_root.resolve()):
            return None
        return p.relative_to(fw_root).as_posix()
    except (OSError, ValueError):
        return None


def _lerobot(card: Card, seed: dict[str, Any], fw_root: Path) -> Any:
    """Seed ``lerobot``; for a ``card:``-linked row whose seed folder is gone, the card's
    laptop cut folder when it holds ``meta/info.json``."""
    cur = seed.get("lerobot")
    if cur and (fw_root / str(cur)).is_dir():
        return cur
    for d in card.lerobot_dirs(fw_root):
        if (d / "meta" / "info.json").is_file():
            rel = _fw_rel(fw_root, d)
            if rel:
                return rel
    return cur


def _card_row(card: Card, seed: dict[str, Any] | None, fw_root: Path) -> dict[str, Any]:
    """One catalog row in seed shape: the card wins; the seed keeps title, size, viewer hints."""
    d = card.data
    s = seed or {}
    linked = seed is not None and seed["id"] != card.id
    rid = seed["id"] if seed is not None else card.id
    aliases = list(s.get("aliases") or [])
    for a in (d["alias"], card.id if linked else None):
        if a and a not in aliases:
            aliases.append(a)
    kind = d["kind"]
    if kind == "cut":
        data_type = (s.get("data_type") if seed is not None else None) or _SOURCE_TYPE.get(
            str(d.get("source_detail") or ""), "teleop"
        )
    else:
        data_type = _DATA_TYPE[kind]
    fmt = d.get("format")
    m = _FPS_RE.search(fmt or "")
    counts = d["counts"]
    q = d.get("quality") or {}
    size = s.get("size")
    lin = d.get("lineage") or {}
    return {
        **s,
        "id": rid,
        "name": d["alias"],
        "title": s.get("title") or _title(d),
        "kind": _KIND[kind],
        "data_type": data_type,
        "task": d["task"],
        "episodes": counts.get("episodes"),
        "frames": counts.get("frames"),
        "hours": counts.get("hours"),
        "fps": int(m.group(1)) if m else s.get("fps"),
        "format": fmt,
        "licence": d["license"],
        "data_class": d["data_class"],
        "size": None if size in (None, "?") else size,
        "status": d["status"],
        "notes": "; ".join(q.get("known_issues") or []),
        "qa": _qa(q.get("qa_decisions")),
        "locations": _locations(card),
        "parents": card.parents,
        "aliases": aliases,
        "lerobot": _lerobot(card, s, fw_root) if linked else s.get("lerobot"),
        "ego_viewer": s.get("ego_viewer"),
        "scene": d.get("scene"),
        "superseded_by": list(d.get("superseded_by") or []),
        "story": lin.get("story"),
        "replay_qa": q.get("replay_qa"),
        "card": "fwdata/" + card.path.relative_to(fw_root).as_posix(),
    }


def merged(
    paths: ConsolePaths, strict: bool = True
) -> tuple[list[dict[str, Any]], list[list[str]]]:
    """Seed rows overlaid with the cards under ``paths.fw_root``, and the catalog edges.

    A card overrides the seed row with its ``id``, or the row whose ``card:`` names it (that
    row keeps its seed id). A card without a row adds one. Seed rows without a card are kept
    as they are. ``strict`` raises ``CardError`` on a bad card; otherwise bad cards are
    skipped. Edges are the seed edges plus ``[parent, id]`` for each card parent that is a
    row of the merged catalog."""
    doc = seed_doc(paths)
    fw = paths.fw_root
    seed_rows = [r for r in doc["rows"] if isinstance(r, dict)]
    edges: list[list[str]] = [list(e) for e in doc.get("edges") or []]
    rows: list[dict[str, Any]] = [{**r, **CARD_FIELDS} for r in seed_rows]
    found = load_cards(fw) if strict else load_cards_lenient(fw)
    if not found:
        return rows, edges
    by_id = {str(r["id"]): k for k, r in enumerate(seed_rows)}
    by_link = {str(r["card"]): k for k, r in enumerate(seed_rows) if r.get("card")}
    taken: set[int] = set()
    link: dict[str, str] = {}
    for c in found:
        k = by_link.get(c.id, by_id.get(c.id))
        if k is not None and k in taken:
            if strict:
                raise _fail(c.path, "id", f"seed row '{seed_rows[k]['id']}' has another card")
            continue
        if k is None:
            if any(r["id"] == c.id for r in rows):
                if strict:
                    raise _fail(c.path, "id", f"'{c.id}' is already a catalog row")
                continue
            rows.append(_card_row(c, None, fw))
        else:
            taken.add(k)
            rows[k] = _card_row(c, seed_rows[k], fw)
            link[c.id] = rows[k]["id"]
    ids = {str(r["id"]) for r in rows}
    seen = {tuple(e) for e in edges}
    for r in rows:
        if r["card"] is None:
            continue
        r["parents"] = [link.get(p, p) for p in r["parents"]]
        for p in r["parents"]:
            if p in ids and (p, r["id"]) not in seen:
                seen.add((p, r["id"]))
                edges.append([p, r["id"]])
    return rows, edges
