"""The number rule of DA-43 K2: the contract reads numbers as the eval lane does.

The table was run through the lane's `flywheel.eval.agentqa.numbers.numbers_in`
at origin/master dae6b13c and gave the same results; the contract may not import
the lane, so the table pins the parity instead.
"""

import pytest
from flywheel.contracts.agentqa import bare_numbers, numbers_in

PARITY = [
    # Digits inside names, run ids, dates and versions are not numbers.
    ("pair60k-C_ALL-60000", []),
    ("pair60k-C_ALL-60000-rp_abc", []),
    ("19/11/2026", []),
    ("attempt-1", []),
    ("v1.2", []),
    ("p99 of H2 on episode_000012 and T1", []),
    # Non-ASCII digits are numbers.
    ("٣", ["٣"]),
    ("３", ["３"]),
    # Placeholders are not numbers.
    ("{F12}", []),
    ("{F1} and {F2}", []),
    ("{F1} of rollouts pass", []),
    # Bare numbers, with a unit, a percent sign or thousands groups.
    ("3 rollouts", ["3"]),
    ("0.5", ["0.5"]),
    ("50%", ["50%"]),
    ("1,000", ["1,000"]),
    ("12ms", ["12ms"]),
    ("3/10", ["3", "10"]),
    ("45/90", ["45", "90"]),
    ("step 4", ["4"]),
    ("Only 3 of 6 pass", ["3", "6"]),
    ("tilt above 0.4 rad", ["0.4"]),
    ("", []),
]


@pytest.mark.parametrize(("text", "numbers"), PARITY)
def test_numbers_in_follows_the_lane_rule(text: str, numbers: list[str]) -> None:
    assert numbers_in(text) == numbers


@pytest.mark.parametrize(("text", "numbers"), PARITY)
def test_bare_numbers_is_numbers_in(text: str, numbers: list[str]) -> None:
    assert bare_numbers(text) == numbers
