"""Step B4, judge: the rank role asks the model to order each cluster's hypotheses.

The only step that calls a model, always through the gateway (architecture 20/11 B4,
section 25). One call per cluster, largest first, at most `max_clusters` of
`roles.yaml`; the rest stay on the code floor (`over_cap`). The user message is ONE
JSON object; strings from artifacts (labels, fact values, notes) enter only as JSON
values, cut to `FACT_TEXT_CHARS`. After each reply the rule library decides on the one
resend (attempt 2, with the failures as `previous_errors`); `failed` and
`budget_exhausted` replies get none. B5 (`verify.py`) gives the verdicts; this step only
writes `judged.jsonl`, which holds everything B5 needs so it never rebuilds a prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from flywheel.eval.agentqa.round.gateway import Gateway
from flywheel.eval.agentqa.round.hypotheses import HYPOTHESES_FILE, load_rules, rule_title
from flywheel.eval.agentqa.round.measure import FACTS_FILE
from flywheel.eval.agentqa.round.records import (
    CheckRef,
    FactRecord,
    HypothesisRecord,
    JudgedItem,
    ModelRequest,
    Offered,
    OfferedFact,
)
from flywheel.eval.agentqa.round.reply_rules import RANK_REPLY_SCHEMA, check_rank
from pydantic import BaseModel, ConfigDict, Field, ValidationError

JUDGED_FILE = "judged.jsonl"
ROLES_FILE = Path("configs") / "eval" / "agentqa" / "roles.yaml"  # from the repo root
RANK_PROMPT = Path("configs") / "eval" / "agentqa" / "prompts" / "rank.md"
MAX_RANK_CLUSTERS = 8
MAX_RANK_FACTS = 60
RANK_MAX_TOKENS = 1500
FACT_TEXT_CHARS = 200
OVER_CAP = "over_cap"
ANSWERED = ("ok", "cut")
_FACT_NUMBER = re.compile(r"^F([0-9]+)$")


COMPARISON_MARKERS = ("_above_tau", "_exceeds_tau", "_separates_", "_in_domain", "_near_miss",
                      "_within_", "_matches_", "_judgeable", "_largest_drop")


def is_comparison_fact(name: str, value: object, markers: tuple[str, ...]) -> bool:
    """A comparison fact: the code compared for the model (a boolean, or a marked name)."""
    return isinstance(value, bool) or any(m in name for m in markers)


class RolesRefused(ValueError):
    """`roles.yaml` or a prompt cannot be used; no call was made."""


class RankLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_clusters: int = Field(default=MAX_RANK_CLUSTERS, ge=0)
    max_facts: int = Field(default=MAX_RANK_FACTS, ge=0)
    comparison_markers: tuple[str, ...] = Field(default=COMPARISON_MARKERS)


class Roles(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: RankLimits = Field(default_factory=RankLimits)


def load_roles(path: Path | None = None) -> Roles:
    target = path or ROLES_FILE
    try:
        return Roles.model_validate(yaml.safe_load(target.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise RolesRefused(f"{target}: {str(error).strip().splitlines()[0][:200]}") from error


def load_prompt(path: Path | None = None) -> str:
    target = path or RANK_PROMPT
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as error:
        raise RolesRefused(f"{target}: {error}") from error
    if not text.strip():
        raise RolesRefused(f"{target}: empty prompt")
    return text


@dataclass
class JudgeResult:
    items: list[JudgedItem] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def clusters_of(hypotheses: list[HypothesisRecord]) -> list[list[HypothesisRecord]]:
    """The hypotheses by cluster, each in code order, clusters largest first."""
    by_cluster: dict[str, list[HypothesisRecord]] = {}
    for h in hypotheses:
        by_cluster.setdefault(h.cluster.cluster_id, []).append(h)
    groups = [sorted(m, key=lambda h: h.code_rank) for m in by_cluster.values()]
    return sorted(groups, key=lambda m: (-m[0].cluster.size, m[0].cluster.cluster_id))


def _fact_order(fact_id: str) -> tuple[int, str]:
    match = _FACT_NUMBER.match(fact_id)
    return (int(match.group(1)) if match else 1 << 62, fact_id)


def offered_facts(members: list[HypothesisRecord], facts: list[FactRecord],
                  cap: int) -> list[FactRecord]:
    """Cited facts first, then the run's facts of its step or label, then its not-judged ones."""
    by_id = {f.fact_id: f for f in facts}
    cited = [fid for h in members for fid in (*h.support, *h.contra) if fid in by_id]
    cluster = members[0].cluster
    related = [f.fact_id for f in sorted(facts, key=lambda f: _fact_order(f.fact_id))
               if cluster.run in f.name
               and (cluster.step in f.name or cluster.label in f.name
                    or f.name.endswith("_not_judged"))]
    chosen = list(dict.fromkeys([*cited, *related]))[:cap]
    return [by_id[fid] for fid in chosen]


def _value(value: float | int | str | bool) -> float | int | str | bool:
    return value[:FACT_TEXT_CHARS] if isinstance(value, str) else value


def _checks(members: list[HypothesisRecord]) -> list[dict[str, Any]]:
    """The union of the hypotheses' checks, cheapest first; pairs named by hypothesis id."""
    by_rule = {h.rule_id: h.hypothesis_id for h in members}
    merged: dict[str, tuple[CheckRef, list[list[str]]]] = {}
    for h in members:
        for c in h.checks:
            pairs = [[by_rule.get(r, r) for r in pair] for pair in c.separates]
            ref, known = merged.setdefault(c.check_id, (c, []))
            known += [p for p in pairs if p not in known]
    ordered = sorted(merged.values(), key=lambda x: (x[0].cost_rank, x[0].check_id))
    return [{"id": ref.check_id, "cost_rank": ref.cost_rank, "cost_key": ref.cost_key,
             "separates": pairs} for ref, pairs in ordered]


def build_unit(members: list[HypothesisRecord], facts: list[FactRecord],
               titles: dict[str, str], max_facts: int,
               markers: tuple[str, ...] = COMPARISON_MARKERS,
               system_rules: frozenset[str] = frozenset()) -> tuple[dict[str, Any], Offered]:
    """The user payload of one rank call, and what it offered."""
    cluster = members[0].cluster
    chosen = offered_facts(members, facts, max_facts)
    checks = _checks(members)
    payload: dict[str, Any] = {
        "cluster": {"id": cluster.cluster_id, "run": cluster.run, "step": cluster.step,
                    "label": cluster.label, "level": cluster.level, "size": cluster.size},
        "hypotheses": [{
            "id": h.hypothesis_id, "title": rule_title(h.rule_id, titles),
            "diagnosis": h.diagnosis, "note": h.note, "support": h.support,
            "contra": h.contra, "interventions": list(h.interventions),
            "checks": [c.check_id for c in h.checks],
            "system": h.rule_id in system_rules} for h in members],
        "checks": checks,
        "facts": [{"id": f.fact_id, "name": f.name[:FACT_TEXT_CHARS], "value": _value(f.value),
                   "unit": f.unit, "provenance": f.provenance} for f in chosen],
        "blocked_data_spend": members[0].blocked_data_spend,
    }
    offered = Offered(
        cluster_id=cluster.cluster_id, hypotheses=[h.hypothesis_id for h in members],
        interventions={h.hypothesis_id: list(h.interventions) for h in members},
        checks=[c["id"] for c in checks],
        facts={f.fact_id: OfferedFact(
            unit=f.unit, provenance=f.provenance,
            comparison=is_comparison_fact(f.name, f.value, markers)) for f in chosen},
        blocked_data_spend=members[0].blocked_data_spend,
        system=[h.hypothesis_id for h in members if h.rule_id in system_rules])
    return payload, offered


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _rank_one(gateway: Gateway, system: str, payload: dict[str, Any],
              offered: Offered) -> tuple[list[str], str]:
    """Call ids of one cluster, and a problem line ("" when the item may stand)."""
    unit = offered.cluster_id
    first = gateway.call("rank", ModelRequest(
        unit=unit, attempt=1, system=system, user=_dump(payload),
        reply_schema=RANK_REPLY_SCHEMA, max_tokens=RANK_MAX_TOKENS))
    if first.status not in ANSWERED:
        return [first.call_id], f"{unit}: call {first.call_id} {first.status}: {first.error}"
    failures = check_rank(first.text, offered, cut=first.status == "cut")
    if not failures:
        return [first.call_id], ""
    second = gateway.call("rank", ModelRequest(
        unit=unit, attempt=2, system=system,
        user=_dump({**payload, "previous_errors": [str(f) for f in failures]}),
        reply_schema=RANK_REPLY_SCHEMA, max_tokens=RANK_MAX_TOKENS))
    calls = [first.call_id, second.call_id]
    if second.status not in ANSWERED:
        return calls, f"{unit}: resend {second.call_id} {second.status}: {second.error}"
    again = check_rank(second.text, offered, cut=second.status == "cut")
    if again:
        rules = ", ".join(dict.fromkeys(f.rule for f in again))
        return calls, f"{unit}: the resend {second.call_id} also failed ({rules})"
    return calls, ""


def judge(out: Path, gateway: Gateway, *, roles: Roles | None = None,
          system: str | None = None) -> JudgeResult:
    """Rank the clusters of the run directory `out`; writes `judged.jsonl`."""
    limits = (roles or load_roles()).rank
    prompt = system if system is not None else load_prompt()
    hypotheses = [HypothesisRecord.model_validate_json(x) for x in _lines(out / HYPOTHESES_FILE)]
    facts = [FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE)]
    rules = load_rules()
    titles = {r.id: r.title for r in rules}
    system_rules = frozenset(r.id for r in rules if r.system)
    result = JudgeResult()
    for k, members in enumerate(clusters_of(hypotheses)):
        payload, offered = build_unit(members, facts, titles, limits.max_facts,
                                     limits.comparison_markers, system_rules)
        unit = offered.cluster_id
        if k >= limits.max_clusters:
            result.items.append(JudgedItem(item_id=f"rank:{unit}", role="rank", unit=unit,
                                           offered=offered, skipped_reason=OVER_CAP))
            continue
        calls, problem = _rank_one(gateway, prompt, payload, offered)
        if problem:
            result.problems.append(problem)
        result.items.append(JudgedItem(item_id=f"rank:{unit}", role="rank", unit=unit,
                                       call_ids=calls, offered=offered))
    (out / JUDGED_FILE).write_text("".join(i.model_dump_json() + "\n" for i in result.items),
                                   encoding="utf-8")
    return result
