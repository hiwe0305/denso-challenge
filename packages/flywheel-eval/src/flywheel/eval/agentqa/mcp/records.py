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
directory (`hypotheses.jsonl`, step B3); an unbound record has none, so no cluster is
blocked there and `verify`/`assemble` of a run directory stay the place of that rule.

Every file of the record directory is rewritten whole (a temporary file, then
`os.replace`), so a crash leaves each one valid JSONL. Opening a record writes nothing
but `record.json` when it is absent; a record of another pack is refused.

DA-54 task 3.1: a record may be bound to a run directory of the same pack (`--run`). Its
book then starts with the run's `facts.jsonl`, so the record's fact ids continue the run's
numbering, its hypothesis ids continue after the run's rule hypotheses
(`hypotheses.jsonl`), and a cluster where a system hypothesis stands blocks data spend,
all as the round's investigate step does; `fw agentqa chat-page` can then lay the record
over that run. `record.json` keeps the binding (the run's id, the sha256 of its
`facts.jsonl`, its resolved path); a later open without `--run` follows it, and a run
whose facts changed since is refused. An unbound record is what it was before.

DA-55 task 2.2: `fw agentqa chat` appends each turn's question to `questions.jsonl` before
it spawns the harness (`record_question`; the only file here that is appended to, never
rewritten). `answer_submit` copies the latest question, when the file holds one, into the
`question` of the answer line it writes; a record used without `chat` has no such file and
its answer lines are what they were before.
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
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Literal, cast, get_args

from flywheel.contracts.evidence import INTERVENTIONS_OF_DIAGNOSIS, Diagnosis, InterventionKind
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.mcp.bridge import CallOutcome, ToolSession, _one_of, _strings
from flywheel.eval.agentqa.round.hypotheses import HYPOTHESES_FILE
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
from flywheel.eval.agentqa.round.measure import FACTS_FILE
from flywheel.eval.agentqa.round.pipeline import RUN_FILE
from flywheel.eval.agentqa.round.records import (
    CitedText,
    ClusterRef,
    FactRecord,
    HypothesisRecord,
    InvestigatedHypothesis,
    RunRecord,
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
QUESTIONS_FILE = "questions.jsonl"  # the chat's questions, one per turn (DA-55 task 2.2)
FILES = (RECORD_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE, INVESTIGATED_FILE,
         VERDICTS_LIVE_FILE, ANSWERS_FILE, DROPPED_FILE, QUESTIONS_FILE)
BINDING = ("run_id", "run_facts_sha256", "run_dir")  # the keys of record.json a run binds
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


def record_question(directory: Path, text: str,
                    now: Callable[[], datetime] = _now) -> dict[str, Any]:
    """Append `text` as the next turn's question to `directory/questions.jsonl`; the line."""
    turn = 1 + sum(1 for x in _lines(directory / QUESTIONS_FILE) if _row(x) is not None)
    line = {"turn": turn, "question": text, "ts": now().isoformat()}
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / QUESTIONS_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return line


def latest_question(directory: Path) -> str | None:
    """The question of the last readable line of `directory/questions.jsonl`, if any."""
    try:
        lines = _lines(directory / QUESTIONS_FILE)
    except (OSError, UnicodeDecodeError):
        return None
    for raw in reversed(lines):
        row = _row(raw)
        if row is not None and isinstance(row.get("question"), str) and row["question"]:
            return str(row["question"])
    return None


def _row(line: str) -> dict[str, Any] | None:
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


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


def rendered_answer(text: str, cites: Sequence[str],
                    facts: Mapping[str, FactRecord]) -> tuple[str, list[dict[str, Any]]]:
    """(the text shown, the cited facts) of an accepted answer; `KeyError` for an unknown id.

    Shared by `answer_submit` and `fw agentqa chat-page`, which checks that a recorded
    answer still reads the same from the facts it cites.
    """
    cited = list(dict.fromkeys(cites))
    listed = "".join(f"\n- {fid} {facts[fid].name}: {full_value(facts[fid])}" for fid in cited)
    shown = [{"id": fid, "name": facts[fid].name, "value": facts[fid].value,
              "unit": facts[fid].unit} for fid in cited]
    return fill_answer(text, facts) + (f"\n\nCited facts:{listed}" if shown else ""), shown


# --- the binding to a run -------------------------------------------------------------------


def _first(error: BaseException) -> str:
    lines = str(error).strip().splitlines()
    return lines[0][:200] if lines else type(error).__name__


def run_binding(run: Path, pack_id: str, pack_sha256: str
                ) -> tuple[dict[str, str], list[FactRecord]]:
    """(the binding of `run`, its facts); `RecordRefused` unless it is a run of this pack.

    `RecordRefused` too when it has no `facts.jsonl` or `hypotheses.jsonl` (a run that
    did not get past hypothesize cannot number a record).
    """
    if not run.is_dir():
        raise RecordRefused(f"{run} is not a run directory")
    try:
        record = RunRecord.model_validate_json((run / RUN_FILE).read_text(encoding="utf-8"))
        raw = (run / FACTS_FILE).read_bytes()
        facts = [FactRecord.model_validate_json(x)
                 for x in raw.decode("utf-8").splitlines() if x.strip()]
        run_rules(run)
    except (OSError, ValueError) as error:  # ValidationError is a ValueError
        raise RecordRefused(f"{run} is not a usable run directory: {_first(error)}"
                            ) from error
    if (record.pack_id, record.pack_sha256) != (pack_id, pack_sha256):
        raise RecordRefused(f"{run} is a run of another pack ({record.pack_id!r}); a record "
                            "binds to a run of its own pack")
    binding = {"run_id": record.run_id, "run_facts_sha256": sha256(raw).hexdigest(),
               "run_dir": str(run.resolve())}
    return binding, facts


def run_rules(run: Path) -> list[HypothesisRecord]:
    """The rule hypotheses of `run` (`hypotheses.jsonl`, step B3)."""
    return [HypothesisRecord.model_validate_json(x) for x in _lines_strict(run / HYPOTHESES_FILE)]


def _lines_strict(path: Path) -> list[str]:
    """The lines of `path`; `OSError` when it is absent, as a run's files must be there."""
    return [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _same_run(held: Mapping[str, Any], binding: Mapping[str, str]) -> bool:
    """The same run's facts: the path may differ (a moved or copied run), the facts may not."""
    return all(held.get(k) == binding[k] for k in ("run_id", "run_facts_sha256"))


@dataclass(frozen=True)
class _Opened:
    head: dict[str, Any] | None  # the head to write; None when the one on disk stands
    base: list[FactRecord]  # the bound run's facts, first in the book
    rules: list[HypothesisRecord]  # the bound run's rule hypotheses
    facts: list[FactRecord]
    calls: list[ToolCallRecord]
    open_: list[InvestigatedHypothesis]
    verdicts: list[VerdictRecord]
    answers: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    book: FactBook  # seeded with base, then facts


def _held(head: Path) -> dict[str, Any] | None:
    if not head.exists():
        return None
    try:
        held = json.loads(head.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RecordRefused(f"{head} cannot be read: {error}") from error
    if not isinstance(held, dict):
        raise RecordRefused(f"{head.parent} holds the record of another pack (None); use "
                            "another directory")
    return held


def _opened(directory: Path, pack_id: str, pack_sha256: str, run: Path | None) -> _Opened:
    """Every check of opening `directory`, reading only; what to write is in the result."""
    if directory.exists() and not directory.is_dir():
        raise RecordRefused(f"{directory} exists and is not a directory")
    mine: dict[str, Any] = {"pack_id": pack_id, "pack_sha256": pack_sha256}
    head = directory / RECORD_FILE
    held = _held(head)
    records = directory.is_dir() and any((directory / f).exists() for f in FILES[1:])
    if held is not None and {k: held.get(k) for k in mine} != mine:
        raise RecordRefused(f"{directory} holds the record of another pack "
                            f"({held.get('pack_id')!r}); use another directory")
    if held is None and records:
        raise RecordRefused(f"{directory} holds record files but no {RECORD_FILE}; use "
                            "another directory")
    bound = held is not None and "run_id" in held
    base: list[FactRecord] = []
    where: Path | None = run
    write: dict[str, Any] | None = None if held is not None else mine
    if run is not None:
        binding, base = run_binding(run, pack_id, pack_sha256)
        if bound:
            assert held is not None
            if not _same_run(held, binding):
                raise RecordRefused(
                    f"{directory} is bound to run {held.get('run_id')!r}, not to {run} "
                    f"({binding['run_id']!r}, or its {FACTS_FILE} changed); use another "
                    "record directory")
        elif records:
            raise RecordRefused(f"{directory} already holds records made without a run; "
                                "bind a new record directory to the run")
        else:
            write = {**mine, **binding}
    elif bound:
        assert held is not None
        where = Path(str(held.get("run_dir", "")))
        if not where.is_dir():
            raise RecordRefused(f"{directory} is bound to run {held.get('run_id')!r} at "
                                f"{where}, which is gone")
        binding, base = run_binding(where, pack_id, pack_sha256)
        if not _same_run(held, binding):
            raise RecordRefused(f"{directory} is bound to run {held.get('run_id')!r}, but "
                                f"{where / FACTS_FILE} changed since; use another record "
                                "directory")
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
        book = seeded_book([*base, *facts])
        rules = run_rules(where) if where is not None else []
    except (OSError, ValueError) as error:  # ValidationError is a ValueError
        raise RecordRefused(f"{directory}: {_first(error)}") from error
    return _Opened(write, base, rules, facts, calls, open_, verdicts,
                   [a for a in answers if isinstance(a, dict)],
                   [d for d in dropped if isinstance(d, dict)], book)


def _write_head(directory: Path, head: Mapping[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / RECORD_FILE, json.dumps(dict(head), ensure_ascii=True) + "\n")


def bind_record(directory: Path, pack_id: str, pack_sha256: str, run: Path | None
                ) -> dict[str, Any]:
    """The head of `directory` after binding it to `run` (`None`: as it is); `RecordRefused`
    when `Recorder.open` would refuse it. Every check runs first; then only `record.json`
    is written, when it is absent or gains the binding.

    `fw agentqa chat` calls it before spawning the harness, so the server the harness
    starts finds the binding in the head and needs no flag of its own.
    """
    opened = _opened(directory, pack_id, pack_sha256, run)
    if opened.head is not None:
        _write_head(directory, opened.head)
        return opened.head
    held = _held(directory / RECORD_FILE)
    assert held is not None
    return held


# --- the record -----------------------------------------------------------------------------


class Recorder:
    """One record directory for one pack: the session's fact book and the model's records."""

    def __init__(self, directory: Path, session: ToolSession, *, facts: list[FactRecord],
                 calls: list[ToolCallRecord], open_: list[InvestigatedHypothesis],
                 verdicts: list[VerdictRecord], answers: list[dict[str, Any]],
                 dropped: list[dict[str, Any]], markers: tuple[str, ...],
                 now: Callable[[], datetime] = _now,
                 base: Sequence[FactRecord] = (),
                 rules: Sequence[HypothesisRecord] = ()) -> None:
        self.directory = directory
        self.session = session
        self._base = list(base)  # the bound run's facts: in the book, never written here
        self._provenance: dict[str, Literal["code", "vision", "history"]] = {
            f.fact_id: f.provenance for f in self._base}
        self._rule_ids = {h.hypothesis_id for h in rules}
        self._blocked = frozenset(h.cluster.cluster_id for h in rules if h.blocked_data_spend)
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
        used = [*self._rule_ids, *self._open, *dropped_ids, *(v.unit for v in verdicts)]
        self._next_hypothesis = 1 + max((_number(h) for h in used), default=0)
        self._next_call = 1 + max((_number(x) for x in [
            *(c.call_id for c in calls), *(f.tool_call_id for f in facts)]), default=0)
        self._next_answer = 1 + max((_number(str(a.get("answer_id", ""))) for a in answers),
                                    default=0)

    # -- opening -------------------------------------------------------------------------

    @classmethod
    def open(cls, directory: Path, session: ToolSession, pack_id: str, pack_sha256: str, *,
             markers: tuple[str, ...] | None = None,
             now: Callable[[], datetime] = _now, run: Path | None = None) -> Recorder:
        """The record of `directory` for this pack; `RecordRefused` when it cannot be used.

        Every check runs before anything is written; then `directory` and `record.json`
        are created when absent (or the head gains the binding to `run`), and nothing
        else. The returned recorder's `session` holds the bound run's facts, then the facts
        of earlier sessions, under their ids (a fresh book seeded with them). `run`: the
        run directory to bind to; `None` follows the binding the head holds, if any.
        """
        opened = _opened(directory, pack_id, pack_sha256, run)
        gone = {str(d.get("hypothesis_id")) for d in opened.dropped}
        open_ = [h for h in opened.open_ if h.hypothesis_id not in gone]  # a drop cut short
        recorder = cls(directory, ToolSession(session.ctx, opened.book), facts=opened.facts,
                       calls=opened.calls, open_=open_, verdicts=opened.verdicts,
                       answers=opened.answers, dropped=opened.dropped,
                       markers=_markers() if markers is None else markers, now=now,
                       base=opened.base, rules=opened.rules)
        if opened.head is not None:
            _write_head(directory, opened.head)
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
        return {f.name: f for f in [*self._base, *self._facts]}

    def _by_id(self) -> dict[str, FactRecord]:
        return {f.fact_id: f for f in [*self._base, *self._facts]}

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
                                   self.clusters, self._blocked)
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
            offered=offered_facts(cited, self.session.book, self._provenance, self._markers),
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
        problem = drop_problem(args.hypothesis, is_open, args.hypothesis in self._rule_ids,
                               args.refuted_by, self._known())
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
                                self.session.book, self._provenance, self._markers)
        reasons += text_comparison("text", cites, text, offered,
                                   comparison_flags(offered, self._markers))
        if reasons:
            return _rejected(ANSWER, *reasons)
        rendered, facts = rendered_answer(text, cites, self._by_id())
        answer_id = f"A{self._next_answer}"
        line = {"answer_id": answer_id, "text": text, "cites": cites, "rendered": rendered,
                "facts": facts, "ts": self._now().isoformat()}
        question = latest_question(self.directory)  # written by `fw agentqa chat`
        if question is not None:
            line["question"] = question
        _write(self.directory / ANSWERS_FILE, _jsonl([*self._answers, line]))
        self._answers.append(line)
        self._next_answer += 1
        return RecordOutcome(ANSWER, payload={"answer": answer_id, "rendered": rendered,
                                              "facts": facts}, cites=tuple(cites))


__all__ = ["ANSWERS_FILE", "BINDING", "DROPPED_FILE", "FILES", "QUESTIONS_FILE", "RECORD_FILE",
           "RECORD_TOOLS", "VERDICTS_LIVE_FILE", "RecordOutcome", "RecordRefused", "Recorder",
           "answer_value", "bind_record", "fill_answer", "full_value", "latest_question",
           "record_question", "record_schemas", "rendered_answer", "run_binding"]
