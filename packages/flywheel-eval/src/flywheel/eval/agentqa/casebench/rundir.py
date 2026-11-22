"""Verify a finished run directory and read the parts the scorer needs (rules 2 and 3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from flywheel.eval.agentqa.casebench.answers import Refused
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE
from flywheel.eval.agentqa.round.measure import FACTS_FILE
from flywheel.eval.agentqa.round.pack import PACK_FILE
from flywheel.eval.agentqa.round.pipeline import RUN_FILE
from flywheel.eval.agentqa.round.records import Assembly, FactRecord, Pack, RunRecord

LEAK_PARTS = ("answers", "vault", "docs")
TERMINAL = ("ok", "degraded", "broken")


@dataclass(frozen=True)
class Run:
    path: Path
    record: RunRecord
    assembly: Assembly
    facts: list[FactRecord]


def _leaks(ref: str) -> str | None:
    parts = [p.lower() for p in PurePosixPath(ref.replace("\\", "/")).parts]
    return next((x for x in LEAK_PARTS if x in parts), None)


def load_run(path: Path) -> Run:
    """Run state checked, answer not opened yet. Raises `Refused` on any problem."""
    run_file = path / RUN_FILE
    if not run_file.is_file():
        raise Refused(f"{path}: no {RUN_FILE}; the run is not finished")
    try:
        record = RunRecord.model_validate_json(run_file.read_text(encoding="utf-8"))
    except ValueError as error:
        raise Refused(f"{run_file}: not a run record: {error}") from error
    unfinished = [s.name for s in record.steps if s.status not in TERMINAL]
    if not record.steps or unfinished:
        raise Refused(f"{path}: run has no finished steps: {unfinished or 'no steps'}")
    assembly_file = path / ASSEMBLY_FILE
    if not assembly_file.is_file():
        raise Refused(f"{path}: no {ASSEMBLY_FILE}; the run is not finished")
    try:
        assembly = Assembly.model_validate_json(assembly_file.read_text(encoding="utf-8"))
        facts_file = path / FACTS_FILE
        lines = facts_file.read_text(encoding="utf-8").splitlines() if facts_file.is_file() else []
        facts = [FactRecord.model_validate_json(x) for x in lines if x.strip()]
    except ValueError as error:
        raise Refused(f"{path}: unreadable run file: {error}") from error
    return Run(path, record, assembly, facts)


def check_leaks(run: Run) -> None:
    """Rule 3: nothing the run read may come from an answer, vault or docs directory."""
    refs = [("facts.jsonl source_ref", f.source_ref) for f in run.facts]
    pack_file = run.path / PACK_FILE
    if pack_file.is_file():
        try:
            pack = Pack.model_validate_json(pack_file.read_text(encoding="utf-8"))
        except ValueError as error:
            raise Refused(f"{pack_file}: not a pack: {error}") from error
        refs += [("pack.json entry", e.ref) for e in pack.entries]
    for where, ref in refs:
        part = _leaks(ref)
        if part is not None:
            raise Refused(f"answer leak: {where} {ref!r} has a `{part}` path part")
