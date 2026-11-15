"""Simulation library index (one-site design 7): the episodes of the latest training cut and a
fixed sample of their videos.

Reads ``meta/`` of ``tray/pair-cuts/C70_R1.tar`` without unpacking the 5 GB tar, labels each
episode by the part of the cut it came from (``meta/flywheel_subset.json``), and copies about 40
public videos plus posters to ``<console>/media/sim/<sha8>/`` (served at ``/simmedia/``). Eight
teleop trials come from the psi-data zip. Files already on disk are kept.

Mid-episode frames of this task all look alike (the tray held in front of the camera), so the
posters of one group step through ``POSTER_AT``: start, lift, carry, placed. The frame position is
in the file name (``ep_000003.p30.jpg``), so a new position writes a new file once and an existing
one is kept.
"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import IO, Any

import cv2
from flywheel.console.index.story import FOLLOW
from flywheel.console.paths import ConsolePaths

CUT = "tray/pair-cuts/C70_R1.tar"
TELEOP_ZIP = "psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip"
N_COVERAGE = 16
N_TARGETED = 16
N_TELEOP = 8
POSTER_W = 320
POSTER_AT = (0.03, 0.3, 0.6, 0.97)  # fraction of the episode: start, lift, carry, placed
_FOR = re.compile(r"-L(\d+)-(\d+)$")


def _spread(items: list[Any], k: int) -> list[Any]:
    """``k`` items at even steps from the start (all of them when there are fewer)."""
    if len(items) <= k:
        return list(items)
    return [items[i * len(items) // k] for i in range(k)]


def _copy(src: IO[bytes], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        shutil.copyfileobj(src, f, 1 << 20)
    tmp.replace(dest)


def _frame_jpeg(video: Path, at: float, width: int = POSTER_W) -> bytes:
    """JPEG (q70) of the frame at fraction ``at`` of the video, scaled to ``width``."""
    cap = cv2.VideoCapture(str(video))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(n - 1, int(at * n))))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        raise ValueError(f"unreadable video: {video}")
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (width, max(1, int(width * h / w))))
    done, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not done:
        raise ValueError("jpeg encode failed")
    return bytes(buf.tobytes())


def _poster(video: Path, at: float = 0.5) -> str | None:
    """Poster next to the video, cut at fraction ``at``; None for an unreadable video."""
    jpg = video.with_name(f"{video.stem}.p{round(at * 100):02d}.jpg")
    if not jpg.is_file():
        try:
            jpg.write_bytes(_frame_jpeg(video, at))
        except (ValueError, OSError, cv2.error):
            return None
    return jpg.name


def _labels(subset: dict[str, Any], n: int) -> list[tuple[str, int, int, str]]:
    """(label, first index, count, release) for each part of the cut."""
    base = subset.get("base") or {}
    parts = list(base.get("parts") or [])
    names = ["coverage", "prev"]
    out = [
        (
            names[i] if i < len(names) else "coverage",
            int(p["first_episode_index"]),
            int(p["n"]),
            str(p.get("release_id", "")),
        )
        for i, p in enumerate(parts)
    ]
    tg = subset.get("targeted") or {}
    if tg:
        out.append(
            ("round", int(tg["first_episode_index"]), int(tg["n"]), str(tg.get("release_id", "")))
        )
    return out or [("coverage", 0, n, "")]


def _episode(e: dict[str, Any], label: str) -> dict[str, Any]:
    cfg = e.get("environment_config") or {}
    cfg = json.loads(cfg) if isinstance(cfg, str) else cfg
    fwm, tray = cfg.get("flywheel") or {}, cfg.get("tray") or {}
    sample, report = tray.get("sample") or {}, tray.get("report") or {}
    cluster = fwm.get("cluster_id")
    m = _FOR.search(cluster or "")
    return {
        "i": int(e["episode_index"]),
        "label": label,
        "purpose": fwm.get("purpose"),
        "cluster": cluster,
        "for": [int(m.group(1)), int(m.group(2))] if m else None,
        "seed": fwm.get("seed"),
        "level": fwm.get("level", sample.get("level")),
        "len": e.get("length"),
        "tray": sample.get("tray_pose"),
        "target": sample.get("target_pose"),
        "spawn": sample.get("robot_spawn"),
        "steps": report.get("steps"),
        "public": fwm.get("data_class") == "public",
        "video": None,
        "poster": None,
    }


def _sample(eps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pub = [e for e in eps if e["public"]]
    follow = [
        e
        for e in pub
        if e["for"] == list(FOLLOW) or (e["cluster"] or "").endswith(f"L{FOLLOW[0]}-{FOLLOW[1]}")
    ]
    cov = _spread([e for e in pub if e["label"] == "coverage"], N_COVERAGE)
    first: dict[str, dict[str, Any]] = {}
    for e in pub:
        if e["label"] != "coverage":
            first.setdefault(str(e["cluster"]), e)
    tgt = _spread([first[k] for k in sorted(first)], N_TARGETED)
    seen: dict[int, dict[str, Any]] = {}
    for e in follow + cov + tgt:
        seen.setdefault(e["i"], e)
    return sorted(seen.values(), key=lambda e: e["i"])


def _cut(paths: ConsolePaths, media: Path) -> dict[str, Any]:
    tar_path = paths.fw_root / CUT
    if not tar_path.is_file():
        return {}
    side = tar_path.with_name(tar_path.name + ".json")
    sha = str(json.loads(side.read_text()).get("sha256", "")) if side.is_file() else ""
    sha8 = sha[:8] or "cut"
    with tarfile.open(tar_path) as t:
        names = t.getnames()
        meta = next(
            (n[: -len("episodes.jsonl")] for n in names if n.endswith("/meta/episodes.jsonl")), None
        )
        if meta is None:
            return {}
        root = meta[: -len("meta/")]

        def read(rel: str) -> bytes:
            f = t.extractfile(root + rel)
            return f.read() if f else b""

        rows = [
            json.loads(x) for x in read("meta/episodes.jsonl").decode().splitlines() if x.strip()
        ]
        subset = (
            json.loads(read("meta/flywheel_subset.json") or b"{}")
            if root + "meta/flywheel_subset.json" in names
            else {}
        )
        batch = (
            json.loads(read("meta/batch_summary.json") or b"{}")
            if root + "meta/batch_summary.json" in names
            else {}
        )
        has_info = root + "meta/info.json" in names
        info = json.loads(read("meta/info.json") or b"{}") if has_info else {}
        parts = _labels(subset, len(rows))
        lab = {}
        for name, first, n, _ in parts:
            for i in range(first, first + n):
                lab[i] = name
        eps = [_episode(e, lab.get(int(e["episode_index"]), "coverage")) for e in rows]
        k: Counter[str] = Counter()
        for e in _sample(eps):
            rel = f"{sha8}/ep_{e['i']:06d}.mp4"
            dest = media / rel
            if not dest.is_file():
                src = t.extractfile(f"{root}videos/chunk-000/egocentric/episode_{e['i']:06d}.mp4")
                if src is None:
                    continue
                _copy(src, dest)
            e["video"] = rel
            at = POSTER_AT[k[e["label"]] % len(POSTER_AT)]
            k[e["label"]] += 1
            jpg = _poster(dest, at)
            e["poster"] = f"{sha8}/{jpg}" if jpg else None
    base = subset.get("base") or {}
    cuts = {"C70_R1": {"sha256": sha, "of": "tar"}}
    if base.get("marker_sha256"):
        cuts["S70"] = {"sha256": base["marker_sha256"], "of": "marker"}
    if (base.get("from_cut") or {}).get("marker_sha256"):
        cuts["ALL"] = {"sha256": base["from_cut"]["marker_sha256"], "of": "marker"}
    return {
        "source": CUT,
        "sha8": sha8,
        "parts": [{"label": a, "first": f, "n": n, "release": r} for a, f, n, r in parts],
        "cuts": cuts,
        "format": f"LeRobot {info['codebase_version']}" if info.get("codebase_version") else None,
        "batch": batch,
        "episodes": eps,
    }


def _teleop(paths: ConsolePaths, media: Path) -> list[dict[str, Any]]:
    zp = paths.fw_root / TELEOP_ZIP
    if not zp.is_file():
        return []
    out: list[dict[str, Any]] = []
    with zipfile.ZipFile(zp) as z:
        vids = sorted(n for n in z.namelist() if n.endswith(".mp4") and "/egocentric/" in n)
        for k, name in enumerate(_spread(vids, N_TELEOP)):
            i = int(re.findall(r"(\d+)\.mp4$", name)[0])
            rel = f"teleop/ep_{i:06d}.mp4"
            dest = media / rel
            if not dest.is_file():
                with z.open(name) as src:
                    _copy(src, dest)
            jpg = _poster(dest, POSTER_AT[k % len(POSTER_AT)])
            poster = f"teleop/{jpg}" if jpg else None
            # the authors' teleop set is the two-table pick task, not tray carrying (design 6.1)
            out.append(
                {"i": i, "label": "teleop", "task": "two_table", "video": rel, "poster": poster}
            )
    return out


def build(paths: ConsolePaths, out: Path) -> dict[str, int]:
    """Write ``out/sim.json``; return the episode and sampled-media counts."""
    media = paths.sim_media
    doc: dict[str, Any] = {
        "source": CUT,
        "sha8": None,
        "parts": [],
        "cuts": {},
        "batch": {},
        "episodes": [],
    }
    doc.update(_cut(paths, media))
    doc["teleop"] = _teleop(paths, media)
    for e in doc["episodes"]:
        e.pop("public", None)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sim.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    n_media = sum(1 for e in doc["episodes"] if e["video"]) + len(doc["teleop"])
    return {"sim_episodes": len(doc["episodes"]), "sim_media": n_media}
