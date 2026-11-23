"""The rank role's rule library: one pass and one fail case per rule (DA-43 task 5.3)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from flywheel.eval.agentqa.round import reply_rules as rr
from flywheel.eval.agentqa.round.records import Offered, OfferedFact

OFFERED = Offered(
    cluster_id="C_70/place/L-PLACE-POSE/l1", hypotheses=["H1", "H2"],
    interventions={"H1": ["repair_ticket"], "H2": ["sim_s1", "report_only"]},
    checks=["K1", "K2"],
    facts={"F1": OfferedFact(unit="rollouts", provenance="code"),
           "F2": OfferedFact(unit="rollouts", provenance="code"),
           "F3": OfferedFact(unit="s", provenance="code"),
           "F9": OfferedFact(unit="", provenance="vision")},
    blocked_data_spend=False)


def good() -> dict[str, Any]:
    return {
        "cluster": "C_70/place/L-PLACE-POSE/l1",
        "order": ["H1", "H2"],
        "why": [{"hypothesis": "H1", "cites": ["F1"],
                 "text": "The chain broke in {F1} rollouts of run C_70 at step p99."}],
        "check": {"id": "K1", "cites": ["F2"], "text": "It costs one rerun of {F2} rollouts."},
        "intervention": {"id": "repair_ticket", "for": "H1", "cites": ["F1"],
                         "text": "Open a ticket on the scorer."},
    }


def text_of(reply: dict[str, Any]) -> str:
    return json.dumps(reply)


def rules_failed(reply: dict[str, Any] | str, offered: Offered = OFFERED,
                 cut: bool = False) -> list[str]:
    text = reply if isinstance(reply, str) else text_of(reply)
    return rr.failed_rules(rr.check_rank(text, offered, cut=cut))


def test_a_good_reply_passes_every_rule() -> None:
    assert rr.check_rank(text_of(good()), OFFERED) == []


# schema ----------------------------------------------------------------------------------

def test_schema_accepts_a_json_fence_and_whitespace_only() -> None:
    assert rules_failed("\n  ```json\n" + text_of(good()) + "\n```  \n") == []
    assert rules_failed("  " + text_of(good()) + "\n") == []
    assert rules_failed("Here is my answer: " + text_of(good())) == ["schema"]
    assert rules_failed("```\n" + text_of(good()) + "\n```") == ["schema"]


@pytest.mark.parametrize("edit", [
    lambda r: r.pop("order"),
    lambda r: r.update(extra=1),
    lambda r: r.update(order="H1"),
    lambda r: r["why"][0].update(cites="F1"),
    lambda r: r["intervention"].pop("for"),
])
def test_schema_fails_on_a_wrong_shape(edit: Any) -> None:
    reply = good()
    edit(reply)
    failures = rr.check_rank(text_of(reply), OFFERED)
    assert [f.rule for f in failures] == ["schema"]  # schema stops the other rules


def test_schema_fails_on_a_cut_reply_and_on_non_json() -> None:
    assert rules_failed(good(), cut=True) == ["schema"]
    assert rules_failed(text_of(good())[:-5]) == ["schema"]
    assert rules_failed("[1, 2]") == ["schema"]


def test_check_may_be_absent_or_null() -> None:
    reply = good()
    reply["check"] = None
    assert rules_failed(reply) == []
    reply.pop("check")
    assert rules_failed(reply) == []


# one rule each ---------------------------------------------------------------------------

def test_cluster() -> None:
    reply = good()
    reply["cluster"] = "C_70/place/L-PLACE-POSE/l2"
    assert rules_failed(reply) == ["cluster"]


def test_ids_offered() -> None:
    reply = good()
    reply["why"].append({"hypothesis": "H7", "cites": ["F1"], "text": "Not it."})
    assert rules_failed(reply) == ["ids_offered"]
    reply = good()
    reply["why"][0]["cites"] = ["F1", "F77"]
    assert rules_failed(reply) == ["ids_offered"]


def test_order_permutation() -> None:
    for order in (["H1"], ["H1", "H1", "H2"], ["H1", "H2", "H2"]):
        reply = good()
        reply["order"] = order
        assert rules_failed(reply) == ["order_permutation"], order
    reply = good()
    reply["order"] = ["H2", "H1"]
    reply["why"][0]["hypothesis"] = "H2"
    reply["intervention"] = {"id": "report_only", "for": "H2", "cites": ["F1"], "text": "Wait."}
    assert rules_failed(reply) == []


def test_intervention_allowed() -> None:
    reply = good()
    reply["intervention"]["id"] = "sim_s1"  # H2's, not H1's
    assert rules_failed(reply) == ["intervention_allowed"]
    reply = good()
    reply["intervention"]["for"] = "H9"
    assert rules_failed(reply) == ["intervention_allowed"]


def test_intervention_allowed_refuses_a_data_spend_on_a_blocked_cluster() -> None:
    reply = good()
    reply["intervention"] = {"id": "sim_s1", "for": "H2", "cites": ["F1"], "text": "More data."}
    assert rules_failed(reply) == []
    blocked = OFFERED.model_copy(update={"blocked_data_spend": True})
    assert rules_failed(reply, blocked) == ["intervention_allowed"]


def test_check_offered_or_null() -> None:
    reply = good()
    reply["check"]["id"] = "K9"
    assert rules_failed(reply) == ["check_offered_or_null"]


def test_cites_present() -> None:
    reply = good()
    reply["check"]["cites"] = []
    reply["check"]["text"] = "Cheap."
    assert rules_failed(reply) == ["cites_present"]
    reply = good()
    reply["why"] = []
    assert rules_failed(reply) == ["cites_present"]
    reply = good()
    reply["why"][0]["hypothesis"] = "H2"  # no why for order[0] = H1
    assert rules_failed(reply) == ["cites_present"]


@pytest.mark.parametrize("text", [
    "The chain broke in 7 rollouts.",
    "A drop of 12% at {F1}.",
    "It took 120ms.",
    "Half of them, 45/90.",
])
def test_numbers_refuses_a_bare_number(text: str) -> None:
    reply = good()
    reply["why"][0]["text"] = text
    assert rules_failed(reply) == ["numbers"]


def test_numbers_refuses_a_placeholder_not_cited() -> None:
    reply = good()
    reply["why"][0]["text"] = "The chain broke in {F1} of {F2} rollouts."  # F2 not cited
    assert rules_failed(reply) == ["numbers"]


def test_numbers_allows_digits_inside_names() -> None:
    reply = good()
    reply["why"][0]["text"] = "Run C_70 and B_ALL fail at step_3 like H2 and K1, see {F1}."
    assert rules_failed(reply) == []


def test_comparison() -> None:
    reply = good()
    reply["why"][0].update(cites=["F1", "F3"], text="{F1} rollouts is more than {F3}.")
    assert rules_failed(reply) == ["comparison"]
    reply["why"][0].update(cites=["F1", "F2"], text="{F1} rollouts is more than {F2}.")
    assert rules_failed(reply) == []  # same unit
    reply["why"][0].update(cites=["F1", "F3"], text="{F1} rollouts and {F3}.")
    assert rules_failed(reply) == []  # no comparison word


def test_provenance() -> None:
    reply = good()
    reply["why"][0].update(cites=["F9"], text="The frames show it, {F9}.")
    assert rules_failed(reply) == ["provenance"]
    reply["why"][0].update(cites=["F9", "F1"], text="The frames {F9} and the scores {F1}.")
    assert rules_failed(reply) == []


def test_failures_carry_the_rule_and_a_message() -> None:
    reply = good()
    reply["cluster"] = "x"
    reply["why"][0]["text"] = "In 7 rollouts."
    failures = rr.check_rank(text_of(reply), OFFERED)
    assert [f.rule for f in failures] == ["cluster", "numbers"]
    assert str(failures[1]).startswith("numbers: why[0] (H1) writes the number(s) ['7']")


# comparison facts and trailing commas ----------------------------------------------------

def _with_facts(**extra: OfferedFact) -> Offered:
    return OFFERED.model_copy(update={"facts": {**OFFERED.facts, **extra}})


def test_comparison_passes_when_a_comparison_fact_is_cited() -> None:
    offered = _with_facts(
        F4=OfferedFact(unit="m", provenance="code"),
        F5=OfferedFact(unit="rollouts", provenance="code", comparison=True),
        F6=OfferedFact(unit="", provenance="code", comparison=True))
    reply = good()
    reply["why"][0].update(
        cites=["F5", "F4", "F6"],
        text="One rollout {F5} is above the tolerance, the mean {F4} is below it, "
             "all matched rollouts are in domain {F6}.")
    assert rules_failed(reply, offered) == []
    reply["why"][0].update(cites=["F1", "F3"], text="{F1} rollouts is more than {F3}.")
    assert rules_failed(reply, offered) == ["comparison"]  # none cited


def test_comparison_distance_against_time_without_comparison_fact_fails() -> None:
    offered = _with_facts(F4=OfferedFact(unit="m", provenance="code"))
    reply = good()
    reply["why"][0].update(cites=["F4", "F3"], text="The distance {F4} is longer than {F3}, "
                                                    "which is worse.")
    assert rules_failed(reply, offered) == ["comparison"]


def test_comparison_flag_by_marker_and_by_boolean() -> None:
    from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS, is_comparison_fact

    assert is_comparison_fact("r_coverage_above_tau", 1, COMPARISON_MARKERS)
    assert is_comparison_fact("r_check_separates_h1_h2", 0.3, COMPARISON_MARKERS)
    assert is_comparison_fact("r_coverage_in_domain", True, COMPARISON_MARKERS)
    assert is_comparison_fact("r_anything", False, COMPARISON_MARKERS)  # boolean by value
    assert not is_comparison_fact("r_coverage_mean_distance", 0.4, COMPARISON_MARKERS)
    assert not is_comparison_fact("r_count", 1, ())


def test_old_offered_fact_without_the_flag_loads() -> None:
    from flywheel.eval.agentqa.round.records import OfferedFact as Fact

    old = Fact.model_validate_json('{"unit": "s", "provenance": "code"}')
    assert old.comparison is False


@pytest.mark.parametrize("closer", ["}", "]"])
def test_trailing_comma_before_a_closer_is_accepted(closer: str) -> None:
    text = text_of(good())
    assert rules_failed(text) == []
    broken = text.replace('"cites": ["F2"]', '"cites": ["F2",\n ]', 1) if closer == "]" \
        else text[:-1] + ",\n }"
    assert broken != text and rules_failed(broken) == []


def test_trailing_comma_repair_leaves_strings_alone() -> None:
    raw = '{"a": "x,}y", "b": [1,2,],\n"c": "q,]", }'
    fixed = rr.strip_trailing_commas(raw)
    assert json.loads(fixed) == {"a": "x,}y", "b": [1, 2], "c": "q,]"}
    assert '"x,}y"' in fixed and '"q,]"' in fixed
    esc = r'{"a": "he said \",}\" ok",}'
    assert json.loads(rr.strip_trailing_commas(esc)) == {"a": 'he said ",}" ok'}


def test_other_malformed_json_still_fails_schema() -> None:
    text = text_of(good())
    for broken in (text[:-1], text.replace('"order"', "order", 1), text + ",", "{'a': 1}"):
        assert rules_failed(broken) == ["schema"]


def test_verify_recomputes_the_flag_from_facts_for_an_old_judged_item() -> None:
    from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS
    from flywheel.eval.agentqa.round.records import FactRecord, JudgedItem
    from flywheel.eval.agentqa.round.verify import _with_comparison

    item = JudgedItem(item_id="rank:x", role="rank", unit="x", offered=OFFERED)
    facts = {"F1": FactRecord(fact_id="F1", name="r_coverage_in_domain", value=True,
                              source_ref="s", provenance="code", tool_call_id="t"),
             "F3": FactRecord(fact_id="F3", name="r_time", value=1.0, unit="s",
                              source_ref="s", provenance="code", tool_call_id="t")}
    new = _with_comparison(item, facts, COMPARISON_MARKERS).offered.facts
    assert new["F1"].comparison and not new["F3"].comparison
    assert not new["F2"].comparison  # not in facts.jsonl: the stored flag stands
