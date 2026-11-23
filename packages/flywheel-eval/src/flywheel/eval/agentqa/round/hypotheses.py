"""Step B3, hypothesize: rules over the facts give each failure cluster its hypotheses.

Deterministic code; no model is called (architecture 20/11/2026 section 6, B3). The rules
live in `configs/eval/agentqa/rules/*.yaml`, the checks that tell hypotheses apart in
`configs/eval/agentqa/checks.yaml`; adding a diagnosis is a config change. A hypothesis
never carries a number of its own: support and contra are ids of facts in `facts.jsonl`.

For each cluster of the `failure_clusters` table, every rule whose `when` holds gives one
hypothesis. A cluster no rule matches gets the `none` hypothesis: silence is never
"clean". While a system rule (`system: true`) stands for a cluster, none of its
hypotheses may spend the data budget (spec 6.4: system and scorer before data).

A rule may name diagnoses it `refutes`: its facts rule them out for the cluster (for
instance tracking that fails as often on successes as on failures rules out the
controller). The hypothesis carries the list, so the page and the case bench can say
"ruled out by" with the rule's support, instead of reading silence as a refutation.

Templates may use {run}, {step}, {label}, {level}, {cluster_slug} (the key as
`failure_clusters` and `coverage_distance` spell it in fact names) and {job} (the train job
of the run's checkpoint, the value of the `lineage_{run}_job` fact). A template whose key
cannot be resolved (no lineage fact) names no fact: its condition does not hold and its
support is left out.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, get_args

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
from flywheel.eval.agentqa.tools.clusters import NO_LEVEL, slug
from flywheel.eval.agentqa.tools.lineage import TOOL as LINEAGE_TOOL
from flywheel.eval.agentqa.tools.task import TaskView, load_task
from pydantic import Discriminator, Field, Tag, ValidationError, model_validator
from typing_extensions import Self

HYPOTHESES_FILE = "hypotheses.jsonl"
RULES_DIR = Path("configs") / "eval" / "agentqa" / "rules"  # from the repo root
CHECKS_FILE = Path("configs") / "eval" / "agentqa" / "checks.yaml"
GROUPS: tuple[str, ...] = get_args(Group)
NONE_RULE = "none"
NO_RULE_TITLE = "No rule of the agent explains this cluster"
CLUSTER_TOOL = "failure_clusters"
_TEMPLATE_KEYS = {"run": "r", "step": "s", "label": "l", "level": "0", "cluster_slug": "c",
                  "job": "j"}
# Sets of the task view a cluster condition may test, and what each set holds.
TASK_SETS: dict[str, Literal["label", "step"]] = {"runtime_labels": "label",
                                                  "motion_steps": "step"}


class RulesRefused(ValueError):
    """A rule or check file cannot be used; nothing was hypothesized."""


def _check_template(template: str) -> None:
    try:
        template.format(**_TEMPLATE_KEYS)
    except (KeyError, IndexError, ValueError) as error:
        raise ValueError(f"template {template!r}: only {{run}}, {{step}}, {{label}}, "
                         f"{{level}}, {{cluster_slug}}, {{job}} may be used ({error!r})"
                         ) from error


class ClusterCond(Record):
    """A test of the cluster's key: its step chain, or its label or step in a task set."""

    cluster: Literal["chain_broken", "label_in", "step_in"]
    set: str | None = None

    @model_validator(mode="after")
    def set_fits(self) -> Self:
        if self.cluster == "chain_broken":
            if self.set is not None:
                raise ValueError("chain_broken takes no set")
            return self
        want = "label" if self.cluster == "label_in" else "step"
        if self.set is None or TASK_SETS.get(self.set) != want:
            known = sorted(k for k, v in TASK_SETS.items() if v == want)
            raise ValueError(f"{self.cluster} needs a set of {want}s: one of {known}")
        return self


class FactCond(Record):
    fact: str = Field(min_length=1)
    is_: Literal[True, False, "positive", "zero", "present"] = Field(alias="is")

    @model_validator(mode="after")
    def template_ok(self) -> Self:
        _check_template(self.fact)
        return self


def _cond_kind(value: Any) -> str:
    """Which condition a raw item is, so a bad one is refused with its own error."""
    keys = value if isinstance(value, dict) else getattr(value, "__dict__", {})
    return "any" if "any" in keys else "cluster" if "cluster" in keys else "fact"


Simple = Annotated[Annotated[ClusterCond, Tag("cluster")] | Annotated[FactCond, Tag("fact")],
                   Discriminator(_cond_kind)]


class AnyCond(Record):
    """Holds when every condition of at least one of its groups holds."""

    any: list[list[Simple]] = Field(min_length=2)

    @model_validator(mode="after")
    def groups_not_empty(self) -> Self:
        if any(not group for group in self.any):
            raise ValueError("an `any` group is empty")
        return self


Cond = Annotated[Annotated[ClusterCond, Tag("cluster")] | Annotated[FactCond, Tag("fact")]
                 | Annotated[AnyCond, Tag("any")], Discriminator(_cond_kind)]


class Rule(Record):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    group: Group
    diagnosis: Diagnosis
    note: str = Field(min_length=1)
    system: bool
    interventions: list[InterventionKind] = Field(min_length=1)
    when: list[Cond] = Field(min_length=1)
    support: list[str] = Field(default_factory=list)
    contra: list[str] = Field(default_factory=list)
    refutes: list[Diagnosis] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.id == NONE_RULE:
            raise ValueError(f"rule id {NONE_RULE!r} is reserved")
        if any(ch.isdigit() for ch in self.title):
            raise ValueError(f"rule {self.id}: the title holds a digit (a number is a fact)")
        allowed = INTERVENTIONS_OF_DIAGNOSIS[self.diagnosis]
        wrong = [k for k in self.interventions if k not in allowed]
        if wrong:
            raise ValueError(f"rule {self.id}: interventions {wrong} are not allowed for "
                             f"{self.diagnosis} (allowed: {sorted(allowed)})")
        for template in [*self.support, *self.contra]:
            _check_template(template)
        if self.diagnosis in self.refutes:
            raise ValueError(f"rule {self.id}: it refutes its own diagnosis {self.diagnosis}")
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


def rule_title(rule_id: str, titles: dict[str, str]) -> str:
    """The title a hypothesis of `rule_id` is shown with (`titles`: rule id -> title)."""
    return NO_RULE_TITLE if rule_id == NONE_RULE else titles.get(rule_id, rule_id)


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
    if isinstance(cond, AnyCond):
        return any(all(_holds(c, cluster, task, facts) for c in group) for group in cond.any)
    if isinstance(cond, ClusterCond):
        if cond.cluster == "label_in":
            return cluster.label in task.runtime_labels
        if cond.cluster == "step_in":
            return cluster.step in task.motion_steps
        # tools/latch.py `broken`, on the cluster's key
        spec = task.labels.get(cluster.label)
        implied = None if spec is None else spec.implies_step
        return (implied is not None and cluster.step in task.steps
                and task.index(cluster.step) <= task.index(implied))
    name = _name(cond.fact, cluster, facts)
    fact = None if name is None else facts.get(name, cluster.run)
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


def _level(cluster: ClusterRef) -> int | None:
    """The cluster table spells a missing level -1 (an int column); facts spell it None."""
    return None if cluster.level == NO_LEVEL else cluster.level


def _job(cluster: ClusterRef, facts: _Facts | None) -> str | None:
    """The train job behind the run's checkpoint, from the `lineage` fact; None if unknown."""
    fact = None if facts is None else facts.get(f"{LINEAGE_TOOL}_{cluster.run}_job",
                                                cluster.run)
    return fact.value if fact is not None and isinstance(fact.value, str) else None


def _name(template: str, cluster: ClusterRef, facts: _Facts | None = None) -> str | None:
    """The fact name `template` gives for `cluster`; None when it needs a key not resolved."""
    keys: dict[str, object] = {
        "run": cluster.run, "step": cluster.step, "label": cluster.label,
        "level": _level(cluster),
        "cluster_slug": slug((cluster.step, cluster.label, _level(cluster)))}
    job = _job(cluster, facts) if "{job}" in template else None
    if job is not None:
        keys["job"] = job
    try:
        return template.format(**keys)
    except KeyError:
        return None


def _ids(templates: Sequence[str], cluster: ClusterRef, facts: _Facts) -> list[str]:
    ids: list[str] = []
    for template in templates:
        name = _name(template, cluster, facts)
        fact = None if name is None else facts.get(name, cluster.run)
        if fact is not None and fact.fact_id not in ids:
            ids.append(fact.fact_id)
    return ids


def _cluster_calls(out: Path) -> list[ToolCallRecord]:
    path = out / CALLS_FILE
    if not path.is_file():
        return []
    calls = [ToolCallRecord.model_validate_json(x)
             for x in path.read_text(encoding="utf-8").splitlines()]
    return [c for c in calls if c.tool == CLUSTER_TOOL and c.status == "ran"]


def missing_clusters_reason(out: Path) -> str:
    """Why there is no cluster table to explain in `out`; "" when there is one."""
    if not _cluster_calls(out):
        return f"no {CLUSTER_TOOL} call ran, so no cluster was explained"
    # A call that ran and left no table found no failure: nothing to explain is not a fault.
    return ""


def _clusters(out: Path) -> list[ClusterRef]:
    """The union of every failure_clusters table, each (run, step, label, level) once."""
    found: dict[tuple[str, str, str, int], ClusterRef] = {}
    for call in _cluster_calls(out):
        table = out / TABLES_DIR / f"{call.call_id}-{CLUSTER_TOOL}.json"
        if not table.is_file():
            continue
        for r in json.loads(table.read_text(encoding="utf-8")):
            level = int(r["level"])
            key = (r["run"], r["first_failed_step"], r["label"], level)
            if key in found:
                continue
            spelled = None if level == NO_LEVEL else level
            found[key] = ClusterRef(
                cluster_id=f"{r['run']}/{r['first_failed_step']}/{r['label']}/l{spelled}",
                run=r["run"], step=r["first_failed_step"], label=r["label"], level=level,
                size=int(r["size"]))
    return list(found.values())


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
    refutes: list[Diagnosis]


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
                   _ids(rule.contra, cluster, facts), k, list(rule.refutes))
            for k, rule in enumerate(rules)
            if all(_holds(c, cluster, task, facts) for c in rule.when)]
        if not drafts:
            drafts = [_Draft(NONE_RULE, "data", "unknown", "no_rule_matched", False,
                             ["report_only"], [], [], len(rules), [])]
        drafts.sort(key=lambda d: (GROUPS.index(d.group),
                                   -(len(d.support) - len(d.contra)), d.order))
        blocked = any(d.system for d in drafts)
        present = {d.rule_id for d in drafts}
        for rank, d in enumerate(drafts, start=1):
            records.append(HypothesisRecord(
                hypothesis_id=f"H{len(records) + 1}", cluster=cluster, rule_id=d.rule_id,
                group=d.group, diagnosis=d.diagnosis, note=d.note, support=d.support,
                contra=d.contra, refutes=d.refutes,
                interventions=_keep_budget(d.interventions) if blocked else d.interventions,
                code_rank=rank, blocked_data_spend=blocked,
                checks=_checks(d.rule_id, present, checks)))

    out.mkdir(parents=True, exist_ok=True)
    (out / HYPOTHESES_FILE).write_text(
        "".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    return records
