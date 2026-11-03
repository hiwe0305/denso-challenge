"""A two-table task definition the scorer tests score against (DA-36 AC 6).

The scorer has no task in it, so testing it needs one. This is the six-step
task of spec section 5.1 with the failure kinds of section 5.2, written against
synthetic signals: the predicates are real, the world is not. It lives in the
tests because `TaskDefinition` is what the lane plugs in, not what it owns -
the tray task has seven steps and its own codes, and the same scorer has to
score both (AC 1, 4).

Every threshold arrives through `ScorerParams`. None is written here, for the
same reason none is written in the scorer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pyarrow as pa  # type: ignore[import-untyped]
import pytest
from flywheel.contracts import (
    ConditionSchema,
    FailureKindSpec,
    ScorerParams,
    SignalSpec,
    StageEvaluation,
    StageSpec,
)

SIGNALS: tuple[tuple[str, str], ...] = (
    ("hand_object_distance", "m"),
    ("hand_object_contact", "bool"),
    ("object_height", "m"),
    ("torso_in_source_zone", "bool"),
    ("torso_in_target_zone", "bool"),
    ("object_in_target_zone", "bool"),
    ("collision", "bool"),
    ("torso_height", "m"),
    ("torso_tilt", "rad"),
    ("t", "s"),
)

STEP_SIGNALS: tuple[str, ...] = (
    "hand_object_distance",
    "hand_object_contact",
    "object_height",
    "torso_in_source_zone",
    "torso_in_target_zone",
    "object_in_target_zone",
    "t",
)

_KIND_BY_STAGE = ("L-REACH", "L-GRASP", "L-WALK", "L-WALK", "L-PLACE", "L-RELEASE")


class TwoTableTask:
    """Pick on table A, walk, place on table B (spec section 5.1)."""

    task_id = "two-table"
    version = "0.1.0"
    family = "pick_place"

    def stages(self) -> tuple[StageSpec, ...]:
        return (
            StageSpec(name="approach", failure_class="approach"),
            StageSpec(name="grasp", failure_class="grasp"),
            StageSpec(name="walk", failure_class="carry"),
            StageSpec(name="arrive", failure_class="carry"),
            StageSpec(name="place", failure_class="place"),
            StageSpec(name="release", failure_class="place"),
        )

    def failure_kinds(self) -> tuple[FailureKindSpec, ...]:
        # L-UNKNOWN is not declared: it is what the scorer says when no kind can
        # be assigned, not a kind the task can fail with.
        return (
            FailureKindSpec(kind="L-REACH", failure_class="approach"),
            FailureKindSpec(kind="L-GRASP", failure_class="grasp"),
            FailureKindSpec(kind="L-SLIP", failure_class="carry"),
            FailureKindSpec(kind="L-WALK", failure_class="carry"),
            FailureKindSpec(kind="L-PLACE", failure_class="place"),
            FailureKindSpec(kind="L-RELEASE", failure_class="place"),
            FailureKindSpec(kind="L-BALANCE", failure_class="balance"),
            # The declared class is a placeholder for the next two: spec
            # section 5.2 gives them the class of the failed step, which only
            # the episode knows, so `evaluate` fills `failure_class` instead.
            FailureKindSpec(kind="L-COLLIDE", failure_class="approach"),
            FailureKindSpec(kind="L-TIMEOUT", failure_class="approach"),
        )

    def condition_schema(self) -> ConditionSchema:
        return ConditionSchema(names=("object_x", "object_y", "target_x", "target_y"))

    def required_signals(self) -> tuple[SignalSpec, ...]:
        return tuple(SignalSpec(name=name, unit=unit) for name, unit in SIGNALS)

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation:
        read = _Reader(signals)
        if read.empty or not read.has(*STEP_SIGNALS):
            return StageEvaluation(stage_success=(None,) * 6)

        r_reach = params.thresholds["r_reach"]
        h_grasp = params.thresholds["h_grasp"]
        h_place = params.thresholds["h_place"]
        t_stable = params.thresholds["T_stable"]

        distance = read.column("hand_object_distance")
        contact = read.column("hand_object_contact")
        height = read.column("object_height")
        in_source = read.column("torso_in_source_zone")
        in_target = read.column("torso_in_target_zone")
        in_zone = read.column("object_in_target_zone")
        times = read.column("t")

        approached = _first(
            i for i, value in enumerate(distance) if value is not None and value <= r_reach
        )
        grasped = _first(
            i
            for i in _after(approached, len(contact))
            if _on(contact[i]) and _above(height[i], h_grasp)
        )
        walked = _first(
            i
            for i in _after(grasped, len(contact), strictly=True)
            if _on(contact[i]) and not _on(in_source[i])
        )
        arrived = _first(
            i for i in _after(walked, len(contact)) if _on(contact[i]) and _on(in_target[i])
        )
        placed = _first(
            i
            for i in _after(arrived, len(in_zone))
            if _on(in_zone[i]) and not _above(height[i], h_place)
        )
        released = _first(
            i
            for i in _after(placed, len(contact))
            if not _on(contact[i]) and _settled(i, times, in_zone, t_stable)
        )

        entered = (approached, grasped, walked, arrived, placed, released)
        return self._verdict(entered, read)

    def _verdict(self, entered: tuple[int | None, ...], read: _Reader) -> StageEvaluation:
        outcomes = tuple(index is not None for index in entered)
        failed = _first(i for i, reached in enumerate(outcomes) if not reached)
        if failed is None:
            return StageEvaluation(stage_success=outcomes)
        stage_class = self.stages()[failed].failure_class
        kind = _KIND_BY_STAGE[failed]
        if failed in (2, 3) and _lost_contact(read, entered[1]):
            kind = "L-SLIP"
        if read.hit("collision"):
            kind = "L-COLLIDE"
        elif read.stalled(entered[:failed]):
            kind = "L-TIMEOUT"
        return StageEvaluation(
            stage_success=outcomes,
            first_failed_stage=failed,
            failure_kind=kind,
            failure_class=stage_class,
        )


class _Reader:
    """Column access that answers "not measured" instead of raising."""

    def __init__(self, signals: pa.Table) -> None:
        self._signals = signals
        self.empty = signals.num_rows == 0

    def has(self, *names: str) -> bool:
        return set(names) <= set(self._signals.column_names)

    def column(self, name: str) -> list[float | None]:
        if name not in self._signals.column_names:
            return [None] * self._signals.num_rows
        return list(self._signals[name].to_pylist())

    def hit(self, name: str) -> bool:
        return any(_on(value) for value in self.column(name))

    def stalled(self, entered: tuple[int | None, ...]) -> bool:
        # Spec section 5.2 reads L-TIMEOUT as time running out without changing
        # step. So: no step entered at all, and the hand never moved either. A
        # hand that closed on nothing is a reach failure, and an episode that
        # got to table B and could not place the object is a place failure;
        # neither is a robot standing still.
        if any(index is not None for index in entered):
            return False
        measured = {value for value in self.column("hand_object_distance") if value is not None}
        return len(measured) <= 1


def _after(start: int | None, length: int, strictly: bool = False) -> Iterator[int]:
    if start is None:
        return iter(())
    return iter(range(start + 1 if strictly else start, length))


def _lost_contact(read: _Reader, grasped: int | None) -> bool:
    if grasped is None:
        return False
    return any(not _on(value) for value in read.column("hand_object_contact")[grasped:])


def _settled(
    index: int, times: list[float | None], in_zone: list[float | None], t_stable: float
) -> bool:
    start = times[index]
    if start is None:
        return False
    for step, moment in enumerate(times[index:], start=index):
        if not _on(in_zone[step]):
            return False
        if moment is not None and moment - start >= t_stable:
            return True
    return False


def _on(value: float | None) -> bool:
    return value is not None and value >= 0.5


def _above(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def _first(indices: Iterator[int]) -> int | None:
    return next(indices, None)


STEPS = 20


def const(value: float | None, steps: int = STEPS) -> list[float | None]:
    """One signal that never changes."""
    return [value] * steps


def switch(
    at: int, before: float | None, after: float | None, steps: int = STEPS
) -> list[float | None]:
    """One signal that takes `after` from step `at` on."""
    return [before if step < at else after for step in range(steps)]


def build_rows(steps: int = STEPS, **overrides: list[float | None]) -> list[dict[str, object]]:
    """A clean successful episode, with named signals replaced wholesale.

    The default run reaches every step in order: hand closes on the object at
    step 3, lifts it at 4, leaves table A at 6, arrives at table B at 9, sets
    the object down at 13 and lets go at 14, which leaves half a second of
    stable contact-free time before the episode ends. A test makes a failure by
    replacing the one signal that should break it, so what it is testing is
    visible in the call rather than buried in a fixture file.
    """
    columns: dict[str, list[float | None]] = {
        "hand_object_distance": [max(0.5 - 0.15 * step, 0.02) for step in range(steps)],
        "hand_object_contact": [1.0 if 4 <= step < 14 else 0.0 for step in range(steps)],
        "object_height": [
            0.2 if 4 <= step < 13 else (0.01 if step >= 13 else 0.0) for step in range(steps)
        ],
        "torso_in_source_zone": switch(6, 1.0, 0.0, steps),
        "torso_in_target_zone": switch(9, 0.0, 1.0, steps),
        "object_in_target_zone": switch(13, 0.0, 1.0, steps),
        "collision": const(0.0, steps),
        "torso_height": const(0.95, steps),
        "torso_tilt": const(0.05, steps),
        "t": [round(0.1 * step, 3) for step in range(steps)],
    }
    for name, values in overrides.items():
        columns[name] = values
    return [
        {"episode_id": "ep_test", **{name: values[step] for name, values in columns.items()}}
        for step in range(steps)
    ]


class Signals:
    """The two shapes a test needs to bend one signal out of its clean run."""

    const = staticmethod(const)
    switch = staticmethod(switch)


MakeRows = Callable[..., list[dict[str, object]]]


@pytest.fixture
def make_rows() -> MakeRows:
    return build_rows


@pytest.fixture
def sig() -> Signals:
    return Signals()


@pytest.fixture
def rows() -> list[dict[str, object]]:
    return build_rows()


@pytest.fixture
def task() -> TwoTableTask:
    return TwoTableTask()


@pytest.fixture
def params() -> ScorerParams:
    return ScorerParams(
        thresholds={"r_reach": 0.08, "h_grasp": 0.03, "h_place": 0.9, "T_stable": 0.5}
    )
