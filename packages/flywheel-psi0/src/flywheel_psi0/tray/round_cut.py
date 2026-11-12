"""The dataset of the round's branch: S70 byte for byte, then the targeted set (DA-34 7.4).

docs/he/tray.md 20.6: `C70_R1` trains on C_70's data, the subset S70 of the paired plan
(`pair_cut.subset_cut`), with the round's targeted episodes after it. Unlike C+
(`cplus_cut`), the stats are not the joined set's own: every run of the pair normalises
with ALL's `meta/stats_psi0.json` (`cut.stats_sha256`, 1c745091...), and so does the
round, so C70_R1 differs from C_70 and C_ALL in the episodes only.

- `join_round` copies the S70 dataset whole (episodes 0..n-1, its meta and ALL's stats
  files, byte for byte), then appends each targeted episode from index n on: parquet
  rewritten by DA-03's `write_episode` (new `episode_index`, `index` after S70's frames),
  videos copied, its `meta/episodes.jsonl` row (environment config, seed) and its
  per-episode stats row carried. Stats are never recomputed.
- Before anything is written, `bounds_problems` checks that the targeted set's actions
  and states lie inside ALL's min and max, dimension by dimension: Psi0 normalises with
  those bounds, and a value outside them is one the model never saw scaled. Outside
  means stop and record a Decision (20.6), so the join refuses, unless `--accept` names a
  signed Decision (`verdict: approved`, subject the round plan) whose
  `metrics.bounds_outside` is exactly what `bounds` reports: then it joins and records
  the excess and the Decision's sha256 in the marker (R13 of tray.md 20.15).
- `round_problems` checks a dataset against the round and the paired plan with JSON
  reads only (the Colab VM runs it before any install): marker, S70's seeds per part and
  row by row, the targeted seeds, renumbering, totals and the stats sha256.
  `base_problems` (rtx3060, needs the S70 dataset) checks the first n episodes' files and
  the stats files byte for byte against S70.

On rtx3060 (workspace PYTHONPATH; `join` imports `flywheel.data`):

    python -m flywheel_psi0.tray.round_cut bounds --data <targeted cut> \
        --stats <S70>/meta/stats_psi0.json
    python -m flywheel_psi0.tray.round_cut join --round configs/runplans/tray/round-tray-c70.yaml \
        --base <cut-all-zone1>/S70/<env> --targeted <targeted cut> --out <dir>/C70_R1/<env> \
        [--accept <bounds decision.json>]
    python -m flywheel_psi0.tray.round_cut check --round <plan> --data <dir>/C70_R1/<env> \
        --base <S70>
    python -m flywheel_psi0.tray.round_cut pack --round <plan> --data <dir>/C70_R1/<env> \
        --out C70_R1.tar
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_psi0.tray.cplus_cut import episode_files
from flywheel_psi0.tray.pair_cut import (
    COPIED_STATS,
    MARKER,
    STATS,
    _dataset_problems,
    cut_problems,
    episode_seed,
    pack,
    read_marker,
    read_rows,
    sha256,
)
from flywheel_psi0.tray.pairplan import TrayPairPlan, subset_lists
from flywheel_psi0.tray.pairround import TrayPairRoundPlan
from flywheel_psi0.tray.runplan import REPO

BOUNDED = ("action", "states")  # the features Psi0 normalises with the stats' min and max


def base_name(plan: TrayPairRoundPlan, pair: TrayPairPlan) -> str:
    """The subset the base branch trains on (S70)."""
    return pair.data_of(pair.branches[plan.base_branch])


def bounds_problems(data: Path, stats: dict[str, Any], first: int = 0) -> list[str]:
    """Episodes from `first` on whose action or states leave the stats' [min, max].

    Compared in float32, the type the stats are stored in. One line per feature: frames
    out, the dimensions concerned and the largest excess as a share of that dimension's
    range, so a Decision can say how far out the data is.
    """
    from flywheel.data.ingest.lerobot import iter_episodes

    low = {k: np.asarray(stats[k]["min"], dtype=np.float32) for k in BOUNDED}
    high = {k: np.asarray(stats[k]["max"], dtype=np.float32) for k in BOUNDED}
    out_frames = dict.fromkeys(BOUNDED, 0)
    frames = 0
    worst = {k: np.zeros_like(low[k]) for k in BOUNDED}
    for episode in iter_episodes(data):
        if episode.episode_index < first:
            continue
        frames += len(episode.timestamp)
        for key in BOUNDED:
            values = np.asarray(getattr(episode, key), dtype=np.float32)
            if values.shape[1] != low[key].shape[0]:
                raise ValueError(f"{key} has {values.shape[1]} dims, the stats {low[key].shape[0]}")
            span = np.maximum(high[key] - low[key], np.float32(1e-12))
            excess = np.maximum(low[key] - values, values - high[key]) / span
            out_frames[key] += int((excess > 0).any(axis=1).sum())
            worst[key] = np.maximum(worst[key], excess.max(axis=0, initial=0.0))
    problems = []
    for key in BOUNDED:
        if out_frames[key]:
            dims = [int(d) for d in np.nonzero(worst[key] > 0)[0]]
            problems.append(
                f"{key}: {out_frames[key]} of {frames} frames outside the stats' [min, max],"
                f" dims {dims}, up to {float(worst[key].max()):.3g} x the range beyond it"
            )
    return problems


def _targeted_problems(
    targeted: Path, marker: dict[str, Any], plan: TrayPairRoundPlan
) -> list[str]:
    """The targeted cut is the round's pinned set: its release, set hash and own seeds."""
    problems = [f"targeted cut: {p}" for p in _targeted_problems_of(marker, plan)]
    own = sorted(episode_seed(r) for r in read_rows(targeted))
    if own != plan.targets.seeds:
        problems.append("targeted cut: the episodes' own seeds are not targets.seeds")
    return problems


def accepted_bounds(decision: Path, plan: TrayPairRoundPlan, outside: list[str]) -> list[str]:
    """Why the Decision at `decision` does not accept exactly `outside` for this round."""
    from flywheel.contracts.entities import Decision

    d = Decision.model_validate_json(decision.read_text(encoding="utf-8"))
    problems = []
    if d.verdict != "approved":
        problems.append(f"verdict {d.verdict!r}, not 'approved'")
    if (d.subject_kind, d.subject_id) != ("round_plan", plan.name):
        problems.append(f"subject {d.subject_kind}:{d.subject_id}, not round_plan:{plan.name}")
    if d.metrics.get("bounds_outside") != outside:
        problems.append("metrics.bounds_outside is not what bounds reports now")
    return problems


def join_round(
    base: Path,
    targeted: Path,
    out: Path,
    plan: TrayPairRoundPlan,
    pair: TrayPairPlan,
    repo: Path = REPO,
    accept: Path | None = None,
) -> dict[str, Any]:
    """Write S70 at `base` and the targeted cut at `targeted` as one dataset at `out`.

    `accept`: a signed Decision that lets exactly the reported bounds excess through.
    """
    from flywheel.data.ingest.lerobot import check_index, iter_episodes, read_info, write_episode

    if out.exists():
        raise FileExistsError(f"{out} exists; a demo set dataset is never overwritten")
    name = base_name(plan, pair)
    problems = cut_problems(base, pair, name, repo)
    tmark = read_marker(targeted)
    if tmark is None:
        problems.append(f"{targeted / 'meta' / MARKER} missing: not a demo-set cut")
    else:
        problems += _targeted_problems(targeted, tmark, plan)
    info, tinfo = read_info(base), read_info(targeted)
    same = ("fps", "features", "data_path", "video_path", "chunks_size", "robot_type")
    differ = [k for k in same if info.get(k) != tinfo.get(k)]
    if differ:
        problems.append(f"{targeted} differs from {base} in {differ}")
    if problems:
        raise ValueError("inputs do not hold: " + "; ".join(problems))
    assert tmark is not None
    stats = json.loads((base / "meta" / STATS).read_text(encoding="utf-8"))
    outside = bounds_problems(targeted, stats)
    bounds: dict[str, Any] | None = None
    if outside and accept is None:
        raise ValueError(
            "the targeted set leaves ALL's stats (tray.md 20.6: stop, record a Decision): "
            + "; ".join(outside)
        )
    if outside and accept is not None:
        refused = accepted_bounds(accept, plan, outside)
        if refused:
            raise ValueError(f"{accept} does not accept the excess: " + "; ".join(refused))
        bounds = {"outside": outside, "decision": accept.name, "decision_sha256": sha256(accept)}

    bmark = read_marker(base)
    assert bmark is not None
    n = int(bmark["n"])
    shutil.copytree(base, out)
    (out / "meta" / MARKER).unlink()
    trows = sorted(read_rows(targeted), key=lambda r: int(r["episode_index"]))
    new = {int(r["episode_index"]): n + i for i, r in enumerate(trows)}
    with (out / "meta" / "episodes.jsonl").open("a", encoding="utf-8") as f:
        for r in trows:
            f.write(json.dumps({**r, "episode_index": new[int(r["episode_index"])]}) + "\n")
    with (out / "meta" / "episodes_stats.jsonl").open("a", encoding="utf-8") as f:
        lines = (targeted / "meta" / "episodes_stats.jsonl").read_text().splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
        for row in sorted(rows, key=lambda r: int(r["episode_index"])):
            f.write(json.dumps({**row, "episode_index": new[int(row["episode_index"])]}) + "\n")
    for old, index in new.items():
        for old_path, new_path in zip(
            episode_files(tinfo, old), episode_files(info, index), strict=True
        ):
            if (targeted / old_path).is_file():
                (out / new_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(targeted / old_path, out / new_path)
    for frames in sorted(iter_episodes(targeted), key=lambda f: f.episode_index):
        write_episode(out, dataclasses.replace(frames, episode_index=new[frames.episode_index]))
    total = n + len(trows)
    written = json.loads((out / "meta" / "info.json").read_text())
    (out / "meta" / "info.json").write_text(
        json.dumps({**written, "splits": {"train": f"0:{total}"}}, indent=4)
    )

    marker = {
        "demo_set": plan.branch,
        "n": total,
        "base": {**bmark, "marker_sha256": sha256(base / "meta" / MARKER)},
        "targeted": {
            **{k: tmark.get(k) for k in ("demo_set", "set_hash", "release_id", "release_hash")},
            "n": len(trows),
            "first_episode_index": n,
            "episodes": [
                {
                    "episode_index": new[int(r["episode_index"])],
                    "targeted_episode_index": int(r["episode_index"]),
                    "seed": episode_seed(r),
                }
                for r in trows
            ],
        },
        "stats": f"cut: {STATS} of {pair.cut.name}, copied with {name}, not recomputed",
    }
    if bounds is not None:
        marker["bounds"] = bounds
    (out / "meta" / MARKER).write_text(json.dumps(marker, indent=2))
    problems = round_problems(out, plan, pair, repo) + base_problems(out, base)
    problems += [f"index of episode {f.episode_index} is off" for f in check_index(out)]
    if problems:
        raise ValueError(f"{out} does not hold after the write: " + "; ".join(problems))
    return marker


def round_problems(
    data: Path, plan: TrayPairRoundPlan, pair: TrayPairPlan, repo: Path = REPO
) -> list[str]:
    """Everything wrong between the dataset at `data` and the round's pins (JSON only)."""
    marker = read_marker(data)
    if marker is None:
        return [f"{data / 'meta' / MARKER} missing: not a demo-set cut"]
    name = base_name(plan, pair)
    subset = pair.subset(name)
    if subset is None or subset.episodes is None:
        return [f"{name} is not a pinned subset of {plan.inherits}"]
    n, k = subset.episodes, len(plan.targets.seeds)
    problems = []
    if (marker.get("demo_set"), marker.get("n")) != (plan.branch, n + k):
        problems.append(
            f"dataset is {marker.get('demo_set')!r} of n={marker.get('n')!r}, not"
            f" {plan.branch} of {n} + {k}"
        )
    rows = read_rows(data)
    base = marker.get("base", {})
    if (base.get("demo_set"), base.get("n")) != (name, n):
        problems.append(f"base is {base.get('demo_set')!r} of n={base.get('n')!r}, not {name}")
    lists = subset_lists(pair, repo).get(name, {})
    base_seeds = []
    for part, sp in zip(base.get("parts", []), subset.parts, strict=False):
        seeds = [int(e["seed"]) for e in part.get("episodes", [])]
        if sorted(seeds) != lists.get(sp.regenerates):
            problems.append(f"base part {sp.regenerates}: seeds are not {name}'s list")
        base_seeds += seeds
    if [episode_seed(r) for r in rows[:n]] != base_seeds or len(base_seeds) != n:
        problems.append(f"episodes 0 .. {n - 1}: their own seeds are not {name}'s, row by row")
    if subset.frames is not None and sum(int(r["length"]) for r in rows[:n]) != subset.frames:
        problems.append(f"episodes 0 .. {n - 1}: lengths do not sum to {name}'s frames")
    targeted = marker.get("targeted", {})
    problems += [f"targeted {p}" for p in _targeted_problems_of(targeted, plan)]
    episodes = targeted.get("episodes", [])
    if [e.get("episode_index") for e in episodes] != list(range(n, n + len(episodes))):
        problems.append(f"targeted episodes are not renumbered from {n}")
    if sorted(episode_seed(r) for r in rows[n:]) != plan.targets.seeds:
        problems.append(f"episodes {n} ..: their own seeds are not targets.seeds")
    return problems + _dataset_problems(data, n + k, None, pair.cut.stats_sha256)


def _targeted_problems_of(targeted: dict[str, Any], plan: TrayPairRoundPlan) -> list[str]:
    release = plan.targets.release
    expected = {
        "set_hash": plan.targets.set_hash,
        "release_hash": release.release_hash if release else None,
        "n": len(plan.targets.seeds),
    }
    return [
        f"{key} is {targeted.get(key)!r}, the round's is {value!r}"
        for key, value in expected.items()
        if targeted.get(key) != value
    ]


def base_problems(data: Path, base: Path) -> list[str]:
    """The first n episodes' parquet and videos, and the stats files, are S70's bytes."""
    marker = read_marker(base)
    if marker is None:
        return [f"{base / 'meta' / MARKER} missing"]
    info = json.loads((base / "meta" / "info.json").read_text(encoding="utf-8"))
    name = marker.get("demo_set", base.name)
    problems = []
    for index in range(int(marker["n"])):
        for rel in episode_files(info, index):
            mine, theirs = data / rel, base / rel
            if theirs.is_file() and (not mine.is_file() or sha256(mine) != sha256(theirs)):
                problems.append(f"{rel} is not {name}'s byte for byte")
    for name in COPIED_STATS:
        if (base / "meta" / name).is_file() and sha256(data / "meta" / name) != sha256(
            base / "meta" / name
        ):
            problems.append(f"meta/{name} is not the base's byte for byte")
    return problems


def _load(path: Path, repo: Path) -> tuple[TrayPairRoundPlan, TrayPairPlan]:
    plan = TrayPairRoundPlan.load(path)
    return plan, TrayPairPlan.load(repo / plan.inherits)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=["bounds", "join", "check", "pack"])
    parser.add_argument("--round", type=Path, help="the round plan")
    parser.add_argument("--base", type=Path, help="join, check: the S70 dataset")
    parser.add_argument("--targeted", type=Path, help="join: the targeted cut")
    parser.add_argument("--data", type=Path, help="bounds, check, pack: a dataset")
    parser.add_argument("--stats", type=Path, help="bounds: ALL's meta/stats_psi0.json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--accept", type=Path, help="join: a signed bounds Decision (20.6)")
    args = parser.parse_args(argv)
    repo = REPO
    if args.action == "bounds":
        if args.data is None or args.stats is None:
            parser.error("bounds needs --data and --stats")
        outside = bounds_problems(args.data, json.loads(args.stats.read_text(encoding="utf-8")))
        print("\n".join(outside) or f"{args.data}: inside {args.stats}", file=sys.stderr)
        return 1 if outside else 0
    if args.round is None:
        parser.error(f"{args.action} needs --round")
    plan, pair = _load(args.round, repo)
    if args.action == "join":
        if args.base is None or args.targeted is None or args.out is None:
            parser.error("join needs --base, --targeted and --out")
        marker = join_round(args.base, args.targeted, args.out, plan, pair, repo, args.accept)
        print(json.dumps({k: marker[k] for k in ("demo_set", "n", "stats")}, indent=1))
        return 0
    if args.data is None:
        parser.error(f"{args.action} needs --data")
    problems = round_problems(args.data, plan, pair, repo)
    if args.base is not None:
        problems += base_problems(args.data, args.base)
    if args.action == "check" or problems:
        print("\n".join(problems) or f"{plan.branch}: dataset and round hold", file=sys.stderr)
        return 1 if problems else 0
    if args.out is None:
        parser.error("pack needs --out")
    print(json.dumps(pack(args.data, plan.branch, args.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
