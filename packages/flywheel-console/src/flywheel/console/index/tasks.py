"""Task and round manifests (``seed/tasks.yaml``): load, validate, and write ``tasks.json``.

The manifest is the one place that names a task's scoring stages, a round's runs and their roles,
the follow case, the folders a round's files live in and its step count. ``story.py``, ``demo.py``,
``jig.py`` and ``sim.py`` read them from here; the web pages read ``tasks.json``.

Two shapes of round exist. A round listing ``story.pair`` (``tray-r1``) keeps its runs under one
``train_dir`` and its stage-1 reads in ``eval_dir``. A round listing ``story.jig``
(``tray-jig-r1``, story DA-53) names a train job folder, a stats file and an eval outcome folder per
run, the eval set with its ``conditions.sha256``, and the thresholds of its reading rules; the
indexer copies the numbers from each run's ``results.json`` and only compares them to those
thresholds.

``tasks.json`` carries the manifest plus what the indexer resolves for each task: its catalog
totals (origin "file"), the evaluations it lists (read from their summary file, origin "file") and
its cited clusters (``seed/cited.yaml``, origin "cited").

A round may list ``withhold_runs`` (Hiếu, 28/11/2026, story DA-53): runs it does not present at
all, each with optional ``sessions`` (fnmatch patterns of its Colab session and eval watcher
names). Unlike ``withhold_eval`` (only the retest result is held), nothing of such a run reaches a
page: ``tasks.json`` drops it from the round's ``runs``, writes ``after_round: null`` when it is
the after-round run and carries no ``withhold_runs`` key (``hidden.py`` holds the filters).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml
from flywheel.console.index import catalog, cited, hidden
from flywheel.console.paths import ConsolePaths

FILE = "tasks.yaml"
PROCESS_STAGES = ("1", "2", "3", "4", "5", "6", "0")
HOW_KINDS = ("cmd", "config", "module", "doc")
ROLES = ("baseline", "after_round", "control")
RULE_KEYS = ("whole_task", "per_level", "place")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
    # per-run paths (a ``story.jig`` round): train job folder, stats file, eval outcome folder
    train: str | None = None
    stats: str | None = None
    outcome: str | None = None
    bootstrap_seed: int | None = None
    rules_block: str | None = None
    results_cmd: str | None = None
    cut: str | None = None  # the run's data cut record (``<name>.tar.json``)


@dataclass(frozen=True)
class Round:
    id: str
    task: str
    number: int
    max_steps: int
    train_dir: str | None
    eval_dir: str | None
    cut: str | None
    rollouts: str | None
    log_run: str | None
    rule_tag: str | None
    level_key: str
    runs: tuple[Run, ...]
    baseline: str
    after_round: str
    controls: tuple[str, ...]
    follow: tuple[int, int] | None
    index: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False, compare=False)
    withhold_eval: tuple[str, ...] = ()
    # runs not presented at all (``withhold_runs``) and their session/watcher name patterns
    withhold_runs: tuple[str, ...] = ()
    hidden_sessions: tuple[str, ...] = ()
    # a ``story.jig`` round: scene, eval set, rollouts and scorer the results must match, rules
    scene: str | None = None
    eval_set: str | None = None
    conditions_sha256: str | None = None
    rollouts_expected: int | None = None
    scorer_version: int | None = None
    rules: dict[str, Any] | None = None

    @property
    def shown_runs(self) -> tuple[Run, ...]:
        """The runs a page may show: every run but those in ``withhold_runs``."""
        return tuple(r for r in self.runs if r.id not in self.withhold_runs)

    @property
    def shown_after_round(self) -> str | None:
        """``after_round`` unless that run is hidden (``withhold_runs``)."""
        return None if self.after_round in self.withhold_runs else self.after_round

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

    def jig_round(self) -> Round | None:
        """The round whose runs ``story.json · jig`` holds (the one listing ``story.jig``)."""
        return next((r for r in self.rounds if "story.jig" in r.index), None)


# ------------------------------------------------------------------ validation
def _need(d: Any, key: str, where: str, kind: type | tuple[type, ...] = str) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise ManifestError(f"{where}: missing key '{key}'")
    v = d[key]
    if not isinstance(v, kind) or isinstance(v, bool) and kind is int:
        raise ManifestError(f"{where}.{key}: expected {getattr(kind, '__name__', kind)}, got {v!r}")
    return v


def _opt(d: Any, key: str, where: str, required: bool, kind: type | tuple[type, ...] = str) -> Any:
    """``d[key]`` checked like ``_need`` when present or ``required``; else None."""
    if required or (isinstance(d, dict) and d.get(key) is not None):
        return _need(d, key, where, kind)
    return None


def _rules(v: Any, where: str) -> dict[str, Any]:
    """Thresholds of a round's reading rules: each in (0, 1), read at the CI's lower bound."""
    if not isinstance(v, dict):
        raise ManifestError(f"{where}: missing (a story.jig round declares its reading rules)")
    for k in RULE_KEYS:
        x = v.get(k)
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not 0 < x < 1:
            raise ManifestError(f"{where}.{k}: expected a number between 0 and 1, got {x!r}")
    if v.get("read_at") != "lower_bound":
        raise ManifestError(f"{where}.read_at: expected 'lower_bound', got {v.get('read_at')!r}")
    _text(v, "source", where)
    return dict(v)


def _text(d: Any, key: str, where: str) -> dict[str, str]:
    v = _need(d, key, where, dict)
    for lang in ("vi", "en"):
        if not isinstance(v.get(lang), str) or not v[lang].strip():
            raise ManifestError(f"{where}.{key}: needs a non-empty '{lang}' text")
    return {str(k): str(x) for k, x in v.items()}


def _withhold_runs(
    v: Any, where: str, ids: list[str], kept: dict[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Ids and session patterns of ``withhold_runs``; ``kept`` maps the roles a hidden run may
    not hold (baseline, controls, log_run) to their run id."""
    if v is None:
        return (), ()
    if not isinstance(v, list):
        raise ManifestError(f"{where}: expected a list of {{id, sessions}}")
    out: list[str] = []
    patterns: list[str] = []
    for j, x in enumerate(v):
        w = f"{where}[{j}]"
        rid = _need(x, "id", w)
        if not rid.strip():
            raise ManifestError(f"{w}.id: must not be empty")
        if rid not in ids:
            raise ManifestError(f"{w}.id: '{rid}' is not one of its runs {ids}")
        if rid in out:
            raise ManifestError(f"{w}.id: '{rid}' is listed twice")
        for role, run in kept.items():
            if run == rid:
                raise ManifestError(f"{w}.id: '{rid}' is the round's {role} and cannot be hidden")
        ss = x.get("sessions")
        if ss is not None and (
            not isinstance(ss, list) or not all(isinstance(p, str) and p.strip() for p in ss)
        ):
            raise ManifestError(f"{w}.sessions: expected a list of non-empty strings")
        out.append(rid)
        patterns += list(ss or [])
    return tuple(out), tuple(dict.fromkeys(patterns))


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
    index = tuple(_need(r, "index", where, list))
    jig = "story.jig" in index
    runs: list[Run] = []
    for j, x in enumerate(_need(r, "runs", where, list)):
        w = f"{where}.runs[{j}]"
        rid_j = _need(x, "id", w)
        w = f"{where}.runs '{rid_j}'"
        runs.append(
            Run(
                rid_j,
                _need(x, "train_set", w),
                x.get("session"),
                None,
                train=_opt(x, "train", w, jig),
                stats=_opt(x, "stats", w, False),
                outcome=_opt(x, "outcome", w, jig),
                bootstrap_seed=_opt(x, "bootstrap_seed", w, jig, int),
                rules_block=_opt(x, "rules_block", w, False),
                results_cmd=_opt(x, "results_cmd", w, jig),
                cut=_opt(x, "cut", w, False),
            )
        )
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
    runs = [replace(x, role=role.get(x.id)) for x in runs]
    fol = r.get("follow")
    follow: tuple[int, int] | None = None
    if fol is not None:
        w = f"{where}.follow"
        follow = (_need(fol, "level", w, int), _need(fol, "seed", w, int))
    ev = _need(r, "eval", where, dict)
    steps = _need(r, "max_steps", where, int)
    if steps <= 0:
        raise ManifestError(f"{where}.max_steps: must be positive")
    withhold = tuple(r.get("withhold_eval") or [])
    for v in withhold:
        if v not in ids:
            raise ManifestError(f"{where}.withhold_eval: '{v}' is not one of its runs {ids}")
    if r.get("log_run") is not None and r["log_run"] not in ids:
        raise ManifestError(f"{where}.log_run: '{r['log_run']}' is not one of its runs {ids}")
    kept = {"baseline": baseline} | {f"control '{c}'": c for c in controls}
    if r.get("log_run") is not None:
        kept["log_run"] = r["log_run"]
    w_hide = f"{where}.withhold_runs"
    hide, hide_sessions = _withhold_runs(r.get("withhold_runs"), w_hide, ids, kept)
    pair = "story.pair" in index  # the stage-1 reads need one train folder and one eval folder
    sha = _opt(r, "conditions_sha256", where, jig)
    if sha is not None and not _SHA256.match(sha):
        raise ManifestError(f"{where}.conditions_sha256: expected 64 lowercase hex, got {sha!r}")
    expected = _opt(r, "rollouts_expected", where, jig, int)
    if expected is not None and expected <= 0:
        raise ManifestError(f"{where}.rollouts_expected: must be positive")
    return Round(
        id=rid,
        task=_need(r, "task", where),
        number=_need(r, "number", where, int),
        max_steps=steps,
        train_dir=_opt(r, "train_dir", where, pair),
        eval_dir=_opt(r, "eval_dir", where, pair),
        cut=r.get("cut"),
        rollouts=r.get("rollouts"),
        log_run=r.get("log_run"),
        rule_tag=_opt(r, "rule_tag", where, pair),
        level_key=_need(ev, "level_key", f"{where}.eval"),
        runs=tuple(runs),
        baseline=baseline,
        after_round=after,
        controls=controls,
        follow=follow,
        index=index,
        raw=r,
        withhold_eval=withhold,
        withhold_runs=hide,
        hidden_sessions=hide_sessions,
        scene=_opt(r, "scene", where, False),
        eval_set=_opt(r, "eval_set", where, jig),
        conditions_sha256=sha,
        rollouts_expected=expected,
        scorer_version=_opt(r, "scorer_version", where, jig, int),
        rules=_rules(r.get("rules"), f"{where}.rules") if jig or "rules" in r else None,
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
    # a run in withhold_runs never reaches the browser (hidden.tasks_doc)
    doc = hidden.tasks_doc(
        {"version": 1, "source": "seed/tasks.yaml", "tasks": tasks, "rounds": rounds},
        hidden.from_manifest(m),
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return {"tasks": len(tasks), "rounds": len(rounds)}
