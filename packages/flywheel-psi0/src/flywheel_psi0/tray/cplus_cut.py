"""Join C's cut and the targeted cut into the one dataset branch C+ trains on (DA-34 task 5).

C+ = the 160 episodes of C (release `tray_s1_f9433b028c52`) plus the 160 targeted
ones (their own release). Psi0 at cda3fdf trains on one LeRobot dataset, and
`scripts/he/demo_subset.py` cuts one set out of one release, so each part is cut on
its own with demo_subset (marker `meta/flywheel_subset.json`) and then joined here:

- parts keep their order and their own order: C is episodes 0..159, exactly C's
  cut (parquet and video copied, so C+ holds byte for byte the data C trained on),
  the targeted part follows from 160;
- `episode_index` and `index` are rewritten by DA-03's writer, as demo_subset does;
- stats are the joined set's own (`recipe.dataset_stats: own_train_set`), recomputed
  by `flywheel.data.inject.stats.write_stats`; image stats, which need decoded
  video, are carried per episode from each part's own `episodes_stats.jsonl`;
- the marker lists every part's marker and the new index of each of its episodes.

Parts must share fps, features and path templates.

    python -m flywheel_psi0.tray.cplus_cut --part <cut C dir> --part <cut T160 dir> \
        --demo-set C_PLUS --out <work>/sets/C_PLUS/G1WholebodyTrayTransferTeleop-v0

`flywheel.data` is imported when the command runs (rtx3060, workspace PYTHONPATH),
not on the Colab VM, which only checks the marker.
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

MARKER = "flywheel_subset.json"  # what demo_subset writes and colab_train reads
SAME = ("fps", "features", "data_path", "video_path", "chunks_size", "robot_type")


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


def read_marker(part: Path) -> dict[str, Any]:
    path = part / "meta" / MARKER
    if not path.is_file():
        raise ValueError(f"{path} missing: {part} is not a demo-set cut")
    marker: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return marker


def offsets(sizes: Sequence[int]) -> list[int]:
    """First new index of each part: parts follow one another in the given order."""
    out, start = [], 0
    for n in sizes:
        out.append(start)
        start += n
    return out


def join_cuts(parts: Sequence[Path], out: Path, demo_set: str) -> dict[str, Any]:
    """Write the parts as one LeRobot dataset at `out`; return its marker."""
    from flywheel.data.ingest.lerobot import (
        iter_episodes,
        read_episode_rows,
        read_info,
        write_episode,
    )
    from flywheel.data.inject.stats import write_stats

    if out.exists():
        raise FileExistsError(f"{out} exists; a demo set dataset is never overwritten")
    if len(parts) < 2:
        raise ValueError("a join needs at least two parts")
    markers = [read_marker(p) for p in parts]
    infos = [read_info(p) for p in parts]
    for part, info in zip(parts[1:], infos[1:]):
        differ = [k for k in SAME if info.get(k) != infos[0].get(k)]
        if differ:
            raise ValueError(f"{part} differs from {parts[0]} in {differ}")
    rows = [sorted(read_episode_rows(p), key=lambda r: int(r["episode_index"])) for p in parts]
    for part, marker, part_rows in zip(parts, markers, rows):
        if [int(r["episode_index"]) for r in part_rows] != list(range(int(marker["n"]))):
            raise ValueError(f"{part}: episodes are not 0 .. n-1 of its marker")
    starts = offsets([int(m["n"]) for m in markers])
    total = sum(int(m["n"]) for m in markers)

    shutil.copytree(parts[0] / "meta", out / "meta")
    (out / "meta" / MARKER).unlink()
    info = {**infos[0], "splits": {"train": f"0:{total}"}}
    (out / "meta" / "info.json").write_text(json.dumps(info, indent=4))
    joined = [
        {**r, "episode_index": start + int(r["episode_index"])}
        for start, part_rows in zip(starts, rows)
        for r in part_rows
    ]
    (out / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in joined))
    # write_stats carries image stats from a source's episodes_stats.jsonl by index:
    # give it the parts' rows under their new index, then let it rewrite the file.
    carried = []
    for start, part in zip(starts, parts):
        for line in (part / "meta" / "episodes_stats.jsonl").read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                carried.append({**row, "episode_index": start + int(row["episode_index"])})
    (out / "meta" / "episodes_stats.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in carried)
    )

    for start, part, part_rows in zip(starts, parts, rows):
        for r in part_rows:
            old = int(r["episode_index"])
            for old_path, new_path in zip(
                episode_files(info, old), episode_files(info, start + old), strict=True
            ):
                if (part / old_path).is_file():
                    (out / new_path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(part / old_path, out / new_path)
    for start, part in zip(starts, parts):
        for frames in sorted(iter_episodes(part), key=lambda f: f.episode_index):
            write_episode(
                out, dataclasses.replace(frames, episode_index=start + frames.episode_index)
            )
    write_stats(out, source=out)

    marker = {
        "demo_set": demo_set,
        "n": total,
        "parts": [
            {
                **{k: v for k, v in m.items() if k != "episodes"},
                "first_episode_index": start,
                "episodes": [
                    {
                        "episode_index": start + int(e["episode_index"]),
                        "source_episode_index": int(e["source_episode_index"]),
                    }
                    for e in m["episodes"]
                ],
            }
            for start, m in zip(starts, markers)
        ],
        "stats": "own_train_set: stats_psi0.json over all parts (flywheel.data.inject.stats)",
    }
    (out / "meta" / MARKER).write_text(json.dumps(marker, indent=2))
    return marker


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--part", type=Path, action="append", required=True)
    parser.add_argument("--demo-set", required=True, help="e.g. C_PLUS")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    marker = join_cuts(args.part, args.out, args.demo_set)
    summary = {
        "demo_set": marker["demo_set"],
        "n": marker["n"],
        "parts": [
            {k: p[k] for k in ("demo_set", "set_hash", "release_hash", "n", "first_episode_index")}
            for p in marker["parts"]
        ],
    }
    json.dump(summary, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
