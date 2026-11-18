"""Task and round manifests (``seed/tasks.yaml``): load, validate, and write ``tasks.json``.

The manifest is the one place that names a task's scoring stages, a round's runs and their roles,
the follow case, the folders a round's files live in and its step count. ``story.py``, ``demo.py``
and ``sim.py`` read them from here; the web pages read ``tasks.json``.

``tasks.json`` carries the manifest plus what the indexer resolves for each task: its catalog
totals (origin "file"), the evaluations it lists (read from their summary file, origin "file") and
its cited clusters (``seed/cited.yaml``, origin "cited").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from flywheel.console.index import catalog, cited
from flywheel.console.paths import ConsolePaths

FILE = "tasks.yaml"
PROCESS_STAGES = ("1", "2", "3", "4", "5", "6", "0")
HOW_KINDS = ("cmd", "config", "module", "doc")
ROLES = ("baseline", "after_round", "control")


class ManifestError(ValueError):
    """The manifest breaks a rule; the message names the entry and the rule."""


@dataclass(frozen=True)
class Stage:
    id: str
    vi: str
    en: str


@dataclass(frozen=True)
class Run:
    id: str
    train_set: str
    session: str | None
    role: str | None


@dataclass(frozen=True)
class Round:
    id: str
    task: str
    number: int
    max_steps: int
    train_dir: str
    eval_dir: str
    cut: str | None
    rollouts: str | None
    log_run: str | None
    rule_tag: str
    level_key: str
    runs: tuple[Run, ...]
    baseline: str
    after_round: str
    controls: tuple[str, ...]
    follow: tuple[int, int] | None
    index: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False, compare=False)

    @property
    def run_ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.runs)

    @property
    def sessions(self) -> dict[str, str]:
        """Colab watcher session name -> run id."""
        return {r.session: r.id for r in self.runs if r.session}

    @property
    def train_sets(self) -> dict[str, str]:
        return {r.id: r.train_set for r in self.runs}


@dataclass(frozen=True)
class Task:
    id: str
    catalog_task: str
    stages: tuple[Stage, ...]
    rounds: tuple[str, ...]
    index: tuple[str, ...]
    teleop_zip: str | None
    raw: dict[str, Any] = field(repr=False, compare=False)


@dataclass(frozen=True)
class Manifest:
    tasks: tuple[Task, ...]
    rounds: tuple[Round, ...]
    raw: dict[str, Any] = field(repr=False, compare=False)

    def task(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(task_id)

    def round(self, round_id: str) -> Round:
        for r in self.rounds:
            if r.id == round_id:
                return r
        raise KeyError(round_id)

    def story_round(self) -> Round | None:
        """The round whose numbers ``story.json`` holds (the one listing ``story.pair``)."""
        return next((r for r in self.rounds if "story.pair" in r.index), None)

    def sim_round(self) -> Round | None:
        """The round whose training cut ``sim.json`` describes (the one listing ``sim``)."""
        return next((r for r in self.rounds if "sim" in r.index), None)


# ------------------------------------------------------------------ validation
def _need(d: Any, key: str, where: str, kind: type | tuple[type, ...] = str) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise ManifestError(f"{where}: missing key '{key}'")
    v = d[key]
    if not isinstance(v, kind) or isinstance(v, bool) and kind is int:
        raise ManifestError(f"{where}.{key}: expected {getattr(kind, '__name__', kind)}, got {v!r}")
    return v


def _text(d: Any, key: str, where: str) -> dict[str, str]:
    v = _need(d, key, where, dict)
    for lang in ("vi", "en"):
        if not isinstance(v.get(lang), str) or not v[lang].strip():
            raise ManifestError(f"{where}.{key}: needs a non-empty '{lang}' text")
    return {str(k): str(x) for k, x in v.items()}


def _stage(s: Any, where: str) -> Stage:
    return Stage(_need(s, "id", where), _need(s, "vi", where), _need(s, "en", where))


def _process(p: Any, where: str) -> None:
    if not isinstance(p, dict):
        raise ManifestError(f"{where}: expected a mapping of process stages")
    missing = [k for k in PROCESS_STAGES if k not in p]
    if missing:
        raise ManifestError(f"{where}: missing process stages {missing}")
    for k, v in p.items():
        w = f"{where}.{k}"
        if k not in PROCESS_STAGES:
            raise ManifestError(f"{w}: unknown process stage (use {', '.join(PROCESS_STAGES)})")
        _need(v, "needs", w, list)
        for i, h in enumerate(_need(v, "how", w, list)):
            kind = _need(h, "kind", f"{w}.how[{i}]")
            if kind not in HOW_KINDS:
                raise ManifestError(f"{w}.how[{i}].kind: '{kind}' is not one of {HOW_KINDS}")
            if not (h.get("text") or h.get("path")):
                raise ManifestError(f"{w}.how[{i}]: needs 'text' or 'path'")
        _need(v, "logs", w, list)
        _need(v, "results", w, list)
        if "missing" in v:
            _text(v, "missing", w)


def _task(t: Any, i: int) -> Task:
    where = f"tasks[{i}]"
    tid = _need(t, "id", where)
    where = f"task '{tid}'"
    for k in ("name", "word", "description"):
        _text(t, k, where)
    for k in ("robot", "model", "simulator", "catalog_task", "scorer_config"):
        _need(t, k, where)
    if t.get("inventory") not in ("store", "task"):
        raise ManifestError(f"{where}.inventory: expected 'store' or 'task'")
    raw_stages = _need(t, "stages", where, list)
    stages = tuple(_stage(s, f"{where}.stages[{j}]") for j, s in enumerate(raw_stages))
    if not stages:
        raise ManifestError(f"{where}.stages: a task needs at least one scoring stage")
    ids = [s.id for s in stages]
    if len(set(ids)) != len(ids):
        raise ManifestError(f"{where}.stages: duplicate stage id in {ids}")
    _text(t, "success", where)
    _process(_need(t, "process", where, dict), f"{where}.process")
    for j, e in enumerate(_need(t, "evals", where, list)):
        _need(e, "id", f"{where}.evals[{j}]")
        _need(e, "fw", f"{where}.evals[{j}]")
        _text(e, "label", f"{where}.evals[{j}]")
    return Task(
        id=tid,
        catalog_task=t["catalog_task"],
        stages=stages,
        rounds=tuple(_need(t, "rounds", where, list)),
        index=tuple(_need(t, "index", where, list)),
        teleop_zip=t.get("teleop_zip"),
        raw=t,
    )


def _round(r: Any, i: int) -> Round:
    where = f"rounds[{i}]"
    rid = _need(r, "id", where)
    where = f"round '{rid}'"
    _text(r, "title", where)
    runs: list[Run] = []
    for j, x in enumerate(_need(r, "runs", where, list)):
        w = f"{where}.runs[{j}]"
        runs.append(Run(_need(x, "id", w), _need(x, "train_set", w), x.get("session"), None))
    ids = [x.id for x in runs]
    if len(set(ids)) != len(ids):
        raise ManifestError(f"{where}.runs: duplicate run id in {ids}")
    baseline = _need(r, "baseline", where)
    after = _need(r, "after_round", where)
    controls = tuple(_need(r, "controls", where, list))
    named = [("baseline", baseline), ("after_round", after)] + [("controls", c) for c in controls]
    for name, v in named:
        if v not in ids:
            raise ManifestError(f"{where}.{name}: '{v}' is not one of its runs {ids}")
    role = {baseline: "baseline", after: "after_round"} | {c: "control" for c in controls}
    runs = [Run(x.id, x.train_set, x.session, role.get(x.id)) for x in runs]
    fol = r.get("follow")
    follow: tuple[int, int] | None = None
    if fol is not None:
        w = f"{where}.follow"
        follow = (_need(fol, "level", w, int), _need(fol, "seed", w, int))
    ev = _need(r, "eval", where, dict)
    steps = _need(r, "max_steps", where, int)
    if steps <= 0:
        raise ManifestError(f"{where}.max_steps: must be positive")
    for v in r.get("withhold_eval") or []:
        if v not in ids:
            raise ManifestError(f"{where}.withhold_eval: '{v}' is not one of its runs {ids}")
    if r.get("log_run") is not None and r["log_run"] not in ids:
        raise ManifestError(f"{where}.log_run: '{r['log_run']}' is not one of its runs {ids}")
    return Round(
        id=rid,
        task=_need(r, "task", where),
        number=_need(r, "number", where, int),
        max_steps=steps,
        train_dir=_need(r, "train_dir", where),
        eval_dir=_need(r, "eval_dir", where),
        cut=r.get("cut"),
        rollouts=r.get("rollouts"),
        log_run=r.get("log_run"),
        rule_tag=_need(r, "rule_tag", where),
        level_key=_need(ev, "level_key", f"{where}.eval"),
        runs=tuple(runs),
        baseline=baseline,
        after_round=after,
        controls=controls,
        follow=follow,
        index=tuple(_need(r, "index", where, list)),
        raw=r,
    )


def parse(data: Any) -> Manifest:
    """Validate a parsed manifest; raise ``ManifestError`` naming the first broken rule."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ManifestError("tasks.yaml: expected 'version: 1' at the top")
    tasks = tuple(_task(t, i) for i, t in enumerate(_need(data, "tasks", "tasks.yaml", list)))
    rounds = tuple(_round(r, i) for i, r in enumerate(data.get("rounds") or []))
    tids = [t.id for t in tasks]
    if len(set(tids)) != len(tids):
        raise ManifestError(f"tasks.yaml: duplicate task id in {tids}")
    rids = [r.id for r in rounds]
    if len(set(rids)) != len(rids):
        raise ManifestError(f"tasks.yaml: duplicate round id in {rids}")
    for r in rounds:
        if r.task not in tids:
            raise ManifestError(f"round '{r.id}'.task: unknown task '{r.task}'")
    for t in tasks:
        for rid in t.rounds:
            if rid not in rids:
                raise ManifestError(f"task '{t.id}'.rounds: unknown round '{rid}'")
            if next(r for r in rounds if r.id == rid).task != t.id:
                raise ManifestError(f"task '{t.id}'.rounds: round '{rid}' belongs to another task")
    seen: dict[str, str] = {}
    for r in rounds:  # one round per index key until the index holds several rounds (phase 2)
        for k in r.index:
            if k in seen:
                raise ManifestError(f"round '{r.id}'.index: '{k}' already belongs to '{seen[k]}'")
            seen[k] = r.id
    return Manifest(tasks, rounds, data)


def load(paths: ConsolePaths) -> Manifest:
    f = paths.seed / FILE
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ManifestError(f"{FILE}: not valid YAML: {e}") from e
    return parse(data)


# ------------------------------------------------------------------ tasks.json
def _dict(p: Path) -> dict[str, Any]:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _evals(fw: Path, evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each listed evaluation with n and successes read from its summary file (or none)."""
    out: list[dict[str, Any]] = []
    for e in evals:
        s = _dict(fw / e["fw"])
        ok = isinstance(s.get("n"), int) and isinstance(s.get("successes"), int)
        out.append(
            {
                **e,
                "n": s.get("n") if ok else None,
                "successes": s.get("successes") if ok else None,
                "level": s.get("level"),
                "sim_mode": s.get("sim_mode"),
                "origin": "file" if ok else None,
                "source": "fwdata/" + e["fw"],
            }
        )
    return out


def _clusters(paths: ConsolePaths, spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        return {}
    by = {c.key: c for c in cited.load(paths)}
    items = []
    for key in spec.get("cited") or []:
        c = by.get(key)
        if c is None:
            raise ManifestError(f"clusters: cited key '{key}' is not in cited.yaml")
        items.append({**c.value, "source": f"{c.doc} §{c.section}", "quote": c.quote})
    d = by.get(spec.get("diagnosis") or "")
    return {
        "origin": "cited",
        "items": items,
        "diagnosis": d.value if d else None,
        "diagnosis_source": f"{d.doc} §{d.section}" if d else None,
        "diagnosis_quote": d.quote if d else None,
    }


def build(paths: ConsolePaths, out: Path) -> dict[str, int]:
    """Write ``out/tasks.json`` (manifest + resolved task facts); return counts."""
    m = load(paths)
    rows = _dict(out / "catalog.json").get("rows") or []
    tasks = []
    for t in m.tasks:
        raw = dict(t.raw)
        mine = [r for r in rows if r.get("task") == t.catalog_task]
        raw["catalog_totals"] = catalog.totals(mine) if mine else {}
        raw["catalog_rows"] = [
            {"id": r["id"], "title": r.get("title"), "group": r.get("group"),
             "kind": r.get("kind"), "episodes": r.get("episodes"), "status": r.get("status")}
            for r in mine
        ]  # fmt: skip
        raw["evals"] = _evals(paths.fw_root, list(raw.get("evals") or []))
        raw["clusters"] = _clusters(paths, raw.get("clusters"))
        tasks.append(raw)
    rounds = []
    for r in m.rounds:
        raw = dict(r.raw)
        pairs = zip(r.raw["runs"], r.runs, strict=True)
        raw["runs"] = [{**x, "role": run.role} for x, run in pairs]
        rounds.append(raw)
    doc = {"version": 1, "source": "seed/tasks.yaml", "tasks": tasks, "rounds": rounds}
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return {"tasks": len(tasks), "rounds": len(rounds)}
