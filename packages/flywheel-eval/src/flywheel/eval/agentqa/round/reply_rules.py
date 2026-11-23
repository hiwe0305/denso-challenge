"""The rule library of the rank role: pure checks of one reply (architecture 20/11 B4, B5, 25).

B4 runs it after every reply to decide on the one resend; B5 runs it again, as the
official check, on the replies in `model_calls.jsonl`. Same functions, no I/O.

    failures = check_rank(reply_text, offered, cut=False)

Each rule is one function returning failure messages; `check_rank` runs them in a
fixed order and tags each message with the rule id (the `failed_rules` value). A
schema failure stops the run: the other rules need a parsed reply.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flywheel.contracts.evidence import BUDGET_INTERVENTIONS
from flywheel.eval.agentqa.numbers import numbers_in
from flywheel.eval.agentqa.round.records import Offered
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_FENCE = re.compile(r"\A```json[ \t]*\n(.*?)\n?```\Z", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")
COMPARISON_WORDS = ("more", "less", "higher", "lower", "above", "below", "than", "exceeds",
                    "fewer", "greater", "smaller", "worse", "better")
_COMPARISON = re.compile(r"\b(?:" + "|".join(COMPARISON_WORDS) + r")\b", re.IGNORECASE)


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class WhyItem(_Strict):
    hypothesis: str
    cites: list[str]
    text: str


class CheckPick(_Strict):
    id: str
    cites: list[str]
    text: str


class InterventionPick(_Strict):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, populate_by_name=True)

    id: str
    for_: str = Field(alias="for")
    cites: list[str]
    text: str


class RankReply(_Strict):
    """The reply of the rank role, exactly the shape `prompts/rank.md` asks for."""

    cluster: str
    order: list[str]
    why: list[WhyItem]
    check: CheckPick | None = None
    intervention: InterventionPick


RANK_REPLY_SCHEMA: dict[str, Any] = RankReply.model_json_schema(by_alias=True)


@dataclass(frozen=True)
class Failure:
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.message}"


def unwrap(text: str) -> str:
    """The reply without surrounding whitespace or one ```json fence; nothing else is cut."""
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    return fenced.group(1).strip() if fenced else stripped


def strip_trailing_commas(text: str) -> str:
    """`text` without a comma directly before `}` or `]` (whitespace between allowed).

    A small state machine: commas inside a JSON string are never touched.
    """
    out: list[str] = []
    in_string = escaped = False
    for ch in text:
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch in "}]":
            k = len(out)
            while k > 0 and out[k - 1] in " \t\r\n":
                k -= 1
            if k > 0 and out[k - 1] == ",":
                del out[k - 1]
        elif ch == '"':
            in_string = True
        out.append(ch)
    return "".join(out)


def _loads(text: str) -> Any:
    body = unwrap(text)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(strip_trailing_commas(body))  # the one repair; may raise again


def parse_rank(text: str) -> RankReply:
    """Raises `ValueError` (pydantic's `ValidationError` included) on any wrong shape."""
    raw = _loads(text)
    if not isinstance(raw, dict):
        raise ValueError("the reply is not a JSON object")
    return RankReply.model_validate(raw)


def _sentences(reply: RankReply) -> list[tuple[str, list[str], str]]:
    """(where, cites, text) of every sentence the model wrote."""
    out = [(f"why[{k}] ({w.hypothesis})", w.cites, w.text) for k, w in enumerate(reply.why)]
    if reply.check is not None:
        out.append(("check", reply.check.cites, reply.check.text))
    out.append(("intervention", reply.intervention.cites, reply.intervention.text))
    return out


def rule_schema(text: str, *, cut: bool = False) -> list[str]:
    """Not JSON, wrong shape, or a cut reply (a `cut` status always fails)."""
    if cut:
        return ["the reply was cut at max_tokens"]
    try:
        parse_rank(text)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "(root)"
        return [f"{where}: {first['msg']}"[:300]]
    except ValueError as error:
        return [f"not a JSON object: {str(error).splitlines()[0][:200]}"]
    return []


def rule_cluster(reply: RankReply, offered: Offered) -> list[str]:
    if reply.cluster != offered.cluster_id:
        return [f"cluster {reply.cluster!r} is not the unit {offered.cluster_id!r}"]
    return []


def rule_ids_offered(reply: RankReply, offered: Offered) -> list[str]:
    """Hypothesis ids (order, why) and fact ids (every cites) must be ones of this call.

    Check ids are `rule_check_offered_or_null`'s; intervention ids and `for` are
    `rule_intervention_allowed`'s, so one wrong id fails one rule.
    """
    hyps = set(offered.hypotheses)
    bad = [h for h in [*reply.order, *(w.hypothesis for w in reply.why)] if h not in hyps]
    facts = [f for _, cites, _ in _sentences(reply) for f in cites if f not in offered.facts]
    out = [f"hypothesis {h!r} was not offered" for h in dict.fromkeys(bad)]
    out += [f"fact {f!r} was not offered" for f in dict.fromkeys(facts)]
    return out


def rule_order_permutation(reply: RankReply, offered: Offered) -> list[str]:
    if sorted(reply.order) != sorted(offered.hypotheses):
        return [f"order {reply.order} is not each of {offered.hypotheses} exactly once"]
    return []


def rule_intervention_allowed(reply: RankReply, offered: Offered) -> list[str]:
    """The intervention must be one its hypothesis allows; never a data spend when blocked."""
    pick = reply.intervention
    if pick.for_ not in offered.interventions:
        return [f"intervention.for {pick.for_!r} is not an offered hypothesis"]
    out = []
    if pick.id not in offered.interventions[pick.for_]:
        out.append(f"intervention {pick.id!r} is not one of {pick.for_}'s "
                   f"{offered.interventions[pick.for_]}")
    if offered.blocked_data_spend and pick.id in BUDGET_INTERVENTIONS:
        out.append(f"intervention {pick.id!r} spends data budget on a blocked cluster")
    return out


def rule_check_offered_or_null(reply: RankReply, offered: Offered) -> list[str]:
    """Null is allowed, even when checks were offered; a check id not offered is not."""
    if reply.check is not None and reply.check.id not in offered.checks:
        return [f"check {reply.check.id!r} was not offered"]
    return []


def rule_cites_present(reply: RankReply, offered: Offered) -> list[str]:
    out = [f"{where} cites no fact" for where, cites, _ in _sentences(reply) if not cites]
    if not reply.why:
        out.append("why is empty")
    elif reply.order and not any(w.hypothesis == reply.order[0] for w in reply.why):
        out.append(f"no why entry for the first hypothesis {reply.order[0]}")
    return out


def rule_numbers(reply: RankReply, offered: Offered) -> list[str]:
    """No bare number in a text; every `{F#}` placeholder is in that sentence's cites."""
    out = []
    for where, cites, text in _sentences(reply):
        bare = numbers_in(text)
        if bare:
            out.append(f"{where} writes the number(s) {bare}; cite a fact as {{F#}}")
        missing = [f for f in _PLACEHOLDER.findall(text) if f not in cites]
        if missing:
            out.append(f"{where} uses {missing} without citing them")
    return out


def rule_comparison(reply: RankReply, offered: Offered) -> list[str]:
    """A comparison word with cited facts of two or more different units, and no cited
    comparison fact (one the code compared itself: a boolean or a marked name).

    Uncited or unknown facts are `rule_ids_offered`'s and are ignored here.
    """
    out = []
    for where, cites, text in _sentences(reply):
        units = {offered.facts[f].unit for f in cites if f in offered.facts}
        compared = any(offered.facts[f].comparison for f in cites if f in offered.facts)
        if _COMPARISON.search(text) and len(units) >= 2 and not compared:
            out.append(f"{where} compares facts of different units {sorted(units)} "
                       "without citing a comparison fact")
    return out


def rule_provenance(reply: RankReply, offered: Offered) -> list[str]:
    """The first hypothesis may not rest on `vision` facts alone."""
    if not reply.order:
        return []
    first = reply.order[0]
    cited = [f for w in reply.why if w.hypothesis == first for f in w.cites
             if f in offered.facts]
    if cited and all(offered.facts[f].provenance == "vision" for f in cited):
        return [f"{first} is ranked first on vision facts only"]
    return []


RANK_RULES: tuple[tuple[str, Callable[[RankReply, Offered], list[str]]], ...] = (
    ("cluster", rule_cluster),
    ("ids_offered", rule_ids_offered),
    ("order_permutation", rule_order_permutation),
    ("intervention_allowed", rule_intervention_allowed),
    ("check_offered_or_null", rule_check_offered_or_null),
    ("cites_present", rule_cites_present),
    ("numbers", rule_numbers),
    ("comparison", rule_comparison),
    ("provenance", rule_provenance),
)


def check_rank(reply_text: str, offered: Offered, *, cut: bool = False) -> list[Failure]:
    """Every failure of a rank reply, schema first; empty when the reply stands."""
    schema = rule_schema(reply_text, cut=cut)
    if schema:
        return [Failure("schema", m) for m in schema]
    reply = parse_rank(reply_text)
    return [Failure(rule, m) for rule, fn in RANK_RULES for m in fn(reply, offered)]


def failed_rules(failures: list[Failure]) -> list[str]:
    """The rule ids of `failures`, each once, in order."""
    return list(dict.fromkeys(f.rule for f in failures))
