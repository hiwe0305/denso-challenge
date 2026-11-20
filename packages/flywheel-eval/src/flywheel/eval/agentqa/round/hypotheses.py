"""Step B3, hypothesize: rules over the facts give each failure cluster its hypotheses.

Deterministic code; no model is called (architecture 20/11/2026 section 6, B3). The rules
live in `configs/eval/agentqa/rules/*.yaml`, the checks that tell hypotheses apart in
`configs/eval/agentqa/checks.yaml`; adding a diagnosis is a config change. A hypothesis
never carries a number of its own: support and contra are ids of facts in `facts.jsonl`.

For each cluster of the `failure_clusters` table, every rule whose `when` holds gives one
hypothesis. A cluster no rule matches gets the `none` hypothesis: silence is never
"clean". While a system rule (`system: true`) stands for a cluster, none of its
hypotheses may spend the data budget (spec 6.4: system and scorer before data).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

import yaml
from flywheel.contracts.evidence import (
    BUDGET_INTERVENTIONS,
    INTERVENTIONS_OF_DIAGNOSIS,
    Diagnosis,
    InterventionKind,
)
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE, TABLES_DIR
from flywheel.eval.agentqa.round.pack import PACK_FILE, read_pack
from flywheel.eval.agentqa.round.records import (
    CheckRef,
    ClusterRef,
    FactRecord,
    Group,
    HypothesisRecord,
    Record,
    ToolCallRecord,
)
from flywheel.eval.agentqa.tools.task import TaskView, load_task
from pydantic import Field, ValidationError, model_validator
from typing_extensions import Self

HYPOTHESES_FILE = "hypotheses.jsonl"
RULES_DIR = Path("configs") / "eval" / "agentqa" / "rules"  # from the repo root
CHECKS_FILE = Path("configs") / "eval" / "agentqa" / "checks.yaml"
GROUPS: tuple[str, ...] = get_args(Group)
NONE_RULE = "none"
CLUSTER_TOOL = "failure_clusters"
_TEMPLATE_KEYS = {"run": "r", "step": "s", "label": "l", "level": "0"}


class RulesRefused(ValueError):
    """A rule or check file cannot be used; nothing was hypothesized."""


def _check_template(template: str) -> None:
    try:
        template.format(**_TEMPLATE_KEYS)
    except (KeyError, IndexError, ValueError) as error:
        raise ValueError(f"template {template!r}: only {{run}}, {{step}}, {{label}}, "
                         f"{{level}} may be used ({error!r})") from error


class ClusterCond(Record):
    cluster: Literal["chain_broken"]


class FactCond(Record):
    fact: str = Field(min_length=1)
    is_: Literal[True, False, "positive", "zero", "present"] = Field(alias="is")

    @model_validator(mode="after")
    def template_ok(self) -> Self:
        _check_template(self.fact)
        return self


Cond = ClusterCond | FactCond


class Rule(Record):
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    group: Group
    diagnosis: Diagnosis
    note: str = Field(min_length=1)
    system: bool
    interventions: list[InterventionKind] = Field(min_length=1)
    when: list[Cond] = Field(min_length=1)
    support: list[str] = Field(default_factory=list)
    contra: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.id == NONE_RULE:
            raise ValueError(f"rule id {NONE_RULE!r} is reserved")
        allowed = INTERVENTIONS_OF_DIAGNOSIS[self.diagnosis]
        wrong = [k for k in self.interventions if k not in allowed]
        if wrong:
            raise ValueError(f"rule {self.id}: interventions {wrong} are not allowed for "
                             f"{self.diagnosis} (allowed: {sorted(allowed)})")
        for template in [*self.support, *self.contra]:
            _check_template(template)
        return self


class Check(Record):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    separates: list[list[str]] = Field(min_length=1)
    needs: str = Field(min_length=1)
    cost_key: str = Field(min_length=1)
    cost_rank: int

    @model_validator(mode="after")
    def pairs(self) -> Self:
        for pair in self.separates:
            if len(pair) != 2 or pair[0] == pair[1]:
                raise ValueError(f"check {self.id}: {pair} is not a pair of two rule ids")
        return self


def _numbers(value: Any) -> list[Any]:
    """Numeric literals anywhere in `value` (bools are not numbers here)."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    return []


def _items(path: Path, key: str) -> list[Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RulesRefused(f"{path}: {str(error).strip().splitlines()[0][:200]}") from error
    if not isinstance(raw, dict) or not isinstance(raw.get(key), list):
        raise RulesRefused(f"{path}: a list under {key!r} is expected")
    items: list[Any] = raw[key]
    return items


def _first_line(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return f"{where}: {first['msg']}"[:300]


def load_rules(rules_dir: Path | None = None) -> list[Rule]:
    root = rules_dir or RULES_DIR
    paths = sorted(root.glob("*.yaml"))
    if not paths:
        raise RulesRefused(f"{root}: no rule file")
    rules: list[Rule] = []
    for path in paths:
        for k, raw in enumerate(_items(path, "rules"), start=1):
            numbers = _numbers(raw.get("when")) if isinstance(raw, dict) else []
            if numbers:
                raise RulesRefused(f"{path}: rule {k}: numeric literal {numbers[0]!r} in "
                                   "`when` (a threshold is a fact, not a rule constant)")
            try:
                rule = Rule.model_validate(raw)
            except ValidationError as error:
                raise RulesRefused(f"{path}: rule {k}: {_first_line(error)}") from error
            if any(r.id == rule.id for r in rules):
                raise RulesRefused(f"{path}: rule id {rule.id!r} is used twice")
            rules.append(rule)
    return rules


def load_checks(rules: Sequence[Rule], checks_path: Path | None = None) -> list[Check]:
    path = checks_path or CHECKS_FILE
    known = {r.id for r in rules} | {NONE_RULE}
    checks: list[Check] = []
    for k, raw in enumerate(_items(path, "checks"), start=1):
        try:
            check = Check.model_validate(raw)
        except ValidationError as error:
            raise RulesRefused(f"{path}: check {k}: {_first_line(error)}") from error
        unknown = sorted({rid for pair in check.separates for rid in pair} - known)
        if unknown:
            raise RulesRefused(f"{path}: check {check.id} names unknown rules {unknown}")
        if any(c.id == check.id for c in checks):
            raise RulesRefused(f"{path}: check id {check.id!r} is used twice")
        checks.append(check)
    return checks


@dataclass(frozen=True)
class _Facts:
    by_name: dict[str, list[FactRecord]]
    scores_ref: dict[str, str]  # run -> ref of its scores entry

    def get(self, name: str, run: str) -> FactRecord | None:
        found = self.by_name.get(name, [])
        preferred = [f for f in found if f.source_ref == self.scores_ref.get(run)]
        candidates = preferred or found
        return candidates[0] if candidates else None


def _holds(cond: Cond, cluster: ClusterRef, task: TaskView, facts: _Facts) -> bool:
    if isinstance(cond, ClusterCond):  # tools/latch.py `broken`, on the cluster's key
        spec = task.labels.get(cluster.label)
        implied = None if spec is None else spec.implies_step
        return (implied is not None and cluster.step in task.steps
                and task.index(cluster.step) <= task.index(implied))
    fact = facts.get(_name(cond.fact, cluster), cluster.run)
    if fact is None:
        return False
    value, want = fact.value, cond.is_
    if want == "present":
        return True
    if isinstance(want, bool):
        return isinstance(value, bool) and value is want
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value > 0 if want == "positive" else value == 0


def _name(template: str, cluster: ClusterRef) -> str:
    return template.format(run=cluster.run, step=cluster.step, label=cluster.label,
                           level=cluster.level)


def _ids(templates: Sequence[str], cluster: ClusterRef, facts: _Facts) -> list[str]:
    ids: list[str] = []
    for template in templates:
        fact = facts.get(_name(template, cluster), cluster.run)
        if fact is not None and fact.fact_id not in ids:
            ids.append(fact.fact_id)
    return ids


def _cluster_call(out: Path) -> ToolCallRecord | None:
    path = out / CALLS_FILE
    if not path.is_file():
        return None
    calls = [ToolCallRecord.model_validate_json(x)
             for x in path.read_text(encoding="utf-8").splitlines()]
    return next((c for c in calls if c.tool == CLUSTER_TOOL and c.status == "ran"), None)


def missing_clusters_reason(out: Path) -> str:
    """Why there is no cluster table to explain in `out`; "" when there is one."""
    call = _cluster_call(out)
    if call is None:
        return f"no {CLUSTER_TOOL} call ran, so no cluster was explained"
    # A call that ran and left no table found no failure: nothing to explain is not a fault.
    return ""


def _clusters(out: Path) -> list[ClusterRef]:
    call = _cluster_call(out)
    if call is None:
        return []
    table = out / TABLES_DIR / f"{call.call_id}-{CLUSTER_TOOL}.json"
    if not table.is_file():
        return []
    rows = json.loads(table.read_text(encoding="utf-8"))
    return [ClusterRef(
        cluster_id=f"{r['run']}/{r['first_failed_step']}/{r['label']}/l{r['level']}",
        run=r["run"], step=r["first_failed_step"], label=r["label"], level=int(r["level"]),
        size=int(r["size"])) for r in rows]


@dataclass(frozen=True)
class _Draft:
    rule_id: str
    group: Group
    diagnosis: Diagnosis
    note: str
    system: bool
    interventions: list[InterventionKind]
    support: list[str]
    contra: list[str]
    order: int


def _checks(rule_id: str, present: set[str], checks: Sequence[Check]) -> list[CheckRef]:
    """Catalog checks with a pair (this rule, another hypothesis of the cluster).

    `none` ("no cause") is always an alternative, whether or not it is a hypothesis.
    """
    others = (present - {rule_id}) | {NONE_RULE}
    refs: list[CheckRef] = []
    for check in checks:
        pairs = [list(p) for p in check.separates
                 if rule_id in p and (p[1] if p[0] == rule_id else p[0]) in others]
        if pairs:
            refs.append(CheckRef(check_id=check.id, separates=pairs, cost_key=check.cost_key,
                                 cost_rank=check.cost_rank))
    return sorted(refs, key=lambda c: (c.cost_rank, c.check_id))


def _keep_budget(kinds: Sequence[InterventionKind]) -> list[InterventionKind]:
    kept = [k for k in kinds if k not in BUDGET_INTERVENTIONS]
    return kept or ["report_only"]


def hypothesize(out: Path, task_id: str, rules_dir: Path | None = None,
                checks_path: Path | None = None) -> list[HypothesisRecord]:
    """Hypotheses of every failure cluster of the run directory `out`; writes them."""
    rules = load_rules(rules_dir)
    checks = load_checks(rules, checks_path)
    task = load_task(task_id)
    by_name: dict[str, list[FactRecord]] = {}
    facts_path = out / FACTS_FILE
    if facts_path.is_file():
        for line in facts_path.read_text(encoding="utf-8").splitlines():
            fact = FactRecord.model_validate_json(line)
            by_name.setdefault(fact.name, []).append(fact)
    scores_ref: dict[str, str] = {}
    if (out / PACK_FILE).is_file():
        for entry in read_pack(out / PACK_FILE).entries:
            if entry.kind == "scores" and entry.subject.get("run"):
                scores_ref.setdefault(entry.subject["run"], entry.ref)
    facts = _Facts(by_name, scores_ref)

    records: list[HypothesisRecord] = []
    for cluster in _clusters(out):
        drafts = [
            _Draft(rule.id, rule.group, rule.diagnosis, rule.note, rule.system,
                   list(rule.interventions), _ids(rule.support, cluster, facts),
                   _ids(rule.contra, cluster, facts), k)
            for k, rule in enumerate(rules)
            if all(_holds(c, cluster, task, facts) for c in rule.when)]
        if not drafts:
            drafts = [_Draft(NONE_RULE, "data", "unknown", "no_rule_matched", False,
                             ["report_only"], [], [], len(rules))]
        drafts.sort(key=lambda d: (GROUPS.index(d.group),
                                   -(len(d.support) - len(d.contra)), d.order))
        blocked = any(d.system for d in drafts)
        present = {d.rule_id for d in drafts}
        for rank, d in enumerate(drafts, start=1):
            records.append(HypothesisRecord(
                hypothesis_id=f"H{len(records) + 1}", cluster=cluster, rule_id=d.rule_id,
                group=d.group, diagnosis=d.diagnosis, note=d.note, support=d.support,
                contra=d.contra,
                interventions=_keep_budget(d.interventions) if blocked else d.interventions,
                code_rank=rank, blocked_data_spend=blocked,
                checks=_checks(d.rule_id, present, checks)))

    out.mkdir(parents=True, exist_ok=True)
    (out / HYPOTHESES_FILE).write_text(
        "".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    return records
