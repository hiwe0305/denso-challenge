"""Train/serve chain check of checkpoint C (DA-34 task 3.7, docs/he/tray.md 15).

After T1 (0/20 on C's own train scenes, tray.md 14.3) rule 14.1 suspects the chain between
training and serving. This module holds the CPU side of the check; the Psi0 side (train path,
the stats the server loads) is `chain_check_psi0`, run in the Psi0 container.

Part A, open-loop on C's train frames (15.2):

    frames      pick every `stride`-th frame of the T1 episodes in set C, label each with the
                scorer stage from the raw batch's `observation.tray_steps`, give it a noise seed
    serve-path  POST each frame to the Psi0 server's /act as SIMPLE's client does (mp4 frame
                as uint8, raw 32-dim state, `task.lower()`), with `history.reset` and the seed
    summarize-a train path vs serve path vs the recorded actions, by stage; reading of 15.2

Part B, inputs at serve time (15.3):

    compare-b   requests the eval client sent while `replay_server --dump` replayed train
                episodes, against the dataset frames 24k (image, state); with the stats check
                of `chain_check_psi0 stats`, the reading of 15.3

Errors are in the normalized units of Psi0's `bounds` normalization ([-1, 1] per dim,
`ActionStateTransform`), over the dims whose range is not zero (Psi0's `ill_mask`).
Runs in any environment with numpy; `frames` and `compare-b` need pyarrow, `serve-path`
and `compare-b` need PyAV (SIMPLE's venv has both).
"""

from __future__ import annotations

import argparse
import json
import statistics
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_psi0.tray.replay_server import decode, encode

# StepTracker order of the tray scorer (flywheel_simple.tray.predicates.STEP_NAMES); a frame's
# stage is the first step not yet reached, "done" once all seven are.
STEPS = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")
DONE = "done"
EARLY = STEPS[:5]  # approach_a .. reach_b: the steps C passes in closed loop (tray.md 14.3)
ROWS = 24  # rows compared per chunk = action_exec_horizon of eval C's server
IMAGE_KEY = "rgb_head_stereo_left"  # what psi0_decoupled_wbc (SIMPLE 6d10628) sends
DATASET_IMAGE = "observation.images.egocentric"
SEED_BASE = 20_261_107  # noise seed of a frame = SEED_BASE + 10_000 * episode + frame

Array = NDArray[np.float64]


# ---------------------------------------------------------------- shared numerics


def stage_of(steps: Sequence[bool]) -> str:
    """Stage of a frame from its seven StepTracker flags: the first flag still off."""
    for name, on in zip(STEPS, steps, strict=True):
        if not on:
            return name
    return DONE


def live_dims(lo: Array, hi: Array) -> NDArray[np.bool_]:
    """Dims Psi0 really normalizes: not its `ill_mask` (range near zero, e.g. padding)."""
    lo, hi = np.asarray(lo, np.float64), np.asarray(hi, np.float64)
    dead = np.abs(hi - lo) < 1e-4 * (np.abs(hi) + np.abs(lo) + 1e-8)
    return np.asarray(~dead, dtype=np.bool_)


def half_range(lo: Array, hi: Array) -> Array:
    """(hi - lo) / 2: one normalized unit in raw units; 1 on dead dims (not used)."""
    lo, hi = np.asarray(lo, np.float64), np.asarray(hi, np.float64)
    return np.where(live_dims(lo, hi), (hi - lo) / 2.0, 1.0)


def window(actions: Array, t: int, rows: int = ROWS) -> Array:
    """actions[t : t + rows], the last row repeated past the end of the episode."""
    take = np.minimum(np.arange(t, t + rows), len(actions) - 1)
    return np.asarray(np.asarray(actions, np.float64)[take], dtype=np.float64)


def chunk_error(a: Array, b: Array, scale: Array, live: NDArray[np.bool_]) -> float:
    """Mean |a - b| in normalized units over the first ROWS rows and the live dims."""
    a = np.asarray(a, np.float64)[:ROWS]
    b = np.asarray(b, np.float64)[:ROWS]
    return float(np.mean(np.abs(a - b)[:, live] / scale[live]))


def quantile(values: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, np.float64), q)) if values else float("nan")


# ---------------------------------------------------------------- part A


@dataclass(frozen=True)
class Episode:
    """A T1 episode of set C: where it sits in the cut and in the raw batch."""

    seed: int
    episode_index: int  # in the cut of set C
    from_index: int  # global LeRobot index of its frame 0
    length: int
    raw_parquet: Path  # the raw batch episode holding observation.tray_steps


def episodes_of(cut: Path, release: Path, batch: Path, seeds: Sequence[int]) -> list[Episode]:
    """The cut episodes recorded with `seeds`, in that order, traced to their raw batch file."""
    rows = [json.loads(line) for line in (cut / "meta" / "episodes.jsonl").read_text().splitlines()]
    by_seed: dict[int, dict[str, Any]] = {}
    for row in rows:
        seed = int(json.loads(row["environment_config"])["flywheel"]["seed"])
        by_seed[seed] = row
    subset = json.loads((cut / "meta" / "flywheel_subset.json").read_text())
    source = {int(e["episode_index"]): int(e["source_episode_index"]) for e in subset["episodes"]}
    export = json.loads((release / "meta" / "flywheel_export.json").read_text())["episodes"]
    out = []
    for seed in seeds:
        if seed not in by_seed:
            raise ValueError(f"seed {seed} is not in the cut {cut}")
        row = by_seed[seed]
        raw = export[source[int(row["episode_index"])]]
        if int(raw["seed"]) != seed:
            raise ValueError(f"release episode of seed {seed} has seed {raw['seed']}")
        out.append(
            Episode(
                seed=seed,
                episode_index=int(row["episode_index"]),
                from_index=int(row["dataset_from_index"]),
                length=int(row["length"]),
                raw_parquet=batch
                / raw["shard"]
                / "raw"
                / "data"
                / "chunk-000"
                / f"episode_{int(raw['raw_episode']):06d}.parquet",
            )
        )
    return out


def frame_rows(episode: Episode, steps: NDArray[np.bool_], stride: int) -> list[dict[str, Any]]:
    """Every `stride`-th frame of an episode with its stage and noise seed."""
    if len(steps) != episode.length:
        raise ValueError(
            f"seed {episode.seed}: raw episode has {len(steps)} frames, export {episode.length}"
        )
    return [
        {
            "seed": episode.seed,
            "episode_index": episode.episode_index,
            "frame": t,
            "index": episode.from_index + t,
            "stage": stage_of(steps[t].tolist()),
            "noise_seed": SEED_BASE + 10_000 * episode.episode_index + t,
        }
        for t in range(0, episode.length, stride)
    ]


def read_a1(d_path: Sequence[float]) -> dict[str, Any]:
    """Rule A1 of tray.md 15.2 on the per-frame train-vs-serve differences."""
    med, p95 = quantile(d_path, 0.5), quantile(d_path, 0.95)
    if med <= 0.01 and p95 <= 0.03:
        verdict = "match"
    elif med > 0.05 or p95 > 0.15:
        verdict = "serve_chain_fault"
    else:
        verdict = "small_difference"
    return {"frames": len(d_path), "median": med, "p95": p95, "verdict": verdict}


def read_a2(by_stage: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    """Rule A2 of tray.md 15.2: `place` against the early steps and the hold baseline."""
    place = by_stage.get("place")
    early = [by_stage[s]["e"] for s in EARLY if s in by_stage]
    if place is None or not early:
        return {"verdict": "no_data"}
    e_early = statistics.median(early)
    r_place, e_place = place["r"], place["e"]
    if r_place <= 0.7 and e_place <= 1.5 * e_early:
        verdict = "learned_open_loop"
    elif r_place >= 1.0 or e_place >= 2.0 * e_early:
        verdict = "not_learned"
    else:
        verdict = "weak"
    return {
        "r_place": r_place,
        "e_place": e_place,
        "e_early_median": e_early,
        "e_place_over_early": e_place / e_early if e_early else float("inf"),
        "verdict": verdict,
    }


def summarize_a(
    frames: Sequence[Mapping[str, Any]],
    serve: Mapping[int, Array],
    train: Mapping[int, Array],
    actions: Mapping[int, Array],
    lo: Array,
    hi: Array,
) -> dict[str, Any]:
    """Part A: per frame d_path, e (train path vs recorded) and h (hold baseline), by stage.

    `serve` and `train` map a frame's global index to the predicted chunk (raw units, at
    least ROWS rows); `actions` maps an episode index to its recorded (T, 36) actions.
    """
    scale, live = half_range(lo, hi), live_dims(lo, hi)
    d_path: list[float] = []
    per_stage: dict[str, dict[str, list[float]]] = {}
    for f in frames:
        idx, t = int(f["index"]), int(f["frame"])
        recorded = actions[int(f["episode_index"])]
        gt = window(recorded, t)
        hold = np.repeat(np.asarray(recorded, np.float64)[t][None], ROWS, axis=0)
        bucket = per_stage.setdefault(str(f["stage"]), {"e": [], "h": [], "e_serve": []})
        if idx in serve and idx in train:
            d_path.append(chunk_error(serve[idx], train[idx], scale, live))
        if idx in train:
            bucket["e"].append(chunk_error(train[idx], gt, scale, live))
            bucket["h"].append(chunk_error(hold, gt, scale, live))
        if idx in serve:
            bucket["e_serve"].append(chunk_error(serve[idx], gt, scale, live))
    order = [*STEPS, DONE]
    by_stage = {}
    for stage in sorted(per_stage, key=order.index):
        v = per_stage[stage]
        e, h = quantile(v["e"], 0.5), quantile(v["h"], 0.5)
        by_stage[stage] = {
            "frames": len(v["e"]),
            "e": e,
            "e_p90": quantile(v["e"], 0.9),
            "h": h,
            "r": e / h if h else float("inf"),
            "e_serve": quantile(v["e_serve"], 0.5),
        }
    return {
        "frames": len(frames),
        "live_dims": int(live.sum()),
        "rows": ROWS,
        "a1": read_a1(d_path),
        "by_stage": by_stage,
        "a2": read_a2(by_stage),
    }


def act_payload(
    image: NDArray[np.uint8], state: Array, instruction: str, noise_seed: int
) -> dict[str, Any]:
    """An /act body as SIMPLE's `HttpActionClient.query_action` builds it, starting an episode."""
    body: dict[str, Any] = encode(
        {
            "image": {IMAGE_KEY: np.ascontiguousarray(image, dtype=np.uint8)},
            "instruction": instruction,
            "history": {"reset": True, "seed": int(noise_seed)},
            "state": {"states": np.asarray(state, np.float32).reshape(1, -1)},
            "condition": {},
            "gt_action": [],
            "dataset_name": "simple",
            "timestamp": "chain-check",
        }
    )
    return body


def post_act(server: str, body: Mapping[str, Any], timeout_s: float = 300.0) -> Array:
    request = urllib.request.Request(
        f"http://{server}/act",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as reply:
        payload = decode(json.loads(reply.read()))
    if not isinstance(payload, dict) or "action" not in payload:
        raise RuntimeError(f"server answered without an action: {str(payload)[:300]}")
    return np.asarray(payload["action"], np.float64)


def video_frames(path: Path) -> list[NDArray[np.uint8]]:
    """All frames of an episode mp4 as RGB uint8, in order (PyAV, as LeRobot's `pyav`)."""
    import av  # type: ignore[import-not-found]  # SIMPLE's venv

    with av.open(str(path)) as container:
        return [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]


def read_parquet(path: Path, columns: Sequence[str]) -> dict[str, Array]:
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    table = pq.read_table(path, columns=list(columns))
    return {c: np.stack(table.column(c).to_numpy(zero_copy_only=False)) for c in columns}


def task_of(cut: Path) -> str:
    """The lower-cased task string, as SimpleRepackTransform feeds it in training."""
    rows = [json.loads(line) for line in (cut / "meta" / "tasks.jsonl").read_text().splitlines()]
    if len(rows) != 1:
        raise ValueError(f"{cut} has {len(rows)} tasks, expected 1")
    return str(rows[0]["task"]).lower()


def episode_file(cut: Path, episode_index: int, kind: str) -> Path:
    name = f"episode_{episode_index:06d}"
    if kind == "data":
        return cut / "data" / "chunk-000" / f"{name}.parquet"
    return cut / "videos" / "chunk-000" / "egocentric" / f"{name}.mp4"


# ---------------------------------------------------------------- part B


def psnr(a: NDArray[np.uint8], b: NDArray[np.uint8]) -> float:
    mse = float(np.mean((np.asarray(a, np.float64) - np.asarray(b, np.float64)) ** 2))
    return float("inf") if mse == 0 else 10.0 * np.log10(255.0**2 / mse)


def image_metrics(served: NDArray[Any], data: NDArray[np.uint8]) -> dict[str, Any]:
    """Shape, dtype, channel order and PSNR of a served image against the dataset frame."""
    out: dict[str, Any] = {
        "served_shape": list(served.shape),
        "served_dtype": str(served.dtype),
        "data_shape": list(data.shape),
    }
    if served.shape != data.shape:
        return out
    as_is = np.asarray(served, np.float64)
    out["mae"] = float(np.mean(np.abs(as_is - data)))
    out["mae_channels_reversed"] = float(np.mean(np.abs(as_is[..., ::-1] - data)))
    out["psnr"] = psnr(np.clip(served, 0, 255).astype(np.uint8), data)
    return out


def read_b2(first: Mapping[str, Any]) -> dict[str, Any]:
    """Rule B2 of tray.md 15.3 on the frame-0 image metrics."""
    expected = [360, 640, 3]
    if first["served_shape"] != expected or first["served_dtype"] != "uint8":
        return {"verdict": "differs", "why": "shape or dtype"}
    if first["mae_channels_reversed"] < first["mae"]:
        return {"verdict": "differs", "why": "channel order"}
    if first["psnr"] >= 30.0:
        return {"verdict": "match"}
    if first["psnr"] < 20.0:
        return {"verdict": "differs", "why": "pixels (camera, pose, render or colour)"}
    return {"verdict": "report"}


def state_metrics(served: Array, data: Array, lo: Array, hi: Array) -> list[dict[str, Any]]:
    """Per dim: frame-0 and median |diff| (normalized), best-correlated dataset dim, slope."""
    served, data = np.asarray(served, np.float64), np.asarray(data, np.float64)
    n = data.shape[1]
    scale, live = half_range(lo[:n], hi[:n]), live_dims(lo[:n], hi[:n])
    diff = np.abs(served[:, :n] - data) / scale
    out = []
    for i in range(n):
        row: dict[str, Any] = {
            "dim": i,
            "live": bool(live[i]),
            "frame0": float(diff[0, i]),
            "median": float(np.median(diff[:, i])),
        }
        x = served[:, i]
        if live[i] and np.std(x) > 1e-9:
            corr = [
                abs(float(np.corrcoef(x, data[:, j])[0, 1])) if np.std(data[:, j]) > 1e-9 else 0.0
                for j in range(n)
            ]
            row["best_match"] = int(np.argmax(corr))
            row["corr_self"] = corr[i]
            y = data[:, i]
            row["slope"] = float(np.polyfit(y, x, 1)[0]) if np.std(y) > 1e-9 else None
        out.append(row)
    return out


def read_b3(dims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rule B3 of tray.md 15.3."""
    live = [d for d in dims if d["live"]]
    bad = [
        d["dim"]
        for d in live
        if d["median"] > 0.2
        or d.get("best_match", d["dim"]) != d["dim"]
        or (d.get("slope") is not None and not 0.5 <= d["slope"] <= 2.0)
    ]
    if bad:
        return {"verdict": "differs", "dims": bad}
    if all(d["median"] <= 0.05 for d in live):
        return {"verdict": "match"}
    return {"verdict": "report", "dims": [d["dim"] for d in live if d["median"] > 0.05]}


def dumped_requests(dump: Path) -> list[dict[str, Any]]:
    """The requests `replay_server --dump` saved, in order, arrays decoded."""
    rows = []
    for meta in sorted(dump.glob("req-*.json")):
        row = json.loads(meta.read_text())
        with np.load(meta.with_suffix(".npz")) as arrays:
            row["arrays"] = {k: arrays[k] for k in arrays.files}
        rows.append(row)
    return rows


def compare_episode(
    requests: Sequence[Mapping[str, Any]],
    frames: Sequence[NDArray[np.uint8]],
    states: Array,
    lo: Array,
    hi: Array,
    task: str,
    chunk: int = ROWS,
) -> dict[str, Any]:
    """B2 and B3 for one replayed episode: request k against dataset frame chunk * k."""
    ks = [k for k in range(len(requests)) if chunk * k < len(frames)]
    images = [
        image_metrics(requests[k]["arrays"][f"image.{IMAGE_KEY}"], frames[chunk * k]) for k in ks
    ]
    served = np.stack([requests[k]["arrays"]["state.states"].reshape(-1) for k in ks])
    dims = state_metrics(served, states[[chunk * k for k in ks]], lo, hi)
    instructions = sorted({str(r.get("instruction")) for r in requests})
    return {
        "requests": len(requests),
        "compared": len(ks),
        "image_keys": sorted({k for r in requests for k in r.get("image_keys", [])}),
        "instructions": instructions,
        "instruction_matches_train": instructions == [task],
        "image_frame0": images[0],
        "psnr_by_request": [i.get("psnr") for i in images],
        "b2": read_b2(images[0]),
        "state_dims": dims,
        "b3": read_b3(dims),
    }


# ---------------------------------------------------------------- CLI


def _stats(path: Path) -> tuple[Array, Array, Array, Array]:
    stats = json.loads(path.read_text())
    return (
        np.asarray(stats["action"]["min"], np.float64),
        np.asarray(stats["action"]["max"], np.float64),
        np.asarray(stats["states"]["min"], np.float64),
        np.asarray(stats["states"]["max"], np.float64),
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _chunks(path: Path) -> dict[int, Array]:
    return {int(r["index"]): np.asarray(r["action"], np.float64) for r in _jsonl(path)}


def _cmd_frames(args: argparse.Namespace) -> int:
    rows = []
    for ep in episodes_of(args.cut, args.release, args.batch, args.seed):
        steps = read_parquet(ep.raw_parquet, ["observation.tray_steps"])["observation.tray_steps"]
        rows.extend(frame_rows(ep, steps > 0.5, args.stride))
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(json.dumps({"frames": len(rows), "out": str(args.out)}))
    return 0


def _cmd_serve_path(args: argparse.Namespace) -> int:
    frames = _jsonl(args.frames)
    done = set(_chunks(args.out)) if args.out.exists() else set()
    task = task_of(args.cut)
    by_episode: dict[int, list[dict[str, Any]]] = {}
    for f in frames:
        by_episode.setdefault(int(f["episode_index"]), []).append(f)
    with args.out.open("a", encoding="utf-8") as out:
        for ep, rows in by_episode.items():
            todo = [f for f in rows if int(f["index"]) not in done]
            if not todo:
                continue
            video = video_frames(episode_file(args.cut, ep, "video"))
            states = read_parquet(episode_file(args.cut, ep, "data"), ["states"])["states"]
            for f in todo:
                t = int(f["frame"])
                body = act_payload(video[t], states[t], task, int(f["noise_seed"]))
                action = post_act(args.server, body)
                out.write(json.dumps({"index": int(f["index"]), "action": action.tolist()}) + "\n")
                out.flush()
    return 0


def _cmd_summarize_a(args: argparse.Namespace) -> int:
    frames = _jsonl(args.frames)
    lo, hi, _, _ = _stats(args.stats)
    actions = {
        ep: read_parquet(episode_file(args.cut, ep, "data"), ["action"])["action"]
        for ep in sorted({int(f["episode_index"]) for f in frames})
    }
    result = summarize_a(frames, _chunks(args.serve), _chunks(args.train), actions, lo, hi)
    text = json.dumps(result, indent=1)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)
    return 0


def _cmd_compare_b(args: argparse.Namespace) -> int:
    _, _, slo, shi = _stats(args.stats)
    episodes = {ep.seed: ep for ep in episodes_of(args.cut, args.release, args.batch, args.seed)}
    task = task_of(args.cut)
    result: dict[str, Any] = {"episodes": {}}
    for seed, dump in zip(args.seed, args.dump, strict=True):
        ep = episodes[seed]
        states = read_parquet(episode_file(args.cut, ep.episode_index, "data"), ["states"])[
            "states"
        ]
        video = video_frames(episode_file(args.cut, ep.episode_index, "video"))
        result["episodes"][str(seed)] = compare_episode(
            dumped_requests(dump), video, states, slo, shi, task
        )
    if args.stats_check:
        result["b1"] = json.loads(args.stats_check.read_text())
    text = json.dumps(result, indent=1)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("frames")
    p.add_argument("--cut", type=Path, required=True, help="LeRobot dir of set C")
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--batch", type=Path, required=True, help="raw batch of the release")
    p.add_argument("--seed", type=int, action="append", required=True)
    p.add_argument("--stride", type=int, default=10)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=_cmd_frames)

    p = sub.add_parser("serve-path")
    p.add_argument("--cut", type=Path, required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--server", default="127.0.0.1:22185")
    p.add_argument("--out", type=Path, required=True, help="jsonl, appended (resumable)")
    p.set_defaults(fn=_cmd_serve_path)

    p = sub.add_parser("summarize-a")
    p.add_argument("--cut", type=Path, required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--serve", type=Path, required=True)
    p.add_argument("--train", type=Path, required=True)
    p.add_argument("--stats", type=Path, required=True, help="stats_psi0.json of set C")
    p.add_argument("--json", type=Path)
    p.set_defaults(fn=_cmd_summarize_a)

    p = sub.add_parser("compare-b")
    p.add_argument("--cut", type=Path, required=True)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--seed", type=int, action="append", required=True)
    p.add_argument("--dump", type=Path, action="append", required=True, help="one per --seed")
    p.add_argument("--stats", type=Path, required=True)
    p.add_argument("--stats-check", type=Path, help="json of chain_check_psi0 stats (B1)")
    p.add_argument("--json", type=Path)
    p.set_defaults(fn=_cmd_compare_b)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
