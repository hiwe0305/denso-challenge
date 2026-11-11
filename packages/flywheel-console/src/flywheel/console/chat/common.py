# ruff: noqa: UP031
"""Shared helpers of the chat tools: guarded cached readers, result builders, small formatters."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.paths import PathDenied, active, guard

Result = dict[str, Any]
MODEL_CHARS = 4000  # about 1,200 tokens
DENY_PARTS = ("vault", "holdout")

_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


# ------------------------------------------------------------------ path allowlist and loaders
def allowed(path: str | Path) -> bool:
    """True only for a real path under ``fw_root`` that does not touch vault/ or a holdout."""
    try:
        guard(path, [active().fw_root])
    except (PathDenied, OSError, ValueError):
        return False
    return True


def jload(path: str | Path, default: Any = None) -> Any:
    """Read JSON from an allowed path, cached by mtime."""
    p = Path(path)
    if not allowed(p) or not p.is_file():
        return default
    key = str(p)
    mt = p.stat().st_mtime
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] == mt:
            return hit[1]
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    with _lock:
        _cache[key] = (mt, v)
    return v


def jsonl(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    p = Path(path)
    if not allowed(p) or not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    with open(p, encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out[-limit:] if limit else out


def tail_lines(path: str | Path, n: int = 80, grep: str | None = None) -> tuple[str | None, bool]:
    p = Path(path)
    if not allowed(p) or not p.is_file():
        return None, False
    size = p.stat().st_size
    with open(p, "rb") as f:
        f.seek(max(0, size - 400_000))
        txt = f.read().decode("utf-8", "replace")
    lines = txt.replace("\r", "\n").splitlines()
    if grep:
        g = grep.lower()
        lines = [x for x in lines if g in x.lower()]
    return "\n".join(lines[-n:]), len(lines) > n


def catalog() -> dict[str, Any]:
    d = jload(active().index / "catalog.json", {"rows": [], "edges": [], "runs": []})
    return d if isinstance(d, dict) else {"rows": [], "edges": [], "runs": []}


def story() -> dict[str, Any]:
    d = jload(active().index / "story.json", {})
    return d if isinstance(d, dict) else {}


def ds_file(ds: str, name: str) -> Any:
    return jload(active().index / "ds" / ds / (name + ".json"))


# ------------------------------------------------------------------ small helpers
def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def to_int(v: Any, default: int, lo: int = 1, hi: int = 200) -> int:
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return default


def table(
    title: str,
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    total: int | None = None,
    link: str | None = None,
    row_link: str | None = None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {"type": "table", "title": title, "columns": columns, "rows": rows}
    if total is not None:
        spec["total"] = total
    if link:
        spec["link"] = link
    if row_link:
        spec["row_link"] = row_link
    return spec


def cols(*names: str) -> list[dict[str, str]]:
    return [{"key": n, "label": n.replace("_", " ")} for n in names]


def cap(text: str) -> str:
    return text if len(text) <= MODEL_CHARS else text[:MODEL_CHARS] + "\n[truncated]"


def result(ui: dict[str, Any], model: str, ok: bool = True) -> Result:
    return {"ok": ok, "ui": ui, "model": cap(model)}


def fail(msg: str, candidates: list[str] | None = None) -> Result:
    m = msg + ((" Candidates: " + ", ".join(candidates)) if candidates else "")
    return result({"type": "text", "text": m}, m, ok=False)


def fmtv(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, list):
        return ",".join(map(str, v))
    return str(v)


def rows_text(rows: list[dict[str, Any]], keys: list[str], n: int = 12) -> str:
    out = [" | ".join(f"{k}={fmtv(r.get(k))}" for k in keys) for r in rows[:n]]
    if len(rows) > n:
        out.append("... %d more" % (len(rows) - n))
    return "\n".join(out)


def parse_ts(s: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s))
    except ValueError:
        return None


def dur_s(j: dict[str, Any]) -> float | None:
    a, b = parse_ts(j.get("started") or ""), parse_ts(j.get("ended") or "")
    if a and b:
        try:
            return (b - a).total_seconds()
        except TypeError:
            return None
    return None
