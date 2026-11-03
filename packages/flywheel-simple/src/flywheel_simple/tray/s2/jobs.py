"""S2 jobs: which parent to replay on which condition, with which generation seed (DA-35).

Conditions stay in the train domain (levels 0 and 1, train seeds; spec 7.3).
Pure numpy: runs in the workspace.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.tray.pico.conditions import LEVELS, Condition
from flywheel_simple.tray.randomize import split_of


@dataclass(frozen=True)
class S2Job(Condition):
    """One S2 attempt: `parent_id` replayed on the condition (level, seed)."""

    parent_id: str
    gen_seed: int = 0

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"{self}: level {self.level} is outside the S2 train domain {LEVELS}")
        if split_of(self.seed) != "train":
            raise ValueError(f"{self}: seed {self.seed} is not a train seed")

    @property
    def key(self) -> tuple[str, int, int, int]:
        return (self.parent_id, self.level, self.seed, self.gen_seed)


def read_jobs(path: Path) -> list[S2Job]:
    """Jobs of a JSON-lines file (`parent_id`, `level`, `seed`, `gen_seed` per line)."""
    jobs = []
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            jobs.append(
                S2Job(int(row["level"]), int(row["seed"]), row["parent_id"], int(row["gen_seed"]))
            )
    return jobs


def sample_jobs(
    parents: Sequence[Mapping[str, Any]],
    count: int,
    gen_base: int,
    level1_share: float,
    seed_range: tuple[int, int],
) -> list[S2Job]:
    """`count` jobs drawn from `gen_base`: the same base gives the same list.

    Job i draws from `SeedSequence([gen_base, i])`: a parent uniformly, level 1
    with probability `level1_share` (else 0), a condition seed in `seed_range`
    and its generation seed. Level 0 is the default scene whatever the seed, so a
    level-0 parent on level 0 would replay its own scene and a second level-0
    job of a parent the same scene again; such draws are drawn again.
    """
    jobs: list[S2Job] = []
    scenes: set[tuple[str, int, int]] = set()
    i = 0
    while len(jobs) < count:
        if i > 100 * count + 1000:
            raise RuntimeError(f"only {len(jobs)} distinct jobs after {i} draws")
        rng = np.random.default_rng(np.random.SeedSequence([gen_base, i]))
        i += 1
        parent = parents[int(rng.integers(len(parents)))]
        level = 1 if rng.random() < level1_share else 0
        seed = int(rng.integers(seed_range[0], seed_range[1] + 1))
        gen_seed = int(rng.integers(2**31))
        scene = (str(parent["parent_id"]), level, seed if level == 1 else 0)
        if (level == 0 and int(parent["level"]) == 0) or scene in scenes:
            continue
        scenes.add(scene)
        jobs.append(S2Job(level, seed, str(parent["parent_id"]), gen_seed))
    return jobs
