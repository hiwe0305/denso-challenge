"""Robot (LeRobot v2.1) dataset index: episodes, env, quality, method and posters."""

from __future__ import annotations

import collections
import json
import math
import shutil
from pathlib import Path
from typing import Any

import yaml
from flywheel.console.index.posters import write_posters
from flywheel.console.paths import ConsolePaths

GROUPS = ["left_hand", "right_hand", "left_arm", "right_arm", "navigate", "waist", "base_height"]
RELEASE_TAG = {"41899efb4b27": "pool", "4a8f4a8c6a8d": "tgt"}
DEFAULT_VIDEO = "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4"


def load_rows(paths: ConsolePaths) -> list[dict[str, Any]]:
    """Seed catalog rows (a YAML list, or a mapping with ``rows``); absent file means none."""
    p = paths.seed / "catalog.yaml"
    if not p.is_file():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rows")
    if not isinstance(data, list):
        raise ValueError(f"{p}: expected a YAML list of rows")
    return [r for r in data if isinstance(r, dict)]


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    with p.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_json(p: Path) -> Any:
    if not p.is_file():
        return None
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def hist(
    vals: list[Any], label: str, field: str, nb: int = 24, unit: str = ""
) -> dict[str, Any] | None:
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    lo, hi = min(xs), max(xs)
    if hi == lo:
        hi = lo + 1
    width = (hi - lo) / nb
    c = [0] * nb
    for v in xs:
        c[min(nb - 1, int((v - lo) / width))] += 1
    bins = [
        {"lo": round(lo + i * width, 3), "hi": round(lo + (i + 1) * width, 3), "c": c[i]}
        for i in range(nb)
    ]
    return {"label": label, "field": field, "unit": unit, "bins": bins}


def _video(root: Path, info: dict[str, Any], i: int) -> Path:
    tpl = info.get("video_path") or DEFAULT_VIDEO
    size = int(info.get("chunks_size") or 1000)
    return root / tpl.format(episode_chunk=i // size, episode_index=i)


def _episodes(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    meta = root / "meta"
    info = read_json(meta / "info.json") or {}
    fps = float(info.get("fps") or 50)
    stats = {
        x["episode_index"]: x["stats"]["action"] for x in read_jsonl(meta / "episodes_stats.jsonl")
    }
    layout = (read_json(meta / "action_layout.json") or {}).get("dimensions", [])
    gi: dict[str, list[int]] = collections.defaultdict(list)
    for k, d in enumerate(layout):
        gi[d["group"]].append(k)
    sub = read_json(meta / "flywheel_subset.json") or {}
    part_of: dict[int, tuple[str, Any]] = {}
    for p in sub.get("parts", []):
        tag = RELEASE_TAG.get(p["release_id"].split("_")[-1], p["release_id"])
        for e in p["episodes"]:
            part_of[e["episode_index"]] = (tag, e.get("cut_episode_index"))
    out: list[dict[str, Any]] = []
    env: dict[str, Any] = {}
    for e in read_jsonl(meta / "episodes.jsonl"):
        i = e["episode_index"]
        raw = e.get("environment_config") or {}
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        tray = cfg.get("tray", {})
        sm = tray.get("sample", {})
        fl = cfg.get("flywheel", {})
        rp = tray.get("report", {})
        a = stats.get(i)
        rng = [
            round(sum(a["max"][k] - a["min"][k] for k in gi[g]) / len(gi[g]), 3)
            if a and gi.get(g)
            else 0.0
            for g in GROUPS
        ]
        tp, gp = sm.get("tray_pose", {}), sm.get("target_pose", {})
        dist = round(
            math.hypot(tp.get("x", 0) - gp.get("x", 0), tp.get("y", 0) - gp.get("y", 0)), 3
        )
        part = part_of.get(i, ("?", None))
        out.append(
            {
                "i": i, "n": e["length"], "s": round(e["length"] / fps, 1),
                "lv": sm.get("level"), "seed": sm.get("seed"), "part": part[0], "cut": part[1],
                "ok": bool(rp.get("success")), "dist": dist, "r": rng,
                "gap": sm.get("table_gap"), "light": sm.get("light_scale"),
            }
        )  # fmt: skip
        keys = ("seed", "level", "planner_version", "purpose", "source_kind", "synthetic_tier",
                "action_quality", "renderer", "story", "split", "data_class")  # fmt: skip
        env[str(i)] = {
            "instruction": (e.get("instruction") or {}).get("task"),
            "sample": sm,
            "flywheel": {k: fl[k] for k in keys if k in fl},
            "report": rp,
            "from": e.get("dataset_from_index"),
            "to": e.get("dataset_to_index"),
        }
    if out:
        ns = [o["n"] for o in out]
        mu = sum(ns) / len(ns)
        sd = (sum((x - mu) ** 2 for x in ns) / len(ns)) ** 0.5
        for o in out:
            z = (o["n"] - mu) / sd if sd else 0.0
            o["out"] = "dài" if z > 2 else ("ngắn" if z < -2 else "")
    return out, env, sub


def _quality(root: Path, out: list[dict[str, Any]]) -> dict[str, Any]:
    bs = read_json(root / "meta" / "batch_summary.json")
    qh = [
        hist([o["n"] for o in out], "Độ dài episode (khung, 50 fps)", "n", 24, "khung"),
        hist([o["dist"] for o in out], "Khoảng cách khay → đích (m)", "dist", 20, "m"),
    ]
    for k, g in enumerate(GROUPS):
        label = "Biên độ action · " + g + " (max−min trung bình theo chiều)"
        qh.append(hist([o["r"][k] for o in out], label, f"r{k}", 20, "rad"))
    lv = collections.Counter(o["lv"] for o in out)
    part = collections.Counter(o["part"] for o in out)
    q: dict[str, Any] = {
        "hists": [h for h in qh if h],
        "levels": sorted(lv.items(), key=lambda x: str(x[0])),
        "parts": sorted(part.items()),
        "funnel": [],
        "failures": [],
        "success_rate_ok": round(sum(o["ok"] for o in out) / len(out), 3) if out else 0.0,
        "source": "meta/batch_summary.json · meta/episodes_stats.jsonl · meta/episodes.jsonl",
        "note": None,
    }
    if bs:
        q["funnel"] = [
            ["Lần chạy", bs["attempts"]], ["Thành công", bs["successes"]],
            ["Đã ghi", bs["recorded"]], ["QA pass", bs["qa_pass"]], ["Giữ trong cut", len(out)],
        ]  # fmt: skip
        q["failures"] = sorted(bs.get("failures", {}).items(), key=lambda x: -x[1])
        q["note"] = (
            f"batch_summary.json trong cut là của lô sinh gốc ({bs['attempts']} lần chạy), "
            "không phải của riêng cut này."
        )
    return q


def _method(root: Path, rel: str, sub: dict[str, Any]) -> dict[str, Any]:
    meta = root / "meta"
    info = read_json(meta / "info.json") or {}
    info.pop("features", None)
    lin = read_jsonl(meta / "flywheel_lineage.jsonl")
    ch = collections.Counter(x.get("change") for x in lin)
    subset: dict[str, Any] = {
        k: sub[k] for k in ("demo_set", "n", "fraction", "order", "from_cut") if k in sub
    }
    subset["parts"] = [
        {k: p.get(k) for k in ("release_id", "n", "first_episode_index")}
        for p in sub.get("parts", [])
    ]
    return {
        "info": info,
        "batch_summary": read_json(meta / "batch_summary.json"),
        "batch_replay": read_json(meta / "batch_replay_summary.json"),
        "subset": subset,
        "lineage_changes": dict(ch),
        "lineage_example": lin[0] if lin else None,
        "files": sorted(p.name for p in meta.iterdir()),
        "root": "fwdata/" + rel,
    }


def build(
    paths: ConsolePaths, out: Path, rows: list[dict[str, Any]] | None = None
) -> dict[str, int]:
    """Write ``out/ds/<id>/`` for every row with a local ``lerobot`` dir; return episode counts."""
    rows = load_rows(paths) if rows is None else rows
    counts: dict[str, int] = {}
    # dataset id -> {cut episode index: (episode index, video)} for poster reuse between cuts
    seen: dict[str, dict[Any, tuple[int, Path]]] = {}
    for row in rows:
        rel = row.get("lerobot")
        if not rel:
            continue
        root = paths.fw_root / rel
        if not (root / "meta" / "episodes.jsonl").is_file():
            continue
        ds = str(row["id"])
        d = out / "ds" / ds
        eps, env, sub = _episodes(root)
        info = read_json(root / "meta" / "info.json") or {}
        write_json(d / "episodes.json", eps)
        write_json(d / "env.json", env)
        write_json(d / "quality.json", _quality(root, eps))
        write_json(d / "method.json", _method(root, rel, sub))
        jobs: list[tuple[Path, Path]] = []
        copies: list[tuple[Path, Path]] = []
        for o in eps:
            i = o["i"]
            vid, dst = _video(root, info, i), d / "posters" / f"{i}.jpg"
            twin = next(
                ((name, m[i]) for name, m in seen.items() if i in m and m[i][1].is_file()), None
            )
            if twin and vid.is_file() and twin[1][1].stat().st_size == vid.stat().st_size:
                copies.append((out / "ds" / twin[0] / "posters" / f"{twin[1][0]}.jpg", dst))
            else:
                jobs.append((vid, dst))
        (d / "posters").mkdir(parents=True, exist_ok=True)
        write_posters(jobs)
        for src, dst in copies:
            if src.is_file() and not dst.exists():
                shutil.copy(src, dst)
        seen[ds] = {o["cut"]: (o["i"], _video(root, info, o["i"])) for o in eps if o["cut"]}
        counts[ds] = len(eps)
    return counts
