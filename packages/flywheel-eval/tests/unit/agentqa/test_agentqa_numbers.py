"""DA-20 AC 3: a number the agent writes must be a fact."""

from __future__ import annotations

from flywheel.contracts.agentqa import AgentFact
from flywheel.eval.agentqa.numbers import numbers_in, unsupported_numbers

FACTS = [
    AgentFact(fact_id="F1", name="latency_p99_s", value=0.04485, unit="s", source_ref="a"),
    AgentFact(fact_id="F2", name="rate", value=0.125, source_ref="a"),
    AgentFact(fact_id="F3", name="episodes", value=12, source_ref="a"),
    AgentFact(fact_id="F4", name="loss", value="NaN", source_ref="a"),
]


def test_placeholders_and_identifiers_are_not_numbers() -> None:
    text = "{F1} on train/job-cf631ab2655c, episode_000012, code T1 and p99 at step {F3}"
    assert numbers_in(text) == []


def test_a_fact_written_to_its_own_precision_is_allowed() -> None:
    assert unsupported_numbers("p99 latency is 0.045 s", FACTS) == []
    assert unsupported_numbers("p99 latency is 0.04485 s", FACTS) == []
    assert unsupported_numbers("12 episodes", FACTS) == []


def test_a_fraction_fact_may_be_written_as_a_percentage() -> None:
    assert unsupported_numbers("12.5% of the episodes", FACTS) == []


def test_an_invented_number_is_reported() -> None:
    assert unsupported_numbers("latency rose to 0.3 s over 40 chunks", FACTS) == ["0.3", "40"]


def test_a_number_inside_a_text_fact_counts() -> None:
    facts = [AgentFact(fact_id="F1", name="detail", value="7 chunks over d", source_ref="a")]
    assert unsupported_numbers("7 chunks stalled", facts) == []


def test_thousands_units_and_fractions_are_read_as_numbers() -> None:
    assert numbers_in("12,000 steps in 120ms, 10x faster, 45/90 episodes, 4GB, 12k") == [
        "12,000", "120ms", "10x", "45", "90", "4GB", "12k"
    ]
    facts = [AgentFact(fact_id="F1", name="steps", value=12000, source_ref="a")]
    assert unsupported_numbers("12,000 steps", facts) == []
    assert unsupported_numbers("12k steps", facts) == []
    assert unsupported_numbers("12,000 steps", [*facts[:0]]) == ["12,000"]
    assert unsupported_numbers("45/90 episodes and 10x", FACTS) == ["45", "90", "10x"]


def test_names_paths_and_dates_stay_out() -> None:
    assert numbers_in("a 3D pose, 6D rotation, 48d actions, Qwen3.5-4B, rtc/job-g1") == []
    assert numbers_in("on 6/11/2026") == []

