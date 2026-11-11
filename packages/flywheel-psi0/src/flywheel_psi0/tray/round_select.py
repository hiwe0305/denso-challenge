"""Plan and pick the targeted set of C70_R1 by the rule fixed before generation (DA-34 7.5).

docs/he/tray.md 20.5 and 20.14, committed before the targeted batch ran:

- Each failure that gets data (20.13) is one line of the conditions file; its
  `cluster_id` starts with its pool, the scorer step it failed first:
  `approach_a-L<level>-<seed>` or `place-L<level>-<seed>`.
- `plan`: the train seeds nearest to each condition, as `flywheel_simple.tray.targets`
  plans them, minus every seed already used: ALL's episodes and every seed a batch in
  the window has logged. `generate.py --conditions` does not exclude seeds, and the
  planner is deterministic, so a reused seed would put an episode of ALL (or S70) into
  C70_R1 twice. The plan is written as the batch's `targets.jsonl`, which
  `generate.py` then reuses (same conditions sha256).
- `select`: among the seeds that passed QA as ALL's targeted part did (release,
  DA-03 QA, quality filter), the earlier step first: each `approach_a` failure takes up
  to `quota` (20) of its nearest passing seeds, in file order. What is left of the
  budget (B_add = 181) goes to the `place` failures round-robin in file order, each
  round one more passing seed per failure, nearest first, until the budget is spent or
  no failure has a seed left.

Writes a demo-set file with one set `R<k>` (k picked) on the targeted release, in the
shape of demo_sets-cplus.json, and the selection: one row per pick with its condition,
pool, rank among the condition's passing seeds and distance.

    python -m flywheel_psi0.tray.round_select plan \
        --conditions configs/runplans/tray/round-c70-conditions.jsonl \
        --exclude <seeds.json> [--exclude ...] --out <batch>/targets.jsonl
    python -m flywheel_psi0.tray.round_select select \
        --conditions configs/runplans/tray/round-c70-conditions.jsonl \
        --targets <batch>/targets.jsonl --release <targeted release> --qa-work <work> \
        --quality <batch>/quality.jsonl --max-tilt-carry-deg 10 --max-part-shift-end-mm 20 \
        --budget 181 --quota 20 --out-sets <demo_sets.json> --out-selection <selection.jsonl>
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from flywheel_psi0.tray.cplus_select import candidates_of, file_sha256, read_jsonl
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

POOLS = ("approach_a", "place")  # earlier failing step first (tray.md 20.5)


@dataclass(frozen=True)
class Pick:
    cluster_id: str
    seed: int
    pool: str
    rank: int  # 1 = the condition's nearest seed that passed QA
    distance: float  # to the condition, as flywheel_simple.tray.targets measured it


def pool_of(cluster_id: str) -> str:
    pool = cluster_id.split("-L", 1)[0]
    if pool not in POOLS:
        raise ValueError(f"{cluster_id}: pool {pool!r} is none of {POOLS}")
    return pool


def select(
    conditions: Sequence[str],
    candidates: Mapping[str, Sequence[tuple[float, int]]],
    passing: set[int],
    budget: int,
    quota: int,
) -> tuple[list[Pick], list[str]]:
    """The picks (at most `budget`), and the conditions that fell short.

    Short: an `approach_a` condition with fewer than `quota` passing seeds, and, when the
    budget is not spent, every `place` condition whose passing seeds ran out.
    """
    if len(set(conditions)) != len(conditions):
        raise ValueError("a condition is listed twice")
    ranked = {c: [(d, s) for d, s in candidates.get(c, []) if s in passing] for c in conditions}
    first = [c for c in conditions if pool_of(c) == "approach_a"]
    rest = [c for c in conditions if pool_of(c) == "place"]
    picks: list[Pick] = []
    for c in first:
        for r, (d, s) in enumerate(ranked[c][:quota]):
            if len(picks) < budget:
                picks.append(Pick(c, s, "approach_a", r + 1, d))
    r = 0
    while len(picks) < budget:
        took = False
        for c in rest:
            if len(picks) < budget and len(ranked[c]) > r:
                d, s = ranked[c][r]
                picks.append(Pick(c, s, "place", r + 1, d))
                took = True
        if not took:
            break
        r += 1
    short = [c for c in first if len(ranked[c]) < quota]
    if len(picks) < budget:
        short += [c for c in rest if len(ranked[c]) <= r]
    return picks, short


def _seeds(path: Path) -> set[int]:
    """A JSON list of seeds, or a JSONL with a `seed` per row."""
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return {int(s) for s in json.loads(text)}
    return {int(json.loads(line)["seed"]) for line in text.splitlines() if line}


def plan(conditions: Path, exclude: Sequence[Path], out: Path) -> int:
    from flywheel_simple.tray.config import TrayConfig
    from flywheel_simple.tray.targets import load_conditions, plan_targets

    if out.exists():
        raise SystemExit(f"{out} exists: a batch is planned once")
    for c in load_conditions(conditions):
        pool_of(c.cluster_id)
    used: set[int] = set()
    for path in exclude:
        used |= _seeds(path)
    targets = plan_targets(TrayConfig.load(), load_conditions(conditions), exclude=used)
    digest = file_sha256(conditions)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps({"conditions_sha256": digest, "target": asdict(t)}) + "\n"
                for t in targets),
        encoding="utf-8",
    )  # fmt: skip
    summary = {"targets": len(targets), "excluded": len(used), "conditions_sha256": digest}
    print(json.dumps({**summary, "targets_sha256": file_sha256(out)}))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="write the batch's targets.jsonl without used seeds")
    p.add_argument("--conditions", type=Path, required=True)
    p.add_argument("--exclude", type=Path, action="append", default=[])
    p.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("select", help="pick the targeted set from the QA'd batch")
    s.add_argument("--conditions", type=Path, required=True)
    s.add_argument("--targets", type=Path, action="append", required=True)
    s.add_argument("--release", type=Path, required=True, help="the targeted release")
    s.add_argument("--qa-work", type=Path, required=True)
    s.add_argument("--quality", type=Path, required=True)
    s.add_argument("--max-tilt-carry-deg", type=float, required=True)
    s.add_argument("--max-part-shift-end-mm", type=float, required=True)
    s.add_argument("--budget", type=int, default=181)
    s.add_argument("--quota", type=int, default=20)
    s.add_argument(
        "--accept-short", action="store_true", help="after 20.14's one extra batch: keep fewer"
    )
    s.add_argument("--out-sets", type=Path, required=True)
    s.add_argument("--out-selection", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "plan":
        return plan(args.conditions, args.exclude, args.out)

    conditions = [str(r["cluster_id"]) for r in read_jsonl(args.conditions)]
    candidates = candidates_of(args.targets, file_sha256(args.conditions))
    release_hash, episodes = read_release(args.release)
    episodes, qa_pin = apply_qa(episodes, args.qa_work, args.release)
    limits = QualityFilter(
        max_tilt_carry_deg=args.max_tilt_carry_deg,
        max_part_shift_end_mm=args.max_part_shift_end_mm,
    )
    episodes, quality_pin = apply_quality(episodes, args.quality, limits)
    index_of = {e.seed: e.episode_index for e in episodes}
    picks, short = select(conditions, candidates, set(index_of), args.budget, args.quota)
    summary = {
        "passing": len(index_of),
        "picked": len(picks),
        "approach_a": sum(p.pool == "approach_a" for p in picks),
        "place": sum(p.pool == "place" for p in picks),
        "short": short,
    }
    if len(picks) < args.budget and not args.accept_short:
        print(json.dumps(summary, indent=1))
        raise SystemExit(f"{len(picks)} < {args.budget}: one extra batch for {len(short)} (20.14)")

    seeds = sorted(p.seed for p in picks)
    name = f"R{len(picks)}"
    sets = DemoSets(
        release_id=args.release.name,
        release_hash=release_hash,
        salt=SALT,  # not used to pick: the order is the rule's, recorded in the selection
        sets={
            name: DemoSet(
                n=len(picks),
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
