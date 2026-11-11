"""Egocentric dataset index: viewer exports (``ego_viewer`` rows) and pipeline work dirs.

Posters come only from de-identified videos (``*.deid.mp4``); a raw-only episode has none.
"""

from __future__ import annotations

import collections
import shutil
from pathlib import Path
from typing import Any

from flywheel.console.index.posters import write_posters
from flywheel.console.index.robot import (
    hist,
    load_rows,
    read_json,
    read_jsonl,
    write_json,
)
from flywheel.console.paths import ConsolePaths, PathDenied, deid_only, guard

FPS = 30.0


def _reason(x: str) -> str:
    return x.split(":")[0].split(" (")[0]


def _deid_video(paths: ConsolePaths, work: Path, ep: str) -> Path | None:
    """The episode's ``*.deid.mp4`` inside ``fw_root``, else None. A raw video is never returned."""
    b = read_json(work / "egocentric" / ep / "bundle.json")
    if not isinstance(b, dict) or not b.get("mp4"):
        return None
    p = Path(b["mp4"])
    if not p.is_absolute():
        p = paths.fw_root / p
    try:
        p = guard(deid_only(p), [paths.fw_root])
    except PathDenied:
        return None
    return p if p.is_file() else None


def _work_dir(paths: ConsolePaths, out: Path, sd: Path, note: str | None) -> int:
    sid = sd.name
    d = out / "ds" / sid
    qs = read_jsonl(sd / "qa" / "egocentric.jsonl")
    src = read_json(sd / "source.json") or {}
    jobs: list[tuple[Path, Path]] = []
    posters: set[str] = set()
    for q in qs:
        v = _deid_video(paths, sd, q["episode_id"])
        if v is not None:
            jobs.append((v, d / "posters" / f"{q['episode_id']}.jpg"))
            posters.add(q["episode_id"])
    write_posters(jobs)
    rows: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    for q in qs:
        ep = q["episode_id"]
        ck = {c["name"]: c for c in q["checks"]}
        fr = ck.get("min_frames", {}).get("value")
        has = ep in posters and (d / "posters" / f"{ep}.jpg").is_file()
        rows.append(
            {
                "id": ep, "qa": q["decision"], "reasons": [_reason(x) for x in q["reasons"]],
                "detail": q["reasons"][:2], "n": fr, "s": round(fr / FPS, 1) if fr else None,
                "out": ck.get("hand_out_of_frame", {}).get("value"),
                "jit": ck.get("camera_jitter_deg_s", {}).get("value"),
                "lowc": ck.get("pose_low_confidence", {}).get("value"),
                "ego": has, "poster": f"posters/{ep}.jpg" if has else None,
            }
        )  # fmt: skip
        checks[ep] = [
            [c["name"], round(c["value"], 3), c["threshold"], c["passed"]] for c in q["checks"]
        ]
    qc = collections.Counter(r["qa"] for r in rows)
    rc = collections.Counter(x for r in rows for x in r["reasons"])
    fail = collections.Counter(c[0] for v in checks.values() for c in v if not c[3])
    hs = [
        hist([r["s"] for r in rows], "Độ dài clip (giây)", "s", 20, "s"),
        hist([r["out"] for r in rows], "Tỉ lệ tay ngoài khung", "out", 20),
        hist([r["jit"] for r in rows], "Rung camera (độ/giây)", "jit", 20, "°/s"),
    ]
    write_json(d / "episodes.json", rows)
    write_json(d / "qa.json", checks)
    write_json(
        d / "quality.json",
        {
            "hists": [h for h in hs if h], "qa": dict(qc), "reasons": rc.most_common(),
            "checks_fail": fail.most_common(),
            "n_checks": len(next(iter(checks.values()))) if checks else 0,
            "source": "qa/egocentric.jsonl", "note": note,
        },
    )  # fmt: skip
    report = sd / "report"
    write_json(
        d / "method.json",
        {
            "config_version": src.get("config_version"), "data_class": src.get("data_class"),
            "deid_waiver": src.get("deid_waiver"), "files": sorted(p.name for p in sd.iterdir()),
            "root": "fwdata/pipeline/" + sid,
            "report_files": sorted(p.name for p in report.iterdir()) if report.is_dir() else [],
        },
    )  # fmt: skip
    return len(rows)


def _viewer(paths: ConsolePaths, out: Path, row: dict[str, Any]) -> int | None:
    viewer = paths.fw_root / row["ego_viewer"]
    idx = read_json(viewer / "data" / "index.json")
    if not isinstance(idx, dict):
        return None
    label = row.get("ego_source")
    es = [e for e in idx["episodes"] if label is None or e.get("source") == label]
    d = out / "ds" / str(row["id"])
    pref = row.get("qa_work")
    pq: dict[str, Any] = {}
    if pref:
        for q in read_jsonl(paths.fw_root / "pipeline" / pref / "qa" / "egocentric.jsonl"):
            pq[q["episode_id"]] = q
    rows: list[dict[str, Any]] = []
    for e in es:
        src = viewer / e["poster"]
        has = src.is_file()
        if has:
            (d / "posters").mkdir(parents=True, exist_ok=True)
            shutil.copy(src, d / "posters" / f"{e['id']}.jpg")
        qrow = pq.get(e["id"])
        rows.append(
            {
                "id": e["id"], "title": e["title"], "s": e["seconds"], "qa": e["qa"],
                "hands": round(e["hands"], 3), "pose": e["pose"], "nsub": e["n_subtasks"],
                "reasons": [_reason(x) for x in (qrow["reasons"] if qrow else [])],
                "poster": f"posters/{e['id']}.jpg" if has else None,
            }
        )  # fmt: skip
    qc = collections.Counter(r["qa"] for r in rows)
    rc = collections.Counter(x for r in rows for x in r["reasons"])
    hs = [
        hist([r["s"] for r in rows], "Độ dài clip (giây)", "s", 20, "s"),
        hist([r["hands"] for r in rows], "Tỉ lệ khung thấy tay", "hands", 20),
    ]
    source = "viewer/data/index.json"
    if pref:
        source += f" · qa/egocentric.jsonl của {pref}"
    write_json(d / "episodes.json", rows)
    write_json(
        d / "quality.json",
        {
            "hists": [h for h in hs if h], "qa": dict(qc), "reasons": rc.most_common(),
            "source": source,
        },
    )  # fmt: skip
    parent = viewer.parent
    sub = parent / row["ego_dir"] if row.get("ego_dir") else parent
    rel = parent.relative_to(paths.fw_root).as_posix()
    write_json(
        d / "method.json",
        {
            "summary": read_json(parent / "summary.json"),
            "files": sorted(p.name for p in sub.iterdir())[:40] if sub.is_dir() else [],
            "root": "fwdata/" + rel,
        },
    )  # fmt: skip
    return len(rows)


def build(
    paths: ConsolePaths, out: Path, rows: list[dict[str, Any]] | None = None
) -> dict[str, int]:
    """Write ``out/ds/<id>/`` for ``ego_viewer`` rows and every ``pipeline/src_*`` work dir."""
    rows = load_rows(paths) if rows is None else rows
    counts: dict[str, int] = {}
    for row in rows:
        if row.get("ego_viewer"):
            n = _viewer(paths, out, row)
            if n is not None:
                counts[str(row["id"])] = n
    note_of = {str(r["id"]): r.get("qa") for r in rows}
    pipeline = paths.fw_root / "pipeline"
    for sd in sorted(pipeline.glob("src_*")) if pipeline.is_dir() else []:
        if not (sd / "qa" / "egocentric.jsonl").is_file():
            continue
        note = note_of.get(sd.name)
        counts[sd.name] = _work_dir(paths, out, sd, note if note and "stale" in note else None)
    return counts
