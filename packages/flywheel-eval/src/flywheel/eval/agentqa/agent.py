"""The agent's half: rank, explain and suggest, on the facts code computed (DA-20 AC 3, 5).

One call sends the facts and the candidates of a subject as JSON and asks for one
JSON object back (`configs/eval/agentqa/prompts/system.md`). The reply is checked
before anything is kept:

    - it parses, every cid, code, target and fact id it names exists;
    - every number in an insight or a suggestion is a fact (`numbers.py`);
    - the AgentReport it builds validates against the contract.

A reply that fails is sent back once with what was wrong; failing again gives a
report with `status = broken`, the reasons in `problems` and no findings, so a
model that cannot follow the rules never scores what code found as its own.

A candidate a lane detector raised (`origin = code`) that the model drops needs a
`reason`, held to the same number rule; the drop comes back beside the report
(`AgentRun.dropped`) so the run can show it to the reviewer. An `ok` report may
not carry `problems` (contract), and a drop is a verdict, not a failure; but a
detector's finding must never vanish without a word (#175: 36 T6 candidates
dropped on a misread threshold left an `ok` report with nothing in it).

Subjects with more candidates than `candidates_per_call` are split into calls;
findings of all calls are ranked together by the priority the model gave, then
by the order it wrote them in.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from flywheel.contracts.agentqa import (
    FINDING_CODE,
    AgentEstimate,
    AgentFact,
    AgentFinding,
    AgentModel,
    AgentReport,
)
from flywheel.contracts.base import new_ulid
from flywheel.eval.agentqa.endpoint import DEFAULT_AGENT_CONFIG, ChatModel, EndpointError
from flywheel.eval.agentqa.facts import Analysis, Candidate, DroppedCandidate
from flywheel.eval.agentqa.numbers import unsupported_numbers
from pydantic import ValidationError

_CODE = re.compile(FINDING_CODE)
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")


@dataclass(frozen=True)
class AgentConfig:
    prompt: str
    prompt_sha256: str
    context_tokens: int = 64000
    reply_tokens: int = 4096
    chars_per_token: float = 3.5
    candidates_per_call: int = 20
    retries: int = 1
    raw: dict[str, Any] = field(default_factory=dict)


def load_agent_config(path: Path = DEFAULT_AGENT_CONFIG) -> AgentConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    prompt_path = path.parent / str(raw["prompt"])
    prompt = prompt_path.read_text(encoding="utf-8")
    limits = raw.get("limits", {})
    return AgentConfig(
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        context_tokens=int(limits.get("context_tokens", 64000)),
        reply_tokens=int(limits.get("reply_tokens", 4096)),
        chars_per_token=float(limits.get("chars_per_token", 3.5)),
        candidates_per_call=int(limits.get("candidates_per_call", 20)),
        retries=int(limits.get("retries", 1)),
        raw=raw,
    )


class ReplyError(ValueError):
    """A reply the agent cannot keep; the message goes back to the model."""


@dataclass(frozen=True)
class AgentRun:
    """The report of one subject and the code candidates the model dropped in it."""

    report: AgentReport
    dropped: tuple[DroppedCandidate, ...] = ()


@dataclass
class _Drafted:
    code: str
    target: str
    priority: int
    order: int
    evidence: list[str]
    insight: str
    suggestion: str
    figures: list[str]


def _fact_json(fact: AgentFact) -> dict[str, Any]:
    return {"id": fact.fact_id, "name": fact.name, "value": fact.value, "unit": fact.unit}


def _candidate_json(c: Candidate) -> dict[str, Any]:
    return {
        "cid": c.cid,
        "code": c.code,
        "target": c.target,
        "evidence": list(c.evidence),
        "origin": c.origin,
        "detail": c.detail,
    }


def _relevant_facts(analysis: Analysis, batch: Sequence[Candidate], cap: int) -> list[AgentFact]:
    """Facts of the batch's candidates first, then subject-wide facts, up to `cap`."""
    cited = {f for c in batch for f in c.evidence}
    first = [f for f in analysis.book.facts if f.fact_id in cited]
    rest = [f for f in analysis.book.facts if f.fact_id not in cited and "@" not in f.name]
    return (first + rest)[: max(cap, len(first))]


def build_messages(
    analysis: Analysis, batch: Sequence[Candidate], config: AgentConfig
) -> tuple[list[dict[str, Any]], list[AgentFact]]:
    budget_chars = int(
        (config.context_tokens - config.reply_tokens) * config.chars_per_token
    ) - len(config.prompt)
    cap = len(analysis.book.facts)
    while True:
        facts = _relevant_facts(analysis, batch, cap)
        payload = {
            "subject": analysis.subject_ref,
            "stage": analysis.stage,
            "units": list(analysis.units)[:400],
            "allowed_codes": _allowed_codes(analysis.stage),
            "cleared_by_code": list(analysis.cleared),
            "facts": [_fact_json(f) for f in facts],
            "candidates": [_candidate_json(c) for c in batch],
            "not_judged_by_code": analysis.notes[:50],
        }
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) <= budget_chars or cap <= len(batch):
            break
        cap = max(len(batch), cap // 2)  # summarise: keep cited facts, fewer others
    messages = [
        {"role": "system", "content": config.prompt},
        {"role": "user", "content": text},
    ]
    return messages, facts


def _allowed_codes(stage: str) -> list[str]:
    prefix = {"dataset": "D", "train": "T", "stage1": "", "stage3": "O", "inference": "R",
              "eval": "R"}.get(stage, "")
    counts = {"D": 8, "T": 8, "O": 4, "R": 6}
    return [f"{prefix}{i}" for i in range(1, counts[prefix] + 1)] if prefix else []


def _parse_reply(
    text: str,
    analysis: Analysis,
    batch: Sequence[Candidate],
    facts: Sequence[AgentFact],
    order_base: int,
) -> tuple[list[_Drafted], list[dict[str, Any]], list[DroppedCandidate]]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ReplyError("the reply holds no JSON object")
    try:
        reply = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ReplyError(f"the reply is not valid JSON: {exc}") from exc
    if not isinstance(reply, dict):
        raise ReplyError("the reply is not a JSON object")
    known = {f.fact_id for f in facts}
    by_id = {f.fact_id: f for f in facts}
    by_cid = {c.cid: c for c in batch}
    units = set(analysis.units)
    allowed = set(_allowed_codes(analysis.stage))
    problems: list[str] = []
    drafted: list[_Drafted] = []
    dropped: list[DroppedCandidate] = []
    order = order_base

    def scope(item: dict[str, Any], extra: Sequence[str] = ()) -> list[AgentFact]:
        """The facts one item may lean on: what it lists, what it cites, its candidate's."""
        listed = item.get("evidence")
        ids = [str(x) for x in listed] if isinstance(listed, list) else []
        for key in ("insight", "suggestion"):
            if isinstance(item.get(key), str):
                ids += _PLACEHOLDER.findall(item[key])
        ids += list(extra)
        return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]

    def text_field(item: dict[str, Any], key: str, where: str, cited: list[AgentFact]) -> str:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{where}: {key} missing")
            return ""
        bad = unsupported_numbers(value, cited)
        if bad:
            problems.append(
                f"{where}: {key} states numbers no cited fact holds: {', '.join(bad)}"
            )
        unknown = set(_PLACEHOLDER.findall(value)) - known
        if unknown:
            problems.append(f"{where}: {key} cites unknown facts {sorted(unknown)}")
        return value.strip()

    def evidence_of(item: dict[str, Any], insight: str, suggestion: str, where: str) -> list[str]:
        listed = item.get("evidence") or []
        if not isinstance(listed, list):
            listed = []
        cited = _PLACEHOLDER.findall(insight) + _PLACEHOLDER.findall(suggestion)
        evidence = list(dict.fromkeys([str(x) for x in listed] + cited))
        unknown = [e for e in evidence if e not in known]
        if unknown:
            problems.append(f"{where}: evidence cites unknown facts {unknown}")
        if not evidence:
            problems.append(f"{where}: no evidence")
        return [e for e in evidence if e in known]

    decided: set[str] = set()
    for item in reply.get("decisions") or []:
        if not isinstance(item, dict) or item.get("cid") not in by_cid:
            problems.append(f"decision for unknown candidate {item!r:.80}")
            continue
        if item["cid"] in decided:
            problems.append(f"{item['cid']}: decided twice")
            continue
        decided.add(item["cid"])
        keep = item.get("keep", True)
        if not isinstance(keep, bool):
            problems.append(f"{item['cid']}: keep must be true or false, not {keep!r:.20}")
            continue
        candidate = by_cid[item["cid"]]
        where = str(item["cid"])
        if not keep:
            if candidate.origin == "code":
                cited = scope(item, candidate.evidence)
                reason = text_field(item, "reason", where, cited)
                dropped.append(DroppedCandidate(candidate.cid, candidate.code, candidate.target,
                                                candidate.detail, reason, candidate.evidence))
            continue
        cited = scope(item, candidate.evidence)
        insight = text_field(item, "insight", where, cited)
        suggestion = text_field(item, "suggestion", where, cited)
        evidence = evidence_of(item, insight, suggestion, where)
        evidence = list(dict.fromkeys(list(candidate.evidence) + evidence))
        drafted.append(
            _Drafted(candidate.code, candidate.target, _priority(item), order, evidence,
                     insight, suggestion, [])
        )
        order += 1
    # A candidate the model left out would vanish without a word; code proposed it.
    missing = [c.cid for c in batch if c.cid not in decided]
    if missing:
        problems.append(f"no decision for candidates {missing}")
    for n, item in enumerate(reply.get("added") or []):
        where = f"added[{n}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: not an object")
            continue
        code, target = str(item.get("code", "")), str(item.get("target", ""))
        if not _CODE.fullmatch(code) or code not in allowed:
            problems.append(f"{where}: code {code!r} not allowed for {analysis.stage}")
            continue
        if units and target not in units:
            problems.append(f"{where}: target {target!r} is not a unit of {analysis.subject_ref}")
            continue
        if code in analysis.cleared:
            problems.append(
                f"{where}: a detector judged {code} on {analysis.subject_ref} with these facts "
                "and found no fault (cleared_by_code); do not add it"
            )
            continue
        cited = scope(item)
        insight = text_field(item, "insight", where, cited)
        suggestion = text_field(item, "suggestion", where, cited)
        evidence = evidence_of(item, insight, suggestion, where)
        drafted.append(
            _Drafted(code, target, _priority(item), order, evidence, insight, suggestion, [])
        )
        order += 1
    estimates = []
    for n, item in enumerate(reply.get("estimates") or []):
        if not isinstance(item, dict):
            continue
        basis = [str(b) for b in item.get("basis") or [] if str(b) in known]
        if not basis:
            problems.append(f"estimates[{n}]: no basis among the facts")
            continue
        try:
            estimates.append({
                "quantity": str(item["quantity"]),
                "low": float(item["low"]),
                "high": float(item["high"]),
                "unit": str(item.get("unit") or "-"),
                "basis": basis,
            })
        except (KeyError, TypeError, ValueError):
            problems.append(f"estimates[{n}]: needs quantity, low, high")
    if problems:
        raise ReplyError("; ".join(problems))
    return drafted, estimates, dropped


def _priority(item: dict[str, Any]) -> int:
    try:
        return min(5, max(1, int(item.get("priority", 3))))
    except (TypeError, ValueError):
        return 3


def _batches(candidates: Sequence[Candidate], size: int) -> list[list[Candidate]]:
    if not candidates:
        return [[]]
    return [list(candidates[i : i + size]) for i in range(0, len(candidates), size)]


def run_agent(
    analysis: Analysis,
    model: ChatModel,
    config: AgentConfig,
    *,
    now: datetime | None = None,
    report_id: str | None = None,
) -> AgentReport:
    """The AgentReport of one subject: ok with ranked findings, or broken with why."""
    return review_subject(analysis, model, config, now=now, report_id=report_id).report


def review_subject(
    analysis: Analysis,
    model: ChatModel,
    config: AgentConfig,
    *,
    now: datetime | None = None,
    report_id: str | None = None,
) -> AgentRun:
    """`run_agent` with the code candidates the model dropped, for the run to show."""
    drafted: list[_Drafted] = []
    estimates: list[dict[str, Any]] = []
    dropped: list[DroppedCandidate] = []
    problems: list[str] = []
    for batch in _batches(analysis.candidates, config.candidates_per_call):
        if not batch and not analysis.book.facts:
            continue
        messages, facts = build_messages(analysis, batch, config)
        for attempt in range(config.retries + 1):
            try:
                reply = model.complete(messages)
                got, est, drop = _parse_reply(reply, analysis, batch, facts, len(drafted))
            except ReplyError as exc:
                if attempt == config.retries:
                    problems.append(f"model reply rejected: {exc}")
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"Your reply broke the rules: {exc}. "
                     "Answer again with one JSON object that follows every rule."},
                ]
                continue
            except EndpointError as exc:
                problems.append(f"endpoint failed: {exc}")
                break
            drafted += got
            estimates += est
            dropped += drop
            break
    report = _assemble(analysis, model, config, drafted, estimates, problems, now, report_id)
    # A broken report keeps no verdict of the model, drops included.
    return AgentRun(report, tuple(dropped) if report.status == "ok" else ())


def _assemble(
    analysis: Analysis,
    model: ChatModel,
    config: AgentConfig,
    drafted: list[_Drafted],
    estimates: list[dict[str, Any]],
    problems: list[str],
    now: datetime | None,
    report_id: str | None,
) -> AgentReport:
    if problems:
        drafted, estimates = [], []
    # One finding per (code, target): the model may keep a candidate and add it again.
    unique: dict[tuple[str, str], _Drafted] = {}
    for d in sorted(drafted, key=lambda d: (d.priority, d.order)):
        unique.setdefault((d.code, d.target), d)
    findings = [
        AgentFinding(
            finding_id=f"find_{rank:03d}",
            code=d.code,
            rank=rank,
            target_ref=d.target,
            evidence=d.evidence,
            figures=d.figures or analysis.figures[:3],
            insight=d.insight,
            suggestion=d.suggestion,
        )
        for rank, d in enumerate(unique.values(), start=1)
    ]
    agent_estimates = [
        AgentEstimate(
            estimate_id=f"est_{n:03d}",
            quantity=e["quantity"],
            low=min(e["low"], e["high"]),
            high=max(e["low"], e["high"]),
            unit=e["unit"],
            basis=e["basis"],
        )
        for n, e in enumerate(estimates, start=1)
    ]
    try:
        return AgentReport(
            report_id=report_id or f"rep_{new_ulid()}",
            subject_ref=analysis.subject_ref,
            stage=analysis.stage,
            created_at=now or datetime.now(timezone.utc),
            model=AgentModel(
                name=model.name,
                revision=model.revision,
                temperature=model.temperature,
                prompt_sha256=config.prompt_sha256,
            ),
            inputs=analysis.inputs,
            facts=analysis.book.facts,
            findings=findings,
            estimates=agent_estimates,
            status="broken" if problems else "ok",
            problems=problems,
        )
    except ValidationError as exc:
        if problems:
            raise
        return _assemble(analysis, model, config, [], [], [f"report invalid: {exc}"], now,
                         report_id)
