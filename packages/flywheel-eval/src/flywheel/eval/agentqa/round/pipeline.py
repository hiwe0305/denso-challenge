"""The round runner: steps in order, one run directory, a truthful `run.json` (DA-43 task 4.2).

    run_round(pack.json, out)                       a fresh run into a new directory
    run_round(pack.json, out, from_step="measure")  redo from a step, keep what is before
    run_round(pack.json, out, no_model=False)       with the model steps judge and verify

A no-model run executes `NO_MODEL_STEPS` only; `run.json` records the mode and `--from`
keeps it (a different mode is refused). `model_calls.jsonl` is never deleted by a redo:
`--from adjudicate` and `--from judge` replay its answered requests, `--from verify` makes
no call at all.

`adjudicate` (`adjudicate.py`) runs in both modes, before judge: version 3's report of
each source the pack holds, through the gateway in a model run and on the code floor in a
no-model run. A pack with no such source writes nothing there. One gateway serves both
model roles of a command.

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
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from flywheel.contracts.base import new_ulid
from flywheel.eval.agentqa.round.adjudicate import (
    DROPPED_FILE,
    ESTIMATES_FILE,
    FIGURES_DIR,
    REPORTS_FILE,
    adjudicate,
)
from flywheel.eval.agentqa.round.admit import ADMISSION_FILE, Admitted, admit, write_admission
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE, assemble
from flywheel.eval.agentqa.round.gateway import (
    MODEL_CALLS_FILE,
    Gateway,
    ProviderFactory,
    Usage,
)
from flywheel.eval.agentqa.round.gateway_config import CONFIG_ROOT as GATEWAY_ROOT
from flywheel.eval.agentqa.round.gateway_config import load_gateway_config
from flywheel.eval.agentqa.round.hypotheses import (
    HYPOTHESES_FILE,
    configured_disabled,
    disabled_rules,
    hypothesize,
    missing_clusters_reason,
)
from flywheel.eval.agentqa.round.judge import JUDGED_FILE, MAX_RANK_CLUSTERS, judge
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
from flywheel.eval.agentqa.round.records import (
    Admission,
    Pack,
    RunRecord,
    RunTotals,
    Status,
    StepRecord,
)
from flywheel.eval.agentqa.round.render import INDEX_FILE, render
from flywheel.eval.agentqa.round.verify import VERDICTS_FILE, verify
from flywheel.eval.agentqa.round.version import agent_hash, agent_version
from flywheel.eval.agentqa.run import _ledger
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from pydantic import ValidationError

RUN_FILE = "run.json"
STEPS = ("pack", "admit", "measure", "hypothesize", "adjudicate", "judge", "verify", "assemble",
         "render")
MODEL_STEPS = ("judge", "verify")
NO_MODEL_STEPS = tuple(s for s in STEPS if s not in MODEL_STEPS)
MODEL_ROLE_STEPS = ("adjudicate", "judge")  # steps that may call the gateway
STORY = "DA-43"
SECONDS_NO_MODEL = 5.0
SECONDS_PER_MODEL_CALL = 30.0  # an assumption until a model round is measured
STEP_FILES: dict[str, tuple[str, ...]] = {
    "pack": (PACK_FILE,),
    "admit": (ADMISSION_FILE,),
    "measure": (FACTS_FILE, CALLS_FILE),
    "hypothesize": (HYPOTHESES_FILE,),
    # Not model_calls.jsonl: judge appends to it after this step recorded its sha256.
    "adjudicate": (REPORTS_FILE, DROPPED_FILE, ESTIMATES_FILE),
    "judge": (JUDGED_FILE, MODEL_CALLS_FILE),
    "verify": (VERDICTS_FILE,),
    "assemble": (ASSEMBLY_FILE,),
    "render": (INDEX_FILE,),
}
# Kept when a step is redone: the gateway replays answered requests from it.
KEPT_ON_REDO: frozenset[str] = frozenset({MODEL_CALLS_FILE})
STEP_DIRS: dict[str, tuple[str, ...]] = {"measure": (TABLES_DIR,), "adjudicate": (FIGURES_DIR,)}
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
    gateway_root: Path = GATEWAY_ROOT
    factory: ProviderFactory | None = None
    usage: Usage | None = None
    gateway: Gateway | None = None
    disabled: tuple[str, ...] = ()  # rule ids switched off: agent.yaml's and --disable-rule
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
    result = measure(w.pack, w.admitted, w.plan(), w.out)
    w.degraded += [f"{c.call_id} {c.tool} skipped: {c.reason}" for c in result.calls
                   if c.status == "skipped"]
    return len(result.facts)


def _step_hypothesize(w: _Work) -> int:
    assert w.pack is not None
    hypotheses = hypothesize(w.out, w.pack.task_id, disabled=w.disabled)
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


def _gateway(w: _Work) -> Gateway:
    """The command's one gateway, built by the first model step that needs it."""
    if w.gateway is None:
        w.gateway = Gateway(w.out, load_gateway_config(w.gateway_root), factory=w.factory)
        w.usage = w.gateway.usage
    return w.gateway


def _step_adjudicate(w: _Work) -> int:
    assert w.pack is not None and w.admitted is not None
    result = adjudicate(w.out, w.pack_path.parent, w.pack, w.admitted,
                        None if w.no_model else (lambda: _gateway(w)))
    w.degraded += result.problems
    return len(result.reports)


def _step_judge(w: _Work) -> int:
    # Built first: a refused config or a hosted route the pack may not take stops the
    # step before any call (GatewayRefused, recorded as broken like any failure).
    gateway = _gateway(w)
    result = judge(w.out, gateway)
    w.degraded += result.problems
    return len(result.items)


def _step_verify(w: _Work) -> int:
    verdicts = verify(w.out)
    # Any cluster on the code floor in a model run degrades it (architecture section 9).
    w.degraded += [f"{v.unit}: {v.reason}" for v in verdicts
                   if v.verdict in ("rejected", "not_ranked")]
    return len(verdicts)


def _step_render(w: _Work) -> int:
    render(w.out)
    return 1


RUNNERS = {"pack": _step_pack, "admit": _step_admit, "measure": _step_measure,
           "hypothesize": _step_hypothesize, "adjudicate": _step_adjudicate,
           "judge": _step_judge, "verify": _step_verify,
           "assemble": _step_assemble, "render": _step_render}


def steps_of(no_model: bool) -> tuple[str, ...]:
    """The steps a run of this mode executes, in order."""
    return NO_MODEL_STEPS if no_model else STEPS


def _write(out: Path, record: RunRecord) -> None:
    (out / RUN_FILE).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _pack_part(admission: Admission) -> dict[str, object]:
    """What admit derives from the pack alone; `missing_kinds` follows the plan."""
    return admission.model_dump(exclude={"missing_kinds"})


def _recorded(out: Path) -> RunRecord:
    try:
        return RunRecord.model_validate_json((out / RUN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise RunRefused(f"{out / RUN_FILE}: {str(error).strip().splitlines()[0][:200]}"
                         ) from error


def _mode(no_model: bool) -> str:
    return "no-model" if no_model else "model"


def _resume(pack_path: Path, out: Path, from_step: str, plan: dict[str, object],
            work: _Work, old: RunRecord) -> RunRecord:
    """The record `old` of `out` cut back to the steps before `from_step`, checked.

    A run directory belongs to one pack and one mode. Steps after measure are kept only
    with the plan that measured them; admit's plan-derived part is worked out for the
    plan in use.
    """
    steps = steps_of(old.no_model)
    if from_step not in steps:
        raise RunRefused(f"{out}: step {from_step} is not a step of this {_mode(old.no_model)} "
                         f"run (steps: {', '.join(steps)})")
    start = steps.index(from_step)
    if old.pack_sha256 != sha256_of(pack_path):
        raise RunRefused(f"{pack_path} is not the pack of run {old.run_id} in {out}; a run "
                         "directory belongs to one pack: use a new --out")
    if start > steps.index("measure") and old.plan_sha256 != plan["plan_sha256"]:
        raise RunRefused(f"{out}: the kept measure outputs come from plan "
                         f"{old.plan_path or '(not recorded)'}, not {plan['plan_path']}; "
                         "redo from measure, or pass that plan")
    wanted = plan["disabled_rules"]
    assert isinstance(wanted, list)
    if start > steps.index("hypothesize") and set(old.disabled_rules) != set(wanted):
        raise RunRefused(f"{out}: the kept hypotheses were made with the rules "
                         f"{old.disabled_rules or 'none'} switched off, not "
                         f"{plan['disabled_rules'] or 'none'}; redo from hypothesize")
    if start > len(old.steps) or [s.name for s in old.steps[:start]] != list(steps[:start]):
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
    for step_name in steps[start:]:
        for name in STEP_FILES[step_name]:
            if name not in KEPT_ON_REDO:
                (out / name).unlink(missing_ok=True)
        for d in STEP_DIRS.get(step_name, ()):
            shutil.rmtree(out / d, ignore_errors=True)
    return old.model_copy(update={
        **plan, "steps": kept, "status": _worst([s.status for s in kept]),
        "problems": problems})


def run_round(pack_path: Path, out: Path, *, plan_path: Path | None = None,
              from_step: str | None = None, command: str = "",
              now: datetime | None = None, no_model: bool | None = None,
              store: Path | None = None, run_plan_id: str | None = None,
              gateway_root: Path | None = None,
              gateway_factory: ProviderFactory | None = None,
              disable_rules: Sequence[str] = ()) -> RunRecord:
    """Run the pipeline on the pack `pack_path` into `out`; see the module docstring.

    `no_model`: None means the code floor for a fresh run and the recorded mode for
    `from_step`; a value that differs from the recorded mode is refused. `gateway_root`
    holds `routing.yaml` and `hosted.yaml` (default: the repo's config root);
    `gateway_factory` builds providers in place of the real ones (tests).
    `disable_rules`: rule ids switched off for this run besides `agent.yaml`'s
    `disabled_rules`; recorded in run.json and in the agent hash. An unknown id is refused
    before anything is created.
    """
    if from_step is not None and from_step not in STEPS:
        raise RunRefused(f"unknown step {from_step!r} (steps: {', '.join(STEPS)})")
    # Checked before anything is created, so a typo leaves nothing behind.
    if not pack_path.is_file():
        raise RunRefused(f"{pack_path}: no pack file there")
    task_id = read_pack(pack_path).task_id
    plan_file = plan_path or plan_of(task_id)
    if not plan_file.is_file():
        raise RunRefused(f"{plan_file}: no plan file there")
    disabled = disabled_rules(disable_rules)  # RulesRefused for an unknown id
    configured = configured_disabled()
    old: RunRecord | None = None
    if from_step is not None:
        if not (out / RUN_FILE).is_file():
            raise RunRefused(f"{out}: no {RUN_FILE} to continue from")
        old = _recorded(out)
        if no_model is not None and no_model != old.no_model:
            raise RunRefused(f"{out} is a {_mode(old.no_model)} run; it cannot be continued "
                             f"as a {_mode(no_model)} run: use a new --out")
        mode = old.no_model
    else:
        mode = True if no_model is None else no_model
    groot = gateway_root if gateway_root is not None else GATEWAY_ROOT
    planned: dict[str, object] = {
        "plan_path": plan_file.as_posix(), "plan_sha256": sha256_of(plan_file),
        "agent_version": agent_version(),
        "agent_hash": agent_hash(task_id, plan_file, gateway_root=gateway_root,
                                 disabled=[i for i in disabled if i not in configured]),
        "disabled_rules": disabled}
    work = _Work(pack_path, out, plan_path, no_model=mode, store=store, gateway_root=groot,
                 factory=gateway_factory, disabled=tuple(disabled))
    steps = steps_of(mode)
    if from_step is None:
        if out.exists():
            raise FileExistsError(f"{out} exists: a run directory is written once")
        out.mkdir(parents=True)
        started = now or datetime.now(timezone.utc)
        sha = sha256_of(pack_path)
        record = RunRecord(
            run_id="run_" + hashlib.sha256((sha + started.isoformat()).encode()).hexdigest()[:16],
            command=command, started_at=started, pack_sha256=sha, status="ok",
            no_model=mode,
        ).model_copy(update=planned)
        start = 0
    else:
        assert old is not None
        record = _resume(pack_path, out, from_step, planned, work, old)
        record = record.model_copy(update={"command": command or record.command})
        start = steps.index(from_step)
    _write(out, record)

    ledger = StorePaths(store)
    plan = run_plan_id or f"g0-{STORY}-{date.today():%Y%m%d}"
    job_id = f"job_agentqa_{new_ulid()}"
    if mode:
        seconds = SECONDS_NO_MODEL
        said = f"assumed {SECONDS_NO_MODEL:g} s for a round without a model"
    else:
        most = 2 * MAX_RANK_CLUSTERS  # the default cap, one resend per cluster at most
        seconds = SECONDS_NO_MODEL + most * SECONDS_PER_MODEL_CALL
        said = (f"assumed {seconds:g} s for a round with up to {most} model calls of "
                f"{SECONDS_PER_MODEL_CALL:g} s")
    estimate = _ledger(plan, job_id, seconds, "estimated", said, None)
    append_ledger_entry(estimate, ledger)
    began_run, outcome = time.monotonic(), "ok"
    try:
        return _run_steps(work, record, steps[start:])
    except BaseException as error:
        outcome = f"failed: {type(error).__name__}"
        raise
    finally:
        model_note = "" if mode else (
            f", {work.usage.calls if work.usage is not None else 0} model calls "
            f"({work.usage.replayed if work.usage is not None else 0} replayed)")
        append_ledger_entry(
            _ledger(plan, job_id, max(time.monotonic() - began_run, 0.0), "measured",
                    f"wall seconds of an Agent QA/QC round, {outcome}, from step "
                    f"{steps[start]}{model_note}", estimate.id), ledger)


def _usage_update(usage: Usage) -> dict[str, object]:
    return {"totals": RunTotals(calls=usage.calls, replayed=usage.replayed,
                                tokens_in=usage.tokens_in, tokens_out=usage.tokens_out,
                                usd=usage.usd),
            "model_hosts": sorted(usage.hosts)}


def _run_steps(work: _Work, record: RunRecord, names: tuple[str, ...]) -> RunRecord:
    out = work.out
    for name in names:
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
            if name in MODEL_ROLE_STEPS and work.usage is not None:
                record = record.model_copy(update=_usage_update(work.usage))
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
        if name in MODEL_ROLE_STEPS and work.usage is not None:
            update.update(_usage_update(work.usage))
        steps = [*record.steps, StepRecord(
            name=name, status=status, seconds=time.monotonic() - began, rows=rows,
            outputs=_outputs(out, name))]
        record = record.model_copy(update={
            **update, "steps": steps, "status": _worst([s.status for s in steps]),
            "problems": [*record.problems, *problems]})
        _write(out, record)
    return record
