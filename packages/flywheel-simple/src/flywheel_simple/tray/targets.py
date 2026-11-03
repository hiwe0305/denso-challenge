"""Failure-targeted generation: train seeds whose scene is near a failure condition (DA-33 Task 10).

A Failure -> Data round (design 28/10/2026 section 6.6) finds failures on dev
conditions, but new episodes must stay in the train domain (spec 7.3 rule 7,
Q-33A). So a failure condition is never regenerated; instead, for each one, the
generator searches a window of train seeds for those whose `sample_episode`
lands nearest to the condition's scene parameters, and records those seeds as
they are. Every scene then comes from (level, seed) alone, so replay QA rebuilds
it from `environment_config` like any other episode.

A conditions file is JSONL, one failure condition per line:

    {"cluster_id": "c1", "level": 1, "n": 10, "seed": 1000123}
    {"cluster_id": "c2", "level": 1, "n": 5, "tray_pose": [x, y, yaw], "match": ["tray"]}

`seed` (any split) names the condition through its sampled scene; explicit
`tray_pose` / `target_pose` ([m, m, rad], world frame) override that or stand
alone. `match` picks the parameter groups the distance uses; by default the
groups `level` randomises. Distance is Euclidean over each parameter divided by
its randomisation half-range, so 1.0 means "one jitter apart".

The plan is written once to <batch>/targets.jsonl; running again reuses it, so
a resumed batch works through the same seeds.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D
from flywheel_simple.tray.randomize import (
    GAP_RANGE,
    LIGHT_RANGE,
    PART_MASS_RANGE,
    POSE_JITTER,
    SEED_RANGES,
    SPAWN_JITTER,
    YAW_JITTER,
    EpisodeSample,
    sample_episode,
)

TARGETS_NAME = "targets.jsonl"
PURPOSE = "failure_targeted"
# Train seeds searched for neighbours; disjoint from every seed DA-33 used so far
# (0-143 tuning and t7, 1000-1129 release tray_s1_0d84cc87b1e5).
SEARCH = range(100_000, 200_000)
GROUPS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("tray", "target"),
    2: ("tray", "target", "gap", "spawn", "part_mass", "light"),
}
ALL_GROUPS = GROUPS_BY_LEVEL[2]


@dataclass(frozen=True)
class Condition:
    cluster_id: str
    level: int
    n: int
    seed: int | None = None
    tray_pose: tuple[float, float, float] | None = None
    target_pose: tuple[float, float, float] | None = None
    match: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.level not in (1, 2):
            raise ValueError(f"{self.cluster_id}: level {self.level} varies nothing; use 1 or 2")
        if self.n <= 0:
            raise ValueError(f"{self.cluster_id}: n must be positive")
        if self.seed is None and self.tray_pose is None and self.target_pose is None:
            raise ValueError(f"{self.cluster_id}: give a seed, a tray_pose or a target_pose")
        groups = self.match or GROUPS_BY_LEVEL[self.level]
        unknown = set(groups) - set(ALL_GROUPS)
        if unknown:
            raise ValueError(f"{self.cluster_id}: unknown match groups {sorted(unknown)}")
        if self.seed is None:
            groups = tuple(g for g in groups if (g == "tray" and self.tray_pose) or
                           (g == "target" and self.target_pose))
        if not groups:
            raise ValueError(f"{self.cluster_id}: no parameter left to match")
        object.__setattr__(self, "match", tuple(groups))


@dataclass(frozen=True)
class Target:
    seed: int
    level: int
    cluster_id: str
    distance: float
    purpose: str = field(default=PURPOSE)


def load_conditions(path: Path) -> list[Condition]:
    conditions = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for key in ("tray_pose", "target_pose", "match"):
            if key in row:
                row[key] = tuple(row[key])
        conditions.append(Condition(**row))
    ids = [c.cluster_id for c in conditions]
    if not conditions:
        raise ValueError(f"{path} has no condition")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: cluster_id must be unique per line")
    return conditions


def _pose(p: Pose2D) -> tuple[float, float, float]:
    return (p.x, p.y, p.yaw)


def _yaw_gap(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _scaled(sample: EpisodeSample) -> dict[str, tuple[float, ...]]:
    """Each parameter group of a sample in units of its randomisation half-range."""
    def half(r: tuple[float, float]) -> float:
        return (r[1] - r[0]) / 2

    return {
        "gap": (sample.table_gap / half(GAP_RANGE),),
        "spawn": (sample.robot_spawn.x / SPAWN_JITTER,),
        "part_mass": (sample.part_mass / half(PART_MASS_RANGE),),
        "light": (sample.light_scale / half(LIGHT_RANGE),),
    }


def distance(cond: Condition, ref: EpisodeSample | None, cand: EpisodeSample) -> float:
    """How far a candidate scene is from the condition, over cond.match."""
    total = 0.0
    for group in cond.match:
        if group in ("tray", "target"):
            given = cond.tray_pose if group == "tray" else cond.target_pose
            if given is None:
                assert ref is not None
                given = _pose(ref.tray_pose if group == "tray" else ref.target_pose)
            pose = cand.tray_pose if group == "tray" else cand.target_pose
            total += ((pose.x - given[0]) / POSE_JITTER) ** 2
            total += ((pose.y - given[1]) / POSE_JITTER) ** 2
            total += (_yaw_gap(pose.yaw, given[2]) / YAW_JITTER) ** 2
        else:
            assert ref is not None  # groups beyond the poses need a seed (__post_init__)
            total += sum((a - b) ** 2 for a, b in zip(_scaled(cand)[group], _scaled(ref)[group]))
    return math.sqrt(total)


def plan_targets(
    cfg: TrayConfig,
    conditions: Sequence[Condition],
    exclude: Iterable[int] = (),
    search: range = SEARCH,
) -> list[Target]:
    """The n nearest unused train seeds of each condition, conditions in file order."""
    train = SEED_RANGES["train"]
    if not (train.start <= search.start and search.stop <= train.stop):
        raise ValueError(f"search window {search} leaves the train range")
    used = set(exclude)
    samples = {level: [sample_episode(cfg, level, s) for s in search]
               for level in sorted({c.level for c in conditions})}
    targets: list[Target] = []
    for cond in conditions:
        ref = sample_episode(cfg, cond.level, cond.seed) if cond.seed is not None else None
        ranked = sorted(
            (distance(cond, ref, cand), cand.seed)
            for cand in samples[cond.level]
            if cand.seed not in used
        )[: cond.n]
        if len(ranked) < cond.n:
            raise ValueError(f"{cond.cluster_id}: only {len(ranked)} free seeds in {search}")
        for dist, seed in ranked:
            used.add(seed)
            targets.append(Target(seed, cond.level, cond.cluster_id, round(dist, 4)))
    return targets


def conditions_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_targets(
    out: Path, conditions_path: Path, cfg: TrayConfig | None = None, search: range = SEARCH
) -> list[Target]:
    """Plan targets for a batch once; later calls return the saved plan (same conditions only)."""
    path = Path(out) / TARGETS_NAME
    digest = conditions_hash(conditions_path)
    if path.exists():
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        if rows[0]["conditions_sha256"] != digest:
            raise ValueError(f"{path} was planned from other conditions; use a new batch directory")
        return [Target(**r["target"]) for r in rows]
    conditions = load_conditions(conditions_path)
    targets = plan_targets(cfg or TrayConfig.load(), conditions, search=search)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"conditions_sha256": digest, "target": asdict(t)}) for t in targets]
    path.write_text("\n".join(lines) + "\n")
    return targets


def read_targets(out: Path) -> list[Target]:
    path = Path(out) / TARGETS_NAME
    return [Target(**json.loads(line)["target"]) for line in path.read_text().splitlines() if line]
