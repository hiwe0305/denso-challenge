"""Cut one HE-1 demo set out of the pinned psi-data dataset (DA-26 AC 2, task 3).

Psi0 at cda3fdf trains on every episode of the LeRobot dataset it is given; it has
no episode filter. So each point trains on a dataset of its own: the episodes of
its demo set (`configs/runplans/he/demo_sets.json`, keyed by the source's
`episode_index`), renumbered 0 .. n-1 in ascending source order, as LeRobot v2.1's
loader needs contiguous indices. Its stats are its own (`recipe.dataset_stats:
own_train_set`): Psi0 normalises states and actions by `meta/stats_psi0.json`, and
stats over all 99 episodes would leak the episodes a point does not train on.

The cut goes through the DA-03 reader and writer (`flywheel.data.ingest.lerobot`):
parquet and video are copied under the new index, `write_episode` rewrites
`episode_index`, `index` and the meta rows (a changed `index` goes to
`meta/flywheel_lineage.jsonl`, never silently), and `write_stats` recomputes the
four stats files from the cut's own data, as SIMPLE's export does; image stats,
which need decoded video, are carried from each episode's own source row.
`meta/flywheel_subset.json` maps every new index to its source index and pins the
set hash, which is recomputed from the source here and must match the plan's.

    python scripts/he/demo_subset.py --src <dataset dir> --sets configs/runplans/he/demo_sets.json \
        --set N20 --out <work>/sets/N20/G1WholebodyLocomotionPickBetweenTablesTeleop-v0
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

from flywheel.data.ingest.lerobot import iter_episodes, read_episode_rows, read_info, write_episode
from flywheel.data.inject.stats import write_stats
from flywheel_psi0.tray.demo_sets import DemoSets, set_hash

MARKER = "flywheel_subset.json"


def episode_files(info: dict[str, Any], index: int) -> list[str]:
    """Parquet and video paths of one episode, relative to the dataset root."""
    chunk = index // int(info["chunks_size"])
    paths = [info["data_path"].format(episode_chunk=chunk, episode_index=index)]
    for name, feature in info["features"].items():
        if feature.get("dtype") == "video":
            paths.append(
                info["video_path"].format(episode_chunk=chunk, episode_index=index, video_key=name)
            )
    return paths


def build_subset(src: Path, out: Path, sets: DemoSets, name: str) -> dict[str, Any]:
    """Write demo set `name` of `sets` as its own LeRobot dataset at `out`; return the marker."""
    if out.exists():
        raise FileExistsError(f"{out} exists; a demo set dataset is never overwritten")
    demo = sets.sets[name]
    kept = sorted(demo.episode_indices)
    if set_hash(sets.release_hash, kept) != demo.set_hash:
        raise ValueError(f"{name}: episode indices do not give the set hash {demo.set_hash}")
    info = read_info(src)
    rows = {int(r["episode_index"]): r for r in read_episode_rows(src)}
    missing = [i for i in kept if i not in rows]
    if missing:
        raise ValueError(f"{name}: episodes {missing} are not in {src}/meta/episodes.jsonl")
    source_of = dict(enumerate(kept))  # new index -> source index

    # meta first (lang_map, modality and the rest are per dataset, not per episode),
    # then the kept rows under their new index; write_episode recounts the totals.
    shutil.copytree(src / "meta", out / "meta")
    (out / "meta" / "info.json").write_text(
        json.dumps({**info, "splits": {"train": f"0:{len(kept)}"}}, indent=4)
    )
    renumbered = [{**rows[old], "episode_index": new} for new, old in source_of.items()]
    (out / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in renumbered))
    for new, old in source_of.items():
        for old_path, new_path in zip(
            episode_files(info, old), episode_files(info, new), strict=True
        ):
            if (src / old_path).is_file():
                (out / new_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src / old_path, out / new_path)

    frames = {f.episode_index: f for f in iter_episodes(src) if f.episode_index in set(kept)}
    for new, old in source_of.items():
        write_episode(out, dataclasses.replace(frames[old], episode_index=new))
    write_stats(out, source=src, owners=source_of)

    marker = {
        "demo_set": name,
        "set_hash": demo.set_hash,
        "release_id": sets.release_id,
        "release_hash": sets.release_hash,
        "n": len(kept),
        "episodes": [{"episode_index": n, "source_episode_index": o} for n, o in source_of.items()],
        "stats": "own_train_set: stats_psi0.json of these episodes (flywheel.data.inject.stats)",
    }
    (out / "meta" / MARKER).write_text(json.dumps(marker, indent=2))
    return marker


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--src", type=Path, required=True, help="the unzipped psi-data dataset")
    parser.add_argument("--sets", type=Path, required=True, help="demo_sets.json of the plan")
    parser.add_argument("--set", required=True, help="e.g. N20")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    sets = DemoSets.model_validate_json(args.sets.read_text(encoding="utf-8"))
    marker = build_subset(args.src, args.out, sets, args.set)
    json.dump({k: v for k, v in marker.items() if k != "episodes"}, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
