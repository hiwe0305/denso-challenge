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

With `--quality` (quality.py on the release's generate.py batch) and its two
limits, only episodes under the limits are ranked; the quality file's sha256,
the limits and the counts kept and dropped are recorded with the sets. The
ranking key does not change, so dropping an episode never reorders the rest.

With `--qa-work` (the `fw data ingest` work directory of this release after
`fw data qa`), episodes DA-03's QA rejected or quarantined are left out before
the quality filter, and listed with their reasons (decision of 5/11/2026). It
fails closed: the work directory must be of this export and every episode needs
a report.

Run on a release directory (no simulator):

    python -m flywheel_psi0.tray.demo_sets --release <release dir> \
        --size A=80 --size C=40 --out configs/runplans/tray/demo_sets.json
    python -m flywheel_psi0.tray.demo_sets --release <release dir> \
        --size A=80 --size C=40 --check configs/runplans/tray/demo_sets.json
    python -m flywheel_psi0.tray.demo_sets --release <release dir> --quality quality.jsonl \
        --max-tilt-carry-deg 10 --max-part-shift-end-mm 20 --size A=320 --size C=160 --out ...
    python -m flywheel_psi0.tray.demo_sets --release <release dir> --qa-work <work dir> \
        --quality quality.jsonl --max-tilt-carry-deg 10 --max-part-shift-end-mm 20 \
        --size N40=40 --size N80=80 --size C=160 --size A=320 --out ...
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

from flywheel_psi0.tray.quality import QualityFilter, read_quality

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


class QualityPin(_Frozen):
    file_sha256: str
    filter: QualityFilter
    kept: int
    dropped: int


class QaExclusion(_Frozen):
    seed: int
    episode_id: str
    decision: str
    reasons: list[str]


class QaPin(_Frozen):
    reports_sha256: str  # qa/reports.jsonl of the `fw data ingest` work directory
    threshold_version: str
    excluded: list[QaExclusion]  # ascending seed


class DemoSets(_Frozen):
    release_id: str
    release_hash: str
    salt: str
    sets: dict[str, DemoSet]
    quality: QualityPin | None = None
    qa: QaPin | None = None


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
    quality: QualityPin | None = None,
    qa: QaPin | None = None,
) -> DemoSets:
    """One set per name, each the first n of `rank`, so every smaller set is in every larger.

    `episodes` are the ones eligible for the sets (already quality-filtered).
    """
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
    return DemoSets(
        release_id=release_id,
        release_hash=release_hash,
        salt=salt,
        sets=sets,
        quality=quality,
        qa=qa,
    )


def apply_quality(
    episodes: Sequence[ReleaseEpisode], quality_file: Path, limits: QualityFilter
) -> tuple[list[ReleaseEpisode], QualityPin]:
    """The release episodes under the limits, and what to record about the filter."""
    by_seed = {q.seed: q for q in read_quality(quality_file)}
    missing = sorted(e.seed for e in episodes if e.seed not in by_seed)
    if missing:
        raise ValueError(f"{quality_file} has no row for seeds {missing[:10]}")
    kept = [e for e in episodes if limits.passes(by_seed[e.seed])]
    pin = QualityPin(
        file_sha256=hashlib.sha256(quality_file.read_bytes()).hexdigest(),
        filter=limits,
        kept=len(kept),
        dropped=len(episodes) - len(kept),
    )
    return kept, pin


def apply_qa(
    episodes: Sequence[ReleaseEpisode], qa_work: Path, release_root: Path
) -> tuple[list[ReleaseEpisode], QaPin]:
    """The release episodes DA-03's QA did not reject, and the ones it did, with reasons.

    `qa_work` is the directory `fw data ingest` printed for this release, after
    `fw data qa`. Its `source.json` must list this release's export metadata, every
    episode needs a report (fails closed), and all reports share one threshold
    version. Quarantined episodes are left out with the rejected ones: neither is
    cleared for training.
    """
    listed = json.loads((qa_work / "source.json").read_text(encoding="utf-8"))["files"]
    export_sha = hashlib.sha256((release_root / EXPORT_META).read_bytes()).hexdigest()
    if listed.get(EXPORT_META) != export_sha:
        raise ValueError(f"{qa_work} is the QA of another export than {release_root}")
    index = json.loads((qa_work / "episode_index.json").read_text(encoding="utf-8"))
    reports_file = qa_work / "qa" / "reports.jsonl"
    reports = [json.loads(line) for line in reports_file.read_text().splitlines() if line]
    by_index = {index[r["episode_id"]]: r for r in reports}
    missing = sorted(e.seed for e in episodes if e.episode_index not in by_index)
    if missing:
        raise ValueError(f"no DA-03 QA report in {reports_file} for seeds {missing[:10]}")
    versions = sorted({r["threshold_version"] for r in reports})
    if len(versions) != 1:
        raise ValueError(f"{reports_file} mixes threshold versions {versions}")
    excluded = [
        QaExclusion(
            seed=e.seed,
            episode_id=by_index[e.episode_index]["episode_id"],
            decision=by_index[e.episode_index]["decision"],
            reasons=list(by_index[e.episode_index]["reasons"]),
        )
        for e in sorted(episodes, key=lambda e: e.seed)
        if by_index[e.episode_index]["decision"] in ("reject", "quarantine")
    ]
    left_out = {x.seed for x in excluded}
    pin = QaPin(
        reports_sha256=hashlib.sha256(reports_file.read_bytes()).hexdigest(),
        threshold_version=versions[0],
        excluded=excluded,
    )
    return [e for e in episodes if e.seed not in left_out], pin


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
    parser.add_argument("--qa-work", type=Path, help="`fw data ingest` work dir after `fw data qa`")
    parser.add_argument("--quality", type=Path, help="quality.jsonl of the release's batch")
    parser.add_argument("--max-tilt-carry-deg", type=float)
    parser.add_argument("--max-part-shift-end-mm", type=float)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path, help="write the sets here")
    target.add_argument("--check", type=Path, help="exit 1 unless this file has the same sets")
    args = parser.parse_args(argv)

    release_hash, episodes = read_release(args.release)
    qa_pin = pin = None
    if args.qa_work is not None:
        episodes, qa_pin = apply_qa(episodes, args.qa_work, args.release)
    if args.quality is not None:
        limits = QualityFilter(
            max_tilt_carry_deg=args.max_tilt_carry_deg,
            max_part_shift_end_mm=args.max_part_shift_end_mm,
        )
        episodes, pin = apply_quality(episodes, args.quality, limits)
    sets = nested_sets(
        args.release.name, release_hash, episodes, dict(args.size), quality=pin, qa=qa_pin
    )
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
