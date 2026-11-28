"""Catalog index: seed rows plus build-time facts (local presence, view, children)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from flywheel.console.index import cards, hidden
from flywheel.console.paths import ConsolePaths, PathDenied, guard

_GROUPS = {
    "egocentric": "egocentric",
    "teleop": "teleop",
    "synthetic S1": "s1",
    "synthetic S2": "s2",
}
_ROBOT_IDS = ("S70", "ALL")
# Kinds whose episodes are new data. Pipeline sources, exports, cuts and bench copies
# repeat the episodes of their parents, so summing them counts one clip several times.
_ORIGIN_KINDS = ("raw source", "release")
_EGO_IDS = ("h1m-team", "h1m-egodex")
_PSI_IDS = ("psi-two-table", "psi-hug")
_COND_IDS = ("he-dev-eval-v1", "he-dev-eval-v1-l0n10", "he-eval-n20-interleaved")
# Statuses whose rows count in the totals; ``reference`` (the authors' psi-data) counts too.
LIVE_STATUSES = ("current", "reference")


def _parse_loc(raw: str) -> dict[str, str]:
    s = raw.strip()
    for prefix, where in (("laptop:", "laptop"), ("rtx3060:", "rtx3060")):
        if s.startswith(prefix):
            return {"where": where, "path": s[len(prefix) :].split(" (")[0].strip(), "raw": s}
    if s.startswith("Colab"):
        return {"where": "colab", "path": s, "raw": s}
    if s.startswith("HF") or "huggingface" in s:
        return {"where": "hf", "path": s, "raw": s}
    if s.startswith("http"):
        return {"where": "remote", "path": s.split(" ")[0], "raw": s}
    return {"where": "?", "path": s, "raw": s}


def _local_dir(paths: ConsolePaths, rel: str) -> Path | None:
    """Return the existing directory for an fw-relative path, or None if absent or denied."""
    clean = rel.split("{")[0].split("...")[0].rstrip("/")
    clean = clean.removeprefix("fwdata/")
    try:
        p = guard(paths.fw_root / clean, [paths.fw_root])
    except PathDenied:
        return None
    return p if p.is_dir() else None


def _exists(paths: ConsolePaths, loc: dict[str, str]) -> bool:
    if loc["where"] != "laptop":
        return False
    clean = loc["path"].split("{")[0].split("...")[0].rstrip("/").removeprefix("fwdata/")
    try:
        return guard(paths.fw_root / clean, [paths.fw_root]).exists()
    except PathDenied:
        return False


def _qa_counts(q: str | None) -> dict[str, int] | None:
    out: dict[str, int] = {}
    for k in ("pass", "flag", "reject"):
        m = re.search(r"\b(\d+)\s*" + k + r"\b", q or "")
        if m:
            out[k] = int(m.group(1))
    return out or None


def _rsync(r: dict[str, Any], locs: list[dict[str, str]], view: str, local: bool) -> dict[str, str]:
    """Copy commands for a remote-only row; glob or elided paths are left out."""
    rt = [x for x in locs if x["where"] == "rtx3060"]
    if not rt or local or view not in ("remote", "cond", "meta"):
        return {}
    p = rt[0]["path"].rstrip("/")
    if "*" in p or "..." in p:
        return {}
    dst = f"./fwdata/remote/{r['id']}/"
    return {
        "rsync": f"rsync -a rtx3060:{p}/meta {dst}",
        "rsync_full": f"rsync -a rtx3060:{p}/ {dst}   # kích thước: {r['size']}",
    }


def enrich(index_dir: Path) -> None:
    """Fill ``thumbs`` and ``qa_counts`` from the built ``ds/<id>/`` folders (idempotent)."""
    cat = index_dir / "catalog.json"
    if not cat.is_file():
        return
    doc = json.loads(cat.read_text(encoding="utf-8"))
    for row in doc.get("rows", []):
        d = index_dir / "ds" / row["id"]
        files = sorted(p.name for p in (d / "posters").glob("*.jpg")) if d.is_dir() else []
        if files:
            n = min(4, len(files))
            pick = [files[k * len(files) // n] for k in range(n)]
            row["thumbs"] = [f"/data/ds/{row['id']}/posters/{f}" for f in pick]
        try:
            q = json.loads((d / "quality.json").read_text(encoding="utf-8")).get("qa")
        except (OSError, ValueError, AttributeError):
            q = None
        if isinstance(q, dict) and any(k in q for k in ("pass", "flag", "reject")):
            row["qa_counts"] = {k: int(v) for k, v in q.items() if k in ("pass", "flag", "reject")}
    cat.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _view(paths: ConsolePaths, r: dict[str, Any], laptop_dir: Path | None, has_laptop: bool) -> str:
    rid = r["id"]
    first = (r.get("locations") or [""])[0]
    if r["status"] == "missing" or first.startswith("?"):
        return "missing"
    if rid in _ROBOT_IDS:
        return "robot"
    if rid in _EGO_IDS:
        return "ego"
    if rid.startswith("src_") and (paths.fw_root / "pipeline" / rid).is_dir():
        return "src"
    if rid in _PSI_IDS:
        return "psi"
    if rid in _COND_IDS and laptop_dir is not None:
        return "cond"
    if not has_laptop or laptop_dir is None:
        return "remote"
    return "meta"


def _is_unique(row: dict[str, Any]) -> bool:
    """True when the row's episodes are counted once in the catalog totals."""
    return bool(
        row["kind"] in _ORIGIN_KINDS and row["status"] in LIVE_STATUSES and row["group"] != "eval"
    )


def _totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Distinct episodes and hours per group and overall, from the unique rows only."""
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        if not r["unique"]:
            continue
        for key in (r["group"], "all"):
            t = out.setdefault(key, {"sets": 0, "episodes": 0, "hours": 0.0})
            t["sets"] += 1
            t["episodes"] += r["episodes"] or 0
            t["hours"] = round(t["hours"] + (r["hours"] or 0.0), 3)
    return out


totals = _totals  # public: tasks.py totals the rows of one task the same way


def _load_seed(paths: ConsolePaths) -> dict[str, Any]:
    data = yaml.safe_load((paths.seed / "catalog.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _human_size(n: int) -> str:
    return "%.0f MB" % (n / 1e6) if n < 1e9 else "%.1f GB" % (n / 1e9)


def _dir_size(d: Path) -> str:
    """Total bytes of the files under ``d``, written like ``4.4 GB``."""
    tot = 0
    for dp, _dns, fns in os.walk(d):
        for fn in fns:
            try:
                tot += (Path(dp) / fn).stat().st_size
            except OSError:
                continue
    return _human_size(tot)


def build(paths: ConsolePaths, out: Path) -> dict[str, int]:
    """Write ``out/catalog.json`` and return the counts of rows, edges, runs and cards.

    Rows are the seed rows overlaid with the dataset cards (a bad card raises ``CardError``),
    without the rows ``hidden.catalog_rows`` drops (a hidden run's story, e.g. DA-50).
    Only ``out`` is written; nothing under ``fw_root`` changes."""
    seed = _load_seed(paths)
    merged, edges = cards.merged(paths, strict=True)
    # rows of a hidden run's story or naming a hidden run never reach a page (decision Q1)
    merged, edges = hidden.catalog_rows(merged, edges, hidden.load(paths))
    rows: list[dict[str, Any]] = []
    for r in merged:
        locs = [_parse_loc(x) for x in r["locations"]]
        laptop_dir: Path | None = None
        has_laptop = False
        for loc in locs:
            loc["exists"] = _exists(paths, loc)  # type: ignore[assignment]
            if loc["where"] == "laptop":
                has_laptop = True
                if laptop_dir is None:
                    laptop_dir = _local_dir(paths, loc["path"])
        size = r["size"]
        if size is None:  # a card row without a seed size: measure the laptop copy
            size = _dir_size(laptop_dir) if laptop_dir is not None else "?"
        rows.append(
            {
                "id": r["id"],
                "name": r["name"],
                "title": r["title"],
                "kind": r["kind"],
                "group": "eval"
                if r["kind"] in ("eval conditions", "bench copy")
                else _GROUPS.get(r["data_type"], "teleop"),
                "data_type": r["data_type"],
                "task": r["task"],
                "episodes": r["episodes"],
                "frames": r["frames"],
                "hours": r["hours"],
                "fps": r["fps"],
                "format": r["format"],
                "licence": r["licence"],
                "data_class": r["data_class"],
                "locations": locs,
                "size": size,
                "status": r["status"],
                "notes": r["notes"],
                "qa": r["qa"],
                "qa_counts": _qa_counts(r["qa"]),
                "view": _view(paths, r, laptop_dir, has_laptop),
                "laptop_dir": (
                    "fwdata/" + laptop_dir.relative_to(paths.fw_root.resolve()).as_posix()
                    if laptop_dir is not None
                    else None
                ),
                "parents": list(r.get("parents", [])),
                "children": [b for a, b in edges if a == r["id"]],
                "thumbs": [],
                "aliases": list(r.get("aliases", [])),
                "lerobot": r.get("lerobot"),
                "ego_viewer": r.get("ego_viewer"),
                "scene": r.get("scene"),
                "superseded_by": list(r.get("superseded_by") or []),
                "story": r.get("story"),
                "replay_qa": r.get("replay_qa"),
                "card": r.get("card"),
            }
        )
        rows[-1]["unique"] = _is_unique(rows[-1])
        rows[-1].update(_rsync({**r, "size": size}, locs, rows[-1]["view"], laptop_dir is not None))
    runs = list(seed["runs"])
    n_cards = sum(1 for r in rows if r["card"])
    out.mkdir(parents=True, exist_ok=True)
    doc = {
        "generated": seed["generated"],
        "cards": n_cards,
        "rows": rows,
        "edges": edges,
        "runs": runs,
        "totals": _totals(rows),
    }
    (out / "catalog.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return {"rows": len(rows), "edges": len(edges), "runs": len(runs), "cards": n_cards}
