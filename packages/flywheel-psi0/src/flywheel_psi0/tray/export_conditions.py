"""Write tray conditions (level, seed) as contract `Condition` records (DA-43 K1).

The lane's coverage check (`configs/eval/agentqa/tasks/tray.yaml`, block `coverage`) reads
each component of a condition BY NAME from `Condition.values`. This command fixes those
names from the simulator's own sample, `flywheel_simple.tray.randomize.sample_episode`:

    tray_x, tray_y, tray_yaw        tray pose on table A, `tray_pose` (m, m, rad)
    target_x, target_y, target_yaw  target zone on table B, `target_pose` (m, m, rad)
    table_gap                       corridor width between the tables, `table_gap` (m)
    spawn_x                         robot spawn x, `robot_spawn.x` (m); its y and yaw are
                                    never randomised (randomize.py, D-05)
    part_mass                       mass of each part, `part_mass` (kg)
    light_scale                     light scale, `light_scale` (unitless)

All ten are written for every level, the ones the level keeps at their defaults too;
`vector` holds the same numbers in that order (`COMPONENTS`). Per condition:
`condition_seed` and `level`, `split` per `split_of(seed)` (a holdout seed is refused),
`origin` "generated", `task_id` "tray", `layout_hash` the sha256 of the canonical JSON of
the whole sample without its level and seed (equal layouts hash equal), and `set_id`.

Two sources:

    --set <eval set>      role eval: the set's `conditions.jsonl`; `set_id` is the set's
                          directory name. `--max-chunks N` keeps the conditions of the
                          first N chunks of the run order (`eval_batch.chunk_plan`), as
                          `export_scores --max-chunks` does (6: stage 1, 60 conditions).
    --release <dir> ...   role train: LeRobot datasets (`meta/episodes.jsonl`); level and
                          seed from each episode's `environment_config.tray.sample`,
                          `set_id` the dataset directory's name. Every episode, unless
                          `--plan <pair plan> --cut <name>` selects the episodes a run of
                          the pair trained on: for each release, the plan's cut part whose
                          `release.id` is the directory name gives the seed list, the part's
                          demo set for the cut itself (ALL) or the subset's list (S70, its
                          sha256 checked against the plan's pin), matched by each
                          episode's own seed (`pair_cut.episode_seed`), as `pair_cut` cut it.
                          The sample the episode recorded must equal the rebuilt one.

A (level, seed) met twice in one output is written once; the count is printed.

    python -m flywheel_psi0.tray.export_conditions --set <eval set> [--max-chunks 6] \
        --conditions <file>
    python -m flywheel_psi0.tray.export_conditions --release <dir> [--release <dir>] \
        [--plan configs/runplans/tray/he-tray-pair60k.yaml --cut S70] --conditions <file>

`flywheel_simple` is imported when the command runs, as `place_error` does.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.entities import Condition

from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for
from flywheel_psi0.tray.pair_cut import episode_seed, read_rows
from flywheel_psi0.tray.runplan import REPO

TASK_ID = "tray"
COMPONENTS = (
    "tray_x",
    "tray_y",
    "tray_yaw",
    "target_x",
    "target_y",
    "target_yaw",
    "table_gap",
    "spawn_x",
    "part_mass",
    "light_scale",
)
SAMPLE_TOL = 1e-9  # recorded against rebuilt sample, per number


def values_of(sample: Any) -> dict[str, float]:
    """The ten named components of an `EpisodeSample`."""
    return {
        "tray_x": float(sample.tray_pose.x),
        "tray_y": float(sample.tray_pose.y),
        "tray_yaw": float(sample.tray_pose.yaw),
        "target_x": float(sample.target_pose.x),
        "target_y": float(sample.target_pose.y),
        "target_yaw": float(sample.target_pose.yaw),
        "table_gap": float(sample.table_gap),
        "spawn_x": float(sample.robot_spawn.x),
        "part_mass": float(sample.part_mass),
        "light_scale": float(sample.light_scale),
    }


def layout_hash(sample: Any) -> str:
    """sha256 of the sample's canonical JSON, level and seed left out."""
    layout = {k: v for k, v in dataclasses.asdict(sample).items() if k not in ("level", "seed")}
    return hashlib.sha256(
        json.dumps(layout, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def condition_of(sample: Any, split: str, set_id: str, meta: dict[str, Any]) -> Condition:
    values = values_of(sample)
    return Condition(
        task_id=TASK_ID,
        condition_seed=int(sample.seed),
        level=int(sample.level),
        values=values,
        vector=[values[name] for name in COMPONENTS],
        layout_hash=layout_hash(sample),
        split=split,  # type: ignore[arg-type]
        origin="generated",
        set_id=set_id,
        meta=meta,
    )


Sampler = Callable[[int, int], Any]  # (level, seed) -> EpisodeSample
Splitter = Callable[[int], str]


def default_sim() -> tuple[Sampler, Splitter]:
    from flywheel_simple.tray.config import TrayConfig
    from flywheel_simple.tray.randomize import sample_episode, split_of

    cfg = TrayConfig.load()
    return (lambda level, seed: sample_episode(cfg, level, seed)), split_of


def build(
    items: Iterable[tuple[int, int, str, dict[str, Any], dict[str, Any] | None]],
    sample_of: Sampler,
    split_of: Splitter,
) -> tuple[list[Condition], int]:
    """Conditions of (level, seed, set_id, meta, recorded sample); duplicates written once."""
    out: list[Condition] = []
    seen: set[tuple[int, int]] = set()
    duplicates = 0
    for level, seed, set_id, meta, recorded in items:
        if (level, seed) in seen:
            duplicates += 1
            continue
        seen.add((level, seed))
        sample = sample_of(level, seed)
        if recorded is not None:
            mismatch = recorded_mismatch(sample, recorded)
            if mismatch:
                raise ValueError(f"(level {level}, seed {seed}) in {set_id}: {mismatch}")
        split = split_of(seed)
        if split not in ("train", "dev"):
            raise ValueError(f"seed {seed} is a {split} seed; it never leaves vault/")
        out.append(condition_of(sample, split, set_id, meta))
    return out, duplicates


def recorded_mismatch(sample: Any, recorded: dict[str, Any]) -> str | None:
    """What differs between the rebuilt sample and the one an episode recorded."""
    want = values_of(sample)
    got = {
        "tray_x": recorded["tray_pose"]["x"],
        "tray_y": recorded["tray_pose"]["y"],
        "tray_yaw": recorded["tray_pose"]["yaw"],
        "target_x": recorded["target_pose"]["x"],
        "target_y": recorded["target_pose"]["y"],
        "target_yaw": recorded["target_pose"]["yaw"],
        "table_gap": recorded["table_gap"],
        "spawn_x": recorded["robot_spawn"]["x"],
        "part_mass": recorded["part_mass"],
        "light_scale": recorded["light_scale"],
    }
    off = [k for k in COMPONENTS if not math.isclose(want[k], got[k], abs_tol=SAMPLE_TOL)]
    return f"recorded sample differs from the rebuilt one in {off}" if off else None


def eval_items(
    eval_set: Path, chunk: int = 10, max_chunks: int | None = None
) -> list[tuple[int, int, str, dict[str, Any], None]]:
    rows = [json.loads(line) for line in (eval_set / "conditions.jsonl").read_text().splitlines()]
    chunks = chunk_plan(rows, chunk, phases_for(rows))
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    return [
        (c.level, seed, eval_set.name, {"role": "eval"}, None) for c in chunks for seed in c.seeds
    ]


def selection(release: Path, plan_path: Path, cut: str) -> set[int]:
    """Seeds of the release that cut `cut` of the pair plan kept (the cut or a subset)."""
    from flywheel_psi0.tray.pairplan import (
        TrayPairPlan,
        part_seeds,
        seeds_sha256,
        subset_lists,
    )

    plan = TrayPairPlan.load(plan_path)
    repo = REPO  # the plan's demo-set files are paths in this repo, as pair_cut reads them
    part = next((p for p in plan.cut.parts if p.release and p.release.id == release.name), None)
    if part is None:
        raise ValueError(f"{release.name} is no part of the plan's cut {plan.cut.name}")
    if cut == plan.cut.name:
        seeds = part_seeds(part, repo)
        if seeds is None:
            raise ValueError(f"part {part.regenerates} is not pinned")
        return set(seeds)
    subset = plan.subset(cut)
    if subset is None:
        raise ValueError(f"{cut} is neither the cut {plan.cut.name} nor a subset of the plan")
    seeds = subset_lists(plan, repo).get(cut, {}).get(part.regenerates)
    pin = next((sp for sp in subset.parts if sp.regenerates == part.regenerates), None)
    if seeds is None or pin is None or seeds_sha256(seeds) != pin.seeds_sha256:
        raise ValueError(f"subset {cut} part {part.regenerates}: list missing or off its pin")
    return set(seeds)


def release_items(
    releases: Sequence[Path], plan: Path | None = None, cut: str | None = None
) -> list[tuple[int, int, str, dict[str, Any], dict[str, Any]]]:
    items = []
    for release in releases:
        rows = read_rows(release)
        if not rows:
            raise ValueError(f"{release}: no meta/episodes.jsonl")
        keep = selection(release, plan, cut) if plan is not None and cut is not None else None
        found = set()
        for row in rows:
            if keep is not None:
                if episode_seed(row) not in keep:
                    continue
                found.add(episode_seed(row))
            config = row["environment_config"]
            config = json.loads(config) if isinstance(config, str) else config
            sample = config["tray"]["sample"]
            meta = {"role": "train", "episode_index": int(row["episode_index"])}
            if cut is not None:
                meta["cut"] = cut
            items.append((int(sample["level"]), int(sample["seed"]), release.name, meta, sample))
        if keep is not None and found != keep:
            raise ValueError(f"{release.name}: {len(keep - found)} seeds of cut {cut} not found")
    return items


def write(conditions: Sequence[Condition], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(c.model_dump_json() + "\n" for c in conditions))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--set", type=Path, help="eval set of eval_set.py (role eval)")
    source.add_argument(
        "--release", type=Path, action="append", help="LeRobot dataset dir (role train)"
    )
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--max-chunks", type=int, help="--set: first N chunks only (6: stage 1)")
    parser.add_argument("--plan", type=Path, help="--release: pair plan whose cut selects")
    parser.add_argument("--cut", help="--release: the cut (ALL) or a subset (S70) of --plan")
    parser.add_argument("--conditions", type=Path, required=True, help="conditions.jsonl to write")
    args = parser.parse_args(argv)
    if (args.plan is None) != (args.cut is None):
        parser.error("--plan and --cut go together")
    if args.set is not None and args.plan is not None:
        parser.error("--plan and --cut select release episodes, not eval conditions")
    if args.conditions.exists():
        parser.error(f"{args.conditions} exists; write to a new file")
    sample_of, split_of = default_sim()
    try:
        items: Sequence[tuple[int, int, str, dict[str, Any], dict[str, Any] | None]]
        if args.set is not None:
            items = eval_items(args.set, args.chunk, args.max_chunks)
        else:
            items = release_items(args.release, args.plan, args.cut)
        conditions, duplicates = build(items, sample_of, split_of)
    except ValueError as exc:
        print(f"export_conditions: {exc}", file=sys.stderr)
        return 1
    write(conditions, args.conditions)
    by_level: dict[int, int] = {}
    for c in conditions:
        by_level[c.level] = by_level.get(c.level, 0) + 1
    print(
        json.dumps(
            {
                "conditions": len(conditions),
                "duplicates_skipped": duplicates,
                "by_level": {str(k): v for k, v in sorted(by_level.items())},
                "file": str(args.conditions),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
