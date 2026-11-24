"""Step B6, assemble: the hypotheses, facts and not-judged items of a round, ready to show.

The no-model path (DA-43 task 4.4): every hypothesis, rank and choice is the code floor
of step B3. With a model (task 5.2), a cluster whose rank item B5 `accepted` or
`repaired` shows the model's order, sentences, check and intervention; every other
cluster shows exactly the code floor, with the reason. A rejected item earns the model
nothing. The file holds ids and words, never a new number; the page (`render.py`) looks
every number up in `facts.jsonl`, placeholders `{F#}` included.
"""

from __future__ import annotations

from pathlib import Path

from flywheel.eval.agentqa.round.admit import ADMISSION_FILE
from flywheel.eval.agentqa.round.hypotheses import (
    HYPOTHESES_FILE,
    NO_RULE_TITLE,
    load_rules,
    rule_title,
)
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE
from flywheel.eval.agentqa.round.pack import PACK_FILE
from flywheel.eval.agentqa.round.records import (
    Admission,
    Assembly,
    ClusterView,
    FactRecord,
    HypothesisRecord,
    HypothesisView,
    ModelCallRecord,
    NotJudged,
    Pack,
    RunRecord,
    ToolCallRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.reply_rules import parse_rank
from flywheel.eval.agentqa.round.verify import VERDICTS_FILE, read_calls

ASSEMBLY_FILE = "assembly.json"
__all__ = ["ASSEMBLY_FILE", "NO_RULE_TITLE", "assemble"]
FLOOR_REASON = "code floor, the model did not judge this cluster: {reason}"
NO_MODEL_NOTE = "No model was called: every hypothesis, rank and choice is the code floor."
NO_COST_NOTE = "Costs are not attached yet (cost lookup, task 3.4)."


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def _view(h: HypothesisRecord, titles: dict[str, str]) -> HypothesisView:
    return HypothesisView(
        hypothesis_id=h.hypothesis_id, rule_id=h.rule_id,
        title=rule_title(h.rule_id, titles),
        group=h.group, diagnosis=h.diagnosis, note=h.note, rank=h.code_rank, source="code",
        support=h.support, contra=h.contra, refutes=h.refutes)


def _not_judged(facts: list[FactRecord], calls: list[ToolCallRecord],
                admission: Admission) -> list[NotJudged]:
    items = [NotJudged(what=f.name, reason=str(f.value), fact_id=f.fact_id)
             for f in facts if f.name.endswith("_not_judged")]
    items += [NotJudged(what=c.tool, reason=c.reason) for c in calls if c.status == "skipped"]
    items += [NotJudged(what=r.ref, reason=r.reason) for r in admission.rejected]
    items += [NotJudged(what=k, reason="no accepted entry of this kind")
              for k in admission.missing_kinds]
    return items


def _floor(members: list[HypothesisRecord], titles: dict[str, str]) -> ClusterView:
    top = members[0]
    return ClusterView(
        cluster=top.cluster, hypotheses=[_view(h, titles) for h in members],
        blocked_data_spend=top.blocked_data_spend,
        check=top.checks[0] if top.checks else None,
        intervention=top.interventions[0] if top.interventions else None,
        intervention_source="code", costed=False)


def _ranked(members: list[HypothesisRecord], titles: dict[str, str],
            verdict: VerdictRecord, call: ModelCallRecord) -> ClusterView:
    """The cluster as the model ranked it; B5 has already checked every id of the reply."""
    reply = parse_rank(call.reply)
    by_id = {h.hypothesis_id: h for h in members}
    why = {w.hypothesis: w.text for w in reversed(reply.why)}  # the first entry wins
    views = [_view(by_id[hid], titles).model_copy(update={
        "rank": k, "source": "model", "explanation": why.get(hid, "")})
        for k, hid in enumerate(reply.order, start=1)]
    checks = {c.check_id: c for h in members for c in h.checks}
    pick = reply.check if reply.check is not None and reply.check.id is not None else None
    cites = [f for w in reply.why for f in w.cites]  # a check with no id is `check: null`
    if pick is not None:
        cites += pick.cites
    cites += reply.intervention.cites
    return ClusterView(
        cluster=members[0].cluster, hypotheses=views,
        blocked_data_spend=members[0].blocked_data_spend,
        check=checks.get(pick.id or "") if pick is not None else None,
        intervention=reply.intervention.id, intervention_source="model", costed=False,
        verdict=verdict.verdict, ranked_by=call.model,
        check_text=pick.text if pick is not None else "",
        intervention_text=reply.intervention.text, intervention_for=reply.intervention.for_,
        model_cites=list(dict.fromkeys(cites)))


def _model_view(members: list[HypothesisRecord], titles: dict[str, str],
                verdict: VerdictRecord | None,
                calls: dict[str, ModelCallRecord]) -> ClusterView:
    call = calls.get(verdict.accepted_call_id) if verdict is not None else None
    if verdict is not None and verdict.verdict in ("accepted", "repaired") and call is not None:
        return _ranked(members, titles, verdict, call)
    reason = verdict.reason if verdict is not None else "no rank item for it"
    return _floor(members, titles).model_copy(update={
        "verdict": verdict.verdict if verdict is not None else "",
        "floor_reason": FLOOR_REASON.format(reason=reason)})


def _counts(verdicts: list[VerdictRecord]) -> str:
    n = {k: sum(1 for v in verdicts if v.verdict == k)
         for k in ("accepted", "repaired", "rejected", "not_ranked")}
    return (f"Model ranking: {n['accepted']} accepted, {n['repaired']} repaired, "
            f"{n['rejected']} rejected, {n['not_ranked']} not ranked.")


def assemble(out: Path, run: RunRecord, no_model: bool = True) -> Assembly:
    """Build `out/assembly.json` from the files of the earlier steps."""
    pack = Pack.model_validate_json((out / PACK_FILE).read_text(encoding="utf-8"))
    admission = Admission.model_validate_json((out / ADMISSION_FILE).read_text("utf-8"))
    hypotheses = [HypothesisRecord.model_validate_json(x)
                  for x in _lines(out / HYPOTHESES_FILE)]
    facts = [FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE)]
    calls = [ToolCallRecord.model_validate_json(x) for x in _lines(out / CALLS_FILE)]
    titles = {r.id: r.title for r in load_rules()}
    verdicts = ([] if no_model else
                [VerdictRecord.model_validate_json(x) for x in _lines(out / VERDICTS_FILE)])
    by_unit = {v.unit: v for v in verdicts if v.role == "rank"}
    model_calls = {} if no_model else read_calls(out)

    by_cluster: dict[str, list[HypothesisRecord]] = {}
    for h in hypotheses:
        by_cluster.setdefault(h.cluster.cluster_id, []).append(h)
    clusters: list[ClusterView] = []
    for cluster_id, members in by_cluster.items():
        members.sort(key=lambda h: h.code_rank)
        clusters.append(_floor(members, titles) if no_model else
                        _model_view(members, titles, by_unit.get(cluster_id), model_calls))
    clusters.sort(key=lambda c: (-c.cluster.size, c.cluster.cluster_id))

    not_judged = _not_judged(facts, calls, admission)
    notes = [NO_MODEL_NOTE] if no_model else [_counts(verdicts)]
    notes.append(NO_COST_NOTE)
    rejected = any(v.verdict in ("rejected", "not_ranked") for v in verdicts)
    answered = sorted({c.model for c in model_calls.values() if c.status in ("ok", "cut")})
    assembly = Assembly(
        run_id=run.run_id, pack_id=pack.pack_id, task_id=pack.task_id,
        data_class=admission.data_class,
        status="degraded" if no_model or not_judged or rejected else "ok",
        agent_version=run.agent_version, agent_hash=run.agent_hash,
        model=", ".join(answered),
        clusters=clusters, headline=clusters[0] if clusters else None,
        not_judged=not_judged, notes=notes)
    (out / ASSEMBLY_FILE).write_text(assembly.model_dump_json(indent=2) + "\n",
                                     encoding="utf-8")
    return assembly
