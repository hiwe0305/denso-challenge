"""Nested robot-demo sets of the tray experiment, fixed by hash (DA-34 AC 1).

Branch A trains on N_full = 80 episodes of DA-33's synthetic S1 release, C and
C-NOEGO on N_cut = 40 of those 80 (design 28/10/2026 section 6.2). Every episode
is ranked by sha256(salt | release_hash | seed) and a set of size n is the first
n of that ranking, so the smaller set is a prefix of the larger, hence a subset,
and A minus C is a uniform draw of the episodes C left out: the "evenly added"
side of the C+ vs A comparison of section 6.6.

An episode is keyed by its condition seed, not its `episode_index`: the seed
names the scene and survives a re-export, the index is a position in one export.
The release seeds are consecutive (1000-1129 minus failures), so taking the
first seeds would mean taking the earliest shards; the hash ranking does not.

`set_hash` is the sha256 of the canonical JSON {"release_hash", "seeds"}: it
names the content of the set, so the same episodes of the same release always
give the same hash whatever the salt or order they were picked in.

Run on a release directory (stdlib only, no simulator):

    python -m flywheel_psi0.tray.demo_sets --release <release dir> \
        --size A=80 --size C=40 --out configs/runplans/tray/demo_sets.json
    python -m flywheel_psi0.tray.demo_sets --release <release dir> \
        --size A=80 --size C=40 --check configs/runplans/tray/demo_sets.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SALT = "DA-34/demo-sets/v1"
MANIFEST = "release_manifest.json"  # written by flywheel_simple.tray.release
EXPORT_META = "meta/flywheel_export.json"  # written by flywheel_simple.tray.export


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseEpisode(_Frozen):
    episode_index: int = Field(ge=0)
    seed: int = Field(ge=0)


class DemoSet(_Frozen):
    n: int = Field(gt=0)
    set_hash: str
    seeds: list[int]  # ascending
    episode_indices: list[int]  # ascending; positions in this release's export

    @model_validator(mode="after")
    def _check(self) -> DemoSet:
        if len(self.seeds) != self.n or len(self.episode_indices) != self.n:
            raise ValueError(f"set of n={self.n} lists {len(self.seeds)} seeds")
        if self.seeds != sorted(set(self.seeds)):
            raise ValueError("seeds must be unique and ascending")
        return self


class DemoSets(_Frozen):
    release_id: str
    release_hash: str
    salt: str
    sets: dict[str, DemoSet]


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def set_hash(release_hash: str, seeds: Sequence[int]) -> str:
    return canonical_sha256({"release_hash": release_hash, "seeds": sorted(seeds)})


def rank(release_hash: str, episodes: Sequence[ReleaseEpisode], salt: str = SALT) -> list[int]:
    """Seeds of the release, in the fixed pseudo-random order every set is cut from."""
    seeds = [e.seed for e in episodes]
    if len(set(seeds)) != len(seeds):
        raise ValueError("two episodes of the release share a seed")

    def key(seed: int) -> str:
        return hashlib.sha256(f"{salt}|{release_hash}|{seed}".encode()).hexdigest()

    return sorted(seeds, key=key)


def nested_sets(
    release_id: str,
    release_hash: str,
    episodes: Sequence[ReleaseEpisode],
    sizes: Mapping[str, int],
    salt: str = SALT,
) -> DemoSets:
    """One set per name, each the first n of `rank`, so every smaller set is in every larger."""
    order = rank(release_hash, episodes, salt)
    too_big = {name: n for name, n in sizes.items() if n > len(order)}
    if too_big:
        raise ValueError(f"release has {len(order)} episodes, asked for {too_big}")
    index_of = {e.seed: e.episode_index for e in episodes}
    sets = {}
    for name, n in sizes.items():
        seeds = sorted(order[:n])
        sets[name] = DemoSet(
            n=n,
            set_hash=set_hash(release_hash, seeds),
            seeds=seeds,
            episode_indices=sorted(index_of[s] for s in seeds),
        )
    return DemoSets(release_id=release_id, release_hash=release_hash, salt=salt, sets=sets)


def read_release(release_root: Path) -> tuple[str, list[ReleaseEpisode]]:
    """`release_hash` and episodes of a tray release, checked against its own manifest.

    Recomputes `release_hash` from the manifest's file list and the sha256 of the
    export metadata the episodes come from; it does not rehash the 0.9 GB of data
    (`flywheel_simple.tray.release.verify_manifest` does that).
    """
    manifest = json.loads((release_root / MANIFEST).read_text(encoding="utf-8"))
    release_hash = str(manifest["release_hash"])
    if canonical_sha256(manifest["files"]) != release_hash:
        raise ValueError(f"{MANIFEST}: file list does not hash to release_hash {release_hash}")
    export = release_root / EXPORT_META
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    actual = hashlib.sha256(export.read_bytes()).hexdigest()
    if listed.get(EXPORT_META) != actual:
        raise ValueError(f"{EXPORT_META} is not the file the manifest lists")
    rows = json.loads(export.read_text(encoding="utf-8"))["episodes"]
    episodes = [ReleaseEpisode(episode_index=r["episode_index"], seed=r["seed"]) for r in rows]
    return release_hash, episodes


def _size(text: str) -> tuple[str, int]:
    name, _, n = text.partition("=")
    if not name or not n.isdigit():
        raise argparse.ArgumentTypeError(f"--size {text!r} is not NAME=N")
    return name, int(n)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--size", type=_size, action="append", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path, help="write the sets here")
    target.add_argument("--check", type=Path, help="exit 1 unless this file has the same sets")
    args = parser.parse_args(argv)

    release_hash, episodes = read_release(args.release)
    sets = nested_sets(args.release.name, release_hash, episodes, dict(args.size))
    text = sets.model_dump_json(indent=1) + "\n"
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: " + ", ".join(f"{k}={v.set_hash}" for k, v in sets.sets.items()))
        return 0
    recorded = DemoSets.model_validate_json(args.check.read_text(encoding="utf-8"))
    if recorded != sets:
        print(f"{args.check} differs from the sets of {args.release}", file=sys.stderr)
        return 1
    print(f"{args.check} matches {args.release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
