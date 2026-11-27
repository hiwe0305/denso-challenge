"""The record tools of the MCP server (DA-54 task 2.2): the model's hypotheses and answers.

A chat shell drives the model loop, so the model's hypotheses and its final answer no
longer pass the `investigate` step. With `--record <dir>` the server offers three more
tools and is the gate itself; the shell is trusted with nothing:

    hypothesis_propose  the checks of `investigate` (`proposal_problem`, `text_problem` on
                        the statement, the data to collect and the first check); accepted,
                        it gets `H<n>` and at once the verdict `verify` would give it
                        (`investigated_verdict` on the record `investigated.jsonl` holds)
    hypothesis_drop     `drop_problem`: an open hypothesis of this record, refuting facts
    answer_submit       the answer for the user: `verify`'s numbers and comparison rules on
                        one text; accepted, the text comes back with every `{F#}` filled
                        by code (`fill_answer`: a short value, the unit once) and the list
                        of the facts it cites with their full values

A fact is known when a tool call of this record returned it (this server session, or an
earlier one whose facts `investigation_facts.jsonl` holds). A rejected call records
nothing. The data-spend block of `investigate` needs the rule hypotheses of a run
directory (`hypotheses.jsonl`, step B3); the server has none, so no cluster is blocked
here and `verify`/`assemble` of a run directory stay the place of that rule.

Every file of the record directory is rewritten whole (a temporary file, then
`os.replace`), so a crash leaves each one valid JSONL. Opening a record writes nothing
but `record.json` when it is absent; a record of another pack is refused.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, cast, get_args

from flywheel.contracts.evidence import INTERVENTIONS_OF_DIAGNOSIS, Diagnosis, InterventionKind
from flywheel.eval.agentqa.mcp.bridge import CallOutcome, ToolSession, _one_of, _strings
from flywheel.eval.agentqa.round.investigate import (
    INVESTIGATION_CALLS_FILE,
    TEXT_CHARS,
    drop_problem,
    offered_facts,
    proposal_problem,
    roll_back,
    seeded_book,
    text_problem,
)
from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS, RolesRefused, load_roles
from flywheel.eval.agentqa.round.records import (
    CitedText,
    ClusterRef,
    FactRecord,
    InvestigatedHypothesis,
    ToolCallRecord,
    VerdictRecord,
)
from flywheel.eval.agentqa.round.verify import (
    EVIDENCE,
    INVESTIGATED_FILE,
    INVESTIGATION_FACTS_FILE,
    comparison_flags,
    investigated_verdict,
    text_comparison,
    text_numbers,
)
from flywheel.eval.agentqa.tools.clusters import NO_LEVEL, keys_of
from flywheel.eval.agentqa.tools.measures import cluster_id
from pydantic import BaseModel, ConfigDict, Field, ValidationError

RECORD_FILE = "record.json"
VERDICTS_LIVE_FILE = "verdicts_live.jsonl"
ANSWERS_FILE = "answers.jsonl"
DROPPED_FILE = "dropped.jsonl"
FILES = (RECORD_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE, INVESTIGATED_FILE,
         VERDICTS_LIVE_FILE, ANSWERS_FILE, DROPPED_FILE)
PROPOSE, DROP, ANSWER = "hypothesis_propose", "hypothesis_drop", "answer_submit"
RECORD_TOOLS = (PROPOSE, DROP, ANSWER)
ANSWER_CHARS = 4000
CALL_PREFIX = "M"  # the server's tool calls; the plan's are T1.., the loop's I1..
FACT_ID = r"^F[0-9]+$"
HYPOTHESIS_ID = r"^H[1-9][0-9]*$"
_NUMBER = re.compile(r"[0-9]+")
_PLACEHOLDER = re.compile(r"\{(F[0-9]+)\}")  # as `round/render.py` reads one
SIGNIFICANT = 4
PLAIN_FROM, PLAIN_BELOW = 1e-4, 1e6  # a float outside [1e-4, 1e6) keeps an exponent

INSTRUCTIONS = (
    " Record what you conclude with hypothesis_propose, hypothesis_drop and answer_submit: "
    "their texts write no number, only {F#} placeholders of facts the tools returned and "
    "the text cites; answer_submit returns the answer with the numbers filled in by code."
)

DESCRIPTIONS: dict[str, str] = {
    PROPOSE: (
        "Record a hypothesis of yours for one failure cluster: a statement, a diagnosis, an "
        "intervention allowed for it, the facts for and against it, the data to collect and "
        "the first check. Texts write no number: cite facts as {F#} and list them in the "
        "text's cites. Accepted, it gets an id H<n> and its verdict at once: kept, or not "
        "enough evidence (its support needs a measure_compare separated fact, true, of its "
        "own cluster, on a measure the scorer does not threshold), or rejected."),
    DROP: (
        "Close one of your open hypotheses (H<n> of hypothesis_propose), citing the facts "
        "that refute it."),
    ANSWER: (
        "Submit the answer for the user. The text writes no number: cite facts as {F#} and "
        "list them in cites. A comparison word over facts of different units needs a cited "
        "comparison fact. Accepted, it returns the text with every {F#} filled in by code "
        "and the list of the facts it cites; only that text is shown as checked."),
}


class RecordRefused(ValueError):
    """The record directory cannot be used for this pack; nothing was written."""


# --- the parameters -------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


FactId = Annotated[str, Field(pattern=FACT_ID)]


class _Cited(_Strict):
    text: str
    cites: list[FactId]


class _Propose(_Strict):
    cluster: str
    statement: str
    diagnosis: str
    intervention: str
    support: list[FactId]
    contra: list[FactId]
    data_content: _Cited
    first_check: _Cited


class _Drop(_Strict):
    hypothesis: Annotated[str, Field(pattern=HYPOTHESIS_ID)]
    refuted_by: list[FactId]


class _Answer(_Strict):
    text: str
    cites: list[FactId]


def _shape_errors(error: ValidationError) -> list[str]:
    out = []
    for e in error.errors():
        where = ".".join(str(p) for p in e["loc"]) or "(arguments)"
        out.append(f"{where}: {e['msg']}"[:300])
    return out


def _facts_schema(description: str) -> dict[str, Any]:
    return {"type": "array", "description": description,
            "items": {"type": "string", "pattern": FACT_ID}}


def _text_schema(description: str, cap: int) -> dict[str, Any]:
    return {"type": "string", "description": description, "minLength": 1, "maxLength": cap}


def _cited_schema(description: str) -> dict[str, Any]:
    return {"type": "object", "description": description,
            "properties": {
                "text": _text_schema("Free text, no number: {F#} placeholders only.",
                                     TEXT_CHARS),
                "cites": _facts_schema("The fact ids the text rests on; every {F#} of the "
                                       "text is among them.")},
            "required": ["text", "cites"], "additionalProperties": False}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def record_schemas(clusters: Sequence[str]) -> dict[str, dict[str, Any]]:
    """The JSON Schema of each record tool; closed domains are enums of the pack's values."""
    diagnoses = [str(d) for d in get_args(Diagnosis)]
    interventions = [str(k) for k in get_args(InterventionKind)]
    return {
        PROPOSE: _object({
            "cluster": _one_of("One failure cluster of the pack, as "
                               "<run>/<step>/<label>/l<level>.", _strings(list(clusters))),
            "statement": _text_schema("The hypothesis in one or two sentences, no number: "
                                      "{F#} placeholders of support or contra facts only.",
                                      TEXT_CHARS),
            "diagnosis": _one_of("One diagnosis of the closed list.", _strings(diagnoses)),
            "intervention": _one_of(
                "One intervention kind allowed for the diagnosis: "
                + "; ".join(f"{d}: {', '.join(sorted(INTERVENTIONS_OF_DIAGNOSIS.get(d, ())))}"
                            for d in get_args(Diagnosis)) + ".",
                _strings(interventions)),
            "support": _facts_schema("Fact ids that support it."),
            "contra": _facts_schema("Fact ids that speak against it."),
            "data_content": _cited_schema("The data to collect if it holds."),
            "first_check": _cited_schema("The first check that would confirm or refute it."),
        }),
        DROP: _object({
            "hypothesis": {"type": "string", "pattern": HYPOTHESIS_ID,
                           "description": "One of your open hypotheses, H<n>."},
            "refuted_by": {**_facts_schema("Fact ids that refute it."), "minItems": 1},
        }),
        ANSWER: _object({
            "text": _text_schema("The answer for the user, no number: {F#} placeholders "
                                 "only.", ANSWER_CHARS),
            "cites": _facts_schema("The fact ids the answer rests on; every {F#} of the "
                                   "text is among them."),
        }),
    }


# --- outcomes -------------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordOutcome:
    tool: str
    reasons: tuple[str, ...] = ()  # why it was rejected; empty when accepted
    payload: Mapping[str, Any] | None = None  # what an accepted call returns
    cites: tuple[str, ...] = ()

    @property
    def is_error(self) -> bool:
        return bool(self.reasons)

    def result(self) -> dict[str, Any]:
        """The MCP result: the full JSON in the text block (a shell may ignore the rest)."""
        if self.is_error:
            return {"content": [{"type": "text", "text": "\n".join(self.reasons)}],
                    "structuredContent": {"tool": self.tool, "status": "rejected",
                                          "reasons": list(self.reasons)},
                    "isError": True}
        payload = {"tool": self.tool, "status": "accepted", **(self.payload or {})}
        return {"content": [{"type": "text",
                             "text": json.dumps(payload, ensure_ascii=True, allow_nan=False)}],
                "structuredContent": payload, "isError": False}


def _rejected(tool: str, *reasons: str) -> RecordOutcome:
    return RecordOutcome(tool, tuple(r for r in reasons if r) or ("rejected",))


def live_verdict(verdict: VerdictRecord) -> str:
    """`kept`, `not enough evidence: <reason>` or `rejected: <reason>`."""
    if verdict.verdict == "accepted":
        return "kept"
    reason = verdict.reason.removeprefix("rejected: ")
    if verdict.failed_rules == [EVIDENCE]:
        return reason if reason.startswith("not enough evidence") else (
            f"not enough evidence: {reason}")
    return f"rejected: {reason}"


# --- files ----------------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lines(path: Path) -> list[str]:
    return [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if path.is_file() else []


def _write(path: Path, text: str) -> None:
    """`text` as the whole of `path`, through a temporary file and `os.replace`."""
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _jsonl(lines: Sequence[BaseModel | Mapping[str, Any]]) -> str:
    return "".join((x.model_dump_json() if isinstance(x, BaseModel)
                    else json.dumps(x, ensure_ascii=True, allow_nan=False)) + "\n"
                   for x in lines)


def _number(identifier: str) -> int:
    hit = _NUMBER.search(identifier)
    return int(hit.group()) if hit else 0


def _markers() -> tuple[str, ...]:
    try:
        return load_roles().rank.comparison_markers
    except RolesRefused:  # run from another directory: the shipped markers, as `verify`
        return COMPARISON_MARKERS


def pack_clusters(session: ToolSession) -> dict[str, ClusterRef]:
    """The failure clusters of the pack, keyed as `measure_domains` keys them."""
    ctx = session.ctx
    out: dict[str, ClusterRef] = {}
    for name, run in ctx.runs.items():
        for key, members in keys_of(ctx.task, run).items():
            step, label, level = key
            cid = cluster_id(name, key)
            out[cid] = ClusterRef(cluster_id=cid, run=name, step=step, label=label,
                                  level=NO_LEVEL if level is None else level,
                                  size=len(members))
    return dict(sorted(out.items()))


# --- the answer's text ----------------------------------------------------------------------


def answer_value(value: float | int | str | bool) -> str:
    """A fact's value as the answer's text shows it.

    A boolean is `yes`/`no`; an integer stays as it is; a float gets `SIGNIFICANT`
    significant digits in plain notation when its magnitude is in [1e-4, 1e6) (else an
    exponent), without a trailing `.0` or trailing zeros; a string is unchanged.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if not math.isfinite(value):
        return str(value)
    if value == 0:
        return "0"
    rounded = float(f"{value:.{SIGNIFICANT}g}")
    if not PLAIN_FROM <= abs(rounded) < PLAIN_BELOW:
        return f"{value:.{SIGNIFICANT}g}"
    if rounded.is_integer():
        return str(int(rounded))
    decimals = max(0, SIGNIFICANT - 1 - math.floor(math.log10(abs(rounded))))
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")


def _unit_follows(unit: str, rest: str) -> bool:
    """Whether `rest` (the text after a placeholder) already starts with the word `unit`."""
    pattern = r"\s*" + re.escape(unit) + r"(?![A-Za-z0-9_])"
    return re.match(pattern, rest, flags=re.IGNORECASE) is not None


def fill_answer(text: str, facts: Mapping[str, FactRecord]) -> str:
    """`text` with every `{F#}` replaced by `answer_value` and the fact's unit; plain text.

    The unit is left out when it is empty or when the text right after the placeholder
    already starts with it (`{F3} rollouts` with unit `rollouts` gives `11 rollouts`).
    `KeyError` for a placeholder of no fact (the answer's checks run before this).
    """
    def one(match: re.Match[str]) -> str:
        fact = facts[match.group(1)]
        shown = answer_value(fact.value)
        unit = fact.unit.strip()
        if not unit or _unit_follows(unit, text[match.end():]):
            return shown
        return f"{shown} {unit}"

    return _PLACEHOLDER.sub(one, text)


def full_value(fact: FactRecord) -> str:
    """The fact's value as recorded, with its unit: the precise number stays on the record."""
    return f"{fact.value} {fact.unit}".strip()


# --- the record -----------------------------------------------------------------------------


class Recorder:
    """One record directory for one pack: the session's fact book and the model's records."""

    def __init__(self, directory: Path, session: ToolSession, *, facts: list[FactRecord],
                 calls: list[ToolCallRecord], open_: list[InvestigatedHypothesis],
                 verdicts: list[VerdictRecord], answers: list[dict[str, Any]],
                 dropped: list[dict[str, Any]], markers: tuple[str, ...],
                 now: Callable[[], datetime] = _now) -> None:
        self.directory = directory
        self.session = session
        self._facts = facts
        self._calls = calls
        self._open = {h.hypothesis_id: h for h in open_}
        self._verdicts = verdicts
        self._answers = answers
        self._dropped = dropped
        self._markers = markers
        self._now = now
        self.clusters = pack_clusters(session)
        self._schemas = record_schemas(list(self.clusters))
        dropped_ids = {str(d.get("hypothesis_id", "")) for d in dropped}
        used = [*self._open, *dropped_ids, *(v.unit for v in verdicts)]
        self._next_hypothesis = 1 + max((_number(h) for h in used), default=0)
        self._next_call = 1 + max((_number(x) for x in [
            *(c.call_id for c in calls), *(f.tool_call_id for f in facts)]), default=0)
        self._next_answer = 1 + max((_number(str(a.get("answer_id", ""))) for a in answers),
                                    default=0)

    # -- opening -------------------------------------------------------------------------

    @classmethod
    def open(cls, directory: Path, session: ToolSession, pack_id: str, pack_sha256: str, *,
             markers: tuple[str, ...] | None = None,
             now: Callable[[], datetime] = _now) -> Recorder:
        """The record of `directory` for this pack; `RecordRefused` when it cannot be used.

        Every check runs before anything is written; then `directory` and `record.json`
        are created when absent, and nothing else. The returned recorder's `session` holds
        the facts of earlier sessions under their ids (a fresh book seeded with them).
        """
        if directory.exists() and not directory.is_dir():
            raise RecordRefused(f"{directory} exists and is not a directory")
        mine = {"pack_id": pack_id, "pack_sha256": pack_sha256}
        head = directory / RECORD_FILE
        if head.exists():
            try:
                held = json.loads(head.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise RecordRefused(f"{head} cannot be read: {error}") from error
            if not isinstance(held, dict) or {k: held.get(k) for k in mine} != mine:
                got = held.get("pack_id") if isinstance(held, dict) else None
                raise RecordRefused(f"{directory} holds the record of another pack "
                                    f"({got!r}); use another directory")
        elif directory.is_dir() and any((directory / f).exists() for f in FILES):
            raise RecordRefused(f"{directory} holds record files but no {RECORD_FILE}; use "
                                "another directory")
        try:
            facts = [FactRecord.model_validate_json(x)
                     for x in _lines(directory / INVESTIGATION_FACTS_FILE)]
            calls = [ToolCallRecord.model_validate_json(x)
                     for x in _lines(directory / INVESTIGATION_CALLS_FILE)]
            open_ = [InvestigatedHypothesis.model_validate_json(x)
                     for x in _lines(directory / INVESTIGATED_FILE)]
            verdicts = [VerdictRecord.model_validate_json(x)
                        for x in _lines(directory / VERDICTS_LIVE_FILE)]
            answers = [json.loads(x) for x in _lines(directory / ANSWERS_FILE)]
            dropped = [json.loads(x) for x in _lines(directory / DROPPED_FILE)]
            book = seeded_book(facts)
        except (OSError, ValueError) as error:  # ValidationError is a ValueError
            raise RecordRefused(f"{directory}: {str(error).strip().splitlines()[0][:200]}"
                                ) from error
        gone = {str(d.get("hypothesis_id")) for d in dropped if isinstance(d, dict)}
        open_ = [h for h in open_ if h.hypothesis_id not in gone]  # a drop cut short
        recorder = cls(directory, ToolSession(session.ctx, book), facts=facts, calls=calls,
                       open_=open_, verdicts=verdicts,
                       answers=[a for a in answers if isinstance(a, dict)],
                       dropped=[d for d in dropped if isinstance(d, dict)],
                       markers=_markers() if markers is None else markers, now=now)
        if not head.exists():
            directory.mkdir(parents=True, exist_ok=True)
            _write(head, json.dumps(mine, ensure_ascii=True) + "\n")
        return recorder

    # -- the tool list -------------------------------------------------------------------

    def tools(self) -> list[dict[str, Any]]:
        return [{"name": name, "description": DESCRIPTIONS[name],
                 "inputSchema": copy.deepcopy(self._schemas[name])}
                for name in RECORD_TOOLS]

    # -- analysis calls ------------------------------------------------------------------

    def call(self, name: str, arguments: Mapping[str, Any]) -> tuple[CallOutcome, str]:
        """Run one analysis tool and record its call and its new facts; (outcome, call id).

        A tool that raises leaves the book as it was (its facts are cut back) and records
        nothing; `UnknownTool` and the tool's error propagate to the server.
        """
        book = self.session.book
        before = len(book.facts)
        try:
            outcome = self.session.call(name, arguments)
        except Exception:
            roll_back(book, before)
            raise
        call_id = f"{CALL_PREFIX}{self._next_call}"
        new = [FactRecord(fact_id=f.fact_id, name=f.name, value=f.value, unit=f.unit,
                          source_ref=f.source_ref, provenance="code", tool_call_id=call_id)
               for f in book.facts[before:]]
        reason = ("; ".join(outcome.problems) if outcome.status == "refused" else
                  "; ".join(outcome.not_judged) if outcome.status == "skipped" else "")
        record = ToolCallRecord(call_id=call_id, tool=outcome.tool, version=outcome.version,
                                params=dict(outcome.params), fact_ids=list(outcome.fact_ids),
                                not_judged=list(outcome.not_judged), status=outcome.status,
                                reason=reason[:500])
        try:
            if new:
                _write(self.directory / INVESTIGATION_FACTS_FILE, _jsonl([*self._facts, *new]))
            _write(self.directory / INVESTIGATION_CALLS_FILE, _jsonl([*self._calls, record]))
        except Exception:
            roll_back(book, before)
            raise
        self._facts += new
        self._calls.append(record)
        self._next_call += 1
        return outcome, call_id

    # -- record calls --------------------------------------------------------------------

    def _known(self) -> set[str]:
        return {f.fact_id for f in self.session.book.facts}

    def _by_name(self) -> dict[str, FactRecord]:
        return {f.name: f for f in self._facts}

    def _by_id(self) -> dict[str, FactRecord]:
        return {f.fact_id: f for f in self._facts}

    def record(self, name: str, arguments: Mapping[str, Any]) -> RecordOutcome:
        """One call of a record tool; `KeyError` for a name that is not one."""
        handler = {PROPOSE: self._propose, DROP: self._drop, ANSWER: self._answer}[name]
        return handler(dict(arguments))

    def _propose(self, arguments: dict[str, Any]) -> RecordOutcome:
        try:
            args = _Propose.model_validate(arguments)
        except ValidationError as error:
            return _rejected(PROPOSE, *_shape_errors(error))
        known = self._known()
        problem = proposal_problem(args.cluster, args.diagnosis, args.intervention,
                                   self.clusters, frozenset())
        for where, text, cites in (
                ("statement", args.statement, [*args.support, *args.contra]),
                ("data_content", args.data_content.text, args.data_content.cites),
                ("first_check", args.first_check.text, args.first_check.cites)):
            problem = problem or text_problem(where, text, cites, known)
        if problem:
            return _rejected(PROPOSE, problem)
        number = self._next_hypothesis
        cited = list(dict.fromkeys([*args.support, *args.contra, *args.data_content.cites,
                                    *args.first_check.cites]))
        hypothesis = InvestigatedHypothesis(
            hypothesis_id=f"H{number}", cluster=self.clusters[args.cluster],
            statement=args.statement, diagnosis=cast(Diagnosis, args.diagnosis),
            intervention=cast(InterventionKind, args.intervention),
            support=list(args.support), contra=list(args.contra),
            data_content=CitedText(text=args.data_content.text,
                                   cites=list(args.data_content.cites)),
            first_check=CitedText(text=args.first_check.text,
                                  cites=list(args.first_check.cites)),
            offered=offered_facts(cited, self.session.book, {}, self._markers),
            proposed_at=number)
        verdict = investigated_verdict(hypothesis, self._by_name(), self._markers)
        _write(self.directory / INVESTIGATED_FILE,
               _jsonl([*self._open.values(), hypothesis]))
        _write(self.directory / VERDICTS_LIVE_FILE, _jsonl([*self._verdicts, verdict]))
        self._open[hypothesis.hypothesis_id] = hypothesis
        self._verdicts.append(verdict)
        self._next_hypothesis += 1
        return RecordOutcome(PROPOSE, payload={
            "hypothesis": hypothesis.hypothesis_id, "verdict": live_verdict(verdict),
            "failed_rules": list(verdict.failed_rules)}, cites=tuple(cited))

    def _drop(self, arguments: dict[str, Any]) -> RecordOutcome:
        try:
            args = _Drop.model_validate(arguments)
        except ValidationError as error:
            return _rejected(DROP, *_shape_errors(error))
        dropped = {str(d.get("hypothesis_id")) for d in self._dropped}
        is_open = (True if args.hypothesis in self._open else
                   False if args.hypothesis in dropped else None)
        problem = drop_problem(args.hypothesis, is_open, False, args.refuted_by, self._known())
        if problem:
            return _rejected(DROP, problem)
        line = {"hypothesis_id": args.hypothesis, "refuted_by": list(args.refuted_by),
                "ts": self._now().isoformat(),
                "hypothesis": self._open[args.hypothesis].model_dump(mode="json")}
        # the drop first: cut short before the rewrite, the reload still closes it
        _write(self.directory / DROPPED_FILE, _jsonl([*self._dropped, line]))
        rest = [h for h in self._open.values() if h.hypothesis_id != args.hypothesis]
        _write(self.directory / INVESTIGATED_FILE, _jsonl(rest))
        self._dropped.append(line)
        del self._open[args.hypothesis]
        return RecordOutcome(DROP, payload={"hypothesis": args.hypothesis, "dropped": True},
                             cites=tuple(args.refuted_by))

    def _answer(self, arguments: dict[str, Any]) -> RecordOutcome:
        try:
            args = _Answer.model_validate(arguments)
        except ValidationError as error:
            return _rejected(ANSWER, *_shape_errors(error))
        text, cites = args.text, list(args.cites)
        if not text.strip():
            return _rejected(ANSWER, "text is empty")
        if len(text) > ANSWER_CHARS:
            return _rejected(ANSWER, f"text is longer than {ANSWER_CHARS} characters")
        known = self._known()
        reasons = text_numbers("text", cites, text, known)
        offered = offered_facts([f for f in dict.fromkeys(cites) if f in known],
                                self.session.book, {}, self._markers)
        reasons += text_comparison("text", cites, text, offered,
                                   comparison_flags(offered, self._markers))
        if reasons:
            return _rejected(ANSWER, *reasons)
        by_id = self._by_id()
        filled = fill_answer(text, by_id)
        facts = [{"id": fid, "name": by_id[fid].name, "value": by_id[fid].value,
                  "unit": by_id[fid].unit} for fid in dict.fromkeys(cites)]
        listed = "".join(f"\n- {fid} {by_id[fid].name}: {full_value(by_id[fid])}"
                         for fid in dict.fromkeys(cites))
        rendered = filled + (f"\n\nCited facts:{listed}" if facts else "")
        answer_id = f"A{self._next_answer}"
        line = {"answer_id": answer_id, "text": text, "cites": cites, "rendered": rendered,
                "facts": facts, "ts": self._now().isoformat()}
        _write(self.directory / ANSWERS_FILE, _jsonl([*self._answers, line]))
        self._answers.append(line)
        self._next_answer += 1
        return RecordOutcome(ANSWER, payload={"answer": answer_id, "rendered": rendered,
                                              "facts": facts}, cites=tuple(cites))


__all__ = ["ANSWERS_FILE", "DROPPED_FILE", "FILES", "RECORD_FILE", "RECORD_TOOLS",
           "VERDICTS_LIVE_FILE", "RecordOutcome", "RecordRefused", "Recorder",
           "answer_value", "fill_answer", "full_value", "record_schemas"]
