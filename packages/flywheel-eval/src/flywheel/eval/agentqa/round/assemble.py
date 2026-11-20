"""Step B6, assemble: the hypotheses, facts and not-judged items of a round, ready to show.

The no-model path (DA-43 task 4.4): every hypothesis, rank and choice is the code floor
of step B3. The file holds ids and words, never a new number; the page (`render.py`)
looks every number up in `facts.jsonl`.
"""

from __future__ import annotations

from pathlib import Path

from flywheel.eval.agentqa.round.admit import ADMISSION_FILE
from flywheel.eval.agentqa.round.hypotheses import HYPOTHESES_FILE, NONE_RULE, load_rules
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE
from flywheel.eval.agentqa.round.pack import PACK_FILE
from flywheel.eval.agentqa.round.records import (
    Admission,
    Assembly,
    ClusterView,
    FactRecord,
    HypothesisRecord,
    HypothesisView,
    NotJudged,
    Pack,
    RunRecord,
    ToolCallRecord,
)

ASSEMBLY_FILE = "assembly.json"
NO_RULE_TITLE = "No rule of the agent explains this cluster"
NO_MODEL_NOTE = "No model was called: every hypothesis, rank and choice is the code floor."
NO_COST_NOTE = "Costs are not attached yet (cost lookup, task 3.4)."


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def _view(h: HypothesisRecord, titles: dict[str, str]) -> HypothesisView:
    return HypothesisView(
        hypothesis_id=h.hypothesis_id, rule_id=h.rule_id,
        title=NO_RULE_TITLE if h.rule_id == NONE_RULE else titles.get(h.rule_id, h.rule_id),
        group=h.group, diagnosis=h.diagnosis, note=h.note, rank=h.code_rank, source="code",
        support=h.support, contra=h.contra)


def _not_judged(facts: list[FactRecord], calls: list[ToolCallRecord],
                admission: Admission) -> list[NotJudged]:
    items = [NotJudged(what=f.name, reason=str(f.value), fact_id=f.fact_id)
             for f in facts if f.name.endswith("_not_judged")]
    items += [NotJudged(what=c.tool, reason=c.reason) for c in calls if c.status == "skipped"]
    items += [NotJudged(what=r.ref, reason=r.reason) for r in admission.rejected]
    items += [NotJudged(what=k, reason="no accepted entry of this kind")
              for k in admission.missing_kinds]
    return items


def assemble(out: Path, run: RunRecord, no_model: bool = True) -> Assembly:
    """Build `out/assembly.json` from the files of the earlier steps."""
    pack = Pack.model_validate_json((out / PACK_FILE).read_text(encoding="utf-8"))
    admission = Admission.model_validate_json((out / ADMISSION_FILE).read_text("utf-8"))
    hypotheses = [HypothesisRecord.model_validate_json(x)
                  for x in _lines(out / HYPOTHESES_FILE)]
    facts = [FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE)]
    calls = [ToolCallRecord.model_validate_json(x) for x in _lines(out / CALLS_FILE)]
    titles = {r.id: r.title for r in load_rules()}

    by_cluster: dict[str, list[HypothesisRecord]] = {}
    for h in hypotheses:
        by_cluster.setdefault(h.cluster.cluster_id, []).append(h)
    clusters: list[ClusterView] = []
    for members in by_cluster.values():
        members.sort(key=lambda h: h.code_rank)
        top = members[0]
        clusters.append(ClusterView(
            cluster=top.cluster, hypotheses=[_view(h, titles) for h in members],
            blocked_data_spend=top.blocked_data_spend,
            check=top.checks[0] if top.checks else None,
            intervention=top.interventions[0] if top.interventions else None,
            intervention_source="code", costed=False))
    clusters.sort(key=lambda c: (-c.cluster.size, c.cluster.cluster_id))

    not_judged = _not_judged(facts, calls, admission)
    notes = [NO_MODEL_NOTE] if no_model else []
    notes.append(NO_COST_NOTE)
    assembly = Assembly(
        run_id=run.run_id, pack_id=pack.pack_id, task_id=pack.task_id,
        data_class=admission.data_class,
        status="degraded" if no_model or not_judged else "ok",
        agent_version=run.agent_version, agent_hash=run.agent_hash, model="",
        clusters=clusters, headline=clusters[0] if clusters else None,
        not_judged=not_judged, notes=notes)
    (out / ASSEMBLY_FILE).write_text(assembly.model_dump_json(indent=2) + "\n",
                                     encoding="utf-8")
    return assembly
