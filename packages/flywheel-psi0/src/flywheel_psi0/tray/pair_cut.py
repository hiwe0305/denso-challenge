"""The datasets of the four-run pair: cut ALL, its subset S70, and their trip via Drive.

DA-34 task 6.3 (docs/he/tray.md section 19). W1 joined cut ALL on rtx3060 from the two
regenerated pools (`cplus_cut`, marker `meta/flywheel_subset.json`). This module:

- `subset_cut` writes a subset of ALL (S70) as its own LeRobot v2.1 dataset. An
  episode is kept when its own seed, `environment_config.flywheel.seed` in the cut's
  `meta/episodes.jsonl`, is in its part's list (`pairplan.subset_lists`). The demo-set
  file lists `seeds` and `episode_indices` each sorted on its own, so zipping them by
  position names the wrong seed (cut episode 0 is source index 1, seed 1014, not 1001);
  only the episode's own row is read here. Kept episodes keep ALL's order and are
  renumbered 0..k-1, `index` by LeRobot v2.1's rule (DA-03's `write_episode`, its
  renumbering logged in `meta/flywheel_lineage.jsonl`). Stats are **not** recomputed:
  `meta/stats_psi0.json` (and `stats.json`) are ALL's, byte for byte (`subsets[].stats:
  cut`), so the 70 % runs normalise exactly as the ALL runs.
- `cut_problems` checks a dataset against the plan's pins with JSON reads only (the
  Colab VM runs it before anything is installed): marker, parts, each part's seeds as
  sets, the subset's seed lists and their sha256, renumbering, `info.json` totals
  (episodes and frames), the per-episode lengths, and the sha256 of `stats_psi0.json`.
- `pack` writes one reproducible tar per dataset and a `.json` beside it (bytes,
  sha256); `fetch` copies a tar from Drive to the VM, checks its size before and its
  sha256 after the copy, and extracts it safely. The content gate stays `cut_problems`.

On rtx3060 (workspace PYTHONPATH; `subset` imports `flywheel.data`):

    python -m flywheel_psi0.tray.pair_cut subset --plan configs/runplans/tray/he-tray-pair60k.yaml \
        --cut <cut-all-zone1>/ALL/<env> --subset S70 --out <cut-all-zone1>/S70/<env>
    python -m flywheel_psi0.tray.pair_cut check --plan <plan> --name S70 --data <cut>/S70/<env>
    python -m flywheel_psi0.tray.pair_cut pack --data <cut>/S70/<env> --name S70 --out <dir>/S70.tar
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
import sys
import tarfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel_psi0.tray.demo_sets import DemoSets
from flywheel_psi0.tray.pairplan import (
    TrayPairPlan,
    part_seeds,
    seeds_sha256,
    subset_lists,
)
from flywheel_psi0.tray.runplan import REPO

MARKER = "flywheel_subset.json"  # demo_subset, cplus_cut and subset_cut write it
STATS = "stats_psi0.json"  # what Psi0 normalises with (`stat_path` of run_config.json)
COPIED_STATS = (STATS, "stats.json", "relative_stats.json")  # ALL's, never recomputed
LINEAGE = "flywheel_lineage.jsonl"
DRIVE_CUTS = "denso/da34/cuts"  # under MyDrive: <name>.tar and <name>.tar.json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def episode_seed(row: dict[str, Any]) -> int:
    """The seed an episode was generated from, from its own `meta/episodes.jsonl` row."""
    config = row["environment_config"]
    config = json.loads(config) if isinstance(config, str) else config
    return int(config["flywheel"]["seed"])


def read_rows(data: Path) -> list[dict[str, Any]]:
    path = data / "meta" / "episodes.jsonl"
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return sorted(rows, key=lambda r: int(r["episode_index"]))


def read_marker(data: Path) -> dict[str, Any] | None:
    path = data / "meta" / MARKER
    if not path.is_file():
        return None
    marker: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return marker


def _sets(plan: TrayPairPlan, repo: Path) -> list[tuple[Any, DemoSets]]:
    out = []
    for part in plan.cut.parts:
        if part.demo_sets is None or part.release is None or part.set_name is None:
            raise ValueError(f"cut part {part.regenerates} is not pinned yet")
        text = (repo / part.demo_sets.file).read_text(encoding="utf-8")
        out.append((part, DemoSets.model_validate_json(text)))
    return out


def _dataset_problems(
    data: Path, n: int, frames: int | None, stats_sha256: str | None
) -> list[str]:
    """What Psi0 reads: totals in info.json, rows 0..n-1, their lengths, and the stats."""
    problems = []
    info_path = data / "meta" / "info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else {}
    if info.get("total_episodes") != n:
        problems.append(f"meta/info.json total_episodes is {info.get('total_episodes')!r}, not {n}")
    if frames is not None and info.get("total_frames") != frames:
        problems.append(
            f"meta/info.json total_frames is {info.get('total_frames')!r}, not {frames}"
        )
    rows = read_rows(data)
    if [int(r["episode_index"]) for r in rows] != list(range(n)):
        problems.append(f"meta/episodes.jsonl rows are not episodes 0 .. {n - 1}")
    elif frames is not None and sum(int(r["length"]) for r in rows) != frames:
        problems.append(f"meta/episodes.jsonl lengths sum to {sum(int(r['length']) for r in rows)}")
    stats = data / "meta" / STATS
    found = sha256(stats) if stats.is_file() else "missing"
    if found != stats_sha256:
        problems.append(f"meta/{STATS} sha256 {found}, the plan pins the cut's {stats_sha256}")
    return problems


def cut_problems(data: Path, plan: TrayPairPlan, name: str, repo: Path = REPO) -> list[str]:
    """Everything wrong between the dataset at `data` and the plan's pins for `name`."""
    marker = read_marker(data)
    if marker is None:
        return [f"{data / 'meta' / MARKER} missing: not a demo-set cut"]
    try:
        sets = _sets(plan, repo)
    except ValueError as error:
        return [str(error)]
    if name == plan.cut.name:
        return _all_problems(data, marker, plan, sets)
    subset = plan.subset(name)
    if subset is None:
        return [f"{name} is neither the cut {plan.cut.name} nor a subset of the plan"]
    return _subset_problems(data, marker, plan, name, sets, repo)


def _all_problems(
    data: Path, marker: dict[str, Any], plan: TrayPairPlan, sets: list[tuple[Any, DemoSets]]
) -> list[str]:
    cut = plan.cut
    problems = []
    if (marker.get("demo_set"), marker.get("n")) != (cut.name, cut.episodes):
        problems.append(
            f"cut is {marker.get('demo_set')!r} of n={marker.get('n')!r}, not {cut.name} of"
            f" {cut.episodes}"
        )
    parts = marker.get("parts", [])
    if len(parts) != len(sets):
        return [*problems, f"cut has {len(parts)} parts, the plan {len(sets)}"]
    rows = read_rows(data)
    start = 0
    for mark, (part, demo_sets) in zip(parts, sets, strict=True):
        assert part.release is not None and part.demo_sets is not None and part.set_name
        demo = demo_sets.sets[part.set_name]
        label = f"part {part.regenerates}"
        expected = {
            "release_id": part.release.id,
            "release_hash": part.release.release_hash,
            "set_hash": part.demo_sets.hashes[part.set_name],
            "n": demo.n,
            "first_episode_index": start,
        }
        problems += [
            f"{label}: {key} is {mark.get(key)!r}, the plan's is {value!r}"
            for key, value in expected.items()
            if mark.get(key) != value
        ]
        episodes = mark.get("episodes", [])
        if [e["source_episode_index"] for e in episodes] != demo.episode_indices:
            problems.append(f"{label}: episodes are not the set's episode indices in its release")
        if [e["episode_index"] for e in episodes] != list(range(start, start + demo.n)):
            problems.append(f"{label}: episodes are not renumbered from {start}")
        # each episode's own seed, compared as sets: never zip seeds with episode indices
        seeds = [episode_seed(r) for r in rows[start : start + demo.n]]
        if sorted(seeds) != sorted(demo.seeds):
            problems.append(f"{label}: the episodes' own seeds are not set {part.set_name}'s")
        start += demo.n
    return problems + _dataset_problems(data, start, cut.frames, cut.stats_sha256)


def _subset_problems(
    data: Path,
    marker: dict[str, Any],
    plan: TrayPairPlan,
    name: str,
    sets: list[tuple[Any, DemoSets]],
    repo: Path,
) -> list[str]:
    subset = plan.subset(name)
    assert subset is not None
    cut = plan.cut
    problems = []
    if (marker.get("demo_set"), marker.get("n")) != (name, subset.episodes):
        problems.append(
            f"subset is {marker.get('demo_set')!r} of n={marker.get('n')!r}, not {name} of"
            f" {subset.episodes}"
        )
    origin = {"name": cut.name, "episodes": cut.episodes, "frames": cut.frames}
    origin["stats_sha256"] = cut.stats_sha256
    found_origin = {k: marker.get("from_cut", {}).get(k) for k in origin}
    if found_origin != origin:
        problems.append(f"subset from_cut is {found_origin}, the plan's cut is {origin}")
    lists = subset_lists(plan, repo).get(name, {})
    parts = marker.get("parts", [])
    if len(parts) != len(subset.parts):
        return [*problems, f"subset has {len(parts)} parts, the plan {len(subset.parts)}"]
    rows = read_rows(data)
    start = 0
    for mark, sp, (part, _) in zip(parts, subset.parts, sets, strict=True):
        assert part.release is not None and part.demo_sets is not None and part.set_name
        label = f"subset {name} part {sp.regenerates}"
        want = lists.get(sp.regenerates, [])
        expected = {
            "release_id": part.release.id,
            "release_hash": part.release.release_hash,
            "set_hash": part.demo_sets.hashes[part.set_name],
            "n": sp.episodes,
            "seeds_sha256": sp.seeds_sha256,
            "first_episode_index": start,
        }
        problems += [
            f"{label}: {key} is {mark.get(key)!r}, the plan's is {value!r}"
            for key, value in expected.items()
            if mark.get(key) != value
        ]
        episodes = mark.get("episodes", [])
        if sorted(int(e["seed"]) for e in episodes) != want:
            problems.append(f"{label}: seeds are not the list {subset.order} gives")
        if seeds_sha256(want) != sp.seeds_sha256:
            problems.append(f"{label}: the recomputed list is not the pinned seeds_sha256")
        if [e["episode_index"] for e in episodes] != list(range(start, start + len(episodes))):
            problems.append(f"{label}: episodes are not renumbered from {start}")
        own = [episode_seed(r) for r in rows[start : start + len(episodes)]]
        if own != [int(e["seed"]) for e in episodes]:
            problems.append(f"{label}: meta/episodes.jsonl seeds are not the marker's, row by row")
        start += len(episodes)
    if subset.episodes is None:
        return [*problems, f"subset {name}: episodes is not pinned"]
    return problems + _dataset_problems(data, subset.episodes, subset.frames, cut.stats_sha256)


def subset_selection(
    cut: Path, plan: TrayPairPlan, name: str, repo: Path = REPO
) -> list[list[dict[str, Any]]]:
    """Per cut part, ALL's rows the subset keeps, in ALL's order (by each row's own seed)."""
    marker = read_marker(cut)
    if marker is None:
        raise ValueError(f"{cut}: no {MARKER}")
    lists = subset_lists(plan, repo)[name]
    rows = read_rows(cut)
    kept: list[list[dict[str, Any]]] = []
    for mark, part in zip(marker["parts"], plan.cut.parts, strict=True):
        start, n = int(mark["first_episode_index"]), int(mark["n"])
        part_rows = rows[start : start + n]
        seeds = [episode_seed(r) for r in part_rows]
        if len(set(seeds)) != len(seeds) or sorted(seeds) != sorted(part_seeds(part, repo) or []):
            raise ValueError(f"part {part.regenerates}: the cut's seeds are not its set's")
        want = set(lists[part.regenerates])
        kept.append([r for r, s in zip(part_rows, seeds, strict=True) if s in want])
        if len(kept[-1]) != len(want):
            raise ValueError(f"part {part.regenerates}: {len(kept[-1])} of {len(want)} seeds found")
    return kept


def subset_cut(
    cut: Path, out: Path, plan: TrayPairPlan, name: str, repo: Path = REPO
) -> dict[str, Any]:
    """Write subset `name` of the cut at `cut` as a dataset at `out`; return its marker."""
    from flywheel.data.ingest.lerobot import check_index, iter_episodes, read_info, write_episode

    from flywheel_psi0.tray.cplus_cut import episode_files

    if out.exists():
        raise FileExistsError(f"{out} exists; a demo set dataset is never overwritten")
    problems = cut_problems(cut, plan, plan.cut.name, repo)
    if problems:
        raise ValueError(f"{cut} is not the plan's cut: " + "; ".join(problems))
    subset = plan.subset(name)
    if subset is None or subset.episodes is None or subset.frames is None:
        raise ValueError(f"subset {name} is not pinned in the plan")
    kept = subset_selection(cut, plan, name, repo)
    order = [int(r["episode_index"]) for part in kept for r in part]
    new = {old: i for i, old in enumerate(order)}
    info = read_info(cut)

    shutil.copytree(cut / "meta", out / "meta")
    (out / "meta" / MARKER).unlink()
    (out / "meta" / LINEAGE).write_text("")  # this dataset's own renumbering; ALL keeps its own
    (out / "meta" / "info.json").write_text(
        json.dumps({**info, "splits": {"train": f"0:{len(order)}"}}, indent=4)
    )
    rows = {int(r["episode_index"]): r for r in read_rows(cut)}
    (out / "meta" / "episodes.jsonl").write_text(
        "".join(json.dumps({**rows[old], "episode_index": new[old]}) + "\n" for old in order)
    )
    carried = []
    for line in (cut / "meta" / "episodes_stats.jsonl").read_text().splitlines():
        if line.strip() and int((row := json.loads(line))["episode_index"]) in new:
            carried.append({**row, "episode_index": new[int(row["episode_index"])]})
    carried.sort(key=lambda r: int(r["episode_index"]))
    (out / "meta" / "episodes_stats.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in carried)
    )
    for old in order:
        for old_path, new_path in zip(
            episode_files(info, old), episode_files(info, new[old]), strict=True
        ):
            if (cut / old_path).is_file():
                (out / new_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cut / old_path, out / new_path)
    # from the cut's own parquet (its episode_index is the old one), in ascending order:
    # `new` keeps ALL's order, and write_episode numbers `index` after the rows before it
    for frames in iter_episodes(cut):
        if frames.episode_index in new:
            write_episode(out, dataclasses.replace(frames, episode_index=new[frames.episode_index]))

    marker_in = read_marker(cut)
    assert marker_in is not None
    parts: list[dict[str, Any]] = []
    marker: dict[str, Any] = {
        "demo_set": name,
        "n": len(order),
        "from_cut": {
            "name": plan.cut.name,
            "episodes": plan.cut.episodes,
            "frames": plan.cut.frames,
            "stats_sha256": plan.cut.stats_sha256,
            "marker_sha256": sha256(cut / "meta" / MARKER),
        },
        "fraction": subset.fraction,
        "order": subset.order,
        "parts": parts,
        "stats": f"cut: {STATS} of {plan.cut.name}, copied, not recomputed",
    }
    start = 0
    for mark, sp, part_rows in zip(marker_in["parts"], subset.parts, kept, strict=True):
        seeds = [episode_seed(r) for r in part_rows]
        parts.append(
            {
                **{k: mark[k] for k in ("release_id", "release_hash", "set_hash")},
                "n": len(part_rows),
                "seeds_sha256": seeds_sha256(seeds),
                "first_episode_index": start,
                "episodes": [
                    {
                        "episode_index": new[int(r["episode_index"])],
                        "cut_episode_index": int(r["episode_index"]),
                        "seed": s,
                    }
                    for r, s in zip(part_rows, seeds, strict=True)
                ],
            }
        )
        start += len(part_rows)
    (out / "meta" / MARKER).write_text(json.dumps(marker, indent=2))
    problems = cut_problems(out, plan, name, repo)
    problems += [f"index of episode {f.episode_index} is off" for f in check_index(out)]
    if problems:
        raise ValueError(f"{out} does not hold after the write: " + "; ".join(problems))
    return marker


def _members(data: Path) -> list[Path]:
    return sorted(p for p in data.rglob("*") if p.is_file())


def pack(data: Path, name: str, out: Path) -> dict[str, Any]:
    """`<name>/<env>/...` as one tar, byte for byte the same for the same files."""
    if out.exists():
        raise FileExistsError(f"{out} exists")
    root = f"{name}/{data.name}"
    with tarfile.open(out, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in _members(data):
            info = tarfile.TarInfo(f"{root}/{path.relative_to(data).as_posix()}")
            info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
            with path.open("rb") as f:
                tar.addfile(info, f)
    meta = {
        "name": name,
        "root": root,
        "files": len(_members(data)),
        "bytes": out.stat().st_size,
        "sha256": sha256(out),
        "marker_sha256": sha256(data / "meta" / MARKER),
        "stats_sha256": sha256(data / "meta" / STATS),
    }
    Path(f"{out}.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def fetch(src: Path, sets: Path) -> dict[str, Any]:
    """Copy a packed tar (and its .json) to the VM, check it, extract under `sets`."""
    meta_path = Path(f"{src}.json")
    if not src.is_file() or not meta_path.is_file():
        raise SystemExit(f"{src} or its .json missing: upload it to Drive first (and mount it)")
    meta: dict[str, Any] = json.loads(meta_path.read_text())
    if src.stat().st_size != meta["bytes"]:  # Drive still syncing, or another file
        raise SystemExit(f"{src}: {src.stat().st_size} bytes, its .json says {meta['bytes']}")
    sets.mkdir(parents=True, exist_ok=True)
    local = sets / src.name
    shutil.copyfile(src, local)
    if sha256(local) != meta["sha256"]:
        local.unlink()
        raise SystemExit(f"{src}: sha256 differs from its .json after the copy")
    with tarfile.open(local) as tar:
        members = tar.getmembers()
        for member in members:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise SystemExit(f"{src}: member {member.name} is not a plain relative file")
            if path.parts[0] != meta["name"]:
                raise SystemExit(f"{src}: member {member.name} is outside {meta['name']}/")
        if hasattr(tarfile, "data_filter"):  # 3.11.4+: refuse links and odd modes too
            tar.extractall(sets, members=members, filter="data")
        else:
            tar.extractall(sets, members=members)
    local.unlink()
    return meta


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("action", choices=["subset", "check", "pack"])
    parser.add_argument(
        "--plan", type=Path, default=REPO / "configs/runplans/tray/he-tray-pair60k.yaml"
    )
    parser.add_argument("--cut", type=Path, help="subset: the cut's dataset dir")
    parser.add_argument("--subset", help="subset: its name in the plan, e.g. S70")
    parser.add_argument("--data", type=Path, help="check, pack: a dataset dir")
    parser.add_argument("--name", help="check, pack: ALL or a subset name")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    plan = TrayPairPlan.load(args.plan)
    if args.action == "subset":
        if args.cut is None or args.subset is None or args.out is None:
            parser.error("subset needs --cut, --subset and --out")
        marker = subset_cut(args.cut, args.out, plan, args.subset)
        print(json.dumps({k: v for k, v in marker.items() if k != "parts"}, indent=1))
        return 0
    if args.data is None or args.name is None:
        parser.error(f"{args.action} needs --data and --name")
    problems = cut_problems(args.data, plan, args.name)
    if args.action == "check" or problems:
        print("\n".join(problems) or f"{args.name}: dataset and plan hold", file=sys.stderr)
        return 1 if problems else 0
    if args.out is None:
        parser.error("pack needs --out")
    print(json.dumps(pack(args.data, args.name, args.out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
