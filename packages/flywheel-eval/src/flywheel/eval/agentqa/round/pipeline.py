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
from datetime import datetime, timezone
from pathlib import Path

from flywheel.eval.agentqa.round.admit import ADMISSION_FILE, Admitted, admit, write_admission
from flywheel.eval.agentqa.round.measure import (
    CALLS_FILE,
    FACTS_FILE,
    TABLES_DIR,
    PlanRefused,
    measure,
    needed_kinds,
    plan_of,
    read_plan,
)
from flywheel.eval.agentqa.round.pack import PACK_FILE, PackRefused, read_pack, sha256_of
from flywheel.eval.agentqa.round.records import Admission, Pack, RunRecord, Status, StepRecord
from pydantic import ValidationError

RUN_FILE = "run.json"
STEPS = ("pack", "admit", "measure")  # later: hypothesize, judge, verify, assemble, render
STEP_FILES: dict[str, tuple[str, ...]] = {
    "pack": (PACK_FILE,),
    "admit": (ADMISSION_FILE,),
    "measure": (FACTS_FILE, CALLS_FILE),
}
STEP_DIRS: dict[str, tuple[str, ...]] = {"measure": (TABLES_DIR,)}
SEVERITY: dict[str, int] = {"ok": 0, "degraded": 1, "broken": 2}


class RunRefused(ValueError):
    """A run directory cannot be continued: it is not what its run.json says it is."""


@dataclass
class _Work:
    pack_path: Path
    out: Path
    plan_path: Path | None
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


def _step_admit(w: _Work) -> int:
    w.admitted = _admit(w)
    admission = w.admitted.admission
    write_admission(admission, w.out)
    w.degraded += [f"{r.ref} rejected: {r.reason}" for r in admission.rejected]
    w.degraded += [f"no accepted entry of kind {k}" for k in admission.missing_kinds]
    return len(admission.accepted)


def _step_measure(w: _Work) -> int:
    assert w.pack is not None and w.admitted is not None
    result = measure(w.pack, w.admitted, w.plan(), w.out)
    w.degraded += [f"{c.call_id} {c.tool} skipped: {c.reason}" for c in result.calls
                   if c.status == "skipped"]
    return len(result.facts)


RUNNERS = {"pack": _step_pack, "admit": _step_admit, "measure": _step_measure}


def _write(out: Path, record: RunRecord) -> None:
    (out / RUN_FILE).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _resume(pack_path: Path, out: Path, from_step: str, plan_path: Path | None,
            work: _Work) -> RunRecord:
    """The record of `out` cut back to the steps before `from_step`, checked."""
    start = STEPS.index(from_step)
    try:
        old = RunRecord.model_validate_json((out / RUN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise RunRefused(f"{out / RUN_FILE}: {str(error).strip().splitlines()[0][:200]}"
                         ) from error
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
        if old.pack_sha256 != sha256_of(pack_path):
            raise RunRefused(f"{pack_path} is not the pack of run {old.run_id}")
        work.pack = read_pack(out / PACK_FILE)
    if start >= 2:
        stored = Admission.model_validate_json((out / ADMISSION_FILE).read_text("utf-8"))
        work.admitted = _admit(work)
        if work.admitted.admission != stored:
            raise RunRefused(f"{out}: the admission worked out again differs from "
                             f"{ADMISSION_FILE}")
    for step_name in STEPS[start:]:
        for name in STEP_FILES[step_name]:
            (out / name).unlink(missing_ok=True)
        for d in STEP_DIRS.get(step_name, ()):
            shutil.rmtree(out / d, ignore_errors=True)
    names = [s.name for s in kept]
    return old.model_copy(update={
        "steps": kept, "status": _worst([s.status for s in kept]),
        "problems": [p for p in old.problems if p.split(":", 1)[0] in names]})


def run_round(pack_path: Path, out: Path, *, plan_path: Path | None = None,
              from_step: str | None = None, command: str = "",
              now: datetime | None = None) -> RunRecord:
    """Run the pipeline on the pack `pack_path` into `out`; see the module docstring."""
    if from_step is not None and from_step not in STEPS:
        raise RunRefused(f"unknown step {from_step!r} (steps: {', '.join(STEPS)})")
    work = _Work(pack_path, out, plan_path)
    if from_step is None:
        if out.exists():
            raise FileExistsError(f"{out} exists: a run directory is written once")
        out.mkdir(parents=True)
        started = now or datetime.now(timezone.utc)
        sha = sha256_of(pack_path)
        record = RunRecord(
            run_id="run_" + hashlib.sha256((sha + started.isoformat()).encode()).hexdigest()[:16],
            command=command, started_at=started, pack_sha256=sha, status="ok")
        start = 0
    else:
        if not (out / RUN_FILE).is_file():
            raise RunRefused(f"{out}: no {RUN_FILE} to continue from")
        record = _resume(pack_path, out, from_step, plan_path, work)
        record = record.model_copy(update={"command": command or record.command})
        start = STEPS.index(from_step)
    _write(out, record)

    for name in STEPS[start:]:
        began = time.monotonic()
        problems: list[str] = []
        status: Status = "ok"
        rows = 0
        try:
            work.degraded = []
            rows = RUNNERS[name](work)
            if work.degraded:
                status = "degraded"
                problems = [f"{name}: {d}" for d in work.degraded]
        except (PackRefused, PlanRefused) as error:
            record = record.model_copy(update={
                "steps": [*record.steps, StepRecord(
                    name=name, status="broken", seconds=time.monotonic() - began, rows=0)],
                "status": "broken", "problems": [*record.problems, f"{name}: {error}"]})
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
