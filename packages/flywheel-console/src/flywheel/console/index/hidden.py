"""Runs a round does not present at all (``withhold_runs`` in ``seed/tasks.yaml``).

Hiếu, 28/11/2026 (story DA-53): run N of the jig scene is not presented on the console, in chat
or in demo scripts (no training curve, data cut, Colab session, live eval, eval result or N minus
M). The index never writes such a run (``tasks.build``, ``story.build``, ``jig.build``); the
filters here also clean a ``story.json`` or ``tasks.json`` built before the switch, so the server
and the chat run every index file they hand out through them.

The hidden ids come from the **seed** (``tasks.load``), never from the index on disk, so a stale
index cannot switch the hiding off. ``load`` reads the seed again when its mtime changes.

Unlike ``withhold_eval`` (``server/withhold.py``: only the retest result is held; training, data
cut and cost stay), nothing of a hidden run is kept, except the ledger: its rows are money already
spent (story DA-53, decision 28/11/2026 point 2). Decision Q1 of 28/11/2026 (audit 00 · Tổng
hợp): the ledger rows of a hidden story (``withhold_runs[].stories``, e.g. DA-50) are summed into
one row ``story: "other"`` with the same numbers (``story._ledger``), and the catalog rows of that
story, or naming a hidden run, are dropped (``catalog_rows``).
"""

from __future__ import annotations

import fnmatch
import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # tasks imports this module
    from flywheel.console.index.tasks import Manifest, Round
    from flywheel.console.paths import ConsolePaths


@dataclass(frozen=True)
class Hidden:
    """Ids of the hidden runs, their session/watcher name patterns and their folder names."""

    ids: frozenset[str] = frozenset()
    sessions: tuple[str, ...] = ()
    # job folder, train parent folder, outcome folder, cut and stats file names of hidden runs
    names: tuple[str, ...] = ()
    # stories whose work is only the hidden runs' (``withhold_runs[].stories``): their catalog
    # rows are dropped and their ledger rows merge into one "other" row (``story.py``)
    stories: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.ids)

    def run(self, name: Any) -> bool:
        """``name`` is a hidden run id (exact)."""
        return isinstance(name, str) and name in self.ids

    def story(self, name: Any) -> bool:
        """``name`` is a hidden story id (exact, e.g. ``DA-50``)."""
        return isinstance(name, str) and name in self.stories

    def session(self, name: Any) -> bool:
        """``name`` (a Colab session, watcher folder or session name) matches a pattern."""
        return (
            isinstance(name, str)
            and bool(name)
            and any(fnmatch.fnmatchcase(name, p) for p in self.sessions)
        )

    def mentions(self, text: Any) -> bool:
        """``text`` names a hidden run: one of its session patterns or folder names as a token,
        ``run <id>`` as a whole word (any case), or a JSON field ``"run"``/``"branch"`` equal to
        its id. Used on stored chat traces, where a bare substring test of "N" cannot work."""
        rx = _mention_rx(self)
        return bool(self and rx is not None and isinstance(text, str) and rx.search(text))


def _glob_rx(pattern: str) -> str:
    out = []
    for ch in pattern:
        out.append(r"[\w.-]*" if ch == "*" else r"[\w.-]" if ch == "?" else re.escape(ch))
    return "".join(out)


@functools.lru_cache(maxsize=16)
def _mention_rx(h: Hidden) -> re.Pattern[str] | None:
    if not h.ids:
        return None
    tokens = [_glob_rx(p) for p in h.sessions] + [re.escape(n) for n in h.names]
    alts = [rf"(?<![\w.-])(?:{'|'.join(tokens)})(?![\w-])"] if tokens else []
    ids = "|".join(re.escape(i) for i in sorted(h.ids))
    alts.append(rf"\brun\s+(?:{ids})(?!\w)")
    alts.append(rf"\"(?:run|branch|variant|run_id)\"\s*:\s*\"(?:{ids})\"")
    return re.compile("|".join(alts), re.IGNORECASE)


# ------------------------------------------------------------------ from the manifest
def of_round(rnd: Round) -> Hidden:
    """The hidden runs of one round."""
    ids = set(rnd.withhold_runs)
    if not ids:
        return Hidden()
    sessions: list[str] = list(rnd.hidden_sessions)
    stories = frozenset(rnd.hidden_stories)
    names: list[str] = []
    shown_parents = {PurePosixPath(r.train).parent.name for r in rnd.shown_runs if r.train}
    for run in rnd.runs:
        if run.id not in ids:
            continue
        if run.session:
            sessions.append(run.session)
        if run.train:
            job = PurePosixPath(run.train)
            names.append(job.name)
            if job.parent.name and job.parent.name not in shown_parents:
                names.append(job.parent.name)
        if run.outcome:
            names.append(PurePosixPath(run.outcome).name)
        if run.cut:
            names.append(PurePosixPath(run.cut).name.removesuffix(".json"))
        if run.stats:
            names.append(PurePosixPath(run.stats).name)
    return Hidden(
        frozenset(ids),
        tuple(dict.fromkeys(sessions)),
        tuple(dict.fromkeys(n for n in names if n)),
        stories,
    )


def from_manifest(m: Manifest) -> Hidden:
    """The hidden runs of every round (union)."""
    parts = [of_round(r) for r in m.rounds]
    return Hidden(
        frozenset().union(*(p.ids for p in parts)),
        tuple(dict.fromkeys(s for p in parts for s in p.sessions)),
        tuple(dict.fromkeys(n for p in parts for n in p.names)),
        frozenset().union(*(p.stories for p in parts)),
    )


_CACHE: dict[Path, tuple[int, Hidden]] = {}


def load(paths: ConsolePaths) -> Hidden:
    """The hidden runs of the seed manifest, cached until the seed file changes.

    A seed that cannot be read or validated gives no hidden run; the index cannot be built from
    it either (``fw console index`` fails on the same error).
    """
    from flywheel.console.index import tasks

    f = paths.seed / tasks.FILE
    try:
        mtime = f.stat().st_mtime_ns
    except OSError:
        return Hidden()
    hit = _CACHE.get(f)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    try:
        h = from_manifest(tasks.load(paths))
    except (tasks.ManifestError, OSError):
        h = Hidden()
    _CACHE[f] = (mtime, h)
    return h


# ------------------------------------------------------------------ catalog rows
def catalog_row(row: Any, h: Hidden) -> bool:
    """True when a catalog row (seed row or card) belongs to a hidden run: its ``story`` is a
    hidden story, or any of its text (notes, locations, ids) names a hidden run or session
    (``mentions``; e.g. ``analysis/da50-clean`` in the notes of the run-N data sets)."""
    if not h or not isinstance(row, dict):
        return False
    if h.story(row.get("story")):
        return True
    return h.mentions(json.dumps(row, ensure_ascii=False, default=str))


def catalog_rows(
    rows: list[dict[str, Any]], edges: list[Any], h: Hidden
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Catalog rows and edges without the rows of hidden runs (``catalog_row``); the other rows'
    ``parents``, ``children`` and ``superseded_by`` lose the dropped ids, and an edge with a
    dropped end is dropped. Unchanged when no run is hidden."""
    if not h:
        return rows, edges
    gone = {str(r.get("id")) for r in rows if catalog_row(r, h)}
    if not gone:
        return rows, edges
    kept: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("id")) in gone:
            continue
        r = dict(r)
        for key in ("parents", "children", "superseded_by"):
            if isinstance(r.get(key), list):
                r[key] = [x for x in r[key] if str(x) not in gone]
        kept.append(r)
    edges = [
        e for e in edges
        if not (isinstance(e, (list, tuple)) and any(str(x) in gone for x in e[:2]))
    ]  # fmt: skip
    return kept, edges


def catalog_hidden_ids(doc: Any, h: Hidden) -> frozenset[str]:
    """Ids of the rows of a catalog document (``data/catalog.json``, ``story.ds``) that belong to
    a hidden run (``catalog_row``). The server refuses ``/data/ds/<id>/...`` for these ids and
    drops them from ``tasks[].catalog_rows``, whose trimmed rows lack the fields to judge."""
    if not h or not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        return frozenset()
    return frozenset(str(r.get("id")) for r in doc["rows"] if catalog_row(r, h))


def catalog_doc(doc: Any, h: Hidden) -> Any:
    """A catalog document (``data/catalog.json`` or ``story.ds``) without the rows of hidden runs
    (``catalog_rows``), for an index built before the rows were dropped; ``totals``, when
    present, is computed again from the kept rows (``catalog.totals``). Unchanged when no row
    is hidden."""
    if not catalog_hidden_ids(doc, h):
        return doc
    from flywheel.console.index import catalog  # catalog imports this module

    edges = doc.get("edges") if isinstance(doc.get("edges"), list) else []
    rows, edges = catalog_rows(doc["rows"], edges, h)
    out = {**doc, "rows": rows}
    if "edges" in doc:
        out["edges"] = edges
    if "totals" in doc:
        out["totals"] = catalog.totals(rows)
    return out


# ------------------------------------------------------------------ tasks.json
def tasks_doc(doc: Any, h: Hidden) -> Any:
    """``tasks.json`` without the hidden runs: dropped from each round's ``runs``, roles naming
    one become None (``after_round: null``), and no round carries ``withhold_runs``."""
    if not isinstance(doc, dict) or not isinstance(doc.get("rounds"), list):
        return doc
    rounds: list[Any] = []
    for r in doc["rounds"]:
        if not isinstance(r, dict):
            rounds.append(r)
            continue
        r = {k: v for k, v in r.items() if k != "withhold_runs"}
        if h:
            if isinstance(r.get("runs"), list):
                r["runs"] = [
                    x for x in r["runs"] if not (isinstance(x, dict) and h.run(x.get("id")))
                ]
            for key in ("after_round", "baseline", "log_run"):
                if h.run(r.get(key)):
                    r[key] = None
            for key in ("controls", "withhold_eval"):
                if isinstance(r.get(key), list):
                    r[key] = [x for x in r[key] if not h.run(x)]
            if isinstance(r.get("links"), dict):  # a link never leads to a hidden run
                r["links"] = {
                    k: None if isinstance(v, dict) and (h.run(v.get("run")) or h.mentions(
                        json.dumps(v, ensure_ascii=False))) else v
                    for k, v in r["links"].items()
                }  # fmt: skip
        rounds.append(r)
    return {**doc, "rounds": rounds}


# ------------------------------------------------------------------ story.json
def _keep(x: Any, h: Hidden, *keys: str) -> bool:
    return not (isinstance(x, dict) and any(h.run(x.get(k)) for k in keys))


def _rows(v: Any, h: Hidden, *keys: str) -> Any:
    return [x for x in v if _keep(x, h, *keys)] if isinstance(v, list) else v


def off_sessions(v: Any, h: Hidden, *keys: str) -> Any:
    """Rows of ``v`` whose ``keys`` (session or folder names) match no hidden session pattern."""
    if not isinstance(v, list):
        return v
    return [x for x in v if not (isinstance(x, dict) and any(h.session(x.get(k)) for k in keys))]


def _fallback(j: dict[str, Any], key: str) -> str | None:
    """A ``featured``/``best`` run in place of a hidden one: the baseline when its eval is
    ready (shape of ``jig.py``), else, in a doc without ``evals`` (the older shape whose
    ``best`` was the eval row with the most successes), the remaining row with the most."""
    evals = j.get("evals")
    if isinstance(evals, list):
        base = next((e for e in evals if isinstance(e, dict) and e.get("role") == "baseline"), {})
        return base.get("run") if base.get("status") == "ready" else None
    rows = [
        r for r in j.get("runs") or [] if isinstance(r, dict) and r.get("successes") is not None
    ]
    if not rows:
        return None
    best = max(rows, key=lambda r: r["successes"] if isinstance(r["successes"], int) else -1)
    run = best.get("run")
    return run if isinstance(run, str) else None


def _jig(j: dict[str, Any], h: Hidden) -> dict[str, Any]:
    j = dict(j)
    before = [r for r in j.get("runs") or [] if isinstance(r, dict)]
    evals_before = [e for e in j.get("evals") or [] if isinstance(e, dict)]
    for key, ids in (("runs", ("branch", "run")), ("evals", ("run",)), ("outcomes", ("run",)),
                     ("rollouts", ("run",)), ("conditions", ("run",))):  # fmt: skip
        if key in j:
            j[key] = _rows(j[key], h, *ids)
    if isinstance(j.get("cuts"), dict):
        j["cuts"] = {k: v for k, v in j["cuts"].items() if not h.run(k)}
    paired = j.get("paired")
    if isinstance(paired, dict) and (h.run(paired.get("variant")) or h.run(paired.get("baseline"))):
        j["paired"] = None
    for key in ("featured", "best"):
        if key in j and h.run(j[key]):
            j[key] = _fallback(j, key)
    cut = j.get("next_cut")
    after_hidden = any(e.get("role") == "after_round" and h.run(e.get("run")) for e in evals_before)
    if isinstance(cut, dict):
        after_hidden = after_hidden or h.run(cut.get("name")) or h.mentions(cut.get("source"))
    elif "evals" not in j and j.get("n_ckpt_done") is not None:
        after_hidden = True  # older shape: n_ckpt_done is the next run's, and nothing says whose
    if after_hidden:
        j["next_cut"] = None
        if "n_ckpt_done" in j:
            j["n_ckpt_done"] = None
    m_cut = j.get("m_cut")
    if isinstance(m_cut, dict) and (h.run(m_cut.get("name")) or h.mentions(m_cut.get("source"))):
        j["m_cut"] = None
    if j.get("train_log_tail") or j.get("vm_phases"):
        log_run = j.get("log_run")
        if "log_run" in j:
            log_hidden = h.run(log_run)
        else:  # whose log it is: a shown run entry carrying the same tail (or phases), else unknown
            tail, phases = j.get("train_log_tail"), j.get("vm_phases")
            key, value = ("log_tail", tail) if tail else ("vm_phases", phases)
            owners = [r for r in before if r.get(key) == value]
            log_hidden = not any(_keep(r, h, "branch", "run") for r in owners)
        if log_hidden:
            j["train_log_tail"], j["vm_phases"] = [], {}
            if "log_run" in j:
                j["log_run"] = None
    if "live_evals" in j:
        j["live_evals"] = off_sessions(j["live_evals"], h, "folder", "session")
    if "active_sessions" in j:
        j["active_sessions"] = off_sessions(j["active_sessions"], h, "session")
    if isinstance(j.get("agentqa"), list):
        j["agentqa"] = agentqa(j["agentqa"], h)
    c60 = j.get("compare60")
    if isinstance(c60, dict) and h.run(c60.get("run")):
        j["compare60"] = None
    elif isinstance(c60, dict) and isinstance(c60.get("earlier"), list):
        j["compare60"] = {**c60, "earlier": _rows(c60["earlier"], h, "run")}
    return j


def agentqa(assemblies: list[Any], h: Hidden) -> list[Any]:
    """Agent QA assemblies without the clusters of hidden runs; an assembly that had clusters
    and has none left is dropped."""
    out: list[Any] = []
    for a in assemblies:
        if not isinstance(a, dict) or not isinstance(a.get("clusters"), list):
            out.append(a)
            continue
        if h.run(a.get("run_id")):
            continue
        kept = _rows(a["clusters"], h, "run")
        if a["clusters"] and not kept:
            continue
        out.append({**a, "clusters": kept})
    return out


OTHER_STORY = "other"
OTHER_LABEL = "Thí nghiệm khác (không trình bày)"
_LEDGER_KEYS = ("est_cu", "mea_cu", "est_usd", "mea_usd")


def ledger(rows: Any, h: Hidden) -> Any:
    """``story.ledger`` with the rows of hidden stories summed into one last row ``story:
    "other"`` (decision Q1, 28/11/2026), for both shapes: ``{story, label, est_cu, mea_cu,
    est_usd, mea_usd}`` and the older ``[story, est_usd, mea_usd]``. Numbers are kept."""
    if not h.stories or not isinstance(rows, list):
        return rows
    kept: list[Any] = []
    obj: dict[str, Any] | None = None
    old: list[Any] | None = None
    for r in rows:
        if isinstance(r, dict) and h.story(r.get("story")):
            obj = obj or {"story": OTHER_STORY, "label": OTHER_LABEL} | dict.fromkeys(_LEDGER_KEYS)
            for k in _LEDGER_KEYS:
                v = r.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    obj[k] = round((obj[k] or 0.0) + v, 2)
        elif isinstance(r, list) and r and h.story(r[0]):
            old = old or [OTHER_STORY, 0.0, 0.0]
            for i in (1, 2):
                v = r[i] if len(r) > i else None
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    old[i] = round(old[i] + v, 2)
        else:
            kept.append(r)
    return kept + [x for x in (obj, old) if x is not None]


def story(doc: Any, h: Hidden) -> Any:
    """``story.json`` without the hidden runs, for both shapes of its ``jig`` block (the one of
    ``jig.py``, and the older one whose ``jig.runs`` are eval rows keyed ``run`` while the
    top-level ``runs`` hold the jig train entries). The ledger goes through ``ledger``: the rows
    of hidden stories merge into one "other" row with the same numbers, as an index built since
    28/11/2026 already writes it (``story._ledger``), so a stale index names no hidden story
    either. Unchanged when no run is hidden."""
    if not h or not isinstance(doc, dict):
        return doc
    out = dict(doc)
    if "runs" in out:
        out["runs"] = _rows(out["runs"], h, "branch", "run")
    if "colab_sessions" in out:
        out["colab_sessions"] = off_sessions(out["colab_sessions"], h, "session")
    if "ledger" in out:
        out["ledger"] = ledger(out["ledger"], h)
    pair = out.get("pair")
    if isinstance(pair, dict) and pair.get("runs"):
        runs = _rows(pair.get("runs"), h, "run")
        out["pair"] = {
            **pair,
            "runs": runs,
            "comparisons": _rows(pair.get("comparisons"), h, "variant", "baseline"),
        }
        if h.run(pair.get("best")):
            out["pair"]["best"] = _fallback({"runs": runs}, "best")
    if isinstance(out.get("jig"), dict) and out["jig"]:
        out["jig"] = _jig(out["jig"], h)
    for key in ("timeline", "next_steps"):
        if isinstance(out.get(key), list):
            out[key] = [x for x in out[key] if not _names_hidden(x, h)]
    latest = out.get("latest")
    if isinstance(latest, dict) and (h.run(latest.get("run")) or _names_hidden(latest, h)):
        out["latest"] = None
    table = out.get("failure_table")
    if isinstance(table, dict):
        out["failure_table"] = {
            rid: {**t, "runs": {k: v for k, v in t["runs"].items() if not h.run(k)}}
            if isinstance(t, dict) and isinstance(t.get("runs"), dict) else t
            for rid, t in table.items()
        }  # fmt: skip
    return out


def _names_hidden(x: Any, h: Hidden) -> bool:
    """A timeline entry, next step or ``latest`` that belongs to a hidden story or names a
    hidden run anywhere in its text (``run N``, ``da50-*``, ``jig-n``...)."""
    if not isinstance(x, dict):
        return False
    if h.story(x.get("story")) or h.run(x.get("run")):
        return True
    text = json.dumps(x, ensure_ascii=False, default=str)
    if any(re.search(rf"(?<![\w-]){re.escape(s)}(?![\w])", text) for s in h.stories):
        return True
    return h.mentions(text)
