"""The labelling-model trial before choosing (design 6.7.4; DA-04 notes; D3, D6).

30 EgoDex frames and 30 SIMPLE render frames of the two-table task, 3 clips of 10
frames each per domain, every clip one second either side of a grasp. Each model is
asked, per clip, in which image the hand closes on the object (step boundary), and,
per frame, where the hand grasps the object (pointing). Measured:

    boundary error   |answer - reference| in video frames (EgoDex 30 Hz, SIMPLE 50 Hz)
    pointing hits    share of frames whose point is within `HIT_SHARE` of the image
                     diagonal from the reference, and the median distance in pixels
    latency          seconds per query, as the client saw it
    VRAM             measured on the host while the model was loaded (given by the
                     caller; the lane cannot see the GPU)

References. EgoDex: the grasp is the middle of the rule's dwell on the tracked pose
(E-B); the grasp point is the midpoint of thumb and index tips, where it is at the
grasp while the object waits on the table, where it is at that frame once the hand
carries it, projected into each frame. The rule run on E-A (RGB only) is scored
against the same reference, as the baseline a model must beat on the team's videos.
SIMPLE: the grasp is the first frame where the hand that closes has moved half of
its joint range (`observation.hand_joints` of psi-data); grasp points were marked on
the 30 frames by whoever made the reference file, which says who.

The result is a `Decision` (`verdict = open`): Claude ran the trial, Hiếu decides.
"""

from __future__ import annotations

import json
import time
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from flywheel.contracts.entities import Decision
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import (
    LABELS,
    POSE,
    POSE_EA,
    bundle_dir,
    read_bundle,
    read_episodes,
)
from flywheel.data.ingest.egocentric.pose import EgoPose, load_pose
from flywheel.data.ingest.egocentric.segments import find_events
from flywheel.data.ingest.egocentric.video import jpeg, read_frames
from flywheel.data.ingest.egocentric.vlm import (
    BOUNDARY_PROMPT,
    EVENTS,
    POINT_PROMPT,
    VisionModel,
    parse_index,
    parse_point,
)

CLIPS = 3
PER_CLIP = 10
FRAMES = CLIPS * PER_CLIP
HIT_SHARE = 0.05  # of the image diagonal; [Đề xuất]
BOUNDARY_OK_FRAMES = 10  # median error under which model boundaries help; [Đề xuất]
POINT_OK = 0.6  # hit rate over which model grasp points are used; [Đề xuất]
SIMPLE_HAND = "observation.hand_joints"
SIMPLE_VIDEO = "videos/chunk-000/egocentric/episode_{index:06d}.mp4"
SIMPLE_DATA = "data/chunk-000/episode_{index:06d}.parquet"


@dataclass(frozen=True)
class Clip:
    domain: str  # egodex or simple
    episode: str
    mp4: Path
    frames: list[int]
    grasp: int  # reference boundary frame
    points: list[tuple[float, float] | None]  # reference grasp point per frame (shares)
    size: tuple[int, int]
    obj: str
    instruction: str


def clip_frames(grasp: int, total: int, half: int) -> list[int]:
    lo, hi = max(grasp - half, 0), min(grasp + half, total - 1)
    return [int(round(x)) for x in np.linspace(lo, hi, PER_CLIP)]


def egodex_clips(work: Path) -> list[Clip]:
    """The first CLIPS episodes, by id, whose rule found a settled grasp on E-B."""
    clips: list[Clip] = []
    for episode in sorted(read_episodes(work), key=lambda e: e.episode_id):
        folder = bundle_dir(work, episode.episode_id)
        labels = json.loads((folder / LABELS).read_text())
        grasp = next((e for e in labels["events"] if e["kind"] == "grasp" and not e["reasons"]
                      and e["dwell"] is not None), None)
        bundle = read_bundle(work, episode.episode_id)
        if grasp is None or bundle.hdf5 is None or labels["side"] is None:
            continue
        if any(c.instruction == bundle.instruction for c in clips):
            continue
        pose = load_pose(folder / POSE)
        frames = clip_frames(grasp["frame"], bundle.frames, int(bundle.fps))
        k = np.array(bundle.intrinsic)
        points = [_grasp_point(pose, labels["side"], grasp["frame"], f, k, bundle.image_size)
                  for f in frames]
        clips.append(Clip("egodex", episode.episode_id, Path(bundle.mp4), frames,
                          grasp["frame"], points, bundle.image_size,
                          bundle.objects[0] if bundle.objects else "object",
                          bundle.instruction))
        if len(clips) == CLIPS:
            break
    return clips


def _grasp_point(pose: EgoPose, side: str, grasp: int, frame: int, k: Any,
                 size: tuple[int, int]) -> tuple[float, float] | None:
    held = pose.tips(side)[max(frame, grasp)]
    world = np.append((held[0] + held[1]) / 2, 1.0)
    local = np.linalg.inv(pose.camera[frame].astype(np.float64)) @ world
    if not np.isfinite(local).all() or local[2] <= 0:
        return None
    u = k[0, 0] * local[0] / local[2] + k[0, 2]
    v = k[1, 1] * local[1] / local[2] + k[1, 2]
    if not (0 <= u < size[0] and 0 <= v < size[1]):
        return None
    return float(u / size[0]), float(v / size[1])


def simple_grasp(hand: Any) -> int:
    """First frame where the hand that moves most has covered half its range."""
    q = np.asarray(hand, dtype=np.float64)
    moved = np.abs(q - q[0])
    sides = [moved[:, :7].sum(axis=1), moved[:, 7:].sum(axis=1)]
    track = max(sides, key=lambda m: float(m.max()))
    return int(np.argmax(track >= 0.5 * track.max()))


def simple_clips(dataset: Path, reference: Mapping[str, Any]) -> list[Clip]:
    """Clips of the psi-data episodes the reference file marks, grasp from hand joints."""
    info = json.loads((dataset / "meta" / "info.json").read_text())
    shape = info["features"]["observation.images.egocentric"]["shape"]
    size = (int(shape[1]), int(shape[0]))
    fps = int(info["fps"])
    clips: list[Clip] = []
    for key in sorted(reference["episodes"], key=int):
        index = int(key)
        table = pq.read_table(dataset / SIMPLE_DATA.format(index=index), columns=[SIMPLE_HAND])
        hand = np.stack(table.column(SIMPLE_HAND).to_numpy(zero_copy_only=False))
        grasp = simple_grasp(hand)
        frames = clip_frames(grasp, len(hand), fps)
        marked = reference["episodes"][key]
        points = [None if marked.get(str(f)) is None else tuple(marked[str(f)]) for f in frames]
        clips.append(Clip("simple", f"psi_data:{index}", dataset / SIMPLE_VIDEO.format(index=index),
                          frames, grasp, points, size, reference.get("object", "object"),
                          reference.get("instruction", "")))
    return clips


def _ask(model: VisionModel, prompt: str, images: Sequence[bytes]) -> tuple[str | None, float]:
    """The answer and its seconds; None when the call failed (timeout, refused), which
    counts as unparsed."""
    start = time.monotonic()
    try:
        text: str | None = model.complete(prompt, images)
    except OSError:
        text = None
    return text, round(time.monotonic() - start, 2)


def ask_boundary(model: VisionModel, clip: Clip, images: Sequence[bytes]) -> dict[str, Any]:
    prompt = BOUNDARY_PROMPT.format(n=len(images), instruction=clip.instruction,
                                    event=EVENTS["grasp"])
    text, seconds = _ask(model, prompt, images)
    choice = None if text is None else parse_index(text, len(images))
    frame = None if choice is None else clip.frames[choice]
    return {"answer": text, "seconds": seconds, "frame": frame, "reference": clip.grasp,
            "error_frames": None if frame is None else abs(frame - clip.grasp)}


def ask_point(model: VisionModel, clip: Clip, i: int, image: bytes) -> dict[str, Any]:
    text, seconds = _ask(model, POINT_PROMPT.format(object=clip.obj), [image])
    point = None if text is None else parse_point(text, clip.size)
    reference = clip.points[i]
    row: dict[str, Any] = {"frame": clip.frames[i], "answer": text, "seconds": seconds,
                           "point": point,
                           "reference": reference}
    if point is not None and reference is not None:
        w, h = clip.size
        distance = float(np.hypot((point[0] - reference[0]) * w, (point[1] - reference[1]) * h))
        row["distance_px"] = distance
        row["hit"] = distance <= HIT_SHARE * float(np.hypot(w, h))
    return row


def rule_on_ea(work: Path, clips: Sequence[Clip], cfg: EgoConfig) -> list[dict[str, Any]]:
    """The grasp the rule finds on E-A (RGB only) against the E-B reference."""
    rows: list[dict[str, Any]] = []
    for clip in clips:
        path = bundle_dir(work, clip.episode) / POSE_EA
        if not path.is_file():
            rows.append({"episode": clip.episode, "frame": None, "error_frames": None})
            continue
        fps = read_bundle(work, clip.episode).fps
        _, events, _ = find_events(load_pose(path), fps, cfg.segment)
        near = [e.frame for e in events if e.kind == "grasp"]
        frame = min(near, key=lambda f: abs(f - clip.grasp)) if near else None
        rows.append({"episode": clip.episode, "frame": frame, "reference": clip.grasp,
                     "error_frames": None if frame is None else abs(frame - clip.grasp)})
    return rows


def run(
    work: Path, simple: Path, reference: Path, models: Mapping[str, VisionModel],
    cfg: EgoConfig, out: Path, vram: Mapping[str, str] | None = None,
    boundary: Collection[str] | None = None,
) -> dict[str, Any]:
    """Ask every model to point on every frame; ask the models in `boundary` (all by
    default) for the grasp frame of every clip."""
    marked = json.loads(reference.read_text())
    clips = egodex_clips(work) + simple_clips(simple, marked)
    rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for name, model in models.items():
        rows[name] = {"boundary": [], "point": []}
        for clip in clips:
            images = [jpeg(f) for f in read_frames(clip.mp4, clip.frames, cfg.max_image_side_px)]
            if boundary is None or name in boundary:
                rows[name]["boundary"].append({"domain": clip.domain, "episode": clip.episode,
                                               **ask_boundary(model, clip, images)})
            for i, image in enumerate(images):
                rows[name]["point"].append(
                    {"domain": clip.domain, "episode": clip.episode,
                     **ask_point(model, clip, i, image)})
    baseline = rule_on_ea(work, [c for c in clips if c.domain == "egodex"], cfg)
    latencies = {name: list(getattr(m, "latencies_s", [])) for name, m in models.items()}
    summary = summarize(rows, baseline, latencies, vram or {})
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps({"clips": [_clip_json(c) for c in clips],
                                               "rows": rows, "rule_on_ea": baseline},
                                              indent=1, ensure_ascii=False) + "\n")
    decision = make_decision(summary, cfg, marked.get("marked_by", "unknown"))
    (out / "decision.json").write_text(decision.model_dump_json(indent=2) + "\n")
    return {"summary": summary, "decision": decision.id}


def summarize(
    rows: Mapping[str, Mapping[str, list[dict[str, Any]]]], baseline: list[dict[str, Any]],
    latencies: Mapping[str, list[float]], vram: Mapping[str, str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, kinds in rows.items():
        model: dict[str, Any] = {}
        for domain in ("egodex", "simple"):
            errors = [r["error_frames"] for r in kinds["boundary"] if r["domain"] == domain]
            points = [r for r in kinds["point"] if r["domain"] == domain and "hit" in r]
            asked = [r for r in kinds["point"] if r["domain"] == domain
                     and r["reference"] is not None]
            model[domain] = {
                "boundary_errors_frames": errors,
                "boundary_median_frames": _median([e for e in errors if e is not None]),
                "boundary_unparsed": sum(e is None for e in errors),
                "point_frames": len(asked),
                "point_hits": sum(bool(r["hit"]) for r in points),
                "point_hit_rate": sum(bool(r["hit"]) for r in points) / len(asked) if asked
                else None,
                "point_median_px": _median([r["distance_px"] for r in points]),
                "point_unparsed": len(asked) - len(points),
            }
        for kind in ("boundary", "point"):
            model[f"{kind}_seconds_median"] = _median([r["seconds"] for r in kinds[kind]
                                                       if "seconds" in r])
        times = latencies.get(name, [])
        model["latency_median_s"] = _median(times)
        model["latency_p90_s"] = float(np.percentile(times, 90)) if times else None
        model["queries"] = len(times)
        model["vram"] = vram.get(name)
        out[name] = model
    errors = [r["error_frames"] for r in baseline if r["error_frames"] is not None]
    out["rule_on_ea"] = {"boundary_errors_frames": [r["error_frames"] for r in baseline],
                         "boundary_median_frames": _median(errors)}
    return out


def make_decision(summary: Mapping[str, Any], cfg: EgoConfig, marked_by: str) -> Decision:
    models = [k for k in summary if k != "rule_on_ea"]
    asked = [k for k in models
             if any(summary[k][d]["boundary_errors_frames"] for d in ("egodex", "simple"))]

    def boundary(name: str) -> float:
        values = [summary[name][d]["boundary_median_frames"] for d in ("egodex", "simple")]
        known = [v for v in values if v is not None]
        return float(np.mean(known)) if known else float("inf")

    def pointing(name: str) -> float:
        values = [summary[name][d]["point_hit_rate"] for d in ("egodex", "simple")]
        known = [v for v in values if v is not None]
        return float(np.mean(known)) if known else 0.0

    best_boundary = min(asked or models, key=boundary)
    best_point = max(models, key=pointing)
    use_boundary = boundary(best_boundary) <= BOUNDARY_OK_FRAMES
    use_point = pointing(best_point) >= POINT_OK
    reason = (
        f"Boundary: {best_boundary} has the lowest mean of median errors"
        f" ({boundary(best_boundary):.1f} frames);"
        + (" use it for ambiguous events." if use_boundary else
           f" above {BOUNDARY_OK_FRAMES} frames, so ambiguous events go to a person.")
        + f" Pointing: {best_point} hits {pointing(best_point):.0%} of frames;"
        + (" use it for grasp points." if use_point else
           f" under {POINT_OK:.0%}, so grasp points are not taken from a model.")
        + f" SIMPLE grasp points marked by {marked_by}. 3 clips per domain: a small sample."
    )
    return Decision(
        kind="milestone",
        subject_kind="labelling_model",
        subject_id=f"egocentric_labelling@{cfg.version}",
        verdict="open",
        metrics=dict(summary),
        criteria={"boundary_median_frames_max": BOUNDARY_OK_FRAMES, "point_hit_rate_min": POINT_OK,
                  "hit_radius_share_of_diagonal": HIT_SHARE, "clips_per_domain": CLIPS,
                  "frames_per_clip": PER_CLIP,
                  "models": {k: f"{m.name}@{m.revision[:12]} as {m.served}"
                             for k, m in cfg.models.items()}},
        signed_by="claude (DA-04 session); to be signed by Hiếu (PO)",
        reason=reason,
    )


def _clip_json(clip: Clip) -> dict[str, Any]:
    return {"domain": clip.domain, "episode": clip.episode, "mp4": str(clip.mp4),
            "frames": clip.frames, "grasp": clip.grasp, "points": clip.points,
            "size": clip.size, "object": clip.obj}


def _median(values: Sequence[float]) -> float | None:
    return float(np.median(values)) if len(values) else None

