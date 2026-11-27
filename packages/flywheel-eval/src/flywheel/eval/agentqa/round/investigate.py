"""Step investigate (DA-52 task 2.4): a loop where the model calls tools, proposes, concludes.

Run only with `fw agentqa round --investigate`, between hypothesize and adjudicate, through
the model gateway (role `investigate`, route optional in `routing.yaml`). Every request is
stateless: ONE user message holding a JSON object (clusters, the rule hypotheses, the
model's own open and dropped ones, the facts with a code-written `meaning` line, the
tools of the pack with their closed parameter domains, one line per earlier step, the
closed lists of diagnoses and interventions, what is left of the budget). Strings from
artifacts enter only as JSON values, cut to `FACT_TEXT_CHARS`. The reply is one action:

    call_tool   run one tool through `ToolSession.call` (its `check_params` first)
    propose     open a hypothesis of the model for one cluster, citing facts
    drop        close one of the model's own open hypotheses, citing refuting facts
    conclude    keep some open hypotheses, each with the data to collect and a first check

A reply that does not parse gets one resend (attempt 2, `previous_errors`); a second bad
reply, or an action the code refuses (unknown tool, a value outside its domain, an unknown
fact id, a bare number, a rule hypothesis dropped...), is a rejected step: logged with its
reason and told to the model in the next step's history. The caps of `roles.yaml`
(`investigate:`) are checked before every request, from the costs `model_calls.jsonl`
records for this step's calls (a replayed request costs what its line says, so a resumed
run sends the same requests and replays them). The loop also stops on the gateway's own
`budget_exhausted` or `failed`.

Never below the code floor: the step writes only its own four files and never touches
`hypotheses.jsonl`, `facts.jsonl` or another step's file. Only a loop that ended
`concluded` hands hypotheses on (`investigated.jsonl`); any other ending writes the log and
an empty result file, and the step is degraded with the ending as its problem. Whether a
kept hypothesis stands is `verify`'s rule (next task); this step only records what it needs.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, cast, get_args

import yaml
from flywheel.contracts.agentqa import bare_numbers
from flywheel.contracts.evidence import (
    BUDGET_INTERVENTIONS,
    INTERVENTIONS_OF_DIAGNOSIS,
    Diagnosis,
    InterventionKind,
)
from flywheel.eval.agentqa.facts import FactBook, FactClash
from flywheel.eval.agentqa.mcp.bridge import ToolSession, UnknownTool
from flywheel.eval.agentqa.round.admit import Admitted
from flywheel.eval.agentqa.round.gateway import MODEL_CALLS_FILE, Gateway, GatewayReply
from flywheel.eval.agentqa.round.hypotheses import (
    HYPOTHESES_FILE,
    _clusters,
    load_rules,
    rule_title,
)
from flywheel.eval.agentqa.round.judge import (
    FACT_TEXT_CHARS,
    ROLES_FILE,
    RolesRefused,
    is_comparison_fact,
    load_prompt,
    load_roles,
)
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE, _context, _inputs
from flywheel.eval.agentqa.round.records import (
    CitedText,
    ClusterRef,
    Ending,
    FactRecord,
    HypothesisRecord,
    InvestigatedFact,
    InvestigatedHypothesis,
    InvestigationEnd,
    InvestigationStep,
    ModelCallRecord,
    ModelRequest,
    Pack,
    Record,
    ToolCallRecord,
)
from flywheel.eval.agentqa.round.reply_rules import strip_trailing_commas, unwrap
from flywheel.eval.agentqa.tools.meanings import meaning_of
from flywheel.eval.agentqa.tools.registry import REGISTRY
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

ROLE = "investigate"
INVESTIGATION_FILE = "investigation.jsonl"
INVESTIGATION_FACTS_FILE = "investigation_facts.jsonl"
INVESTIGATION_CALLS_FILE = "investigation_calls.jsonl"
INVESTIGATED_FILE = "investigated.jsonl"
FILES = (INVESTIGATION_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE,
         INVESTIGATED_FILE)
PROMPT = Path("configs") / "eval" / "agentqa" / "prompts" / "investigate.md"
RAW_CHARS = 2000  # an unparseable reply, as the log keeps it
TEXT_CHARS = 1000  # a statement or a conclude text of the model
ANSWERED = ("ok", "cut")
CALL_PREFIX = "I"  # investigation tool calls; the plan's are T1.. in tool_calls.jsonl
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")


# --- limits ----------------------------------------------------------------------------------


class InvestigateLimits(BaseModel):
    """The `investigate:` block of `roles.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int = Field(ge=1)
    max_calls: int = Field(ge=0)
    max_input_tokens: int = Field(ge=0)
    max_usd: float = Field(ge=0)
    max_reply_tokens: int = Field(ge=1)
    max_rejected_in_a_row: int = Field(ge=1)
    max_facts: int = Field(ge=0)


def load_limits(path: Path | None = None) -> InvestigateLimits:
    """The investigate block of `roles.yaml`; `RolesRefused` when it is missing or wrong."""
    target = path or ROLES_FILE
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        block = raw.get(ROLE) if isinstance(raw, dict) else None
        if block is None:
            raise RolesRefused(f"{target}: no `{ROLE}:` block")
        return InvestigateLimits.model_validate(block)
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise RolesRefused(f"{target}: {str(error).strip().splitlines()[0][:200]}") from error


# --- the reply -------------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CallTool(_Strict):
    thought: str = ""
    action: Literal["call_tool"]
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class Propose(_Strict):
    thought: str = ""
    action: Literal["propose"]
    cluster_id: str
    statement: str
    diagnosis: str
    intervention: str
    support: list[str] = Field(default_factory=list)
    contra: list[str] = Field(default_factory=list)


class Drop(_Strict):
    thought: str = ""
    action: Literal["drop"]
    hypothesis: str
    refuted_by: list[str]


class Cited(_Strict):
    text: str
    cites: list[str]


class Keep(_Strict):
    hypothesis: str
    data_content: Cited
    first_check: Cited


class Conclude(_Strict):
    thought: str = ""
    action: Literal["conclude"]
    keep: list[Keep]


Action = Annotated[CallTool | Propose | Drop | Conclude, Field(discriminator="action")]
_ACTION: TypeAdapter[CallTool | Propose | Drop | Conclude] = TypeAdapter(Action)
REPLY_SCHEMA: dict[str, Any] = _ACTION.json_schema()


def parse_reply(text: str) -> CallTool | Propose | Drop | Conclude:
    """Raises `ValueError` (pydantic's `ValidationError` included) on any wrong shape."""
    body = unwrap(text)
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        raw = json.loads(strip_trailing_commas(body))  # the one repair; may raise again
    if not isinstance(raw, dict):
        raise ValueError("the reply is not a JSON object")
    return _ACTION.validate_python(raw)


def reply_errors(text: str, *, cut: bool = False) -> list[str]:
    """Why a reply cannot be read; empty when it parses."""
    if cut:
        return ["the reply was cut at max_tokens"]
    try:
        parse_reply(text)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "(root)"
        return [f"{where}: {first['msg']}"[:300]]
    except ValueError as error:
        return [f"not a JSON object: {str(error).splitlines()[0][:200]}"]
    return []


# --- state -----------------------------------------------------------------------------------


@dataclass
class _Hypothesis:
    hypothesis_id: str
    cluster: ClusterRef
    statement: str
    diagnosis: Diagnosis
    intervention: InterventionKind
    support: list[str]
    contra: list[str]
    step: int
    refuted_by: list[str] = field(default_factory=list)
    open: bool = True


@dataclass
class _Spent:
    requests: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0


@dataclass
class InvestigateResult:
    ending: Ending
    kept: list[InvestigatedHypothesis] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


class _Stop(Exception):
    """A cap or the gateway ended the loop before or during a step."""

    def __init__(self, ending: Ending, detail: str) -> None:
        super().__init__(detail)
        self.ending, self.detail = ending, detail


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def _jsonl(lines: Sequence[Record]) -> str:
    return "".join(r.model_dump_json() + "\n" for r in lines)


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _cut(value: float | int | str | bool) -> float | int | str | bool:
    return value[:FACT_TEXT_CHARS] if isinstance(value, str) else value


def seeded_book(facts: Sequence[FactRecord]) -> FactBook:
    """A fact book holding `facts` under their own ids, so new facts continue the numbering.

    `facts.jsonl` lists the book of step B2 in order (F1, F2, ...); replaying it into a
    fresh book gives every name the id it had, and a tool called again returns those ids.
    """
    book = FactBook()
    for fact in facts:
        got = book.add(fact.name, fact.value, fact.source_ref, fact.unit)
        if got != fact.fact_id:
            raise ValueError(f"{FACTS_FILE}: {fact.fact_id} ({fact.name}) would get id {got}; "
                             "the file is not one fact book in order")
    return book


def _hypothesis_number(hypothesis_id: str) -> int:
    return int(hypothesis_id[1:]) if hypothesis_id[1:].isdigit() else 0


# --- the loop --------------------------------------------------------------------------------


class _Investigation:
    def __init__(self, out: Path, gateway: Gateway, pack: Pack, admitted: Admitted,
                 limits: InvestigateLimits, system: str, markers: tuple[str, ...]) -> None:
        self.out, self.gateway, self.limits, self.system = out, gateway, limits, system
        self.markers = markers
        self.profile, _ = gateway.routed(ROLE)  # GatewayRefused before any call
        self.ctx, self.entries = _context(pack, admitted)
        self.seeded = [FactRecord.model_validate_json(x) for x in _lines(out / FACTS_FILE)]
        self.session = ToolSession(self.ctx, seeded_book(self.seeded))
        plan_calls = [ToolCallRecord.model_validate_json(x) for x in _lines(out / CALLS_FILE)]
        tool_of_call = {c.call_id: c.tool for c in plan_calls}
        self.tool_of: dict[str, str] = {f.fact_id: tool_of_call.get(f.tool_call_id, "")
                                        for f in self.seeded}
        self.provenance: dict[str, Literal["code", "vision", "history"]] = {
            f.fact_id: f.provenance for f in self.seeded}
        self.rules = [HypothesisRecord.model_validate_json(x)
                      for x in _lines(out / HYPOTHESES_FILE)]
        self.titles = {r.id: r.title for r in load_rules()}
        self.clusters = {c.cluster_id: c for c in _clusters(out)}
        self.blocked = {h.cluster.cluster_id for h in self.rules if h.blocked_data_spend}
        self.next_id = 1 + max((_hypothesis_number(h.hypothesis_id) for h in self.rules),
                               default=0)
        self.mine: dict[str, _Hypothesis] = {}
        self.found: list[str] = []  # fact ids the investigation's calls returned, in order
        self.new_facts: list[FactRecord] = []
        self.calls: list[ToolCallRecord] = []
        self.offered: set[str] = set()  # every fact id any request showed the model
        self.log: list[InvestigationStep] = []
        self.history: list[dict[str, Any]] = []
        self.spent = _Spent()
        self.concluded: Conclude | None = None
        # Tools whose artifact kind the pack lacks are left out of the requests.
        self.tools: list[dict[str, Any]] = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self.session.tools() if not t.missing]

    # -- the request --------------------------------------------------------------------

    def _fact_ids(self) -> list[str]:
        """Facts of the next request: the investigation's and the open hypotheses' cited
        ones always, then the rule hypotheses' cited ones and those of the clusters."""
        book = self.session.book
        known = {f.fact_id for f in book.facts}
        never_cut = list(dict.fromkeys(
            [*self.found, *(fid for h in self.mine.values() if h.open
                            for fid in (*h.support, *h.contra))]))
        cited = [fid for h in self.rules for fid in (*h.support, *h.contra) if fid in known]
        related = [f.fact_id for f in self.seeded
                   if any(c.run in f.name and (c.step in f.name or c.label in f.name
                                               or f.name.endswith("_not_judged"))
                          for c in self.clusters.values())]
        room = max(self.limits.max_facts - len(never_cut), 0)
        rest = [fid for fid in dict.fromkeys([*cited, *related]) if fid not in never_cut]
        return [*rest[:room], *never_cut]

    def _facts(self) -> list[dict[str, Any]]:
        book = self.session.book
        out = []
        for fid in self._fact_ids():
            fact = book.get(fid)
            out.append({"id": fid, "name": fact.name[:FACT_TEXT_CHARS],
                        "value": _cut(fact.value), "unit": fact.unit,
                        "provenance": self.provenance.get(fid, "code"),
                        "meaning": meaning_of(fact.name, self.tool_of.get(fid, ""))})
        return out

    def _budget(self, step: int) -> dict[str, Any]:
        lim, used = self.limits, self.spent
        return {"steps_left": lim.max_steps - step + 1,
                "calls_left": lim.max_calls - used.requests,
                "input_tokens_left": lim.max_input_tokens - used.tokens_in,
                "usd_left": round(lim.max_usd - used.usd, 6)}

    def _payload(self, step: int) -> dict[str, Any]:
        facts = self._facts()
        self.offered.update(f["id"] for f in facts)
        hypotheses = sorted(self.mine.values(), key=lambda h: _hypothesis_number(h.hypothesis_id))
        return {
            "clusters": [{"id": c.cluster_id, "run": c.run, "step": c.step, "label": c.label,
                          "level": c.level, "size": c.size,
                          "blocked_data_spend": c.cluster_id in self.blocked}
                         for c in sorted(self.clusters.values(),
                                         key=lambda c: (-c.size, c.cluster_id))],
            "rule_hypotheses": [{
                "id": h.hypothesis_id, "cluster": h.cluster.cluster_id,
                "title": rule_title(h.rule_id, self.titles), "diagnosis": h.diagnosis,
                "note": h.note, "support": h.support, "contra": h.contra} for h in self.rules],
            "model_hypotheses": [self._shown(h) for h in hypotheses if h.open],
            "dropped": [{**self._shown(h), "refuted_by": h.refuted_by}
                        for h in hypotheses if not h.open],
            "facts": facts,
            "tools": self.tools,
            "history": self.history,
            "allowed": {
                "diagnoses": list(get_args(Diagnosis)),
                "interventions": list(get_args(InterventionKind)),
                "interventions_of_diagnosis": {d: sorted(INTERVENTIONS_OF_DIAGNOSIS.get(d, ()))
                                               for d in get_args(Diagnosis)},
                "data_spend": sorted(BUDGET_INTERVENTIONS)},
            "budget": self._budget(step),
        }

    @staticmethod
    def _shown(h: _Hypothesis) -> dict[str, Any]:
        return {"id": h.hypothesis_id, "cluster": h.cluster.cluster_id,
                "statement": h.statement, "diagnosis": h.diagnosis,
                "intervention": h.intervention, "support": h.support, "contra": h.contra}

    # -- one request through the gateway ------------------------------------------------

    def _check_caps(self, user: str) -> None:
        lim, used = self.limits, self.spent
        est_in = math.ceil((len(self.system) + len(user)) / self.gateway.budget.chars_per_token)
        reply_cap = min(lim.max_reply_tokens, self.profile.max_tokens)
        est_usd = (est_in * self.profile.usd_per_mtok_in
                   + reply_cap * self.profile.usd_per_mtok_out) / 1e6
        if used.requests + 1 > lim.max_calls:
            raise _Stop("max_calls", f"max_calls {lim.max_calls}")
        if used.tokens_in + est_in > lim.max_input_tokens:
            raise _Stop("max_input_tokens", f"max_input_tokens {lim.max_input_tokens}")
        if used.usd + est_usd > lim.max_usd:
            raise _Stop("max_usd", f"max_usd {lim.max_usd:g}")

    def _record(self, call_id: str) -> ModelCallRecord:
        """The line of `call_id` in model_calls.jsonl, searched from the end."""
        for line in reversed(_lines(self.out / MODEL_CALLS_FILE)):
            record = ModelCallRecord.model_validate_json(line)
            if record.call_id == call_id:
                return record
        raise ValueError(f"{MODEL_CALLS_FILE}: no line for call {call_id}")

    def _ask(self, step: int, attempt: Literal[1, 2], payload: dict[str, Any]) -> GatewayReply:
        user = _dump(payload)
        self._check_caps(user)
        reply = self.gateway.call(ROLE, ModelRequest(
            unit=f"step {step}", attempt=attempt, system=self.system, user=user,
            reply_schema=REPLY_SCHEMA, max_tokens=self.limits.max_reply_tokens))
        record = self._record(reply.call_id)
        self.spent.requests += 1
        self.spent.tokens_in += record.tokens_in
        self.spent.tokens_out += record.tokens_out
        self.spent.usd += record.usd
        return reply

    # -- the checks of one action -------------------------------------------------------

    def _unknown(self, ids: Sequence[str]) -> list[str]:
        return [f for f in dict.fromkeys(ids) if f not in self.offered]

    def _text(self, where: str, text: str, cites: Sequence[str]) -> str:
        """Why a text of the model is refused; "" when it may stand."""
        if not text.strip():
            return f"{where} is empty"
        if len(text) > TEXT_CHARS:
            return f"{where} is longer than {TEXT_CHARS} characters"
        bare = bare_numbers(text)
        if bare:
            return f"{where} writes the number(s) {bare}; cite a fact as {{F#}}"
        placeholders = _PLACEHOLDER.findall(text)
        missing = [p for p in placeholders if p not in cites]
        if missing:
            return f"{where} uses {missing} without citing them"
        unknown = self._unknown(cites)
        if unknown:
            return f"{where} cites fact(s) {unknown} that were not given"
        return ""

    def _propose(self, action: Propose, step: int) -> tuple[str, str]:
        """(hypothesis id, "") when accepted, ("", reason) when rejected."""
        cluster = self.clusters.get(action.cluster_id)
        if cluster is None:
            return "", f"cluster {action.cluster_id!r} is not a cluster of the round"
        if action.diagnosis not in get_args(Diagnosis):
            return "", f"diagnosis {action.diagnosis!r} is not one of allowed.diagnoses"
        if action.intervention not in get_args(InterventionKind):
            return "", f"intervention {action.intervention!r} is not one of allowed.interventions"
        allowed = INTERVENTIONS_OF_DIAGNOSIS.get(action.diagnosis, frozenset())
        if action.intervention not in allowed:
            return "", (f"intervention {action.intervention!r} is not allowed for "
                        f"{action.diagnosis} (allowed: {sorted(allowed)})")
        if cluster.cluster_id in self.blocked and action.intervention in BUDGET_INTERVENTIONS:
            return "", (f"cluster {cluster.cluster_id} has a system hypothesis standing: "
                        f"{action.intervention!r} would spend data budget")
        problem = self._text("statement", action.statement, [*action.support, *action.contra])
        if problem:
            return "", problem
        hypothesis_id = f"H{self.next_id}"
        self.next_id += 1
        self.mine[hypothesis_id] = _Hypothesis(
            hypothesis_id, cluster, action.statement, cast(Diagnosis, action.diagnosis),
            cast(InterventionKind, action.intervention), list(action.support),
            list(action.contra), step)
        return hypothesis_id, ""

    def _drop(self, action: Drop) -> str:
        mine = self.mine.get(action.hypothesis)
        if mine is None:
            if any(h.hypothesis_id == action.hypothesis for h in self.rules):
                return f"{action.hypothesis} is a rule hypothesis; only your own can be dropped"
            return f"{action.hypothesis!r} is not a hypothesis of yours"
        if not mine.open:
            return f"{action.hypothesis} is already dropped"
        if not action.refuted_by:
            return "refuted_by is empty: cite the facts that refute it"
        unknown = self._unknown(action.refuted_by)
        if unknown:
            return f"refuted_by cites fact(s) {unknown} that were not given"
        mine.open = False
        mine.refuted_by = list(action.refuted_by)
        return ""

    def _conclude(self, action: Conclude) -> str:
        seen: set[str] = set()
        for k, keep in enumerate(action.keep):
            mine = self.mine.get(keep.hypothesis)
            if mine is None or not mine.open:
                return f"keep[{k}]: {keep.hypothesis!r} is not an open hypothesis of yours"
            if keep.hypothesis in seen:
                return f"keep[{k}]: {keep.hypothesis} is kept twice"
            seen.add(keep.hypothesis)
            for where, cited in (("data_content", keep.data_content),
                                 ("first_check", keep.first_check)):
                problem = self._text(f"keep[{k}].{where}", cited.text, cited.cites)
                if problem:
                    return problem
        return ""

    def _roll_back(self, before: int) -> None:
        """Drop the facts a failed call added to the book, so none is ever offered.

        `FactBook` has no undo; its list and its (name, source) index are cut back here.
        """
        book = self.session.book
        gone = {f.fact_id for f in book.facts[before:]}
        del book.facts[before:]
        for key in [k for k, fid in book._index.items() if fid in gone]:
            del book._index[key]

    def _call_tool(self, action: CallTool) -> tuple[str, list[str], str]:
        """(tool call id, fact ids, reason); the reason is "" when the call ran."""
        before = len(self.session.book.facts)
        try:
            outcome = self.session.call(action.tool, action.params)
            spec = REGISTRY[outcome.tool]
            inputs = ([] if outcome.status != "ran"
                      else _inputs(spec, dict(outcome.params), self.ctx, self.entries))
        except UnknownTool:
            return "", [], (f"unknown tool {action.tool!r} (tools: "
                            f"{', '.join(t['name'] for t in self.tools)})")
        except FactClash as error:
            self._roll_back(before)
            return "", [], f"the tool could not run: {error}"[:600]
        except Exception as error:  # a broken tool rejects the step, never the run
            self._roll_back(before)
            return "", [], f"the tool failed: {failure_line(error)}"
        call_id = f"{CALL_PREFIX}{len(self.calls) + 1}"
        if outcome.status == "refused":
            reason = "; ".join(outcome.problems)
            self.calls.append(ToolCallRecord(
                call_id=call_id, tool=outcome.tool, version=outcome.version,
                params=dict(outcome.params), status="refused", reason=reason[:500]))
            return call_id, [], f"parameters refused: {reason}"[:600]
        for fact in self.session.book.facts[before:]:
            self.new_facts.append(FactRecord(
                fact_id=fact.fact_id, name=fact.name, value=fact.value, unit=fact.unit,
                source_ref=fact.source_ref, provenance="code", tool_call_id=call_id))
            self.tool_of[fact.fact_id] = outcome.tool
        ids = list(outcome.fact_ids)
        self.found += [f for f in ids if f not in self.found]
        self.calls.append(ToolCallRecord(
            call_id=call_id, tool=outcome.tool, version=outcome.version,
            params=dict(outcome.params),
            input_sha256=inputs,
            fact_ids=ids, not_judged=list(outcome.not_judged), status=outcome.status,
            reason="; ".join(outcome.not_judged)[:500] if outcome.status == "skipped" else ""))
        return call_id, ids, ""

    # -- one step -----------------------------------------------------------------------

    def _note(self, entry: InvestigationStep) -> None:
        self.log.append(entry)
        line: dict[str, Any] = {"step": entry.step, "action": entry.action or "(unreadable)",
                                "outcome": entry.outcome}
        if entry.parsed is not None and entry.action == "call_tool":
            line.update(tool=entry.parsed.get("tool"), params=entry.parsed.get("params"))
        if entry.fact_ids:
            line["facts"] = entry.fact_ids
        if entry.hypothesis_id:
            line["hypothesis"] = entry.hypothesis_id
        if entry.reason:
            line["reason"] = entry.reason
        self.history.append(line)

    def _stop_on(self, reply: GatewayReply, step: int, calls: list[str]) -> None:
        """Raises `_Stop`, after logging the step, for a reply the gateway did not answer."""
        if reply.status in ANSWERED:
            return
        self._note(InvestigationStep(
            step=step, call_ids=calls, outcome="rejected",
            reason=f"call {reply.call_id} {reply.status}: {reply.error}"[:600]))
        raise _Stop("gateway_budget" if reply.status == "budget_exhausted"
                    else "gateway_failed", f"call {reply.call_id} {reply.status}")

    def _read(self, step: int) -> tuple[CallTool | Propose | Drop | Conclude | None, list[str]]:
        """The parsed action of this step (one resend at most), or None when rejected."""
        payload = self._payload(step)
        calls: list[str] = []
        reply = self._ask(step, 1, payload)
        calls.append(reply.call_id)
        self._stop_on(reply, step, calls)
        errors = reply_errors(reply.text, cut=reply.status == "cut")
        if not errors:
            return parse_reply(reply.text), calls
        try:
            again = self._ask(step, 2, {**payload, "previous_errors": errors})
        except _Stop as stop:
            self._note(InvestigationStep(
                step=step, call_ids=calls, raw=reply.text[:RAW_CHARS], outcome="rejected",
                reason=f"{'; '.join(errors)}; the resend was not sent: {stop.detail}"[:600]))
            raise
        calls.append(again.call_id)
        self._stop_on(again, step, calls)
        errors = reply_errors(again.text, cut=again.status == "cut")
        if not errors:
            return parse_reply(again.text), calls
        self._note(InvestigationStep(step=step, call_ids=calls, raw=again.text[:RAW_CHARS],
                                     outcome="rejected",
                                     reason=f"after a resend: {'; '.join(errors)}"[:600]))
        return None, calls

    def step(self, step: int) -> bool:
        """Run one step; True when it concluded. Raises `_Stop` when the loop must end."""
        action, calls = self._read(step)
        if action is None:
            return False
        tool_call_id, hypothesis_id = "", ""
        fact_ids: list[str] = []
        if isinstance(action, CallTool):
            tool_call_id, fact_ids, reason = self._call_tool(action)
        elif isinstance(action, Propose):
            hypothesis_id, reason = self._propose(action, step)
        elif isinstance(action, Drop):
            reason = self._drop(action)
            hypothesis_id = "" if reason else action.hypothesis
        else:
            reason = self._conclude(action)
            if not reason:
                self.concluded = action
        self._note(InvestigationStep(
            step=step, call_ids=calls, action=action.action,
            parsed=action.model_dump(exclude={"thought"}), thought=action.thought,
            outcome="rejected" if reason else "ok", reason=reason,
            tool_call_id=tool_call_id, fact_ids=fact_ids, hypothesis_id=hypothesis_id))
        return isinstance(action, Conclude) and not reason

    # -- the result ---------------------------------------------------------------------

    def kept(self) -> list[InvestigatedHypothesis]:
        assert self.concluded is not None
        book = self.session.book
        out = []
        for keep in self.concluded.keep:
            h = self.mine[keep.hypothesis]
            cited = list(dict.fromkeys([*h.support, *h.contra, *keep.data_content.cites,
                                        *keep.first_check.cites]))
            offered = {}
            for fid in cited:
                fact = book.get(fid)
                offered[fid] = InvestigatedFact(
                    name=fact.name, value=fact.value, unit=fact.unit,
                    provenance=self.provenance.get(fid, "code"),
                    comparison=is_comparison_fact(fact.name, fact.value, self.markers))
            out.append(InvestigatedHypothesis(
                hypothesis_id=h.hypothesis_id, cluster=h.cluster, statement=h.statement,
                diagnosis=h.diagnosis, intervention=h.intervention, support=h.support,
                contra=h.contra,
                data_content=CitedText(text=keep.data_content.text,
                                       cites=list(keep.data_content.cites)),
                first_check=CitedText(text=keep.first_check.text,
                                      cites=list(keep.first_check.cites)),
                offered=offered, proposed_at=h.step))
        return out


def failure_line(error: BaseException) -> str:
    """`<ExceptionType>: <first line>`, the shape of `pipeline.failure` (not imported:
    the pipeline imports this module)."""
    text = error.args[0] if isinstance(error, KeyError) and error.args else error
    lines = str(text).strip().splitlines()
    return f"{type(error).__name__}: {lines[0][:200] if lines else ''}"


def investigate(out: Path, gateway: Gateway, pack: Pack, admitted: Admitted, *,
                limits: InvestigateLimits | None = None,
                system: str | None = None) -> InvestigateResult:
    """Run the loop on the run directory `out`; writes the four files of the step.

    Raises `GatewayRefused` (no route for the role, or a hosted route the pack may not
    take) before any call, and `RolesRefused` for a bad `roles.yaml` or prompt.
    """
    lim = limits or load_limits()
    prompt = system if system is not None else load_prompt(PROMPT)
    markers = load_roles().rank.comparison_markers
    work = _Investigation(out, gateway, pack, admitted, lim, prompt, markers)
    ending: Ending | None = None
    detail = ""
    rejected = 0
    step = 0
    while ending is None:
        if step >= lim.max_steps:
            ending, detail = "max_steps", f"max_steps {lim.max_steps}"
            break
        step += 1
        try:
            done = work.step(step)
        except _Stop as stop:
            ending, detail = stop.ending, stop.detail
            break
        except Exception as error:  # the loop failing leaves the code floor, never a crash
            ending, detail = "error", failure_line(error)
            break
        if done:
            ending = "concluded"
            break
        rejected = rejected + 1 if work.log[-1].outcome == "rejected" else 0
        if rejected >= lim.max_rejected_in_a_row:
            ending, detail = "rejected_in_a_row", f"max_rejected_in_a_row {rejected}"
    kept: list[InvestigatedHypothesis] = []
    if ending == "concluded":
        try:
            kept = work.kept()
        except Exception as error:
            ending, detail = "error", failure_line(error)
    spent = work.spent
    end = InvestigationEnd(ending=ending, steps=len(work.log), calls=spent.requests,
                           tokens_in=spent.tokens_in, tokens_out=spent.tokens_out,
                           usd=spent.usd, kept=len(kept), detail=detail)
    (out / INVESTIGATION_FILE).write_text(_jsonl([*work.log, end]), encoding="utf-8")
    (out / INVESTIGATION_FACTS_FILE).write_text(_jsonl(work.new_facts), encoding="utf-8")
    (out / INVESTIGATION_CALLS_FILE).write_text(_jsonl(work.calls), encoding="utf-8")
    (out / INVESTIGATED_FILE).write_text(_jsonl(kept), encoding="utf-8")
    result = InvestigateResult(ending, kept)
    if ending != "concluded":
        result.problems.append(f"the investigation ended {ending} ({detail}); no model "
                               "hypothesis is handed on, the code floor stands")
    return result


__all__ = ["FILES", "INVESTIGATED_FILE", "INVESTIGATION_CALLS_FILE", "INVESTIGATION_FACTS_FILE",
           "INVESTIGATION_FILE", "REPLY_SCHEMA", "ROLE", "InvestigateLimits",
           "InvestigateResult", "investigate", "load_limits", "parse_reply", "reply_errors",
           "seeded_book"]
