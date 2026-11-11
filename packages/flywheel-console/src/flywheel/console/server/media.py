"""Read-only media and episode data behind ``/api/poster``, ``/api/strip`` and friends.

Egocentric frames come only from ``*.deid.mp4`` files of a pipeline work dir, or from the
viewer export that the console mounts at ``/ego/``. Robot episodes come from the LeRobot
folders named by the ``lerobot`` field of the seed catalog rows.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from flywheel.console.index import posters
from flywheel.console.paths import PathDenied, active, deid_only, guard
from flywheel.console.server.runner import NotFound

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
_lock = threading.Lock()
_rows_cache: tuple[float, list[dict[str, Any]]] | None = None
_layout: dict[str, dict[str, list[tuple[int, str]]]] = {}


def seed_rows() -> list[dict[str, Any]]:
    """Seed catalog rows, re-read when the seed file changes."""
    global _rows_cache
    from flywheel.console.index.robot import load_rows

    paths = active()
    f = paths.seed / "catalog.yaml"
    mt = f.stat().st_mtime if f.is_file() else 0.0
    with _lock:
        if _rows_cache is None or _rows_cache[0] != mt:
            _rows_cache = (mt, load_rows(paths))
        return _rows_cache[1]


def _allowed(p: Path) -> bool:
    try:
        guard(p, [active().fw_root])
    except (PathDenied, OSError):
        return False
    return True


def _jload(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ mounts
def ego_viewer_dir() -> Path | None:
    """The viewer export folder served at ``/ego/`` (first seed row with ``ego_viewer``)."""
    for r in seed_rows():
        if r.get("ego_viewer"):
            p = active().fw_root / str(r["ego_viewer"])
            return p if _allowed(p) else None
    return None


def lerobot_dir(ds: str) -> Path:
    """LeRobot folder of dataset ``ds``; ``NotFound`` when the id has no ``lerobot`` field."""
    for r in seed_rows():
        if str(r.get("id")) == ds and r.get("lerobot"):
            p = active().fw_root / str(r["lerobot"])
            if _allowed(p):
                return p
    raise NotFound(ds)


def media_root(ds: str) -> Path:
    return lerobot_dir(ds) / "videos" / "chunk-000" / "egocentric"


# ------------------------------------------------------------------ egocentric pipeline
def work_dir(work: str) -> Path:
    if not NAME_RE.match(str(work or "")):
        raise ValueError("bad work name")
    d = active().fw_root / "pipeline" / work
    if not _allowed(d) or not (d / "egocentric").is_dir():
        raise NotFound(work)
    return d


def deid_path(d: Path, ep: str) -> Path | None:
    """The episode's ``*.deid.mp4``, or ``None``. A raw video is never returned."""
    if not NAME_RE.match(str(ep or "")):
        raise ValueError("bad episode id")
    b = _jload(d / "egocentric" / ep / "bundle.json")
    if not isinstance(b, dict) or not b.get("mp4"):
        return None
    p = Path(b["mp4"])
    try:
        # judge the resolved file: a ``*.deid.mp4`` symlink to a raw clip must not pass
        deid_only(guard(p, [active().fw_root]))
    except (PathDenied, OSError, ValueError):
        return None
    return p if _allowed(p) and p.is_file() else None


def work_episodes(work: str) -> list[dict[str, Any]]:
    d = work_dir(work)
    qa = {r.get("episode_id"): r.get("decision") for r in _jsonl(d / "qa" / "egocentric.jsonl")}
    out: list[dict[str, Any]] = []
    for e in sorted((d / "egocentric").iterdir()):
        if not e.is_dir():
            continue
        b = _jload(e / "bundle.json") or {}
        out.append(
            {"episode_id": e.name, "deid": deid_path(d, e.name) is not None,
             "frames": b.get("frames"), "qa": qa.get(e.name)}
        )  # fmt: skip
    return out


def episode_video(work: str, ep: str) -> Path:
    """De-identified video of an episode, for a pipeline work dir or a viewer dataset id.

    ``NotFound`` (404) when there is none. Pipeline: the ``mp4`` of ``bundle.json`` when it is a
    ``*.deid.mp4``. Viewer row: ``<ego_viewer>/media/<ep>.mp4`` (the Human-1M export, built
    from de-identified clips only).
    """
    if not NAME_RE.match(str(work or "")) or not NAME_RE.match(str(ep or "")):
        raise ValueError("bad work or episode id")
    try:
        vp = deid_path(work_dir(work), ep)
    except NotFound:
        vp = None
        for r in seed_rows():
            if str(r.get("id")) == work and r.get("ego_viewer"):
                p = active().fw_root / str(r["ego_viewer"]) / "media" / f"{ep}.mp4"
                if _allowed(p) and p.is_file():
                    vp = p
                break
    if vp is None:
        raise NotFound("no deid video")
    return vp


def _cached(name: str) -> Path:
    cdir = active().cache / "posters"
    cdir.mkdir(parents=True, exist_ok=True)
    return cdir / name


def _fresh(cf: Path, src: Path) -> bool:
    return cf.is_file() and cf.stat().st_mtime >= src.stat().st_mtime


def _write(cf: Path, body: bytes) -> None:
    tmp = cf.with_name(cf.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(body)
    os.replace(tmp, cf)


def poster_jpeg(work: str, ep: str, w: int = 320) -> bytes:
    """Middle-frame JPEG of the episode's de-identified video; ``NotFound`` when none."""
    vp = episode_video(work, ep)
    w = max(64, min(1280, int(w)))
    cf = _cached(f"{work}_{ep}_{w}.jpg")
    if _fresh(cf, vp):
        return cf.read_bytes()
    try:
        body = posters.poster_jpeg(vp, w)
    except (FileNotFoundError, ValueError) as e:
        raise NotFound("unreadable deid video") from e
    _write(cf, body)
    return body


def ego_strip_jpeg(work: str, ep: str, n: int = 8) -> bytes:
    """Filmstrip JPEG of ``n`` frames of the de-identified video; ``NotFound`` when none."""
    vp = episode_video(work, ep)
    n = max(2, min(24, int(n)))
    cf = _cached(f"strip_{work}_{ep}_{n}.jpg")
    if _fresh(cf, vp):
        return cf.read_bytes()
    try:
        body = posters.strip_jpeg(vp, n)
    except (FileNotFoundError, ValueError) as e:
        raise NotFound("unreadable deid video") from e
    _write(cf, body)
    return body


# ------------------------------------------------------------------ robot (LeRobot) episodes
def _check_ds_ep(ds: str, ep: int) -> None:
    if not NAME_RE.match(ds or "") or not 0 <= ep < 100000:
        raise ValueError("bad ds/ep")
    lerobot_dir(ds)


def layout(ds: str) -> dict[str, list[tuple[int, str]]]:
    if ds not in _layout:
        al = _jload(lerobot_dir(ds) / "meta" / "action_layout.json") or {}
        groups: dict[str, list[tuple[int, str]]] = {}
        for i, d in enumerate(al.get("dimensions") or []):
            groups.setdefault(d["group"], []).append((i, d.get("name") or f"{d['group']}[{i}]"))
        _layout[ds] = groups
    return _layout[ds]


def episode_json(ds: str, ep: int) -> bytes:
    """Downsampled (50 -> 10 Hz) action and state series of one robot episode, as JSON bytes."""
    _check_ds_ep(ds, ep)
    path = active().cache / f"ep_{ds}_{ep:06d}.json"
    if path.is_file():
        return path.read_bytes()
    import numpy as np
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    pf = lerobot_dir(ds) / "data" / "chunk-000" / f"episode_{ep:06d}.parquet"
    if not pf.is_file():
        raise FileNotFoundError(pf)
    cols = ["action", "timestamp", "observation.hand_joints", "observation.arm_joints",
            "observation.leg_joints", "observation.prev_torso_rpy"]  # fmt: skip
    t = pq.read_table(pf, columns=cols)
    act = np.asarray(t["action"].to_pylist(), dtype=np.float32)
    ts = np.asarray(t["timestamp"].to_pylist(), dtype=np.float32)
    idx = np.arange(0, len(ts), 5)
    out: dict[str, Any] = {
        "ds": ds, "ep": ep, "n": int(len(ts)), "fps": 50, "hz": 10,
        "t": [round(float(x), 3) for x in ts[idx]], "action": {}, "state": {},
    }  # fmt: skip
    for g, dims in layout(ds).items():
        gc = [i for i, _ in dims]
        out["action"][g] = {
            "names": [n for _, n in dims],
            "v": np.round(act[idx][:, gc], 3).T.tolist(),
        }
    state_cols = {
        "hand": "observation.hand_joints",
        "arm": "observation.arm_joints",
        "leg": "observation.leg_joints",
        "torso_rpy": "observation.prev_torso_rpy",
    }
    for g, c in state_cols.items():
        m = np.asarray(t[c].to_pylist(), dtype=np.float32)
        out["state"][g] = {
            "names": [f"{g}[{i}]" for i in range(m.shape[1])],
            "v": np.round(m[idx], 3).T.tolist(),
        }
    body = json.dumps(out, separators=(",", ":")).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, body)
    return body


def strip_jpeg(ds: str, ep: int) -> bytes:
    """Filmstrip of 12 frames of a robot episode's egocentric video."""
    _check_ds_ep(ds, ep)
    cf = active().cache / f"strip_{ds}_{ep:06d}.jpg"
    if cf.is_file():
        return cf.read_bytes()
    body = posters.strip_jpeg(media_root(ds) / f"episode_{ep:06d}.mp4", 12)
    cf.parent.mkdir(parents=True, exist_ok=True)
    _write(cf, body)
    return body
