"""Fuzzy id resolvers: dataset (catalog ids and aliases), training run, console job."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flywheel.console.paths import active

from .common import Result, catalog, fail, norm


def _pick(q: Any, items: list[tuple[str, list[str]]]) -> tuple[str, Any]:
    """items: (id, [aliases]). Returns ('ok', id) | ('ambiguous', [ids]) | ('none', [])."""
    raw = str(q or "").strip()
    if not raw:
        return "none", []
    if "#" in raw:  # release ref "tray_s1_xxx#S70:8ab4e33b657f" -> S70
        raw = raw.split("#", 1)[1].split(":", 1)[0] or raw
    ql = raw.lower()
    qn = norm(raw)
    tiers: list[list[str]] = [[], [], [], []]
    for iid, aliases in items:
        names = [iid] + list(aliases)
        if any(n.lower() == ql for n in names) or any(norm(n) == qn for n in names):
            tiers[0].append(iid)
        elif len(qn) >= 2 and any(norm(n).startswith(qn) for n in names):
            tiers[1].append(iid)
        elif re.fullmatch(r"[0-9a-f]{6,16}", ql) and any(
            norm(n).split("_")[-1].startswith(ql) or ("_" + ql) in n.lower() for n in names
        ):
            tiers[2].append(iid)
        elif len(qn) >= 3 and any(qn in norm(n) for n in names):
            tiers[3].append(iid)
    for t in tiers:
        uniq = list(dict.fromkeys(t))
        if len(uniq) == 1:
            return "ok", uniq[0]
        if len(uniq) > 1:
            return "ambiguous", uniq[:6]
    return "none", []


def dataset_items() -> list[tuple[str, list[str]]]:
    """(id, names) of every catalog row; names are the row name and its ``aliases``."""
    items: list[tuple[str, list[str]]] = []
    for r in catalog().get("rows", []):
        names = [str(r.get("name") or "")] + [str(a) for a in r.get("aliases") or []]
        items.append((r["id"], names))
    return items


def resolve_dataset(q: Any) -> tuple[str, Any]:
    return _pick(q, dataset_items())


def pair_dir() -> Path:
    return active().fw_root / "tray" / "pair60k"


def ledgers_dir() -> Path:
    return active().fw_root / "sites" / "local" / "runs"


def run_index() -> list[dict[str, Any]]:
    """All training runs: job id, branch, dir, from ``tray/pair60k/*/*/metrics.jsonl``."""
    return [
        {"id": f.parent.name, "branch": f.parent.parent.name, "dir": f.parent, "metrics": f}
        for f in sorted(pair_dir().glob("*/*/metrics.jsonl"))
    ]


def resolve_run(q: Any) -> tuple[str, Any]:
    runs = run_index()
    raw = str(q or "").strip()
    qn = norm(raw)
    for r in runs:  # "B_70" / "b70" / "c all": the branch name first
        if qn and norm(r["branch"]) == qn:
            return "ok", r["id"]
    return _pick(raw, [(r["id"], [r["branch"]]) for r in runs])


def job_dirs() -> list[Path]:
    jd = active().jobs
    if not jd.is_dir():
        return []
    return [d for d in jd.iterdir() if d.is_dir() and (d / "job.json").is_file()]


def resolve_job(q: Any) -> tuple[str, Any]:
    raw = str(q or "").strip().lower()
    if not raw:
        return "none", []
    ids = [d.name for d in job_dirs()]
    if raw in ids:
        return "ok", raw
    hits = [i for i in ids if i.startswith(raw) or i.endswith(raw) or raw in i]
    if len(hits) == 1:
        return "ok", hits[0]
    return ("ambiguous", sorted(hits)[-6:]) if hits else ("none", [])


_PRONOUNS = {"this", "current", "selected", "it", "here", "tap nay", "this dataset", "this one"}


def want_dataset(
    args: dict[str, Any], ctx: dict[str, Any], key: str = "dataset_id"
) -> tuple[str | None, Result | None]:
    """-> (id, None) or (None, error result). Falls back to the page context for pronouns."""
    v = args.get(key) or args.get("work_id") or args.get("dataset") or args.get("id")
    if (not v or str(v).strip().lower() in _PRONOUNS) and ctx.get("dataset_id"):
        v = ctx["dataset_id"]
    if not v:
        return None, fail("dataset_id is required.")
    st, r = resolve_dataset(v)
    if st == "ok":
        return str(r), None
    if st == "ambiguous":
        return None, fail(f"Ambiguous dataset '{v}'.", r)
    if ctx.get("dataset_id") and (" " in str(v) or str(v).lower() in _PRONOUNS):
        return str(ctx["dataset_id"]), None
    return None, fail(f"No dataset matches '{v}'.")
