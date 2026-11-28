# ruff: noqa: E501  (one row per line)
"""``failure_table``, ``train_progress`` and ``project_status``: data rows for three common questions.

"Show me every failure label", "how is training going", "where does the project stand" had no
tool of their own, so they were answered from the round report (audit 05, 28/11/2026). These
tools return labelled data rows only (``SECTION | key=value | ...``, header row first), never
sentences to copy or instructions; how to write the answer lives in the system prompt. Words
(failure names, states, titles) are in the user's language, numbers in the user's decimal style.
Doc references go in ``Result["sources"]``.

Holds, as for every chat tool: a run under ``withhold_eval`` (C70_R1) never gets a failure count
or a result; its training numbers may appear, last and never ranked. A hidden run or story
(``withhold_runs``: run N, DA-50) never appears. A next step marked ``historical`` is never offered.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from .common import Result, cols, fail, hidden_runs, result, story, table
from .tools_round import COST_LINE, Say, held_runs, manifest, rounds_named, runs_named

# failure labels of the scorer in plain words (design 28/11/2026 §1); a code never reaches a value
FAIL_NAME = {
    "L-PLACE-POSE": ("Đặt lệch", "Misplaced"),
    "L-TRAY-TILT": ("Khay nghiêng", "Tray tilted"),
    "L-TIMEOUT": ("Hết giờ", "Timed out"),
    "L-PART-DROP": ("Rơi khay", "Tray dropped"),
    "L-ONE-HAND": ("Chỉ cầm một tay", "One hand only"),
}
ROLE_WORD = {"baseline": ("bản gốc", "baseline"), "control": ("bản đối chứng", "control"),
             "after_round": ("bản sau vòng", "after the round")}  # fmt: skip
KIND = {"measured": ("thực đo", "measured"), "estimated": ("ước tính", "estimated")}
TREND = {"falling": ("giảm", "falling"), "flat": ("đi ngang", "flat"), "rising": ("tăng", "rising")}
LOSS_NOTE = (
    "Loss train không phải thước đo kết quả.",
    "Training loss is not a measure of the result.",
)
FLAT = 0.10  # a relative change of the late-loss mean under 10 % reads as flat
END_POINTS = 20  # the loss at the end is the mean of the last 20 logged points

_NEXT_RX = re.compile(
    r"nên làm|làm gì|tiếp theo|bước tiếp|what next|next step|should we|to do", re.I
)
_TIMELINE_RX = re.compile(r"diễn tiến|tiến trình|đã làm|từ \d|timeline|history|so far|since", re.I)


# ------------------------------------------------------------------ rows
def _val(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v)).replace("|", "/").strip()


def row(section: str, pairs: Iterable[tuple[str, Any]]) -> str:
    """``SECTION | key=value | ...``; a pair whose value is None or "" is left out."""
    parts = [section] + [f"{k}={_val(v)}" for k, v in pairs if v is not None and v != ""]
    return " | ".join(parts)


def _num(say: Say, x: Any, d: int = 2) -> str | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return str(x) if isinstance(x, int) else say.num(x, d)


def _pct(say: Say, p: Any) -> str | None:
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        return None
    return say.pct(p) + say(" %", "%")


def _flag(v: Any) -> str:
    return "missing" if v is None else ("yes" if v else "no")


def _fail_name(say: Say, code: str) -> str:
    w = FAIL_NAME.get(code)
    if w:
        return w[0 if say.vi else 1]
    return code.removeprefix("L-").replace("-", " ").replace("_", " ").lower()


def _sources(*refs: Any) -> list[str]:
    out: list[str] = []
    for r in refs:
        items = r if isinstance(r, list) else [r]
        for x in items:
            if isinstance(x, str) and x.strip() and x.strip() not in out:
                out.append(x.strip())
    return out


# ------------------------------------------------------------------ holds
class _Holds:
    """The held runs (no test result) and the hidden runs and stories (nothing at all)."""

    def __init__(self) -> None:
        self.held = set(held_runs())
        self.hidden = hidden_runs()

    def shown(self, run: Any) -> bool:
        """A run whose test result may be given."""
        return isinstance(run, str) and run not in self.held and not self.hidden.run(run)

    def trained(self, run: Any) -> bool:
        """A run whose training numbers may be given (a held run's may; a hidden run's never)."""
        return isinstance(run, str) and bool(run) and not self.hidden.run(run)

    def clean(self, entry: Any) -> bool:
        """A timeline or next-step entry that names no hidden run or story and no held run."""
        if not isinstance(entry, dict):
            return False
        if self.hidden.story(entry.get("story")):
            return False
        text = json.dumps(entry, ensure_ascii=False, default=str)
        if self.hidden.mentions(text):
            return False
        names = sorted(
            self.held | set(self.hidden.stories) | {i for i in self.hidden.ids if len(i) > 2}
        )
        if any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text) for n in names):
            return False
        # a one-letter run id ("N") only as "run N" / "lượt N" / "bản N"
        short = [re.escape(i) for i in self.hidden.ids if len(i) <= 2]
        return not (
            short
            and re.search(rf"(?i:run|lượt|bản|model|policy)\s+(?:{'|'.join(short)})(?![\w])", text)
        )


# ------------------------------------------------------------------ task and rounds
def _task(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any] | None:
    tasks = [t for t in manifest().get("tasks") or [] if isinstance(t, dict)]
    want = str(args.get("task") or ctx.get("task") or "")
    return (next((t for t in tasks if t.get("id") == want), None)
            or next((t for t in tasks if t.get("rounds")), None) or (tasks[0] if tasks else None))  # fmt: skip


def _round_map() -> dict[str, dict[str, Any]]:
    rounds = manifest().get("rounds") or []
    return {str(r["id"]): r for r in rounds if isinstance(r, dict) and r.get("id")}


def _run_ids(rnd: dict[str, Any]) -> list[str]:
    return [str(x.get("id")) for x in rnd.get("runs") or [] if isinstance(x, dict) and x.get("id")]


def _select(
    task: dict[str, Any], args: dict[str, Any], ctx: dict[str, Any]
) -> list[dict[str, Any]] | Result:
    """The round in ``args``, else the rounds (or runs) the question names, else every round of
    the task with the selected one first. A round ``args`` names that the task lacks fails."""
    rm = _round_map()
    ids = [str(i) for i in task.get("rounds") or [] if str(i) in rm]
    want = str(args.get("round") or "")
    if want:
        if want not in ids:
            return fail(f"No round '{want}' in task {task.get('id')}.", ids)
        return [rm[want]]
    q = str(ctx.get("question") or "")
    chosen = [r for r in rounds_named(q) if r in ids]
    runs = runs_named(q)
    chosen += [i for i in ids if runs & set(_run_ids(rm[i]))]
    chosen = list(dict.fromkeys(chosen))
    if not chosen:
        cur = str(ctx.get("round") or "")
        chosen = sorted(ids, key=lambda i: i != cur)
    return [rm[i] for i in chosen]


def _jig(rnd: dict[str, Any], s: dict[str, Any]) -> dict[str, Any] | None:
    """``story.jig`` when it belongs to this round (never another round's block)."""
    j = s.get("jig")
    if "story.jig" not in (rnd.get("index") or []) or not isinstance(j, dict) or not j:
        return None
    return j if j.get("round") in (None, rnd.get("id")) else None


def _is_pair(rnd: dict[str, Any]) -> bool:
    return any(k in (rnd.get("index") or []) for k in ("story.pair", "story.runs"))


def _round_head(say: Say, rnd: dict[str, Any], extra: Iterable[tuple[str, Any]] = ()) -> str:
    return row("ROUND", [("id", rnd.get("id")), ("title", say.name(rnd.get("title"))),
                         ("number", rnd.get("number")), ("scene", rnd.get("scene")), *extra])  # fmt: skip


def _order(runs: Iterable[str], rnd: dict[str, Any]) -> list[str]:
    """Runs in the round's own order, then any other in the order given."""
    own = _run_ids(rnd)
    rest = list(dict.fromkeys(runs))
    return [r for r in own if r in rest] + [r for r in rest if r not in own]


# ------------------------------------------------------------------ failure_table
def _counts(
    rnd: dict[str, Any], s: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], Any, str | None]:
    """{run: {labels, failed, n}}, the scorer version, and the fallback key used (None when the
    index has ``story.failure_table`` for the round)."""
    rid = str(rnd.get("id"))
    ft = s.get("failure_table")
    if isinstance(ft, dict) and isinstance(ft.get(rid), dict):
        e = ft[rid]
        runs = {str(k): v for k, v in (e.get("runs") or {}).items() if isinstance(v, dict)}
        return runs, e.get("scorer_version", rnd.get("scorer_version")), None
    j = _jig(rnd, s)
    if j is not None:
        out: dict[str, dict[str, Any]] = {}
        for ev in j.get("evals") or []:
            h = ev.get("headline") if isinstance(ev, dict) else None
            if isinstance(h, dict) and ev.get("run"):
                n, k = h.get("n"), h.get("successes")
                failed = n - k if isinstance(n, int) and isinstance(k, int) else None
                out[str(ev["run"])] = {"labels": h.get("failures") or {}, "failed": failed, "n": n}
        return out, j.get("scorer_version", rnd.get("scorer_version")), "story.jig.evals"
    if _is_pair(rnd):
        own = set(_run_ids(rnd))
        out = {}
        for r in (s.get("pair") or {}).get("runs") or []:
            if isinstance(r, dict) and r.get("run") in own:
                n, k = r.get("n"), r.get("successes")
                failed = n - k if isinstance(n, int) and isinstance(k, int) else None
                out[str(r["run"])] = {"labels": r.get("failures") or {}, "failed": failed, "n": n}
        return out, rnd.get("scorer_version"), "story.pair.runs"
    return {}, rnd.get("scorer_version"), "story.failure_table"


def _differs(a: dict[str, Any], b: dict[str, Any], key: str, mine: Any, theirs: Any) -> Any:
    """``links`` of either round when they name the other one, else the two values compared;
    None when a value is missing."""
    for x, y in ((a, b), (b, a)):
        for link in (x.get("links") or {}).values():
            if isinstance(link, dict) and link.get("round") == y.get("id") and key in link:
                return bool(link[key])
    if mine is None and theirs is None:
        return None
    if key == "scene_differs":  # a round without a scene is on the plain tables (no jig)
        return mine != theirs
    if mine is None or theirs is None:
        return None
    return mine != theirs


def failure_table(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Failure labels by run for each round (or the round asked about), with failed and n per run."""
    say = Say(ctx.get("lang"))
    task = _task(args, ctx)
    if task is None:
        return fail("No task manifest in the index (run: fw console index).")
    sel = _select(task, args, ctx)
    if not isinstance(sel, list):
        return sel
    holds = _Holds()
    s = story()
    lines = [row("FAILURE_TABLE", [("task", task.get("id")), ("title", say.name(task.get("name"))),
                                   ("rounds", ",".join(str(r.get("id")) for r in sel))])]  # fmt: skip
    ui_rows: list[dict[str, Any]] = []
    labels_ui: list[str] = []
    missing: list[str] = []
    fallback: list[str] = []
    scorers: dict[str, Any] = {}
    srcs: list[Any] = []
    for rnd in sel:
        rid = str(rnd.get("id"))
        counts, scorer, fb = _counts(rnd, s)
        scorers[rid] = scorer
        if fb:
            missing.append(f"story.failure_table.{rid}")
            if counts:
                fallback.append(fb)
        runs = [r for r in _order(counts, rnd) if holds.shown(r)]
        lines.append(_round_head(say, rnd, [("scorer", f"v{scorer}" if scorer is not None else None),
                                            ("runs", ",".join(runs) or None),
                                            ("missing", "scorer" if scorer is None else None)]))  # fmt: skip
        srcs.append(rnd.get("doc"))
        if not runs:
            lines.append(row("FAILURE", [("round", rid), ("missing", "counts")]))
            continue
        tot: dict[str, int] = {}
        for r in runs:
            for code, v in (counts[r].get("labels") or {}).items():
                if isinstance(v, int):
                    tot[str(code)] = tot.get(str(code), 0) + v
        known = list(FAIL_NAME)
        codes = sorted(
            tot, key=lambda c: (-tot[c], known.index(c) if c in known else len(known), c)
        )
        for code in codes:
            name = _fail_name(say, code)
            labels_ui.append(name)
            per = [(r, (counts[r].get("labels") or {}).get(code, 0)) for r in runs]
            lines.append(row("FAILURE", [("round", rid), ("label", name), *per]))
        for r in runs:
            c = counts[r]
            lines.append(row("RUN", [("round", rid), ("run", r), ("failed", c.get("failed")),
                                     ("n", c.get("n"))]))  # fmt: skip
            ui = {"round": rid, "run": r, "failed": c.get("failed"), "n": c.get("n")}
            ui.update({_fail_name(say, k): v for k, v in (c.get("labels") or {}).items()})
            ui_rows.append(ui)
    if len(sel) > 1:
        a = sel[0]
        for b in sel[1:]:
            sc = _differs(
                a, b, "scorer_differs", scorers.get(str(a.get("id"))), scorers.get(str(b.get("id")))
            )
            sn = _differs(a, b, "scene_differs", a.get("scene"), b.get("scene"))
            comparable = "no" if sc or sn else ("yes" if sc is False and sn is False else "missing")
            lines.append(row("COMPARE", [("rounds", f"{a.get('id')},{b.get('id')}"), ("comparable", comparable),
                                         ("scorer_differs", _flag(sc)), ("scene_differs", _flag(sn))]))  # fmt: skip
    if missing:
        lines.append(row("MISSING", [("missing", ",".join(missing)),
                                     ("fallback", ",".join(dict.fromkeys(fallback)) or None)]))  # fmt: skip
    names = list(dict.fromkeys(labels_ui))
    title = say("Nhãn lỗi theo run", "Failure labels by run")
    out = result(
        table(title, cols("round", "run", *names, "failed", "n"), ui_rows, link="#/eval"),
        "\n".join(lines),
    )
    out["sources"] = _sources(*srcs)
    if len(sel) == 1:
        out["round"] = str(sel[0].get("id"))
    return out


# ------------------------------------------------------------------ train_progress
def _points(v: Any) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in v if isinstance(v, list) else []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            a, b = p[0], p[1]
            if (
                isinstance(a, (int, float))
                and isinstance(b, (int, float))
                and not isinstance(b, bool)
            ):
                out.append((float(a), float(b)))
    return out


def _loss(say: Say, v: Any) -> list[tuple[str, Any]]:
    """The loss as a trend only: first value, mean of the last points, and the late trend (mean
    of the third quarter of the steps against the fourth). Never a quality word."""
    pts = _points(v)
    if len(pts) < 4:
        return [("missing", "loss")]
    last = pts[-END_POINTS:]
    end = sum(x for _, x in last) / len(last)
    top = pts[-1][0]
    q3 = [x for st, x in pts if top / 2 <= st < 3 * top / 4]
    q4 = [x for st, x in pts if st >= 3 * top / 4]
    trend: str | None = None
    if q3 and q4:
        m3, m4 = sum(q3) / len(q3), sum(q4) / len(q4)
        rel = (m4 - m3) / m3 if m3 else 0.0
        trend = "flat" if abs(rel) < FLAT else ("falling" if rel < 0 else "rising")
    tw = TREND.get(trend or "")
    lo, hi = (round(top / 2, -2), round(top, -2)) if top >= 1000 else (top / 2, top)
    return [("loss_first", _num(say, pts[0][1])), (f"loss_end_mean{len(last)}", _num(say, end)),
            ("loss_trend_late", tw[0 if say.vi else 1] if tw else None),
            ("late_window", f"{int(lo)}-{int(hi)}" if trend else None)]  # fmt: skip


def _phases(say: Say, ph: Any, steps: Any, speed: Any) -> list[tuple[str, Any]]:
    """Hours of the VM phases (setup, train, persist). When the train phase is too short to hold
    every step at the logged speed (a run resumed on a second VM), the phases cover part of the
    run only, and ``vm_cover`` says so."""
    if not isinstance(ph, dict) or not ph:
        return [("missing", "vm_phases")]
    sec = {k: v for k, v in ph.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    setup = sum(v for k, v in sec.items() if k.startswith("setup"))
    has_setup = any(k.startswith("setup") for k in sec)
    total = sum(sec.values())
    gone = [k for k in ("setup", "train", "persist") if not any(x.startswith(k) for x in sec)]
    cover = None
    if "train" in sec and isinstance(steps, int) and isinstance(speed, (int, float)) and speed > 0:
        part = sec["train"] * speed < 0.9 * steps
        cover = say("một phần run", "part of the run") if part else say("cả run", "whole run")
    return [("vm_hours", _num(say, total / 3600)),
            ("vm_setup_h", _num(say, setup / 3600) if has_setup else None),
            ("vm_train_h", _num(say, sec["train"] / 3600) if "train" in sec else None),
            ("vm_persist_h", _num(say, sec["persist"] / 3600) if "persist" in sec else None),
            ("vm_cover", cover), ("missing", ",".join("vm_" + g for g in gone) or None)]  # fmt: skip


def _train_rows(rnd: dict[str, Any], s: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Training entries of the round's runs by run label (``branch``)."""
    own = set(_run_ids(rnd))
    j = _jig(rnd, s)
    pool = list((j or {}).get("runs") or []) + list(s.get("runs") or [] if _is_pair(rnd) else [])
    out: dict[str, dict[str, Any]] = {}
    for r in pool:
        if isinstance(r, dict) and r.get("branch") in own and str(r["branch"]) not in out:
            out[str(r["branch"])] = r
    return out


def train_progress(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Training of each presented run of the round(s): steps, speed, hours by phase, measured CU,
    and the loss as a trend only."""
    say = Say(ctx.get("lang"))
    task = _task(args, ctx)
    if task is None:
        return fail("No task manifest in the index (run: fw console index).")
    sel = _select(task, args, ctx)
    if not isinstance(sel, list):
        return sel
    holds = _Holds()
    s = story()
    lines = [row("TRAIN", [("task", task.get("id")), ("title", say.name(task.get("name"))),
                           ("rounds", ",".join(str(r.get("id")) for r in sel))])]  # fmt: skip
    ui_rows: list[dict[str, Any]] = []
    srcs: list[Any] = []
    missing: list[str] = []
    for rnd in sel:
        rid = str(rnd.get("id"))
        spec = {str(x.get("id")): x for x in rnd.get("runs") or [] if isinstance(x, dict)}
        tr = _train_rows(rnd, s)
        runs = [r for r in _order(tr, rnd) if holds.trained(r)]
        runs = [r for r in runs if r not in holds.held] + [r for r in runs if r in holds.held]
        lines.append(
            _round_head(
                say, rnd, [("max_steps", rnd.get("max_steps")), ("runs", ",".join(runs) or None)]
            )
        )
        srcs.append(rnd.get("doc"))
        if not runs:
            missing.append(f"train runs of {rid}")
        for r in runs:
            e = tr[r]
            mx, st, ck = (
                e.get("max_steps") or rnd.get("max_steps"),
                e.get("step"),
                e.get("ckpt_step"),
            )
            done_n = st + 1 if isinstance(st, int) else ck if isinstance(ck, int) else None
            if isinstance(done_n, int) and isinstance(mx, int):
                done_n = min(done_n, mx)
            finished = (isinstance(done_n, int) and isinstance(mx, int) and done_n >= mx) or e.get(
                "fetched_train"
            ) == "done"
            state = say("xong", "finished") if finished else say("chưa xong", "not finished")
            steps = f"{done_n}/{mx}" if done_n is not None and mx is not None else None
            role = (spec.get(r) or {}).get("role")
            phases = _phases(say, e.get("vm_phases"), done_n, e.get("steps_per_s"))
            lines.append(row("RUN", [("round", rid), ("run", r), ("role", say(*ROLE_WORD[role]) if role in ROLE_WORD else None),
                                     ("steps", steps), ("state", state),
                                     ("steps_per_s", _num(say, e.get("steps_per_s"))),
                                     *phases, *_loss(say, e.get("loss"))]))  # fmt: skip
            ui_rows.append({"round": rid, "run": r, "steps": steps, "state": state,
                            "steps_per_s": _num(say, e.get("steps_per_s")),
                            "vm_hours": dict(phases).get("vm_hours")})  # fmt: skip
        lines += _train_cost(say, rnd, s, runs, srcs)
    lines.append(row("LOSS_NOTE", [("text", say(*LOSS_NOTE))]))
    if missing:
        lines.append(row("MISSING", [("missing", ",".join(missing))]))
    title = say("Tiến độ train", "Training progress")
    out = result(
        table(
            title,
            cols("round", "run", "steps", "state", "steps_per_s", "vm_hours"),
            ui_rows,
            link="#/runs",
        ),
        "\n".join(lines),
    )
    out["sources"] = _sources(*srcs)
    if len(sel) == 1:
        out["round"] = str(sel[0].get("id"))
    return out


def _train_cost(
    say: Say, rnd: dict[str, Any], s: dict[str, Any], runs: list[str], srcs: list[Any]
) -> list[str]:
    """Measured training CU: ``story.jig.cost.train`` for the jig round's run; for a pair round
    the training lines of ``story.demo.round_cost``, which are per training batch, not per run."""
    rid = str(rnd.get("id"))
    j = _jig(rnd, s)
    if j is not None:
        c = (j.get("cost") or {}).get("train") if isinstance(j.get("cost"), dict) else None
        if isinstance(c, dict) and c.get("cu") is not None:
            kind = KIND.get(str(c.get("measure_kind")))
            srcs.append(c.get("source"))
            run = runs[0] if len(runs) == 1 else None
            return [row("COST", [("round", rid), ("run", run), ("part", say("train", "training")),
                                 ("cu", _num(say, c["cu"])), ("kind", kind[0 if say.vi else 1] if kind else None),
                                 ("story", c.get("story")), ("missing", None if kind else "measure_kind")])]  # fmt: skip
        return [row("COST", [("round", rid), ("missing", "story.jig.cost.train")])]
    if _is_pair(rnd):
        rc = (s.get("demo") or {}).get("round_cost") or {}
        out = []
        kind = KIND.get(str(rc.get("kind") or rc.get("measure_kind")))
        for x in rc.get("lines") or []:
            if (
                isinstance(x, dict)
                and str(x.get("id", "")).startswith("train")
                and x.get("value") is not None
            ):
                w = COST_LINE.get(str(x["id"]))
                srcs.append(x.get("source"))
                out.append(row("COST", [("round", rid), ("part", say(*w) if w else x["id"]),
                                        ("cu", _num(say, x["value"])), ("kind", kind[0 if say.vi else 1] if kind else None),
                                        ("scope", say("một lô train, không phải một run", "one training batch, not one run"))]))  # fmt: skip
        return out or [row("COST", [("round", rid), ("missing", "story.demo.round_cost")])]
    return []


# ------------------------------------------------------------------ project_status
def _headline(
    say: Say, rid: str, run: str, s: dict[str, Any], holds: _Holds
) -> list[tuple[str, Any]]:
    """The headline numbers of one presented run of a round (``story.jig`` or ``story.pair``)."""
    if not holds.shown(run):
        return []
    rnd = _round_map().get(rid) or {}
    j = _jig(rnd, s) if rnd else None
    if j is not None:
        ev = next(
            (e for e in j.get("evals") or [] if isinstance(e, dict) and e.get("run") == run), None
        )
        h = (ev or {}).get("headline") or {}
        if h.get("n"):
            pl = (ev or {}).get("place") or {}
            return [("successes", h.get("successes")), ("n", h.get("n")), ("pct", _pct(say, h.get("p"))),
                    ("place_pct", _pct(say, pl.get("p"))), ("scene", j.get("scene")),
                    ("scorer", f"v{j['scorer_version']}" if j.get("scorer_version") is not None else None)]  # fmt: skip
    for r in (s.get("pair") or {}).get("runs") or []:
        if isinstance(r, dict) and r.get("run") == run and r.get("n"):
            p = r.get("p", r["successes"] / r["n"] if isinstance(r.get("successes"), int) else None)
            return [("successes", r.get("successes")), ("n", r.get("n")), ("pct", _pct(say, p))]
    return []


def project_status(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Where the project stands: the latest presented result, the dated timeline, the next steps
    in the docs, and how the rounds of the task link to each other."""
    say = Say(ctx.get("lang"))
    task = _task(args, ctx)
    if task is None:
        return fail("No task manifest in the index (run: fw console index).")
    holds = _Holds()
    s = story()
    rm = _round_map()
    missing: list[str] = []
    srcs: list[Any] = []
    ui_rows: list[dict[str, Any]] = []
    head = row("STATUS", [("task", task.get("id")), ("title", say.name(task.get("name"))),
                          ("default_round", task.get("default_round"))])  # fmt: skip
    if task.get("default_round") is None:
        missing.append("tasks.default_round")

    latest: list[str] = []
    lt = s.get("latest")
    if (
        isinstance(lt, dict)
        and lt.get("round")
        and holds.trained(lt.get("run"))
        and holds.shown(lt.get("run"))
    ):
        rid, run = str(lt["round"]), str(lt.get("run") or "")
        nums = _headline(say, rid, run, s, holds)
        latest.append(row("LATEST", [("round", rid), ("title", say.name((rm.get(rid) or {}).get("title"))),
                                     ("run", run), ("date", lt.get("date")), *nums,
                                     ("missing", None if nums else "headline")]))  # fmt: skip
        srcs.append((rm.get(rid) or {}).get("doc"))
        ui_rows.append({"part": "latest", "date": lt.get("date"), "round": rid, "run": run,
                        "what": dict(nums).get("pct")})  # fmt: skip
    else:
        missing.append("story.latest")

    timeline: list[str] = []
    tl = s.get("timeline")
    if isinstance(tl, list):
        entries = sorted((e for e in tl if holds.clean(e)), key=lambda e: str(e.get("date") or ""))
        for e in entries:
            timeline.append(row("EVENT", [("date", e.get("date")), ("story", e.get("story")),
                                          ("round", e.get("round")), ("title", say.name(e.get("title"))),
                                          ("result", say.name(e.get("result")) if e.get("result") else None)]))  # fmt: skip
            srcs.append(e.get("doc"))
            ui_rows.append({"part": "timeline", "date": e.get("date"), "round": e.get("round"),
                            "run": e.get("story"), "what": say.name(e.get("title"))})  # fmt: skip
    else:
        missing.append("story.timeline")

    nexts: list[str] = []
    ns = s.get("next_steps")
    if isinstance(ns, list):
        for e in ns:
            if not holds.clean(e) or e.get("historical") is True:
                continue
            nexts.append(row("NEXT", [("round", e.get("round")), ("text", say.name(e.get("text"))),
                                      ("doc", e.get("doc"))]))  # fmt: skip
            srcs.append(e.get("doc"))
            ui_rows.append({"part": "next", "date": None, "round": e.get("round"), "run": None,
                            "what": say.name(e.get("text"))})  # fmt: skip
    else:
        missing.append("story.next_steps")

    rounds: list[str] = []
    has_links = False
    for rid in [str(i) for i in task.get("rounds") or [] if str(i) in rm]:
        rnd = rm[rid]
        rounds.append(
            _round_head(
                say, rnd, [("default", "yes" if rid == task.get("default_round") else "no")]
            )
        )
        srcs.append(rnd.get("doc"))
        links = rnd.get("links")
        if not isinstance(links, dict):
            continue
        has_links = True
        for way in ("prev", "next"):
            ln = links.get(way)
            if not isinstance(ln, dict) or not ln.get("round"):
                continue
            show = holds.shown(ln.get("run"))
            rounds.append(row("LINK", [("from", rid), ("way", way), ("round", ln.get("round")),
                                       ("run", ln.get("run") if show else None),
                                       ("successes", ln.get("successes") if show else None),
                                       ("n", ln.get("n") if show else None),
                                       ("carried", ln.get("carried") if show else None),
                                       ("placed", ln.get("placed") if show else None),
                                       ("scene_differs", _flag(ln.get("scene_differs")) if "scene_differs" in ln else None),
                                       ("scorer_differs", _flag(ln.get("scorer_differs")) if "scorer_differs" in ln else None)]))  # fmt: skip
    if not has_links:
        missing.append("tasks.rounds.links")

    q = str(ctx.get("question") or "")
    if _NEXT_RX.search(q):
        body = nexts + latest + timeline + rounds
    elif _TIMELINE_RX.search(q):
        body = timeline + latest + nexts + rounds
    else:
        body = latest + timeline + nexts + rounds
    lines = [head, *body]
    if missing:
        lines.append(row("MISSING", [("missing", ",".join(missing))]))
    title = say("Tình hình dự án", "Project status")
    out = result(
        table(title, cols("part", "date", "round", "run", "what"), ui_rows, link="#/"),
        "\n".join(lines),
    )
    out["sources"] = _sources(*srcs)
    return out
