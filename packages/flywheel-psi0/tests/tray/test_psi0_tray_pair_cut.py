"""Cut ALL, subset S70 and their trip via Drive, on CPU with a tiny fake cut (DA-34 6.3)."""

from __future__ import annotations

import copy
import json
import struct
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from flywheel.data.ingest.lerobot import EpisodeFrames, iter_episodes, write_episode
from flywheel.data.inject.stats import write_stats
from flywheel_psi0.tray import pair_cut
from flywheel_psi0.tray.cplus_cut import join_cuts
from flywheel_psi0.tray.pair_cut import (
    MARKER,
    STATS,
    cut_problems,
    episode_seed,
    fetch,
    pack,
    sha256,
    subset_cut,
)
from flywheel_psi0.tray.pairplan import TrayPairPlan, seeds_sha256, subset_seeds

REPO = Path(__file__).resolve().parents[4]
PAIR = REPO / "configs/runplans/tray/he-tray-pair60k.yaml"
TASK = "carry the tray"
ENV = "G1WholebodyTrayTransferTeleop-v0"
# Each part's episodes in release order: their seeds are NOT ascending, so zipping the
# set's sorted seeds with its sorted episode indices names the wrong seed (the pitfall
# the coordinator hit on the real cut: cut episode 0 is seed 1014, not 1001).
PARTS: dict[str, dict[str, Any]] = {
    "pool": {"seeds": [1014, 1001, 1007, 1003], "lengths": [4, 6, 5, 3], "base": 1.0},
    "tgt": {"seeds": [2005, 2002, 2009, 2001, 2004], "lengths": [5, 4, 6, 3, 2], "base": 100.0},
}


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _mp4(path: Path, frames: int, tag: bytes) -> None:
    hdlr = _box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"\0")
    stsz = _box(b"stsz", bytes(4) + struct.pack(">II", 0, frames) + bytes(4 * frames))
    trak = _box(b"trak", _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsz))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_box(b"ftyp", b"isom" + bytes(4)) + _box(b"moov", trak) + _box(b"mdat", tag))


def _part(root: Path, name: str) -> Path:
    """One part's cut, as demo_subset writes it: episode i has action values base + seed."""
    spec = PARTS[name]
    meta = root / "meta"
    meta.mkdir(parents=True)
    scalar = {"dtype": "int64", "shape": [1]}
    info = {
        "codebase_version": "v2.1",
        "fps": 50,
        "chunks_size": 1000,
        "robot_type": "g1",
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
        "splits": {"train": f"0:{len(spec['seeds'])}"},
        "features": {
            "observation.images.egocentric": {"dtype": "video", "shape": [180, 320, 3]},
            "states": {"dtype": "float32", "shape": [32]},
            "action": {"dtype": "float32", "shape": [36]},
            "timestamp": {"dtype": "float32", "shape": [1]},
            **{k: scalar for k in ("frame_index", "episode_index", "index", "task_index")},
            "next.done": {"dtype": "bool", "shape": [1]},
        },
    }
    (meta / "info.json").write_text(json.dumps(info))
    (meta / "tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": TASK}) + "\n")
    rows = []
    for i, (seed, n) in enumerate(zip(spec["seeds"], spec["lengths"], strict=True)):
        _mp4(root / f"videos/chunk-000/observation.images.egocentric/episode_{i:06d}.mp4", n,
             f"{name}-{seed}".encode())  # fmt: skip
        value = spec["base"] + seed
        write_episode(
            root,
            EpisodeFrames(
                episode_index=i,
                task=TASK,
                timestamp=np.arange(n) / 50.0,
                frame_index=np.arange(n, dtype=np.int64),
                states=np.full((n, 32), value, dtype=np.float32),
                action=np.full((n, 36), value, dtype=np.float32),
                video_frames={},
            ),
        )
        rows.append(seed)
    # the env config each real row carries, the seed under `flywheel`
    lines = (meta / "episodes.jsonl").read_text().splitlines()
    with_seed = []
    for line, seed in zip(lines, rows, strict=True):
        config = {"uid": "tray", "flywheel": {"seed": seed, "story": "DA-33"}}
        with_seed.append(json.dumps({**json.loads(line), "environment_config": json.dumps(config)}))
    (meta / "episodes.jsonl").write_text("\n".join(with_seed) + "\n")
    write_stats(root)
    marker = {
        "demo_set": "ALL",
        "set_hash": name[0] * 8,
        "release_id": f"rel-{name}",
        "release_hash": name[0] * 64,
        "n": len(spec["seeds"]),
        "episodes": [
            {"episode_index": i, "source_episode_index": 10 + i} for i in range(len(spec["seeds"]))
        ],
    }
    (meta / MARKER).write_text(json.dumps(marker))
    return root


def _setup(tmp_path: Path) -> tuple[Path, TrayPairPlan, Path]:
    """A fake cut ALL (two parts), its demo-set files in a fake repo, and a plan pinning it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    parts = [_part(tmp_path / f"part-{n}" / ENV, n) for n in PARTS]
    cut = tmp_path / "ALL" / ENV
    join_cuts(parts, cut, "ALL")
    raw: dict[str, Any] = yaml.safe_load(PAIR.read_text(encoding="utf-8"))
    raw["cut"]["parts"], raw["subsets"][0]["parts"] = [], []
    for name, spec in PARTS.items():
        file = f"sets-{name}.json"
        seeds = spec["seeds"]
        demo = {
            "release_id": f"rel-{name}",
            "release_hash": name[0] * 64,
            "salt": "test",
            "sets": {
                "ALL": {
                    "n": len(seeds),
                    "set_hash": name[0] * 8,
                    "seeds": sorted(seeds),
                    "episode_indices": [10 + i for i in range(len(seeds))],
                }
            },
        }
        (repo / file).write_text(json.dumps(demo))
        raw["cut"]["parts"].append(
            {
                "regenerates": f"old-{name}",
                "release": {"id": f"rel-{name}", "release_hash": name[0] * 64,
                            "location": "here", "data_class": "public"},
                "demo_sets": {"file": file, "salt": "test", "hashes": {"ALL": name[0] * 8}},
                "set_name": "ALL",
            }
        )  # fmt: skip
        kept = subset_seeds(seeds, 0.7)
        raw["subsets"][0]["parts"].append(
            {
                "regenerates": f"old-{name}",
                "episodes": len(kept),
                "seeds_sha256": seeds_sha256(kept),
            }
        )
    lengths = {s: n for spec in PARTS.values() for s, n in zip(spec["seeds"], spec["lengths"])}
    kept_all = [s for spec in PARTS.values() for s in subset_seeds(spec["seeds"], 0.7)]
    raw["subsets"][0].update(episodes=len(kept_all), frames=sum(lengths[s] for s in kept_all))
    raw["cut"].update(
        episodes=sum(len(s["seeds"]) for s in PARTS.values()),
        frames=sum(lengths.values()),
        stats_sha256=sha256(cut / "meta" / STATS),
    )
    return cut, TrayPairPlan.model_validate(raw), repo


def test_the_fake_cut_all_holds_and_its_seeds_are_not_in_set_order(tmp_path: Path) -> None:
    cut, plan, repo = _setup(tmp_path)
    assert cut_problems(cut, plan, "ALL", repo) == []
    rows = pair_cut.read_rows(cut)
    assert [episode_seed(r) for r in rows][:2] == [1014, 1001]  # not sorted: own row only
    # a row whose seed is not its set's is caught; an equal seed set in another order is not
    broken = copy.deepcopy(rows)
    config = json.loads(broken[0]["environment_config"])
    config["flywheel"]["seed"] = 999
    broken[0]["environment_config"] = json.dumps(config)
    (cut / "meta/episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in broken))
    assert any("own seeds are not set ALL" in p for p in cut_problems(cut, plan, "ALL", repo))


def test_s70_keeps_each_part_by_own_seed_with_alls_stats(tmp_path: Path) -> None:
    cut, plan, repo = _setup(tmp_path)
    out = tmp_path / "S70" / ENV
    marker = subset_cut(cut, out, plan, "S70", repo)
    assert cut_problems(out, plan, "S70", repo) == []
    want = {n: subset_seeds(s["seeds"], 0.7) for n, s in PARTS.items()}
    assert want == {"pool": [1003, 1007, 1014], "tgt": [2001, 2002, 2004, 2005]}
    # ALL's order kept within each part; renumbered 0..k-1
    seeds = [e["seed"] for p in marker["parts"] for e in p["episodes"]]
    assert seeds == [1014, 1007, 1003, 2005, 2002, 2001, 2004]
    episodes = sorted(iter_episodes(out), key=lambda e: e.episode_index)
    assert [e.episode_index for e in episodes] == list(range(7))
    base = {s: spec["base"] for spec in PARTS.values() for s in spec["seeds"]}
    # the data under each new index is its own seed's episode, not a positional neighbour
    assert [float(e.action[0, 0]) for e in episodes] == [base[s] + s for s in seeds]
    # stats are ALL's, byte for byte, never recomputed on the subset
    for name in (STATS, "stats.json"):
        if (cut / "meta" / name).is_file():
            assert (out / "meta" / name).read_bytes() == (cut / "meta" / name).read_bytes()
    info = json.loads((out / "meta/info.json").read_text())
    assert (info["total_episodes"], info["total_frames"]) == (7, plan.subsets[0].frames)  # type: ignore[index]
    rows = pair_cut.read_rows(out)
    assert [r["dataset_from_index"] for r in rows] == [
        sum(r2["length"] for r2 in rows[:i]) for i in range(len(rows))
    ]
    video = out / "videos/chunk-000/observation.images.egocentric/episode_000003.mp4"
    assert video.read_bytes().endswith(b"tgt-2005")
    assert marker["from_cut"]["stats_sha256"] == plan.cut.stats_sha256
    with pytest.raises(FileExistsError):
        subset_cut(cut, out, plan, "S70", repo)


def test_s70_checks_catch_wrong_seeds_stats_and_counts(tmp_path: Path) -> None:
    cut, plan, repo = _setup(tmp_path)
    out = tmp_path / "S70" / ENV
    subset_cut(cut, out, plan, "S70", repo)
    stats = out / "meta" / STATS
    good = stats.read_bytes()
    stats.write_text("{}")  # what an own-stats subset would look like to the check
    assert any("stats_psi0.json sha256" in p for p in cut_problems(out, plan, "S70", repo))
    stats.write_bytes(good)
    marker = json.loads((out / "meta" / MARKER).read_text())
    marker["parts"][0]["episodes"][0]["seed"] = 1001  # left out by the sha256 order
    (out / "meta" / MARKER).write_text(json.dumps(marker))
    problems = cut_problems(out, plan, "S70", repo)
    assert any("seeds are not the list" in p for p in problems)
    assert any("not the marker's, row by row" in p for p in problems)
    raw = json.loads(plan.model_dump_json())
    raw["subsets"][0]["frames"] += 1
    assert any(
        "total_frames" in p
        for p in cut_problems(out, TrayPairPlan.model_validate(raw), "S70", repo)
    )
    assert cut_problems(out, plan, "S99", repo) == [
        "S99 is neither the cut ALL nor a subset of the plan"
    ]


def test_pack_is_reproducible_and_fetch_checks_before_extracting(tmp_path: Path) -> None:
    cut, plan, repo = _setup(tmp_path)
    (tmp_path / "a").mkdir()
    one = pack(cut, "ALL", tmp_path / "a" / "ALL.tar")
    two = pack(cut, "ALL", tmp_path / "b.tar")
    assert one["sha256"] == two["sha256"] and one["bytes"] == two["bytes"]
    assert one["stats_sha256"] == plan.cut.stats_sha256
    sets = tmp_path / "vm" / "sets"
    meta = fetch(tmp_path / "a" / "ALL.tar", sets)
    assert meta["root"] == f"ALL/{ENV}"
    assert cut_problems(sets / "ALL" / ENV, plan, "ALL", repo) == []
    assert not (sets / "ALL.tar").exists()  # the copy is removed once extracted
    # a tar Drive has not finished syncing is refused before any copy
    short = tmp_path / "short.tar"
    short.write_bytes((tmp_path / "b.tar").read_bytes()[:-512])
    Path(f"{short}.json").write_text(Path(f"{tmp_path / 'b.tar'}.json").read_text())
    with pytest.raises(SystemExit, match="bytes"):
        fetch(short, tmp_path / "vm2")
    # a member outside its root is never extracted
    bad = tmp_path / "bad.tar"
    with tarfile.open(bad, "w") as tar:
        info = tarfile.TarInfo("../escape")
        tar.addfile(info, None)
    Path(f"{bad}.json").write_text(
        json.dumps({"name": "ALL", "bytes": bad.stat().st_size, "sha256": sha256(bad)})
    )
    with pytest.raises(SystemExit, match="not a plain relative file"):
        fetch(bad, tmp_path / "vm3")
    assert not (tmp_path / "escape").exists()
