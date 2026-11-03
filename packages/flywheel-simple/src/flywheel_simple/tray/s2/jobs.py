"""S2 jobs: which parent to replay on which condition, with which generation seed (DA-35).

Conditions stay in the train domain (levels 0 and 1, train seeds; spec 7.3).
Pure Python: runs in the workspace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
