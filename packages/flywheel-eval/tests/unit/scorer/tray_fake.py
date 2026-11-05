"""A tray task definition the scorer tests score against (DA-36 task 9.2, AC 8).

The tray task of DA-32 has no `TaskDefinition` yet: its predicates live in
`flywheel_simple.tray.predicates` and read MuJoCo state, which the lane may not
import. This is the same task written against synthetic trace signals - seven
scorer steps (design 28/10/2026 section 3.2), the tray codes of spec v10.6
section 5.2 - so the scorer can be shown to score it through
`configs/eval/scorer/tray.yaml` with nothing tray-specific in its own code.

It follows the DA-32 predicates where they decide anything the scorer sees:
steps are reached in order; the first failure ends the episode, so k is the
first step not reached before it; tilt counts from the grasp until the tray is
placed. Signal names are this file's, not a recorded trace's; the real ones
come with the tray `TaskDefinition`.

`evaluate()` never fills `StageEvaluation.failure_class`. The shared class has
to come out of the scorer from `FailureKindSpec` - a fixed class for most
codes, `from_failed_stage` for L-TRAY-TILT, L-COLLIDE and L-TIMEOUT - which is
exactly what the tests check.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pyarrow as pa  # type: ignore[import-untyped]
from flywheel.contracts import (
    ConditionSchema,
    FailureKindSpec,
    ScorerParams,
    SignalSpec,
    StageEvaluation,
    StageSpec,
)
from flywheel.contracts.v0 import FailureClass

BOTH_HANDS = ("left_handle_contact", "right_handle_contact")

BY_STEP: dict[str, tuple[str, ...]] = {
    "approach_a": ("torso_in_zone_a", "left_palm_handle_distance", "right_palm_handle_distance"),
    "grasp": BOTH_HANDS,
    "lift": ("tray_lift_height", "parts_in_tray"),
    "carry": (*BOTH_HANDS, "torso_in_zone_a", "tray_tilt_deg"),
    "reach_b": (*BOTH_HANDS, "torso_in_zone_b"),
    "place": ("tray_on_table_b", "tray_target_pos_error", "tray_target_yaw_error_deg"),
    "release_stand": (*BOTH_HANDS, "tray_speed", "t"),
}

# Step k -> shared class, spec v10.6 section 5.2: 1 approach, 2-3 grasp,
# 4-5 carry, 6-7 place.
CLASS_BY_STEP: tuple[FailureClass, ...] = (
    "approach",
    "grasp",
    "grasp",
    "carry",
    "carry",
    "place",
    "place",
)

EPISODE_SIGNALS = ("collision",)
BALANCE_SIGNALS = ("pelvis_height", "torso_tilt")

# Steps that are walking: with no failure signal at all, not reaching one of
# them is L-WALK. Any other step left unreached with no signal gets no kind.
WALKING_STEPS = (0, 3, 4)


class TrayTask:
    """Carry a tray of six parts from table A to table B (design 28/10, 3.2)."""

    task_id = "tray"
    version = "0.1.0"
    family = "tray_transfer"

    def stages(self) -> tuple[StageSpec, ...]:
        return tuple(
            StageSpec(name=name, failure_class=klass, signals=signals)
            for (name, signals), klass in zip(BY_STEP.items(), CLASS_BY_STEP, strict=True)
        )

    def failure_kinds(self) -> tuple[FailureKindSpec, ...]:
        return (
            FailureKindSpec(kind="L-PART-DROP", failure_class="carry"),
            FailureKindSpec(kind="L-ONE-HAND", failure_class="carry"),
            FailureKindSpec(kind="L-PLACE-POSE", failure_class="place"),
            FailureKindSpec(kind="L-WALK", failure_class="carry"),
            FailureKindSpec(kind="L-BALANCE", failure_class="balance"),
            FailureKindSpec(kind="L-TRAY-TILT", failure_class="from_failed_stage"),
            FailureKindSpec(kind="L-COLLIDE", failure_class="from_failed_stage"),
            FailureKindSpec(kind="L-TIMEOUT", failure_class="from_failed_stage"),
        )

    def condition_schema(self) -> ConditionSchema:
        return ConditionSchema(names=("tray_x", "tray_y", "target_x", "target_y"))

    def required_signals(self) -> tuple[SignalSpec, ...]:
        names = dict.fromkeys(
            [s for signals in BY_STEP.values() for s in signals]
            + list(EPISODE_SIGNALS)
            + list(BALANCE_SIGNALS)
        )
        return tuple(SignalSpec(name=name, unit="-") for name in names)

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation:
        step_signals = {s for names in BY_STEP.values() for s in names}
        if signals.num_rows == 0 or not step_signals <= set(signals.column_names):
            return StageEvaluation(stage_success=(None,) * 7)
        col = {name: list(signals[name].to_pylist()) for name in signals.column_names}
        th = params.thresholds
        rows = signals.num_rows

        failure_row, kind = _first_failure(col, rows, th)
        end = rows if failure_row is None else failure_row
        reached = _reached(col, end, th)
        failed = next((k for k, row in enumerate(reached) if row is None), None)
        outcomes = tuple(row is not None for row in reached)
        if failed is None:
            return StageEvaluation(stage_success=outcomes)
        if kind is None and failed in WALKING_STEPS:
            kind = "L-WALK"
        return StageEvaluation(stage_success=outcomes, first_failed_stage=failed, failure_kind=kind)


def _reached(
    col: dict[str, list[float | None]], end: int, th: dict[str, float]
) -> list[int | None]:
    """The row each step was first reached on, before row `end`."""
    both = [
        _on(col["left_handle_contact"][i]) and _on(col["right_handle_contact"][i])
        for i in range(end)
    ]
    none = [
        not _on(col["left_handle_contact"][i]) and not _on(col["right_handle_contact"][i])
        for i in range(end)
    ]
    tests: tuple[Callable[[int], bool], ...] = (
        lambda i: (
            _on(col["torso_in_zone_a"][i])
            and _le(col["left_palm_handle_distance"][i], th["r_reach"])
            and _le(col["right_palm_handle_distance"][i], th["r_reach"])
        ),
        lambda i: both[i],
        lambda i: _gt(col["tray_lift_height"][i], th["h_lift"]) and _on(col["parts_in_tray"][i]),
        lambda i: (
            both[i]
            and not _on(col["torso_in_zone_a"][i])
            and _lt(col["tray_tilt_deg"][i], th["tilt_max_deg"])
        ),
        lambda i: both[i] and _on(col["torso_in_zone_b"][i]),
        lambda i: _on(col["tray_on_table_b"][i]) and _in_pose(col, i, th),
        lambda i: none[i] and _held(col, i, end, th, lambda j: none[j] and _still(col, j, th)),
    )
    reached: list[int | None] = []
    start: int | None = 0
    for test in tests:
        row = None if start is None else _first(i for i in range(start, end) if test(i))
        reached.append(row)
        start = row
    return reached


def _first_failure(
    col: dict[str, list[float | None]], rows: int, th: dict[str, float]
) -> tuple[int | None, str | None]:
    """The first row a failure signal fires on, and its code (DA-32 order)."""
    grasped = _first(
        i
        for i in range(rows)
        if _on(col["left_handle_contact"][i]) and _on(col["right_handle_contact"][i])
    )
    placed = _first(i for i in range(rows) if _on(col["tray_on_table_b"][i]))
    candidates: list[tuple[int, str]] = []
    if (row := _first(i for i in range(rows) if _on(col["collision"][i]))) is not None:
        candidates.append((row, "L-COLLIDE"))
    if grasped is not None:
        last = rows if placed is None else placed
        tilted = _first(
            i for i in range(grasped, last) if _gt(col["tray_tilt_deg"][i], th["tilt_max_deg"])
        )
        if tilted is not None:
            candidates.append((tilted, "L-TRAY-TILT"))
        held = _first(i for i in range(grasped, rows) if _on(col["parts_in_tray"][i]))
        if held is not None:
            dropped = _first(i for i in range(held, rows) if not _on(col["parts_in_tray"][i]))
            if dropped is not None:
                candidates.append((dropped, "L-PART-DROP"))
        one_hand = _one_hand(col, grasped, last, th["contact_grace"])
        if one_hand is not None:
            candidates.append((one_hand, "L-ONE-HAND"))
    misplaced = _first(
        i
        for i in range(rows)
        if _on(col["tray_on_table_b"][i])
        and not _in_pose(col, i, th)
        and _held(col, i, rows, th, lambda j: not _in_pose(col, j, th) and _still(col, j, th))
    )
    if misplaced is not None:
        candidates.append((misplaced, "L-PLACE-POSE"))
    timeout = _first(i for i in range(rows) if _ge(col["t"][i], th["episode_limit_s"]))
    if timeout is not None:
        candidates.append((timeout, "L-TIMEOUT"))
    if not candidates:
        return None, None
    return min(candidates)


def _one_hand(col: dict[str, list[float | None]], start: int, end: int, grace: float) -> int | None:
    since: float | None = None
    for i in range(start, end):
        left, right = _on(col["left_handle_contact"][i]), _on(col["right_handle_contact"][i])
        t = col["t"][i]
        if left != right and t is not None:
            since = t if since is None else since
            if t - since > grace:
                return i
        else:
            since = None
    return None


def _held(
    col: dict[str, list[float | None]],
    start: int,
    end: int,
    th: dict[str, float],
    holds: Callable[[int], bool],
) -> bool:
    """`holds` stays true from row `start` for `t_stable` seconds."""
    t0 = col["t"][start]
    if t0 is None:
        return False
    for j in range(start, end):
        if not holds(j):
            return False
        t = col["t"][j]
        if t is not None and t - t0 >= th["t_stable"] - 1e-9:
            return True
    return False


def _in_pose(col: dict[str, list[float | None]], i: int, th: dict[str, float]) -> bool:
    return _le(col["tray_target_pos_error"][i], th["target_pos_tol"]) and _le(
        col["tray_target_yaw_error_deg"][i], th["target_yaw_tol_deg"]
    )


def _still(col: dict[str, list[float | None]], i: int, th: dict[str, float]) -> bool:
    return _lt(col["tray_speed"][i], th["still_speed"])


def _on(value: float | None) -> bool:
    return value is not None and value >= 0.5


def _le(value: float | None, limit: float) -> bool:
    return value is not None and value <= limit


def _lt(value: float | None, limit: float) -> bool:
    return value is not None and value < limit


def _gt(value: float | None, limit: float) -> bool:
    return value is not None and value > limit


def _ge(value: float | None, limit: float) -> bool:
    return value is not None and value >= limit


def _first(indices: Iterator[int]) -> int | None:
    return next(indices, None)


ROWS = 36


def tray_rows(**overrides: list[float | None]) -> list[dict[str, object]]:
    """A clean successful tray episode, with named signals replaced wholesale.

    The default run: both palms on the handles at row 2, both hands close at 3,
    the tray leaves table A at 5, the robot leaves A's zone at 10 and reaches
    B's at 14, the tray sits on B in pose at 18, the hands let go at 22 and the
    tray stays still for the 1 s of `t_stable` until row 32.
    """
    rows = ROWS
    columns: dict[str, list[float | None]] = {
        "torso_in_zone_a": [1.0 if i < 10 else 0.0 for i in range(rows)],
        "left_palm_handle_distance": [max(0.3 - 0.12 * i, 0.04) for i in range(rows)],
        "right_palm_handle_distance": [max(0.3 - 0.12 * i, 0.04) for i in range(rows)],
        "left_handle_contact": [1.0 if 3 <= i < 22 else 0.0 for i in range(rows)],
        "right_handle_contact": [1.0 if 3 <= i < 22 else 0.0 for i in range(rows)],
        "tray_lift_height": [0.1 if 5 <= i < 18 else 0.0 for i in range(rows)],
        "parts_in_tray": [1.0] * rows,
        "tray_tilt_deg": [2.0] * rows,
        "torso_in_zone_b": [1.0 if i >= 14 else 0.0 for i in range(rows)],
        "tray_on_table_b": [1.0 if i >= 18 else 0.0 for i in range(rows)],
        "tray_target_pos_error": [0.01] * rows,
        "tray_target_yaw_error_deg": [2.0] * rows,
        "tray_speed": [0.2 if i < 19 else 0.0 for i in range(rows)],
        "t": [round(0.1 * i, 3) for i in range(rows)],
        "collision": [0.0] * rows,
        "pelvis_height": [0.75] * rows,
        "torso_tilt": [0.05] * rows,
    }
    for name, values in overrides.items():
        columns[name] = values
    return [
        {"episode_id": "ep_tray", **{name: values[i] for name, values in columns.items()}}
        for i in range(rows)
    ]


def from_row(
    at: int, before: float | None, after: float | None, rows: int = ROWS
) -> list[float | None]:
    """One signal that takes `after` from row `at` on."""
    return [before if i < at else after for i in range(rows)]
