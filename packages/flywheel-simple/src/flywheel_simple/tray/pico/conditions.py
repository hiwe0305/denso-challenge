"""The (level, seed) list a teleop session records, in the train domain only.

SIMPLE's teleop CLI resets without a seed, so the task draws one at random. A
session here walks an explicit list instead, retrying a condition until the
operator succeeds or the attempts run out. Demos and their S2 variants stay in
levels 0 and 1 of the train seed range (spec 7.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flywheel_simple.tray.randomize import split_of

LEVELS = (0, 1)


@dataclass(frozen=True)
class Condition:
    level: int
    seed: int


def parse_conditions(spec: str) -> list[Condition]:
    """`"0:0-4,1:10,1:20-21"` -> conditions; refuses level 2, dev and holdout seeds, repeats."""
    out: list[Condition] = []
    for item in spec.split(","):
        level_text, sep, seeds = item.strip().partition(":")
        if not sep or not level_text.isdigit():
            raise ValueError(f"condition {item!r} is not <level>:<seed>[-<seed>]")
        level = int(level_text)
        if level not in LEVELS:
            raise ValueError(f"level {level} is outside the S2 train domain {LEVELS}")
        first, _, last = seeds.partition("-")
        if not first.isdigit() or (last and not last.isdigit()):
            raise ValueError(f"condition {item!r} has a malformed seed")
        lo, hi = int(first), int(last or first)
        if hi < lo:
            raise ValueError(f"condition {item!r} has an empty seed range")
        for seed in range(lo, hi + 1):
            if split_of(seed) != "train":
                raise ValueError(f"seed {seed} is not a train seed")
            out.append(Condition(level, seed))
    if len(set(out)) != len(out):
        raise ValueError("a condition is listed twice")
    return out


class ConditionQueue:
    """Current condition and attempt number; moves on after a success or `max_attempts` tries."""

    def __init__(self, conditions: Sequence[Condition], max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._conditions = list(conditions)
        self._index = 0
        self.max_attempts = max_attempts
        self.attempt = 1

    @property
    def current(self) -> Condition | None:
        return self._conditions[self._index] if self._index < len(self._conditions) else None

    def record(self, success: bool) -> None:
        if self.current is None:
            raise RuntimeError("no condition left")
        if success or self.attempt >= self.max_attempts:
            self._index += 1
            self.attempt = 1
        else:
            self.attempt += 1
