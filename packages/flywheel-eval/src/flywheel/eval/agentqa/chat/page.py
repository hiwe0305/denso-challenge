"""`fw agentqa chat-page`: a chat record's results on the round's page (DA-54 task 3.1, AC 4).

A chat session records its hypotheses and checked answers into a record directory bound
to a run (`fw agentqa chat --run`). `record_page` lays that record over a copy of the run
and runs the round's own `verify`, `assemble` and `render` on the copy, so the page shows
the chat's hypotheses exactly as it shows those of the investigate step:

    out/            a copy of the run directory, then
      investigated.jsonl, investigation_facts.jsonl, investigation_calls.jsonl
                    the record's (its facts continue the run's ids: the binding)
      answers.jsonl the record's checked answers, shown as recorded
      record_source.json
                    the record's head, the base run id, the sha256 of each copied file
      run.json      the base run's, with `derived_from` set to its id

The live verdicts of the record (`verdicts_live.jsonl`) are not trusted: `verify` judges
every hypothesis again. An answer is shown only when its recorded text still reads the
same from the facts it cites (no number is computed here; the check refuses a tampered
line). Every check runs before anything is written, and the run and the record
directories are only read.
"""

from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any

from flywheel.eval.agentqa.mcp.records import (
    ANSWERS_FILE,
    BINDING,
    RECORD_FILE,
    RecordRefused,
    rendered_answer,
    run_binding,
    run_rules,
)
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE, assemble
from flywheel.eval.agentqa.round.investigate import INVESTIGATION_CALLS_FILE, seeded_book
from flywheel.eval.agentqa.round.measure import FACTS_FILE
from flywheel.eval.agentqa.round.pipeline import RUN_FILE
from flywheel.eval.agentqa.round.records import (
    ChatAnswer,
    FactRecord,
    InvestigatedHypothesis,
    RunRecord,
    ToolCallRecord,
)
from flywheel.eval.agentqa.round.render import render
from flywheel.eval.agentqa.round.verify import (
    INVESTIGATED_FILE,
    INVESTIGATION_FACTS_FILE,
    text_numbers,
    verify,
)

SOURCE_FILE = "record_source.json"
MODEL_FILES = (INVESTIGATED_FILE, INVESTIGATION_FACTS_FILE, INVESTIGATION_CALLS_FILE)
COPIED = (*MODEL_FILES, ANSWERS_FILE)
RECORD_NOTE = ("The model hypotheses and checked answers on this page come from chat "
               "sessions of a record bound to this run; verify judged the hypotheses again "
               "here.")


class PageRefused(ValueError):
    """The page cannot be built from this run and record; nothing was written."""


def _first(error: BaseException) -> str:
    lines = str(error).strip().splitlines()
    return lines[0][:200] if lines else type(error).__name__


def _lines(path: Path) -> list[str]:
    return [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if path.is_file() else []


def _inside(path: Path, other: Path) -> bool:
    return path == other or other in path.parents


def _check_out(out: Path, run: Path, record: Path) -> None:
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise PageRefused(f"{out} exists and is not an empty directory; use a new one")
    target = out.resolve()
    for name, source in (("run", run), ("record", record)):
        if _inside(target, source.resolve()) or _inside(source.resolve(), target):
            raise PageRefused(f"{out} overlaps the {name} directory {source}")


def _base(run: Path) -> RunRecord:
    try:
        base = RunRecord.model_validate_json((run / RUN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PageRefused(f"{run} is not a run directory: {_first(error)}") from error
    if base.derived_from:
        raise PageRefused(f"{run} is itself a chat page of run {base.derived_from!r}; use "
                          "that run")
    if base.status == "broken" or not (run / ASSEMBLY_FILE).is_file():
        raise PageRefused(f"{run} did not finish (status {base.status}); run the round first")
    held = [name for name in MODEL_FILES if _lines(run / name)]
    if held:
        raise PageRefused(f"{run} already holds model hypotheses or their facts "
                          f"({', '.join(held)}): one source of model hypotheses per page")
    return base


def _head(record: Path, base: RunRecord, run: Path) -> tuple[dict[str, Any], list[FactRecord]]:
    """The record's head, checked against the run; the run's facts."""
    try:
        head = json.loads((record / RECORD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PageRefused(f"{record} is not a record directory: {_first(error)}") from error
    if not isinstance(head, dict):
        raise PageRefused(f"{record / RECORD_FILE} is not a record head")
    if (head.get("pack_id"), head.get("pack_sha256")) != (base.pack_id, base.pack_sha256):
        raise PageRefused(f"{record} is a record of another pack ({head.get('pack_id')!r}); "
                          f"the run is of {base.pack_id!r}")
    if "run_id" not in head:
        raise PageRefused(f"{record} is not bound to a run; record a chat with --run")
    try:
        binding, facts = run_binding(run, base.pack_id, base.pack_sha256)
    except RecordRefused as error:
        raise PageRefused(str(error)) from error
    if any(head.get(k) != binding[k] for k in ("run_id", "run_facts_sha256")):
        raise PageRefused(f"{record} is bound to run {head.get('run_id')!r}, not to {run} "
                          f"({binding['run_id']!r}, or its {FACTS_FILE} changed)")
    return head, facts


def _answers(record: Path, facts: dict[str, FactRecord]) -> list[ChatAnswer]:
    """The record's answers, each checked to read the same from the facts it cites."""
    out = []
    for line in _lines(record / ANSWERS_FILE):
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{ANSWERS_FILE}: a line is not an object")
        answer_id, text = str(row.get("answer_id", "")), row.get("text")
        cites, rendered = row.get("cites"), row.get("rendered")
        if not (isinstance(text, str) and isinstance(rendered, str)
                and isinstance(cites, list) and all(isinstance(c, str) for c in cites)):
            raise ValueError(f"{ANSWERS_FILE}: answer {answer_id!r} lacks its text, cites "
                             "or rendered text")
        problems = text_numbers(f"answer {answer_id}", cites, text, facts)
        if problems or rendered_answer(text, cites, facts)[0] != rendered:
            raise ValueError(f"{ANSWERS_FILE}: answer {answer_id!r} does not read the same "
                             f"from the facts it cites{': ' + problems[0] if problems else ''}")
        question = row.get("question")
        out.append(ChatAnswer(answer_id=answer_id, rendered=rendered, cites=list(cites),
                              question=question if isinstance(question, str) else ""))
    return out


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def record_page(run: Path, record: Path, out: Path) -> Path:
    """Lay the chat record `record` over a copy of `run` in the new directory `out` and
    build its page; the path of `index.html`. `PageRefused` before any write."""
    _check_out(out, run, record)
    base = _base(run)
    head, run_facts = _head(record, base, run)
    try:
        own = [FactRecord.model_validate_json(x)
               for x in _lines(record / INVESTIGATION_FACTS_FILE)]
        seeded_book([*run_facts, *own])  # the record's ids continue the run's
        rules = {h.hypothesis_id for h in run_rules(run)}
        for x in _lines(record / INVESTIGATED_FILE):
            hid = InvestigatedHypothesis.model_validate_json(x).hypothesis_id
            if hid in rules:
                raise ValueError(f"{INVESTIGATED_FILE}: {hid} is the id of a rule hypothesis "
                                 "of the run")
        for x in _lines(record / INVESTIGATION_CALLS_FILE):
            ToolCallRecord.model_validate_json(x)
        answers = _answers(record, {f.fact_id: f for f in [*run_facts, *own]})
    except (OSError, ValueError, KeyError) as error:  # ValidationError is a ValueError
        raise PageRefused(f"{record}: {_first(error)}") from error

    shutil.copytree(run, out, dirs_exist_ok=True)
    for name in COPIED:
        source = record / name
        if source.is_file():
            shutil.copyfile(source, out / name)
        else:
            (out / name).write_text("", encoding="utf-8")
    source_record = {
        "record": {k: head[k] for k in ("pack_id", "pack_sha256", *BINDING) if k in head},
        "base_run_id": base.run_id,
        "files": {name: _sha(out / name) for name in COPIED},
    }
    (out / SOURCE_FILE).write_text(json.dumps(source_record, indent=2) + "\n",
                                   encoding="utf-8")
    derived = base.model_copy(update={"derived_from": base.run_id})
    (out / RUN_FILE).write_text(derived.model_dump_json(indent=2) + "\n", encoding="utf-8")
    verify(out)
    assemble(out, derived, base.no_model, notes=[RECORD_NOTE], answers=answers)
    return render(out)


__all__ = ["RECORD_NOTE", "SOURCE_FILE", "PageRefused", "record_page"]
