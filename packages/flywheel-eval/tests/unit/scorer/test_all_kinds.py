"""One case per declared kind, plus the two controls (DA-36 task 6, AC 6).

Every case here goes through the whole scorer - read the trace, evaluate the
task, state the steps, name the failure, fold in the balance condition - and
each one bends exactly one signal of the clean run, so the trace says what it
is testing. All ten codes of spec section 5.2 appear: the nine the task
declares, and `L-UNKNOWN`, which the scorer answers with when it cannot name
one.

The two controls are the point of the exercise. A successful episode must come
out with no failure *and* no unknown step, because a trace nobody could score
also produces an empty failure list, and an episode missing a signal must come
out unknown rather than clean. That pair is the lesson DA-08 wrote down, tested
here on the scorer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import NaiveTask
from flywheel.contracts import TaskDefinition
from flywheel.eval.api import SCORER_CONFIG_DIR, score_trace
from flywheel.eval.scorer.score import EpisodeScore

MakeRows = Callable[..., list[dict[str, object]]]
CONFIG = SCORER_CONFIG_DIR / "two-table.yaml"

HELD_TO_THE_END = [0.0 if step < 4 else 1.0 for step in range(20)]


def score(tmp_path: Path, task: TaskDefinition, rows: list[dict[str, object]]) -> EpisodeScore:
    path = tmp_path / "ep.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return score_trace(path, task, CONFIG)


def test_a_successful_episode_has_no_failure_and_no_unknown(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    scored = score(tmp_path, task, make_rows())

    assert scored.success is True
    assert scored.failure.failure_kind is None
    assert scored.failure.failure_class is None
    # Both halves of the control: a trace that could not be scored would also
    # have no failure to report.
    assert scored.unknown_steps == ()
    assert scored.balance.unknown is False
    assert scored.missing_signals == ()


def drop(signal: str, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{key: value for key, value in row.items() if key != signal} for row in rows]


@pytest.mark.parametrize("answer", [True, False])
def test_a_task_that_answers_anyway_cannot_make_a_missing_signal_a_verdict(
    tmp_path: Path, make_rows: MakeRows, answer: bool
) -> None:
    # The case the review of 3/11/2026 asked for: a task whose predicates do
    # not check whether the signal is there. `True` would be a pass nobody
    # measured and `False` a reach failure nobody measured; the scorer holds
    # the convention itself, so both come out unknown (AC 2, point 1).
    rows = drop("hand_object_distance", make_rows())

    scored = score(tmp_path, NaiveTask(verdict=answer), rows)

    assert scored.steps[0].status == "unknown"
    assert scored.steps[0].detail == "thiếu tín hiệu: hand_object_distance"
    assert scored.success is None
    assert scored.failure.failure_kind == "L-UNKNOWN"
    assert scored.failure.first_failed_step is None


def test_a_missing_episode_signal_costs_a_clean_episode_its_pass(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    # The collision flag belongs to no step, so every step stays judgeable and
    # the episode does not: six steps passed with nobody watching for a
    # collision is not a success (point 1, second case).
    scored = score(tmp_path, task, drop("collision", make_rows()))

    assert [step.status for step in scored.steps] == ["pass"] * 6
    assert scored.success is None
    assert scored.failure.failure_kind == "L-UNKNOWN"
    assert "collision" in (scored.failure.reason or "")


def test_a_missing_signal_is_unknown_not_clean(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    scored = score(tmp_path, task, drop("hand_object_contact", make_rows()))

    assert scored.success is None
    assert scored.failure.failure_kind == "L-UNKNOWN"
    assert scored.failure.failure_class is None
    assert scored.failure.first_failed_step is None
    assert [step.status for step in scored.steps] == ["unknown"] * 6
    assert scored.missing_signals == ("hand_object_contact",)


@pytest.mark.parametrize(
    ("kind", "failure_class", "failed_step", "overrides"),
    [
        # Step 1: the hand closes in on the object but never gets within r_reach.
        ("L-REACH", "approach", 0, {"hand_object_distance": [0.5 - 0.01 * s for s in range(20)]}),
        # Step 2: the hand reaches the object and never lifts it off the table.
        ("L-GRASP", "grasp", 1, {"object_height": [0.0] * 20}),
        # Step 3: the object is lifted and then dropped on the way out.
        (
            "L-SLIP",
            "carry",
            2,
            {"hand_object_contact": [1.0 if 4 <= s < 6 else 0.0 for s in range(20)]},
        ),
        # Step 3: the object is held but the robot never leaves table A.
        (
            "L-WALK",
            "carry",
            2,
            {"torso_in_source_zone": [1.0] * 20, "hand_object_contact": HELD_TO_THE_END},
        ),
        # Step 5: the robot arrives with the object and never gets it in the zone.
        ("L-PLACE", "place", 4, {"object_in_target_zone": [0.0] * 20}),
        # Step 6: the object is down in the zone and the hand never lets go.
        ("L-RELEASE", "place", 5, {"hand_object_contact": HELD_TO_THE_END}),
        # Any step: unwanted contact, which takes the class of the failed step.
        (
            "L-COLLIDE",
            "place",
            4,
            {"object_in_target_zone": [0.0] * 20, "collision": [0.0] * 8 + [1.0] * 12},
        ),
        # Any step: nothing moves at all, so no step is ever entered.
        ("L-TIMEOUT", "approach", 0, {"hand_object_distance": [0.5] * 20}),
    ],
)
def test_one_case_for_each_declared_kind(
    tmp_path: Path,
    task: TaskDefinition,
    make_rows: MakeRows,
    kind: str,
    failure_class: str,
    failed_step: int,
    overrides: dict[str, list[float]],
) -> None:
    scored = score(tmp_path, task, make_rows(**overrides))

    assert scored.failure.failure_kind == kind
    assert scored.failure.failure_class == failure_class
    assert scored.failure.first_failed_step == failed_step
    assert scored.success is False
    # Nothing unknown: the kind was established on signals that were all there.
    assert scored.unknown_steps == ()
    assert scored.steps[failed_step].status == "fail"
    assert all(step.status == "not_attempted" for step in scored.steps[failed_step + 1 :])


def test_a_fall_after_a_step_failure_keeps_the_step_failure(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows
) -> None:
    # PO decision of 3/11/2026: the grasp is what failed, and `L-BALANCE` there
    # would move the episode out of the grasp cluster. The fall is recorded as
    # `balance_violated` instead.
    rows = make_rows(object_height=[0.0] * 20, torso_tilt=[0.05] * 15 + [0.9] * 5)

    scored = score(tmp_path, task, rows)

    assert scored.failure.failure_kind == "L-GRASP"
    assert scored.failure.first_failed_step == 1
    assert scored.balance.violated is True


@pytest.mark.parametrize(
    ("signal", "value"),
    [("torso_height", 0.2), ("torso_tilt", 0.9)],
)
def test_balance_is_the_kind_at_any_step(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, signal: str, value: float
) -> None:
    # Violated on the last row, after all six steps have passed: the one kind
    # that cannot come out of the per-step predicates (AC 3).
    clean = 0.95 if signal == "torso_height" else 0.05
    rows = make_rows(**{signal: [clean] * 19 + [value]})

    scored = score(tmp_path, task, rows)

    assert scored.failure.failure_kind == "L-BALANCE"
    assert scored.failure.failure_class == "balance"
    assert scored.balance.violated is True
    assert scored.balance.row == 19
    assert [step.status for step in scored.steps] == ["pass"] * 6


def test_every_declared_kind_has_a_case(task: TaskDefinition) -> None:
    """The parametrised cases above cover the task's whole code set (AC 6)."""
    covered = {
        "L-REACH",
        "L-GRASP",
        "L-SLIP",
        "L-WALK",
        "L-PLACE",
        "L-RELEASE",
        "L-COLLIDE",
        "L-TIMEOUT",
        "L-BALANCE",
    }

    assert {spec.kind for spec in task.failure_kinds()} == covered
