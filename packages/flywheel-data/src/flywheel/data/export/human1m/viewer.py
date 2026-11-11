"""The static explorer: HTML + three.js, opened straight from disk, no server.

    viewer/index.html, app.js, style.css     copied from `static/`
    viewer/data/index.js                      gallery, summary, status of every clip
    viewer/data/ep/<episode_id>.js            one episode: subtasks, 2D and 3D hands
    viewer/media/<episode_id>.mp4             the encoded episode (also joined into a shard)
    viewer/posters/<episode_id>.jpg

Data are `.js` files that set a global, because browsers refuse `fetch` on `file://`;
an episode file is loaded by adding a script tag. 2D keypoints are pixels of the
encoded video; 3D points are millimetres, in the world when the camera pose is known
(EgoDex) and in the camera frame otherwise.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.data.export.human1m.build import ClipRow, Item
from flywheel.data.export.human1m.frames import SIDES, project
from flywheel.data.export.human1m.video import Encoder

STATIC = Path(__file__).with_name("static")
OFF_IMAGE = -10000  # a joint behind the camera; the page draws no bone to it
SOURCE_LABEL = {"ego_video": "Team tray", "egodex": "EgoDex"}


def _js(name: str, value: Any) -> str:
    return f"window.{name} = {json.dumps(value, ensure_ascii=False, separators=(',', ':'))};\n"


def episode_payload(item: Item) -> dict[str, Any]:
    ep = item.shard_episode
    assert ep is not None
    f = ep.frames
    t = f.frames
    world = f.camera_position is not None and f.camera_rotation is not None
    rotation = None
    if world:
        q = np.asarray(f.camera_rotation, dtype=np.float64)  # qx qy qz qw
        x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
        rotation = np.stack([
            np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
            np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
            np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1),
        ], axis=1)
    hands2d: dict[str, list[Any]] = {}
    hands3d: dict[str, list[Any]] = {}
    for side in SIDES:
        p = f.hands[side].astype(np.float64)
        mask = f.mask(side)
        pixels, _ = project(p, f.intrinsic)
        if world:
            assert rotation is not None and f.camera_position is not None
            p = np.einsum("tij,tkj->tki", rotation, p) + f.camera_position[:, None, :]
        pixels = np.nan_to_num(pixels, nan=OFF_IMAGE, posinf=OFF_IMAGE, neginf=OFF_IMAGE)
        hands2d[side] = [np.round(pixels[i]).astype(int).reshape(-1).tolist() if mask[i]
                         else None for i in range(t)]
        hands3d[side] = [np.round(p[i] * 1000).astype(int).reshape(-1).tolist()
                         if np.isfinite(p[i]).all() else None for i in range(t)]
    head = None
    if world:
        assert rotation is not None and f.camera_position is not None
        forward = rotation[:, :, 2]
        head = {"position": np.round(f.camera_position * 1000).astype(int).tolist(),
                "forward": np.round(forward, 3).tolist()}
    return {
        "id": ep.episode_id, "title": item.row.title, "task": ep.task, "fps": ep.fps,
        "frames": t, "video": f"media/{ep.episode_id}.mp4", "size": list(f.image_size),
        "space": "world" if world else "camera",
        "subtasks": [{"start": s.start, "end": s.end, "text": s.text, "source": s.source}
                     for s in ep.subtasks],
        "hands2d": hands2d, "hands3d": hands3d, "head": head,
        "meta": {"source": SOURCE_LABEL.get(item.source.source_detail, item.source.source_detail),
                 "shard": item.view.shard if item.view else None,
                 "environment": ep.environment, "scene": ep.scene, "scene_id": ep.scene_id,
                 "collector_id": ep.collector_id, "intrinsic": [round(float(v), 2) for v in (
                     f.intrinsic[0, 0], f.intrinsic[1, 1], f.intrinsic[0, 2], f.intrinsic[1, 2])],
                 **{k: v for k, v in ep.extra.items() if k != "title"}},
    }


def gallery_entry(item: Item) -> dict[str, Any]:
    ep = item.shard_episode
    assert ep is not None
    return {"id": ep.episode_id, "title": item.row.title, "task": ep.task,
            "subtasks": sorted({s.text for s in ep.subtasks}),
            "source": SOURCE_LABEL.get(item.source.source_detail, item.source.source_detail),
            "seconds": round(ep.frames.frames / ep.fps, 2), "qa": item.row.qa,
            "hands": item.row.hands_visible, "pose": item.bundle.pose_source,
            "poster": f"posters/{ep.episode_id}.jpg", "n_subtasks": len(ep.subtasks)}


def write_viewer(out: Path, items: Sequence[Item], summary: dict[str, Any],
                 rows: Sequence[ClipRow], encoder: Encoder | None,
                 media_from: Path | None = None) -> int:
    """Write the explorer for the exported `items` under `out`; posters are made with
    `encoder` (or copied from `media_from/../posters`) and media copied from
    `media_from` when it is not `out/media`. Returns the number of episodes."""
    out.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "style.css"):
        shutil.copyfile(STATIC / name, out / name)
    (out / "data" / "ep").mkdir(parents=True, exist_ok=True)
    (out / "posters").mkdir(parents=True, exist_ok=True)
    (out / "media").mkdir(parents=True, exist_ok=True)
    chosen = [i for i in items if i.shard_episode is not None]
    for item in chosen:
        ep = item.shard_episode
        assert ep is not None
        eid = ep.episode_id
        if media_from is not None and media_from.resolve() != (out / "media").resolve():
            shutil.copyfile(media_from / f"{eid}.mp4", out / "media" / f"{eid}.mp4")
        poster = out / "posters" / f"{eid}.jpg"
        if encoder is not None:
            carry = ep.subtasks[min(1, len(ep.subtasks) - 1)]
            encoder.poster(out / "media" / f"{eid}.mp4", poster,
                           (carry.start + carry.end) // 2, ep.fps)
        elif media_from is not None:
            shutil.copyfile(media_from.parent / "posters" / f"{eid}.jpg", poster)
        (out / "data" / "ep" / f"{eid}.js").write_text(
            f"window.H1M_EPISODES = window.H1M_EPISODES || {{}};\n"
            f"window.H1M_EPISODES[{json.dumps(eid)}] = "
            f"{json.dumps(episode_payload(item), separators=(',', ':'))};\n")
    index = {"episodes": [gallery_entry(i) for i in chosen], "summary": summary,
             "status": [{k: getattr(r, k) for k in (
                 "source", "clip", "episode_id", "seconds", "fps", "width", "height", "deid",
                 "pose_source", "qa", "decision", "reason", "hands_visible", "bone_cv")}
                 for r in rows]}
    (out / "data" / "index.js").write_text(_js("H1M_INDEX", index))
    (out / "data" / "index.json").write_text(json.dumps(index, ensure_ascii=False) + "\n")
    return len(chosen)


def pick_sample(items: Sequence[Item], n: int) -> list[Item]:
    """`n` exported episodes, alternating shards: within a shard QA pass first, then the
    most hand-visible, one per task while tasks last. Deterministic."""
    by_shard: dict[str, list[Item]] = {}
    for item in items:
        if item.shard_episode is not None and item.view is not None:
            by_shard.setdefault(item.view.shard, []).append(item)
    queues = []
    for shard in sorted(by_shard):
        ranked = sorted(by_shard[shard], key=lambda i: (
            i.row.qa != "pass", -(i.row.hands_visible or 0), i.row.episode_id))
        first: list[Item] = []
        rest: list[Item] = []
        seen: set[str] = set()
        for item in ranked:
            key = item.task
            (rest if key in seen else first).append(item)
            seen.add(key)
        queues.append(first + rest)
    out: list[Item] = []
    while len(out) < n and any(queues):
        for queue in queues:
            if queue and len(out) < n:
                out.append(queue.pop(0))
    return out
