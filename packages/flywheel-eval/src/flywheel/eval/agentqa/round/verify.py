"""Step B5, verify: the official check of every model item (architecture 20/11 B5).

Reads `judged.jsonl` and the replies its `call_ids` name in `model_calls.jsonl`, runs
the rule library again, and writes one verdict per item to `verdicts.jsonl`. No model
is called and no gateway is built, so `--from verify` re-checks an old run with the
current rules for free.

    accepted    attempt 1 passes
    repaired    attempt 1 fails, attempt 2 passes
    rejected    otherwise, a failed or budget-stopped call included: the code floor stands
    not_ranked  the cluster was beyond the cap of roles.yaml: the code floor stands
"""

from __future__ import annotations

from pathlib import Path

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
    JudgedItem,
    ModelCallRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.reply_rules import Failure, check_rank, failed_rules

VERDICTS_FILE = "verdicts.jsonl"


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


def verify(out: Path) -> list[VerdictRecord]:
    """Verdicts of every item of `out/judged.jsonl`; writes `verdicts.jsonl`."""
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
    (out / VERDICTS_FILE).write_text("".join(v.model_dump_json() + "\n" for v in verdicts),
                                     encoding="utf-8")
    return verdicts
