"""Step B5, verify: the official check of every model item (architecture 20/11 B5).

Reads `judged.jsonl` and the replies its `call_ids` name in `model_calls.jsonl`, runs
the rule library again, and writes one verdict per item to `verdicts.jsonl`. No model
is called and no gateway is built, so `--from verify` re-checks an old run with the
current rules for free.

    accepted    attempt 1 passes
    repaired    attempt 1 fails, attempt 2 passes
    rejected    otherwise, a failed or budget-stopped call included: the code floor stands
    not_ranked  the cluster was beyond the cap of roles.yaml: the code floor stands

DA-52: a hypothesis the investigate role kept (`investigated.jsonl`) gets a verdict too,
`role="investigate"`, from the record's own `offered` block (no prompt is rebuilt):

    numbers     no bare number; every `{F#}` of a text is among its cites; every cite offered
    comparison  a comparison word over cited facts of two or more units needs a cited
                comparison fact (the rank role's `rule_comparison`)
    provenance  its support may not be `vision` facts only (the rank role's `rule_provenance`)
    evidence    its support cites a `measure_compare` fact of its own cluster that compared:
                `_separated` true, or `_beyond_threshold` over half the call's `_members`

    accepted    every rule passes
    rejected    otherwise; `failed_rules == ["evidence"]` alone is "not enough evidence"
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from flywheel.contracts.agentqa import bare_numbers
from flywheel.eval.agentqa.round.gateway import MODEL_CALLS_FILE
from flywheel.eval.agentqa.round.hypotheses import HYPOTHESES_FILE, RulesRefused, load_rules
from flywheel.eval.agentqa.round.judge import (
    COMPARISON_MARKERS,
    JUDGED_FILE,
    RolesRefused,
    is_comparison_fact,
    load_roles,
)
from flywheel.eval.agentqa.round.measure import FACTS_FILE
from flywheel.eval.agentqa.round.records import (
    FactRecord,
    HypothesisRecord,
    InvestigatedHypothesis,
    JudgedItem,
    ModelCallRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.reply_rules import _COMPARISON, Failure, check_rank, failed_rules
from flywheel.eval.agentqa.tools.clusters import NO_LEVEL
from flywheel.eval.agentqa.tools.measures import COMPARE, cluster_slug, parse_fact_name

VERDICTS_FILE = "verdicts.jsonl"
# Written by the investigate step (round/investigate.py imports the names from here).
INVESTIGATED_FILE = "investigated.jsonl"
INVESTIGATION_FACTS_FILE = "investigation_facts.jsonl"
INVESTIGATE_ROLE = "investigate"
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")
EVIDENCE = "evidence"


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def read_calls(out: Path) -> dict[str, ModelCallRecord]:
    calls = (ModelCallRecord.model_validate_json(x) for x in _lines(out / MODEL_CALLS_FILE))
    return {c.call_id: c for c in calls}


def _with_comparison(item: JudgedItem, facts: dict[str, FactRecord],
                     markers: tuple[str, ...]) -> JudgedItem:
    """The item with every offered fact's `comparison` flag recomputed from `facts.jsonl`.

    Old `judged.jsonl` lines hold no flag (an offer stores no name or value), so the name
    and value are read from the run's facts; a fact missing there keeps its stored flag.
    """
    known = {fid: of.model_copy(update={"comparison": is_comparison_fact(
        facts[fid].name, facts[fid].value, markers)})
        for fid, of in item.offered.facts.items() if fid in facts}
    offered = item.offered.model_copy(update={"facts": {**item.offered.facts, **known}})
    return item.model_copy(update={"offered": offered})


def _with_system(item: JudgedItem, system_of: dict[tuple[str, str], bool]) -> JudgedItem:
    """The item with `offered.system` recomputed from `hypotheses.jsonl` and the rules.

    Old `judged.jsonl` lines hold no list; when a hypothesis is unknown the stored list stays.
    """
    cid = item.offered.cluster_id
    if any((cid, h) not in system_of for h in item.offered.hypotheses):
        return item
    system = [h for h in item.offered.hypotheses if system_of[(cid, h)]]
    return item.model_copy(update={"offered": item.offered.model_copy(update={"system": system})})


def _system_flags(out: Path) -> dict[tuple[str, str], bool]:
    """(cluster id, hypothesis id) -> whether its rule is a system fault; {} if no rules load."""
    try:
        by_rule = {r.id: r.system for r in load_rules()}
    except RulesRefused:
        return {}
    records = (HypothesisRecord.model_validate_json(x) for x in _lines(out / HYPOTHESES_FILE))
    return {(h.cluster.cluster_id, h.hypothesis_id): by_rule[h.rule_id]
            for h in records if h.rule_id in by_rule}


def verdict_of(item: JudgedItem, calls: dict[str, ModelCallRecord]) -> VerdictRecord:
    def base(**fields: object) -> VerdictRecord:
        return VerdictRecord.model_validate({
            "item_id": item.item_id, "role": item.role, "unit": item.unit,
            "call_ids": item.call_ids, **fields})

    if item.skipped_reason:
        return base(verdict="not_ranked",
                    reason=f"not ranked: {item.skipped_reason} (beyond the cluster cap "
                           "of roles.yaml)")
    last: list[Failure] = []
    reason = "no model call was made for it"
    for k, call_id in enumerate(item.call_ids):
        call = calls.get(call_id)
        if call is None:
            reason = f"call {call_id} is not in {MODEL_CALLS_FILE}"
            break
        if call.status not in ("ok", "cut"):
            reason = f"call {call_id} {call.status}: {call.error}"[:300]
            break
        failures = check_rank(call.reply, item.offered, cut=call.status == "cut")
        if not failures:
            return base(
                verdict="accepted" if k == 0 else "repaired",
                accepted_call_id=call_id,  # failed_rules: the reply checked last passed
                reason=("accepted: the reply passed every rule" if k == 0 else
                        f"repaired: the resend passed after {', '.join(failed_rules(last))}"))
        last = failures
        reason = f"reply {call_id} failed {', '.join(failed_rules(failures))}"
    return base(verdict="rejected", failed_rules=failed_rules(last),
                reason=f"rejected: {reason}")


def _texts(h: InvestigatedHypothesis) -> list[tuple[str, list[str], str]]:
    """(where, cites, text) of the three texts of a model hypothesis."""
    return [("statement", [*h.support, *h.contra], h.statement),
            ("data_content", list(h.data_content.cites), h.data_content.text),
            ("first_check", list(h.first_check.cites), h.first_check.text)]


def _numbers(h: InvestigatedHypothesis) -> list[str]:
    out = []
    for where, cites, text in _texts(h):
        bare = bare_numbers(text)
        if bare:
            out.append(f"{where} writes the number(s) {bare}")
        missing = [f for f in _PLACEHOLDER.findall(text) if f not in cites]
        if missing:
            out.append(f"{where} uses {missing} without citing them")
        unknown = [f for f in dict.fromkeys(cites) if f not in h.offered]
        if unknown:
            out.append(f"{where} cites {unknown}, which were not offered")
    return out


def _comparison(h: InvestigatedHypothesis, flags: dict[str, bool]) -> list[str]:
    """As `reply_rules.rule_comparison`: uncited or unknown facts are `numbers`'s."""
    out = []
    for where, cites, text in _texts(h):
        units = {h.offered[f].unit for f in cites if f in h.offered}
        compared = any(flags.get(f, False) for f in cites if f in h.offered)
        if _COMPARISON.search(text) and len(units) >= 2 and not compared:
            out.append(f"{where} compares facts of different units {sorted(units)} without "
                       "citing a comparison fact")
    return out


def _provenance(h: InvestigatedHypothesis) -> list[str]:
    """As `reply_rules.rule_provenance`, for the hypothesis's support."""
    cited = [f for f in h.support if f in h.offered]
    if cited and all(h.offered[f].provenance == "vision" for f in cited):
        return [f"{h.hypothesis_id} rests on vision facts only"]
    return []


def _evidence(h: InvestigatedHypothesis, by_name: dict[str, FactRecord]) -> list[str]:
    """The keep rule (AC 5): comparison evidence the code computed about its own cluster."""
    c = h.cluster
    own = cluster_slug(c.step, c.label, None if c.level == NO_LEVEL else c.level)
    for fid in h.support:
        fact = h.offered.get(fid)
        parts = None if fact is None else parse_fact_name(fact.name)
        if fact is None or parts is None or parts.tool != COMPARE:
            continue
        if parts.run != c.run or parts.cluster != own:
            continue
        if parts.suffix == "_separated" and fact.value is True:
            return []
        if parts.suffix == "_beyond_threshold" and _count(fact.value) is not None:
            members = by_name.get(f"{parts.base}_members")
            size = None if members is None else _count(members.value)
            if size is not None and 2 * (_count(fact.value) or 0) > size:
                return []
    return [f"{h.hypothesis_id}: its support cites no measure_compare fact of its own cluster "
            "that separates it (separated true, or beyond the threshold for more than half "
            "its members)"]


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def investigated_verdict(h: InvestigatedHypothesis, by_name: dict[str, FactRecord],
                         markers: Sequence[str]) -> VerdictRecord:
    """The verdict of one hypothesis the investigate role kept."""
    flags = {fid: is_comparison_fact(f.name, f.value, tuple(markers))
             for fid, f in h.offered.items()}
    failures = [(rule, m) for rule, found in (
        ("numbers", _numbers(h)), ("comparison", _comparison(h, flags)),
        ("provenance", _provenance(h)), (EVIDENCE, _evidence(h, by_name))) for m in found]
    rules = list(dict.fromkeys(rule for rule, _ in failures))
    item_id = f"{INVESTIGATE_ROLE}:{h.hypothesis_id}"
    if not failures:
        return VerdictRecord(item_id=item_id, role=INVESTIGATE_ROLE, unit=h.hypothesis_id,
                             verdict="accepted",
                             reason="accepted: the model's hypothesis passed every rule")
    if rules == [EVIDENCE]:
        reason = "rejected: not enough evidence: " + failures[0][1]
    else:
        reason = "rejected: " + "; ".join(m for _, m in failures)
    return VerdictRecord(item_id=item_id, role=INVESTIGATE_ROLE, unit=h.hypothesis_id,
                         verdict="rejected", failed_rules=rules, reason=reason[:300])


def verify(out: Path) -> list[VerdictRecord]:
    """Verdicts of every item of `out/judged.jsonl`, then of every hypothesis of
    `investigated.jsonl` (DA-52); writes `verdicts.jsonl`."""
    items = [JudgedItem.model_validate_json(x) for x in _lines(out / JUDGED_FILE)]
    calls = read_calls(out)
    facts = {f.fact_id: f for f in
             (FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE))}
    try:
        markers = load_roles().rank.comparison_markers
    except RolesRefused:  # run from another directory: the shipped markers
        markers = COMPARISON_MARKERS
    system_of = _system_flags(out)
    verdicts = [verdict_of(_with_system(_with_comparison(item, facts, markers), system_of), calls)
                for item in items]
    kept = [InvestigatedHypothesis.model_validate_json(x) for x in _lines(out / INVESTIGATED_FILE)]
    if kept:
        found = [FactRecord.model_validate_json(x)
                 for x in _lines(out / INVESTIGATION_FACTS_FILE)]
        by_name = {f.name: f for f in [*facts.values(), *found]}
        verdicts += [investigated_verdict(h, by_name, markers) for h in kept]
    (out / VERDICTS_FILE).write_text("".join(v.model_dump_json() + "\n" for v in verdicts),
                                     encoding="utf-8")
    return verdicts
