"""Step B6, assemble: the hypotheses, facts and not-judged items of a round, ready to show.

The no-model path (DA-43 task 4.4): every hypothesis, rank and choice is the code floor
of step B3. With a model (task 5.2), a cluster whose rank item B5 `accepted` or
`repaired` shows the model's order, sentences, check and intervention; every other
cluster shows exactly the code floor, with the reason. A rejected item earns the model
nothing. The file holds ids and words, never a new number; the page (`render.py`) looks
every number up in `facts.jsonl`, placeholders `{F#}` included.

DA-52: a hypothesis of the investigate role that B5 accepted is shown ABOVE the rule
hypotheses of its group (Hiếu 27/11/2026), never above a system rule's hypothesis, which
still blocks data spend; the "no rule explains this cluster" placeholder stays below it.
Its group is the one of the rules with its diagnosis (the last in the group order; `data`
when no rule has it). One rejected only for lack of comparison evidence is shown last,
flagged; any other rejected one is not shown. When one ends first in its cluster, the
cluster's intervention, data content and first check are the model's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from flywheel.eval.agentqa.round.admit import ADMISSION_FILE
from flywheel.eval.agentqa.round.hypotheses import (
    GROUPS,
    HYPOTHESES_FILE,
    NO_RULE_TITLE,
    NONE_RULE,
    Rule,
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
    Group,
    HypothesisRecord,
    HypothesisView,
    InvestigatedHypothesis,
    ModelCallRecord,
    NotJudged,
    Pack,
    RunRecord,
    ToolCallRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.reply_rules import parse_rank
from flywheel.eval.agentqa.round.verify import (
    EVIDENCE,
    INVESTIGATE_ROLE,
    INVESTIGATED_FILE,
    VERDICTS_FILE,
    read_calls,
)

ASSEMBLY_FILE = "assembly.json"
__all__ = ["ASSEMBLY_FILE", "NO_RULE_TITLE", "assemble"]
FLOOR_REASON = "code floor, the model did not judge this cluster: {reason}"
NO_MODEL_NOTE = "No model was called: every hypothesis, rank and choice is the code floor."
NO_COST_NOTE = "Costs are not attached yet (cost lookup, task 3.4)."
MODEL_TITLE = "Hypothesis of the model"
MODEL_RULE = "model"  # the rule id a model hypothesis is shown with


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


def model_group(diagnosis: str, rules: list[Rule]) -> Group:
    """The group of the rules that carry `diagnosis`, the last in the group order; `data`."""
    groups = [r.group for r in rules if r.diagnosis == diagnosis]
    return max(groups, key=GROUPS.index) if groups else "data"


def _model_hypothesis(h: InvestigatedHypothesis, group: Group,
                      evidence: Literal["kept", "insufficient"]) -> HypothesisView:
    cites = list(dict.fromkeys([*h.support, *h.contra, *h.data_content.cites,
                                *h.first_check.cites]))
    return HypothesisView(
        hypothesis_id=h.hypothesis_id, rule_id=MODEL_RULE, title=MODEL_TITLE, group=group,
        diagnosis=h.diagnosis, note=MODEL_RULE, rank=1, source="model", support=h.support,
        contra=h.contra, explanation=h.statement, origin="model", evidence=evidence,
        intervention=h.intervention, data_content=h.data_content.text,
        first_check=h.first_check.text, cites=cites)


def place(views: list[HypothesisView], kept: list[HypothesisView],
          system_rules: frozenset[str]) -> list[HypothesisView]:
    """`views` with every `kept` model hypothesis above the rule ones of its group.

    Each goes before the first hypothesis of its group or a later one (or the no-rule
    placeholder), but below every system rule's hypothesis and below the ones placed
    before it, so several keep their order. Ranks are renumbered.
    """
    out = list(views)
    floor = 0  # just below the last system hypothesis, then below each one placed
    for k, v in enumerate(out):
        if v.rule_id in system_rules:
            floor = k + 1
    for m in kept:
        at = next((k for k, v in enumerate(out)
                   if v.origin == "rule" and (v.rule_id == NONE_RULE
                                              or GROUPS.index(v.group) >= GROUPS.index(m.group))),
                  len(out))
        at = max(at, floor)
        out.insert(at, m)
        floor = at + 1
    return [v.model_copy(update={"rank": k}) for k, v in enumerate(out, start=1)]


def _with_model(view: ClusterView, kept: list[HypothesisView],
                insufficient: list[HypothesisView],
                system_rules: frozenset[str]) -> ClusterView:
    """The cluster view with the model's hypotheses placed; cluster fields as specified."""
    if not kept and not insufficient:
        return view
    placed = place(view.hypotheses, kept, system_rules)
    shown = [*placed, *(v.model_copy(update={"rank": len(placed) + k})
                        for k, v in enumerate(insufficient, start=1))]
    update: dict[str, object] = {"hypotheses": shown}
    top = placed[0] if placed else None
    if top is not None and top.origin == "model":
        update.update(intervention=top.intervention, intervention_source="model",
                      intervention_text=top.data_content, check_text=top.first_check,
                      check=None, intervention_for=top.hypothesis_id,
                      model_cites=list(dict.fromkeys([*view.model_cites, *top.cites])))
    return view.model_copy(update=update)


def _model_counts(verdicts: list[VerdictRecord]) -> str:
    kept = sum(1 for v in verdicts if v.verdict == "accepted")
    thin = sum(1 for v in verdicts if v.verdict == "rejected" and v.failed_rules == [EVIDENCE])
    return (f"Model investigation: {kept} kept, {thin} not enough evidence, "
            f"{len(verdicts) - kept - thin} rejected.")


def _counts(verdicts: list[VerdictRecord]) -> str:
    n = {k: sum(1 for v in verdicts if v.verdict == k)
         for k in ("accepted", "repaired", "rejected", "not_ranked")}
    return (f"Model ranking: {n['accepted']} accepted, {n['repaired']} repaired, "
            f"{n['rejected']} rejected, {n['not_ranked']} not ranked.")


def _place_model(out: Path, clusters: list[ClusterView], verdicts: list[VerdictRecord],
                 rules: list[Rule], system_rules: frozenset[str]) -> list[ClusterView]:
    """Every cluster view with the investigate role's hypotheses B5 judged."""
    by_id = {v.unit: v for v in verdicts}
    kept: dict[str, list[HypothesisView]] = {}
    thin: dict[str, list[HypothesisView]] = {}
    for line in _lines(out / INVESTIGATED_FILE):
        h = InvestigatedHypothesis.model_validate_json(line)
        verdict = by_id.get(h.hypothesis_id)
        if verdict is None:
            continue
        group = model_group(h.diagnosis, rules)
        if verdict.verdict == "accepted":
            kept.setdefault(h.cluster.cluster_id, []).append(
                _model_hypothesis(h, group, "kept"))
        elif verdict.failed_rules == [EVIDENCE]:
            thin.setdefault(h.cluster.cluster_id, []).append(
                _model_hypothesis(h, group, "insufficient"))
    return [_with_model(c, kept.get(c.cluster.cluster_id, []),
                        thin.get(c.cluster.cluster_id, []), system_rules) for c in clusters]


def assemble(out: Path, run: RunRecord, no_model: bool = True) -> Assembly:
    """Build `out/assembly.json` from the files of the earlier steps."""
    pack = Pack.model_validate_json((out / PACK_FILE).read_text(encoding="utf-8"))
    admission = Admission.model_validate_json((out / ADMISSION_FILE).read_text("utf-8"))
    hypotheses = [HypothesisRecord.model_validate_json(x)
                  for x in _lines(out / HYPOTHESES_FILE)]
    facts = [FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE)]
    calls = [ToolCallRecord.model_validate_json(x) for x in _lines(out / CALLS_FILE)]
    rules = load_rules()
    titles = {r.id: r.title for r in rules}
    system_rules = frozenset(r.id for r in rules if r.system)
    every = ([] if no_model else
             [VerdictRecord.model_validate_json(x) for x in _lines(out / VERDICTS_FILE)])
    verdicts = [v for v in every if v.role != INVESTIGATE_ROLE]
    inquired = [v for v in every if v.role == INVESTIGATE_ROLE]
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
    if inquired:
        clusters = _place_model(out, clusters, inquired, rules, system_rules)

    not_judged = _not_judged(facts, calls, admission)
    notes = [NO_MODEL_NOTE] if no_model else [_counts(verdicts)]
    if inquired:
        notes.append(_model_counts(inquired))
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
