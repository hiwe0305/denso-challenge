"""The answer text of `answer_submit` (DA-54 task 2.3): values and units formatted by code.

Seen in a real session: "11 rollouts rollouts", sixteen-digit floats, "True" in a sentence.
"""

from __future__ import annotations

import pytest
from flywheel.eval.agentqa.mcp.records import answer_value, fill_answer, full_value
from flywheel.eval.agentqa.round.records import FactRecord


def _fact(fid: str, value: float | int | str | bool, unit: str = "") -> FactRecord:
    return FactRecord(fact_id=fid, name=f"n_{fid}", value=value, unit=unit, source_ref="s",
                      provenance="code", tool_call_id="M1")


@pytest.mark.parametrize(("value", "shown"), [
    (0.123456789012345, "0.1235"),
    (0.05, "0.05"),
    (1.0, "1"),
    (3.0, "3"),
    (12345.678, "12350"),
    (123.456789, "123.5"),
    (-2.718281828, "-2.718"),
    (0.000123456, "0.0001235"),
    (999999.4, "1e+06"),
    (0.0, "0"),
    (0.00001234, "1.234e-05"),
    (2.5e7, "2.5e+07"),
    (11, "11"),
    (123456789, "123456789"),
    (True, "yes"),
    (False, "no"),
    ("C_70", "C_70"),
])
def test_a_value_is_shown_short(value: float | int | str | bool, shown: str) -> None:
    assert answer_value(value) == shown


def test_the_unit_is_not_written_twice() -> None:
    facts = {"F1": _fact("F1", 11, "rollouts"), "F2": _fact("F2", 0.051234567, "m"),
             "F3": _fact("F3", True), "F4": _fact("F4", 4, "rollouts")}
    text = ("{F1} rollouts fail, {F4}  Rollouts more; offset {F2} on average; "
            "separated: {F3}.")
    assert fill_answer(text, facts) == ("11 rollouts fail, 4  Rollouts more; offset "
                                        "0.05123 m on average; separated: yes.")


def test_the_unit_is_added_when_the_next_word_only_begins_like_it() -> None:
    facts = {"F1": _fact("F1", 2, "m")}
    assert fill_answer("{F1} more", facts) == "2 m more"
    assert fill_answer("{F1}m", facts) == "2m"  # glued unit counts as written
    assert fill_answer("{F1}", facts) == "2 m"


def test_a_fact_without_unit_gets_none_and_the_text_is_not_escaped() -> None:
    facts = {"F1": _fact("F1", 6)}
    assert fill_answer("A & B <x>: {F1}", facts) == "A & B <x>: 6"


def test_the_full_value_keeps_every_digit() -> None:
    assert full_value(_fact("F1", 0.123456789012345, "m")) == "0.123456789012345 m"
    assert full_value(_fact("F1", True)) == "True"
