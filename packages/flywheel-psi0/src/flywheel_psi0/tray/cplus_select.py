"""Pick the 160 targeted episodes of branch C+ by the rule fixed before generation (DA-34 task 5).

docs/he/tray.md section 17.3, written and committed before the targeted batch ran:

1. In the order of the conditions file, each condition takes its nearest seed that
   passed QA.
2. If that gives fewer than `n`, conditions add their second passing seed, the ones
   with the larger final placement distance in eval C first (place-error file).
3. If still short, a new batch with n = 1 for the conditions with no passing seed;
   its targets file is passed here too and steps 1-2 run again.

"Nearest" is the order `flywheel_simple.tray.targets` gave: each target row carries
its distance to the condition. "Passed QA" is what C's sets used (section 10): in the
release (generator QA and replay QA), not rejected or quarantined by DA-03's QA,
and under the quality limits (`demo_sets.apply_qa`, `demo_sets.apply_quality`).

Writes a demo-set file with one set (`T<n>`) on the targeted release, in the shape
of `demo_sets-v2.json`, and the selection: one row per picked episode with its
condition, step and rank.

    python -m flywheel_psi0.tray.cplus_select \
        --conditions configs/runplans/tray/cplus-conditions.jsonl \
        --place-error configs/runplans/tray/cplus-conditions-place-error.jsonl \
        --targets <batch>/targets.jsonl --release <targeted release> --qa-work <work dir> \
        --quality <batch>/quality.jsonl --max-tilt-carry-deg 10 --max-part-shift-end-mm 20 \
        --n 160 --out-sets configs/runplans/tray/demo_sets-cplus.json \
        --out-selection configs/runplans/tray/cplus-selection.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flywheel_psi0.tray.demo_sets import (
    SALT,
    DemoSet,
    DemoSets,
    apply_qa,
    apply_quality,
    read_release,
    set_hash,
)
from flywheel_psi0.tray.quality import QualityFilter


@dataclass(frozen=True)
class Pick:
    cluster_id: str
    seed: int
    step: int  # rule step of section 17.3 that took it (1 or 2)
    rank: int  # 1 = the condition's nearest passing seed, 2 = its second
    distance: float  # to the condition, as flywheel_simple.tray.targets measured it


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def candidates_of(
    target_files: Sequence[Path], conditions_sha256: str
) -> dict[str, list[tuple[float, int]]]:
    """Per condition, its generated seeds nearest first: (distance, seed).

    Every targets file must come from this conditions file (`conditions_sha256`), and a
    seed may belong to one condition only.
    """
    out: dict[str, list[tuple[float, int]]] = {}
    owner: dict[int, str] = {}
    for path in target_files:
        for row in read_jsonl(path):
            if row["conditions_sha256"] != conditions_sha256:
                raise ValueError(f"{path} was planned from another conditions file")
            t = row["target"]
            seed, cluster = int(t["seed"]), str(t["cluster_id"])
            if owner.setdefault(seed, cluster) != cluster:
                raise ValueError(f"seed {seed} is a target of {owner[seed]} and {cluster}")
            out.setdefault(cluster, []).append((float(t["distance"]), seed))
    return {c: sorted(set(v)) for c, v in out.items()}


def select(
    conditions: Sequence[str],
    place_distance: Mapping[str, float],
    candidates: Mapping[str, Sequence[tuple[float, int]]],
    passing: set[int],
    n: int,
) -> tuple[list[Pick], list[str]]:
    """Steps 1-2 of section 17.3: the picks (at most n), and the conditions with no pick.

    A short result means step 3: a new batch for the returned conditions.
    """
    ranked = {c: [(d, s) for d, s in candidates.get(c, []) if s in passing] for c in conditions}
    picks = [Pick(c, ranked[c][0][1], 1, 1, ranked[c][0][0]) for c in conditions if ranked[c]]
    picks = picks[:n]
    position = {c: i for i, c in enumerate(conditions)}
    for c in sorted(conditions, key=lambda c: (-place_distance[c], position[c])):
        if len(picks) >= n:
            break
        if len(ranked[c]) > 1:
            picks.append(Pick(c, ranked[c][1][1], 2, 2, ranked[c][1][0]))
    unserved = [c for c in conditions if not ranked[c]]
    return picks, unserved


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conditions", type=Path, required=True)
    parser.add_argument("--place-error", type=Path, required=True)
    parser.add_argument("--targets", type=Path, action="append", required=True)
    parser.add_argument("--release", type=Path, required=True, help="the targeted release")
    parser.add_argument("--qa-work", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--max-tilt-carry-deg", type=float, required=True)
    parser.add_argument("--max-part-shift-end-mm", type=float, required=True)
    parser.add_argument("--n", type=int, default=160)
    parser.add_argument("--out-sets", type=Path, required=True)
    parser.add_argument("--out-selection", type=Path, required=True)
    args = parser.parse_args(argv)

    conditions = [str(r["cluster_id"]) for r in read_jsonl(args.conditions)]
    if len(set(conditions)) != len(conditions):
        raise SystemExit(f"{args.conditions} lists a condition twice")
    place = {str(r["cluster_id"]): float(r["distance_m"]) for r in read_jsonl(args.place_error)}
    if set(place) != set(conditions):
        raise SystemExit(f"{args.place_error} does not cover exactly the conditions")
    candidates = candidates_of(args.targets, file_sha256(args.conditions))

    release_hash, episodes = read_release(args.release)
    episodes, qa_pin = apply_qa(episodes, args.qa_work, args.release)
    limits = QualityFilter(
        max_tilt_carry_deg=args.max_tilt_carry_deg,
        max_part_shift_end_mm=args.max_part_shift_end_mm,
    )
    episodes, quality_pin = apply_quality(episodes, args.quality, limits)
    index_of = {e.seed: e.episode_index for e in episodes}

    picks, unserved = select(conditions, place, candidates, set(index_of), args.n)
    summary = {
        "passing": len(index_of),
        "picked": len(picks),
        "step_1": sum(p.step == 1 for p in picks),
        "step_2": sum(p.step == 2 for p in picks),
        "conditions_without_a_passing_seed": len(unserved),
    }
    if len(picks) < args.n:
        print(json.dumps({**summary, "step_3_for": unserved}, indent=1))
        raise SystemExit(f"{len(picks)} < {args.n}: step 3, a new batch for {len(unserved)}")

    seeds = sorted(p.seed for p in picks)
    name = f"T{args.n}"
    sets = DemoSets(
        release_id=args.release.name,
        release_hash=release_hash,
        salt=SALT,  # not used to pick: the order is the rule's, recorded in the selection
        sets={
            name: DemoSet(
                n=args.n,
                set_hash=set_hash(release_hash, seeds),
                seeds=seeds,
                episode_indices=sorted(index_of[s] for s in seeds),
            )
        },
        quality=quality_pin,
        qa=qa_pin,
    )
    args.out_sets.write_text(sets.model_dump_json(indent=1) + "\n", encoding="utf-8")
    args.out_selection.write_text(
        "".join(json.dumps(asdict(p)) + "\n" for p in picks), encoding="utf-8"
    )
    print(json.dumps({**summary, "set": name, "set_hash": sets.sets[name].set_hash}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
