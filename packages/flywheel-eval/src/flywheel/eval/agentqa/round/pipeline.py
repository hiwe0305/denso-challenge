"""The round runner: steps in order, one run directory, a truthful `run.json` (DA-43 task 4.2).

    run_round(pack.json, out)                       a fresh run into a new directory
    run_round(pack.json, out, from_step="measure")  redo from a step, keep what is before

Each step reads files and writes files. After every step its record is appended to
`run.json`, so a crash leaves a run record that says how far the run got. Kept steps are
not trusted: their output files must still have the sha256 recorded for them, and the
admission is worked out again and must equal the stored one. Nothing is cached between
tool calls.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from flywheel.contracts.base import new_ulid
from flywheel.eval.agentqa.round.admit import ADMISSION_FILE, Admitted, admit, write_admission
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE, assemble
from flywheel.eval.agentqa.round.hypotheses import (
    HYPOTHESES_FILE,
    hypothesize,
    missing_clusters_reason,
)
from flywheel.eval.agentqa.round.measure import (
    CALLS_FILE,
    FACTS_FILE,
    TABLES_DIR,
    measure,
    needed_kinds,
    plan_of,
    read_plan,
)
from flywheel.eval.agentqa.round.pack import PACK_FILE, read_pack, sha256_of
from flywheel.eval.agentqa.round.records import Admission, Pack, RunRecord, Status, StepRecord
from flywheel.eval.agentqa.round.render import INDEX_FILE, render
from flywheel.eval.agentqa.round.version import agent_hash, agent_version
from flywheel.eval.agentqa.run import _ledger
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from pydantic import ValidationError

RUN_FILE = "run.json"
STEPS = ("pack", "admit", "measure", "hypothesize", "assemble", "render")
# Later: judge and verify arrive with task 5, between hypothesize and assemble.
STORY = "DA-43"
SECONDS_NO_MODEL = 5.0
NO_MODEL_ONLY = "the model steps (judge, verify) arrive with task 5; run with no_model"
STEP_FILES: dict[str, tuple[str, ...]] = {
    "pack": (PACK_FILE,),
    "admit": (ADMISSION_FILE,),
    "measure": (FACTS_FILE, CALLS_FILE),
    "hypothesize": (HYPOTHESES_FILE,),
    "assemble": (ASSEMBLY_FILE,),
    "render": (INDEX_FILE,),
}
STEP_DIRS: dict[str, tuple[str, ...]] = {"measure": (TABLES_DIR,)}
SEVERITY: dict[str, int] = {"ok": 0, "degraded": 1, "broken": 2}


class RunRefused(ValueError):
    """A run directory cannot be continued: it is not what its run.json says it is."""


def failure(error: BaseException) -> str:
    """`<ExceptionType>: <first line>`, as run.json and the CLI show a failed step."""
    text = error.args[0] if isinstance(error, KeyError) and error.args else error
    lines = str(text).strip().splitlines()
    return f"{type(error).__name__}: {lines[0][:200] if lines else ''}"


@dataclass
class _Work:
    pack_path: Path
    out: Path
    plan_path: Path | None
    no_model: bool = True
    store: Path | None = None
    run: RunRecord | None = None
    pack: Pack | None = None
    admitted: Admitted | None = None
    degraded: list[str] = field(default_factory=list)

    def plan(self) -> Path:
        assert self.pack is not None
        return self.plan_path or plan_of(self.pack.task_id)


def _worst(statuses: list[Status]) -> Status:
    return max(statuses, key=SEVERITY.__getitem__, default="ok")


def _outputs(out: Path, step: str) -> dict[str, str]:
    names = [f for f in STEP_FILES[step] if (out / f).is_file()]
    for d in STEP_DIRS.get(step, ()):
        if (out / d).is_dir():
            names += sorted(p.relative_to(out).as_posix() for p in (out / d).glob("*.json"))
    return {name: sha256_of(out / name) for name in names}


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _step_pack(w: _Work) -> int:
    w.pack = read_pack(w.pack_path)
    shutil.copyfile(w.pack_path, w.out / PACK_FILE)
    return len(w.pack.entries)


def _admit(w: _Work) -> Admitted:
    assert w.pack is not None
    plan = read_plan(w.plan())
    return admit(w.pack_path, expected_kinds=needed_kinds(plan))


def _admit_problems(admission: Admission) -> list[str]:
    return ([f"{r.ref} rejected: {r.reason}" for r in admission.rejected]
            + [f"no accepted entry of kind {k}" for k in admission.missing_kinds])


def _step_admit(w: _Work) -> int:
    w.admitted = _admit(w)
    admission = w.admitted.admission
    write_admission(admission, w.out)
    w.degraded += _admit_problems(admission)
    return len(admission.accepted)


def _step_measure(w: _Work) -> int:
    assert w.pack is not None and w.admitted is not None
    result = measure(w.pack, w.admitted, w.plan(), w.out, w.store)
    w.degraded += [f"{c.call_id} {c.tool} skipped: {c.reason}" for c in result.calls
                   if c.status == "skipped"]
    return len(result.facts)


def _step_hypothesize(w: _Work) -> int:
    assert w.pack is not None
    hypotheses = hypothesize(w.out, w.pack.task_id)
    reason = missing_clusters_reason(w.out)
    if reason:
        w.degraded.append(reason)
    return len(hypotheses)


def _step_assemble(w: _Work) -> int:
    assert w.run is not None
    assembly = assemble(w.out, w.run, w.no_model)
    if assembly.not_judged:
        w.degraded.append(f"{len(assembly.not_judged)} item(s) not judged")
    w.degraded += [n for n in assembly.notes if n.startswith("No model")]
    return len(assembly.clusters)


def _step_render(w: _Work) -> int:
    render(w.out)
    return 1


RUNNERS = {"pack": _step_pack, "admit": _step_admit, "measure": _step_measure,
           "hypothesize": _step_hypothesize, "assemble": _step_assemble,
           "render": _step_render}


def _write(out: Path, record: RunRecord) -> None:
    (out / RUN_FILE).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _pack_part(admission: Admission) -> dict[str, object]:
    """What admit derives from the pack alone; `missing_kinds` follows the plan."""
    return admission.model_dump(exclude={"missing_kinds"})


def _resume(pack_path: Path, out: Path, from_step: str, plan: dict[str, str],
            work: _Work) -> RunRecord:
    """The record of `out` cut back to the steps before `from_step`, checked.

    A run directory belongs to one pack. Steps after measure are kept only with the
    plan that measured them; admit's plan-derived part is worked out for the plan in use.
    """
    start = STEPS.index(from_step)
    try:
        old = RunRecord.model_validate_json((out / RUN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise RunRefused(f"{out / RUN_FILE}: {str(error).strip().splitlines()[0][:200]}"
                         ) from error
    if old.pack_sha256 != sha256_of(pack_path):
        raise RunRefused(f"{pack_path} is not the pack of run {old.run_id} in {out}; a run "
                         "directory belongs to one pack: use a new --out")
    if start > STEPS.index("measure") and old.plan_sha256 != plan["plan_sha256"]:
        raise RunRefused(f"{out}: the kept measure outputs come from plan "
                         f"{old.plan_path or '(not recorded)'}, not {plan['plan_path']}; "
                         "redo from measure, or pass that plan")
    if start > len(old.steps) or [s.name for s in old.steps[:start]] != list(STEPS[:start]):
        raise RunRefused(f"{out}: the steps before {from_step} are not all recorded")
    kept = old.steps[:start]
    for step in kept:
        if step.status == "broken":
            raise RunRefused(f"{out}: step {step.name} is recorded as broken")
        for name, sha in step.outputs.items():
            path = out / name
            if not path.is_file() or sha256_of(path) != sha:
                raise RunRefused(f"{out}: {name} is not the file step {step.name} wrote")
    if start >= 1:
        work.pack = read_pack(out / PACK_FILE)
    names = [s.name for s in kept]
    problems = [p for p in old.problems if p.split(":", 1)[0] in names]
    if start >= 2:
        stored = Admission.model_validate_json((out / ADMISSION_FILE).read_text("utf-8"))
        work.admitted = _admit(work)
        fresh = work.admitted.admission
        if _pack_part(fresh) != _pack_part(stored):
            raise RunRefused(f"{out}: the admission worked out again differs from "
                             f"{ADMISSION_FILE}")
        if fresh != stored:  # another plan wants other kinds
            write_admission(fresh, out)
            mine = [f"admit: {p}" for p in _admit_problems(fresh)]
            kept[1] = kept[1].model_copy(update={
                "outputs": _outputs(out, "admit"), "status": "degraded" if mine else "ok"})
            problems = ([p for p in problems if p.startswith("pack:")] + mine
                        + [p for p in problems if p.split(":", 1)[0] not in ("pack", "admit")])
    for step_name in STEPS[start:]:
        for name in STEP_FILES[step_name]:
            (out / name).unlink(missing_ok=True)
        for d in STEP_DIRS.get(step_name, ()):
            shutil.rmtree(out / d, ignore_errors=True)
    return old.model_copy(update={
        **plan, "steps": kept, "status": _worst([s.status for s in kept]),
        "problems": problems})


def run_round(pack_path: Path, out: Path, *, plan_path: Path | None = None,
              from_step: str | None = None, command: str = "",
              now: datetime | None = None, no_model: bool = True,
              store: Path | None = None, run_plan_id: str | None = None) -> RunRecord:
    """Run the pipeline on the pack `pack_path` into `out`; see the module docstring."""
    if not no_model:
        raise RunRefused(NO_MODEL_ONLY)
    if from_step is not None and from_step not in STEPS:
        raise RunRefused(f"unknown step {from_step!r} (steps: {', '.join(STEPS)})")
    # Checked before anything is created, so a typo leaves nothing behind.
    if not pack_path.is_file():
        raise RunRefused(f"{pack_path}: no pack file there")
    task_id = read_pack(pack_path).task_id
    plan_file = plan_path or plan_of(task_id)
    if not plan_file.is_file():
        raise RunRefused(f"{plan_file}: no plan file there")
    planned = {"plan_path": plan_file.as_posix(), "plan_sha256": sha256_of(plan_file),
            "agent_version": agent_version(), "agent_hash": agent_hash(task_id, plan_file)}
    work = _Work(pack_path, out, plan_path, no_model=no_model, store=store)
    if from_step is None:
        if out.exists():
            raise FileExistsError(f"{out} exists: a run directory is written once")
        out.mkdir(parents=True)
        started = now or datetime.now(timezone.utc)
        sha = sha256_of(pack_path)
        record = RunRecord(
            run_id="run_" + hashlib.sha256((sha + started.isoformat()).encode()).hexdigest()[:16],
            command=command, started_at=started, pack_sha256=sha, status="ok",
        ).model_copy(update=planned)
        start = 0
    else:
        if not (out / RUN_FILE).is_file():
            raise RunRefused(f"{out}: no {RUN_FILE} to continue from")
        record = _resume(pack_path, out, from_step, planned, work)
        record = record.model_copy(update={"command": command or record.command})
        start = STEPS.index(from_step)
    _write(out, record)

    ledger = StorePaths(store)
    plan = run_plan_id or f"g0-{STORY}-{date.today():%Y%m%d}"
    job_id = f"job_agentqa_{new_ulid()}"
    estimate = _ledger(plan, job_id, SECONDS_NO_MODEL, "estimated",
                       f"assumed {SECONDS_NO_MODEL:g} s for a round without a model", None)
    append_ledger_entry(estimate, ledger)
    began_run, outcome = time.monotonic(), "ok"
    try:
        return _run_steps(work, record, start)
    except BaseException as error:
        outcome = f"failed: {type(error).__name__}"
        raise
    finally:
        append_ledger_entry(
            _ledger(plan, job_id, max(time.monotonic() - began_run, 0.0), "measured",
                    f"wall seconds of an Agent QA/QC round, {outcome}, from step "
                    f"{STEPS[start]}", estimate.id), ledger)


def _run_steps(work: _Work, record: RunRecord, start: int) -> RunRecord:
    out = work.out
    for name in STEPS[start:]:
        began = time.monotonic()
        problems: list[str] = []
        status: Status = "ok"
        rows = 0
        try:
            work.degraded = []
            work.run = record
            rows = RUNNERS[name](work)
            if work.degraded:
                status = "degraded"
                problems = [f"{name}: {d}" for d in work.degraded]
        except Exception as error:  # every failure is recorded, then raised again
            record = record.model_copy(update={
                "steps": [*record.steps, StepRecord(
                    name=name, status="broken", seconds=time.monotonic() - began, rows=0)],
                "status": "broken", "problems": [*record.problems, f"{name}: {failure(error)}"]})
            _write(out, record)
            raise
        update: dict[str, object] = {}
        if work.pack is not None:
            update["pack_id"] = work.pack.pack_id
        if name == "admit" and work.admitted is not None:
            update["data_class"] = work.admitted.admission.data_class
        steps = [*record.steps, StepRecord(
            name=name, status=status, seconds=time.monotonic() - began, rows=rows,
            outputs=_outputs(out, name))]
        record = record.model_copy(update={
            **update, "steps": steps, "status": _worst([s.status for s in steps]),
            "problems": [*record.problems, *problems]})
        _write(out, record)
    return record
