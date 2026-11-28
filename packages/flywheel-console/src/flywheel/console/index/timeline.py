"""Project progression for the chat and the Home page (``seed/timeline.yaml``).

Decision of Hiếu, 28/11/2026 evening (audit 05 · Đánh giá chat mục 6): the chat must know the
work from 18/11 to now and the latest presented result, and must not offer round 1's tickets as
a next step. ``story.json`` gets:

- ``timeline``: ``[{date, story, title{vi,en}, result{vi,en}|null, doc, round}]``, from the seed;
  every quote is found verbatim in its doc and every number of ``result`` is in a quote (or is a
  listed sum of quoted numbers), checked by ``verify``.
- ``latest``: ``{round, run, date}``, the newest round whose baseline has a presented eval.
- ``next_steps``: ``[{text{vi,en}, doc, round}]``, from the seed.
- ``failure_table``: ``{<round>: {scorer_version, runs: {<run>: {labels, failed, n}}}}``, from the
  eval reads already in the index (``story.pair`` and ``story.jig``), never from the seed.
- ``historical``/``closed`` on round 1's interventions and checks that name a seed ticket.

Run N and its story are hidden by ``hidden.story``; results in ``withhold_eval`` are left out of
``failure_table`` here.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from flywheel.console.index.tasks import Manifest
    from flywheel.console.paths import ConsolePaths

FILE = "timeline.yaml"
# a number not glued to a letter, digit, underscore or dot: "C_70", "jig2", "60k" are names
_SEP = "[ \u00a0\u202f]"  # thousands separator: space, no-break space, narrow no-break
_NUM = re.compile(r"(?<![\w.])\d+(?:" + _SEP + r"\d{3})*(?:[.,]\d+)?(?![\w])")


def numbers(text: str) -> set[str]:
    """The numbers written in ``text``, normalised: "100 000" → "100000", "56,15" → "56.15"."""
    out: set[str] = set()
    for m in _NUM.finditer(text or ""):
        out.add(re.sub(_SEP, "", m.group()).replace(",", "."))
    return out


def _day(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)


def load(paths: ConsolePaths) -> dict[str, Any]:
    f = paths.seed / FILE
    if not f.is_file():
        return {}
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _doc(sources: list[dict[str, Any]]) -> str:
    """``docs/x.md §4, §5``: the docs of the sources with their sections, in order."""
    by: dict[str, list[str]] = {}
    for s in sources:
        secs = by.setdefault(s["doc"], [])
        if s["section"] not in secs:
            secs.append(str(s["section"]))
    return "; ".join(f"{d} " + ", ".join(f"§{x}" for x in secs) for d, secs in by.items())


def verify(paths: ConsolePaths) -> list[str]:
    """Problems of the seed: a quote not in its doc, a number of a result or next step that no
    quote writes (nor a listed sum), or an English text whose numbers differ."""
    data = load(paths)
    texts: dict[str, str] = {}
    bad: list[str] = []

    def text_of(doc: str) -> str:
        if doc not in texts:
            f = paths.repo / doc
            texts[doc] = f.read_text(encoding="utf-8") if f.is_file() else ""
        return texts[doc]

    def check(where: str, sources: list[dict[str, Any]], said: dict[str, str] | None,
              sums: list[list[float]]) -> None:  # fmt: skip
        quoted: set[str] = set()
        for s in sources:
            if s["quote"] not in text_of(s["doc"]):
                bad.append(f"{where}: quote not in {s['doc']}: {s['quote'][:60]}")
            quoted |= numbers(s["quote"])
        allowed = quoted | {_fmt(sum(x)) for x in sums if {_fmt(v) for v in x} <= quoted}
        if said:
            vi, en = numbers(said.get("vi", "")), numbers(said.get("en", ""))
            if not vi <= allowed:
                bad.append(f"{where}: numbers {sorted(vi - allowed)} are in no quote")
            if vi != en:
                bad.append(f"{where}: vi numbers {sorted(vi)} != en numbers {sorted(en)}")

    for i, e in enumerate(data.get("timeline") or []):
        check(f"timeline[{i}] {e.get('story')}", e["sources"], e.get("result"), e.get("sums") or [])
    for i, n in enumerate(data.get("next_steps") or []):
        check(f"next_steps[{i}]", n["sources"], n.get("text"), n.get("sums") or [])
    for t in data.get("tickets") or []:
        check(f"tickets {t.get('id')}", [t["source"]], None, [])
    return bad


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def timeline(paths: ConsolePaths) -> list[dict[str, Any]]:
    out = []
    for e in load(paths).get("timeline") or []:
        out.append(
            {
                "date": _day(e["date"]),
                "story": e["story"],
                "title": dict(e["title"]),
                "result": dict(e["result"]) if e.get("result") else None,
                "doc": _doc(e["sources"]),
                "round": e.get("round"),
            }
        )
    return sorted(out, key=lambda x: x["date"] or "")  # stable: same-day entries keep seed order


def next_steps(paths: ConsolePaths) -> list[dict[str, Any]]:
    return [
        {"text": dict(n["text"]), "doc": _doc(n["sources"]), "round": n.get("round")}
        for n in load(paths).get("next_steps") or []
    ]


def tickets(paths: ConsolePaths) -> dict[str, dict[str, Any]]:
    """Round 1's tickets: ``{id: {closed, handled_by?, source}}``."""
    out: dict[str, dict[str, Any]] = {}
    for t in load(paths).get("tickets") or []:
        s = t["source"]
        out[t["id"]] = {"closed": _day(t.get("closed"))} | (
            {"handled_by": t["handled_by"]} if t.get("handled_by") else {}
        ) | {"source": f"{s['doc']} §{s['section']}"}  # fmt: skip
    return out


_TICKET = re.compile(r"\bDA-\d+\b")


def mark_historical(items: Any, known: dict[str, dict[str, Any]]) -> Any:
    """Each dict of ``items`` whose ``ticket`` (or ``intervention``) names a known ticket gets
    ``historical: true``, ``closed`` and, when given, ``handled_by``: it is history, never a
    next step. Other items are unchanged."""
    if not isinstance(items, list) or not known:
        return items
    out: list[Any] = []
    for x in items:
        if isinstance(x, dict):
            tid = x.get("ticket")
            if tid not in known and isinstance(x.get("value"), dict):
                tid = x["value"].get("ticket")  # demo.diagnose.checks: cited entries
            if tid not in known:
                m = _TICKET.search(str(x.get("intervention") or ""))
                tid = m.group() if m else None
            if tid in known:
                t = known[tid]
                x = {**x, "historical": True, "closed": t["closed"]}
                if t.get("handled_by"):
                    x["handled_by"] = t["handled_by"]
        out.append(x)
    return out


# ------------------------------------------------------------------ from the index
def failure_table(
    manifest: Manifest, pair: dict[str, Any], jig_block: dict[str, Any]
) -> dict[str, Any]:
    """Failure labels per run of each round, as the Eval page shows them: round 1 from
    ``story.pair.runs[]`` (scorer 1), the jig round from the ready evals of ``story.jig``.
    Runs in ``withhold_eval`` are left out; ``failed`` is ``n - successes``."""
    out: dict[str, Any] = {}
    srnd = manifest.story_round()
    if srnd is not None and isinstance(pair.get("runs"), list):
        held = set(srnd.withhold_eval)
        runs = {}
        for r in pair["runs"]:
            if not isinstance(r, dict) or r.get("run") in held or r.get("n") is None:
                continue
            runs[r["run"]] = _row(r.get("failures"), r.get("successes"), r.get("n"))
        if runs:
            out[srnd.id] = {"scorer_version": srnd.scorer_version, "runs": runs}
    jrnd = manifest.jig_round()
    if jrnd is not None and isinstance(jig_block.get("evals"), list):
        held = set(jrnd.withhold_eval)
        runs = {}
        for e in jig_block["evals"]:
            if not isinstance(e, dict) or e.get("status") != "ready" or e.get("run") in held:
                continue
            h = e.get("headline") or {}
            runs[e["run"]] = _row(h.get("failures"), h.get("successes"), h.get("n"))
        if runs:
            out[jrnd.id] = {"scorer_version": jrnd.scorer_version, "runs": runs}
    return out


def _row(failures: Any, successes: Any, n: Any) -> dict[str, Any]:
    labels = dict(sorted((failures or {}).items(), key=lambda kv: (-kv[1], kv[0])))
    failed = n - successes if isinstance(n, int) and isinstance(successes, int) else None
    return {"labels": labels, "failed": failed, "n": n}


def presented(manifest: Manifest, pair: dict[str, Any], jig_block: dict[str, Any]
              ) -> dict[str, dict[str, Any]]:  # fmt: skip
    """``{round: {run, successes, n}}``: the baseline result each round presents (round 1 from
    ``story.pair``, the jig round from its ready baseline eval)."""
    out: dict[str, dict[str, Any]] = {}
    srnd = manifest.story_round()
    if srnd is not None:
        r = next((x for x in pair.get("runs") or []
                  if isinstance(x, dict) and x.get("run") == srnd.baseline), None)  # fmt: skip
        if r and r.get("n") is not None and srnd.baseline not in srnd.withhold_eval:
            out[srnd.id] = {"run": srnd.baseline, "successes": r.get("successes"), "n": r["n"]}
    jrnd = manifest.jig_round()
    if jrnd is not None:
        e = next((x for x in jig_block.get("evals") or []
                  if isinstance(x, dict) and x.get("role") == "baseline"), None)  # fmt: skip
        if e and e.get("status") == "ready" and jrnd.baseline not in jrnd.withhold_eval:
            h = e.get("headline") or {}
            out[jrnd.id] = {"run": jrnd.baseline, "successes": h.get("successes"), "n": h.get("n")}
    return out


def latest(
    manifest: Manifest, shown: dict[str, dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The newest round (manifest order) whose baseline has a presented eval, with the date of
    the newest timeline entry of that round."""
    for rnd in reversed(manifest.rounds):
        if rnd.id in shown:
            dates = [e["date"] for e in events if e.get("round") == rnd.id and e.get("date")]
            return {"round": rnd.id, "run": shown[rnd.id]["run"],
                    "date": max(dates) if dates else None}  # fmt: skip
    return None
