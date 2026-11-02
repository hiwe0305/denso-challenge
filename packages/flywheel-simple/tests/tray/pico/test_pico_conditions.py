"""Which (level, seed) a PICO teleop session records, and when it moves on (DA-35 AC 1)."""

from __future__ import annotations

import pytest
from flywheel_simple.tray.pico.conditions import Condition, ConditionQueue, parse_conditions


def test_parse_ranges_and_single_seeds() -> None:
    assert parse_conditions("0:0-2,1:10,1:20-21") == [
        Condition(0, 0),
        Condition(0, 1),
        Condition(0, 2),
        Condition(1, 10),
        Condition(1, 20),
        Condition(1, 21),
    ]


@pytest.mark.parametrize("spec", ["2:0", "3:5-6"])
def test_level_two_is_refused(spec: str) -> None:
    # S2 and its demos stay in the train domain: levels 0 and 1 only (spec 7.3).
    with pytest.raises(ValueError, match="level"):
        parse_conditions(spec)


@pytest.mark.parametrize("spec", ["0:1000000", "1:2000000-2000001"])
def test_dev_and_holdout_seeds_are_refused(spec: str) -> None:
    with pytest.raises(ValueError, match="train"):
        parse_conditions(spec)


@pytest.mark.parametrize("spec", ["", "0", "0:5-3", "a:1", "0:1,0:1"])
def test_malformed_specs_are_refused(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_conditions(spec)


def test_queue_moves_on_after_success() -> None:
    queue = ConditionQueue([Condition(0, 0), Condition(1, 3)], max_attempts=3)
    assert (queue.current, queue.attempt) == (Condition(0, 0), 1)
    queue.record(success=True)
    assert (queue.current, queue.attempt) == (Condition(1, 3), 1)
    queue.record(success=True)
    assert queue.current is None


def test_queue_retries_a_condition_until_attempts_run_out() -> None:
    queue = ConditionQueue([Condition(0, 0), Condition(0, 1)], max_attempts=2)
    queue.record(success=False)
    assert (queue.current, queue.attempt) == (Condition(0, 0), 2)
    queue.record(success=False)
    assert (queue.current, queue.attempt) == (Condition(0, 1), 1)


def test_queue_needs_one_attempt_at_least() -> None:
    with pytest.raises(ValueError):
        ConditionQueue([Condition(0, 0)], max_attempts=0)
