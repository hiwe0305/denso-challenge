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
from flywheel.eval.agentqa.round.judge import JUDGED_FILE
from flywheel.eval.agentqa.round.records import (
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
    verdicts = [verdict_of(item, calls) for item in items]
    (out / VERDICTS_FILE).write_text("".join(v.model_dump_json() + "\n" for v in verdicts),
                                     encoding="utf-8")
    return verdicts
