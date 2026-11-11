"""Chat tools of the Data page group: catalog, stats, episodes, QA, lineage.

Frames and posters come only from the index's ``/data/`` poster URLs, which the index builds
from ``*.deid.mp4`` files; a raw video is never returned. QA pass/flag/reject comes only from
rule-layer files, and the failures of a generation batch are reported apart from it.
"""

from __future__ import annotations

import re
from typing import Any

from flywheel.console.paths import active

from .common import (
    Result,
    allowed,
    catalog,
    cols,
    ds_file,
    fail,
    result,
    rows_text,
    table,
    to_int,
)
from .resolve import want_dataset

POSTER_PREFIX = "/data/"


def poster_ok(url: Any) -> bool:
    """True for an index poster URL (``/data/...jpg``) whose file exists under the index."""
    u = str(url or "")
    if not u.startswith(POSTER_PREFIX) or ".." in u or not u.lower().endswith((".jpg", ".png")):
        return False
    p = active().index / u[len(POSTER_PREFIX) :]
    return allowed(p) and p.is_file()


def _row(ds: str) -> dict[str, Any]:
    return next(x for x in catalog()["rows"] if x["id"] == ds)


def catalog_search(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    q = str(args.get("q") or "").strip().lower()
    dt, task, status = (
        str(args.get(k) or "").strip().lower() for k in ("data_type", "task", "status")
    )
    limit = to_int(args.get("limit"), 20)
    hits = []
    for r in catalog().get("rows", []):
        keys = ("id", "name", "title", "kind", "group", "data_type", "task", "notes")
        hay = " ".join(str(r.get(k, "")) for k in keys) + " " + " ".join(r.get("aliases") or [])
        if q and not all(t in hay.lower() for t in q.split()):
            continue
        if (
            dt
            and dt not in str(r.get("data_type", "")).lower()
            and dt not in str(r.get("group", "")).lower()
        ):
            continue
        if task and task not in str(r.get("task", "")).lower():
            continue
        if status and status != str(r.get("status", "")).lower():
            continue
        hits.append(r)
    rows = [
        {"id": r["id"], "type": r.get("data_type"), "task": r.get("task"),
         "episodes": r.get("episodes"), "hours": r.get("hours"), "status": r.get("status"),
         "qa": r.get("qa")}
        for r in hits[:limit]
    ]  # fmt: skip
    ui = table(
        "Catalog", cols("id", "type", "task", "episodes", "hours", "status", "qa"), rows,
        total=len(hits), link="#/data", row_link="#/data/{id}",
    )  # fmt: skip
    show = ["id", "type", "task", "episodes", "hours", "status"]
    return result(
        ui,
        "%d catalog rows match; showing the first %d.\n%s"  # noqa: UP031
        % (len(hits), len(rows), rows_text(rows, show, 15)),
    )


def dataset_stats(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ds, err = want_dataset(args, ctx)
    if err or ds is None:
        return err or fail("dataset_id is required.")
    r = _row(ds)
    items = [
        {"label": "episodes", "value": r.get("episodes")}, {"label": "frames", "value": r.get("frames")},  # noqa: E501
        {"label": "hours", "value": r.get("hours")}, {"label": "fps", "value": r.get("fps")},
        {"label": "size", "value": r.get("size")}, {"label": "data class", "value": r.get("data_class")},  # noqa: E501
    ]  # fmt: skip
    items = [i for i in items if i["value"] not in (None, "")]
    specs: list[dict[str, Any]] = [{"type": "stat", "items": items}]
    qual = ds_file(ds, "quality") or {}
    h = next((x for x in qual.get("hists", []) if x.get("bins")), None)
    if h:
        specs.append({
            "type": "bar", "title": h.get("label"),
            "categories": ["{:.4g}".format(b["lo"]) for b in h["bins"]],
            "series": [{"name": "count", "values": [b["c"] for b in h["bins"]]}],
        })  # fmt: skip
    lines = [
        "dataset {} ({}, {}, task {})".format(ds, r.get("kind"), r.get("data_type"), r.get("task"))
    ]
    lines += ["{}={}".format(i["label"], i["value"]) for i in items]
    lines.append(
        "licence={} status={}; QA decisions={}; split note: {}".format(
            r.get("licence"), r.get("status"), r.get("qa_counts") or "none recorded", r.get("qa")
        )
    )
    if h:
        tot = sum(b["c"] for b in h["bins"])
        mid = max(h["bins"], key=lambda b: b["c"])
        lines.append(
            "histogram '%s': %d values, mode bin %.4g-%.4g (%d)"  # noqa: UP031
            % (h.get("label"), tot, mid["lo"], mid["hi"], mid["c"])
        )
    return result({"type": "group", "items": specs}, "\n".join(lines))


def episode_list(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ds, err = want_dataset(args, ctx)
    if err or ds is None:
        return err or fail("dataset_id is required.")
    eps = ds_file(ds, "episodes")
    if eps is None:
        return fail(f"No episode list for {ds}.")
    limit = to_int(args.get("limit"), 20)
    qa = str(args.get("qa") or "").lower()
    reason = str(args.get("reason") or "").lower()
    sort = str(args.get("sort") or "")
    ego = bool(eps) and "qa" in eps[0]
    out = []
    for e in eps:
        if ego:
            if qa in ("pass", "flag", "reject") and e.get("qa") != qa:
                continue
            if reason and not any(reason in x.lower() for x in e.get("reasons") or []):
                continue
        else:
            if qa in ("pass", "ok") and e.get("ok") is False:
                continue
            if qa in ("fail", "flag", "reject") and e.get("ok") is not False:
                continue
            if reason and reason not in str(e.get("out", "")).lower():
                continue
        out.append(e)
    if sort:
        k = sort.lstrip("-+")
        try:
            out.sort(key=lambda e: (e.get(k) is None, e.get(k)), reverse=sort.startswith("-"))
        except TypeError:
            pass
    shown = out[:limit]
    if ego:
        rows = [
            {"episode_id": e["id"], "qa": e.get("qa"), "len_s": e.get("s"),
             "reasons": ", ".join(e.get("reasons") or []), "hands_out": e.get("out"), "jitter": e.get("jit")}  # noqa: E501
            for e in shown
        ]  # fmt: skip
        cs = cols("episode_id", "qa", "len_s", "reasons", "hands_out", "jitter")
        keys, rl = ["episode_id", "qa", "len_s", "reasons"], f"#/data/{ds}/ep/{{episode_id}}"
    else:
        rows = [
            {"episode_index": e["i"], "len_s": e.get("s"), "frames": e.get("n"), "level": e.get("lv"),  # noqa: E501
             "ok": e.get("ok"), "dist": e.get("dist"), "outcome": e.get("out") or "-"}
            for e in shown
        ]  # fmt: skip
        cs = cols("episode_index", "len_s", "frames", "level", "ok", "dist", "outcome")
        keys, rl = (
            ["episode_index", "len_s", "level", "ok", "outcome"],
            f"#/data/{ds}/ep/{{episode_index}}",
        )
    specs = [
        table(
            "Episodes of " + ds,
            cs,
            rows,
            total=len(out),
            link=f"#/data/{ds}?tab=episodes",
            row_link=rl,
        )
    ]
    thumbs = [
        {
            "src": e["poster"],
            "label": str(e["id"])[:14],
            "link": "#/data/{}/ep/{}".format(ds, e["id"]),
        }
        for e in shown
        if e.get("poster") and poster_ok(e["poster"])
    ]
    if thumbs:
        specs.append({"type": "thumbs", "items": thumbs[:8]})
    note = "" if ego or not qa else " (simulator data: no QA flags, ok means the rollout succeeded)"
    return result(
        {"type": "group", "items": specs},
        "%d episodes of %s match%s; showing the first %d.\n%s"  # noqa: UP031
        % (len(out), ds, note, len(shown), rows_text(rows, keys, 15)),
    )


def _ep_key(v: Any) -> tuple[str, int | None]:
    s = str(v or "").strip().lower()
    m = re.search(r"(\d+)$", s)
    return s, int(m.group(1)) if m and "ep_" not in s else None


def episode_get(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ds, err = want_dataset(args, ctx)
    if err or ds is None:
        return err or fail("dataset_id is required.")
    v = args.get("episode_id")
    if v in (None, ""):
        v = args.get("episode") or args.get("episode_index")
    if v in (None, "", "this", "current", "selected") and ctx.get("episode_id"):
        v = ctx["episode_id"]
    if v in (None, ""):
        return fail("episode_id is required.")
    eps = ds_file(ds, "episodes") or []
    s, idx = _ep_key(v)
    e: dict[str, Any] | None
    if eps and "id" in eps[0]:
        hits = [
            x
            for x in eps
            if x["id"].lower() == s
            or x["id"].lower().startswith(s)
            or (s.isdigit() and x["id"].lower().endswith(s))
        ]
        if len(hits) > 1:
            return fail(f"Ambiguous episode '{v}'.", [h["id"] for h in hits[:6]])
        e = hits[0] if hits else None
    else:
        e = next((x for x in eps if idx is not None and x.get("i") == idx), None)
    if e is None:
        return fail(f"Episode '{v}' not found in {ds}.")
    specs: list[dict[str, Any]] = []
    lines: list[str] = []
    ref = e.get("id", e.get("i"))
    if "qa" in e:  # egocentric: rule-layer checks (value vs threshold)
        qa = (ds_file(ds, "qa") or {}).get(e["id"], [])
        rows = [
            {"check": c[0], "value": c[1], "threshold": c[2], "pass": "✓" if c[3] else "✕"}
            for c in qa
        ]
        specs.append(
            {
                "type": "stat",
                "items": [
                    {"label": "QA (rule layer)", "value": e["qa"]},
                    {"label": "length", "value": e.get("s"), "unit": "s"},
                ],
            }
        )
        specs.append(table("QA checks", cols("check", "value", "threshold", "pass"), rows))
        lines.append(
            "episode {} qa={} len={}s reasons={} detail={}".format(
                e["id"], e["qa"], e.get("s"), e.get("reasons"), e.get("detail")
            )
        )
        lines += [
            "check {} value={} threshold={} {}".format(c[0], c[1], c[2], "pass" if c[3] else "FAIL")
            for c in qa
            if not c[3]
        ][:8]
        if e.get("poster") and poster_ok(e["poster"]):
            specs.append(
                {
                    "type": "thumbs",
                    "items": [
                        {
                            "src": e["poster"],
                            "label": e["id"][:14],
                            "link": "#/data/{}/ep/{}".format(ds, e["id"]),
                        }
                    ],
                }
            )
    else:
        env = (ds_file(ds, "env") or {}).get(str(e.get("i")), {})
        smp = env.get("sample", {})
        items = [
            {"label": "frames", "value": e.get("n")}, {"label": "length", "value": e.get("s"), "unit": "s"},  # noqa: E501
            {"label": "level", "value": e.get("lv")}, {"label": "seed", "value": e.get("seed")},
            {"label": "ok", "value": e.get("ok")}, {"label": "tray dist", "value": e.get("dist"), "unit": "m"},  # noqa: E501
        ]  # fmt: skip
        specs.append({"type": "stat", "items": [i for i in items if i["value"] is not None]})
        lines.append(
            "episode {}/{}: {}".format(
                ds,
                ref,
                ", ".join(
                    "{}={}".format(i["label"], i["value"]) for i in items if i["value"] is not None
                ),
            )
        )
        if smp:
            pose = {k: round(x, 3) for k, x in (smp.get("tray_pose") or {}).items()}
            lines.append(
                "table_gap={} part_mass={} light={} tray_pose={}".format(
                    smp.get("table_gap"), smp.get("part_mass"), smp.get("light_scale"), pose
                )
            )
        if e.get("out"):
            lines.append("outcome={}".format(e["out"]))
    specs.append({"type": "text", "text": f"Open: #/data/{ds}/ep/{ref}"})
    return result({"type": "group", "items": specs}, "\n".join(lines))


def _qa_counts(row: dict[str, Any], q: dict[str, Any]) -> dict[str, Any] | None:
    c = q.get("qa") or row.get("qa_counts")
    if not c:
        return None
    base = {k: c.get(k, 0) for k in ("pass", "flag", "reject")}
    return base | {k: v for k, v in c.items() if k not in base}


def _children(ds: str) -> list[str]:
    """Descendants of ``ds`` in the catalog, nearest first (breadth first)."""
    rows = {r["id"]: r for r in catalog().get("rows", [])}
    out: list[str] = []
    frontier = [ds]
    while frontier:
        nxt: list[str] = []
        for d in frontier:
            for c in (rows.get(d) or {}).get("children") or []:
                if c not in out and c != ds:
                    out.append(c)
                    nxt.append(c)
        frontier = nxt
    return out


def _generation_batch(ds: str, q: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """(owner id, quality doc) of the nearest dataset, itself first, that records failures."""
    if q.get("failures"):
        return ds, q
    for c in _children(ds):
        cq = ds_file(c, "quality") or {}
        if cq.get("failures"):
            return c, cq
    return None


def _decisions_text(c: dict[str, Any]) -> str:
    return ", ".join(f"{v} {k}" for k, v in c.items())


def qa_summary(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ds, err = want_dataset(args, ctx)
    if err or ds is None:
        return err or fail("dataset_id is required.")
    q = ds_file(ds, "quality") or {}
    row = _row(ds)
    rows_by_id = {r["id"]: r for r in catalog().get("rows", [])}
    specs: list[dict[str, Any]] = []
    lines: list[str] = []
    raw: dict[str, Any] = {}
    counts = _qa_counts(row, q)
    if counts:  # QA decisions: rule-layer counts only
        raw["qa"] = {"decisions": counts, "reasons": {}}
        specs.append(
            {"type": "stat", "items": [{"label": "QA " + k, "value": v} for k, v in counts.items()]}
        )
        lines.append(f"QA of {ds}: {_decisions_text(counts)}.")
    else:  # no decisions of its own (a cut): the parents' decisions, one hop, each labelled
        for pid in row.get("parents") or []:
            prow = rows_by_id.get(pid)
            if prow is None:
                continue
            pc = _qa_counts(prow, ds_file(pid, "quality") or {})
            note = _decisions_text(pc) if pc else prow.get("qa")
            if note:
                raw.setdefault("qa", {}).setdefault("parents", {})[pid] = pc or note
                lines.append(f"parent {pid}: {note} (QA decisions of the parent, not of {ds}).")
                specs.append({"type": "text", "text": f"parent {pid}: {note}"})
        if row.get("qa"):
            lines.append(f"QA note of {ds}: {row['qa']}")
    reasons = q.get("reasons")  # rule-layer reasons of egocentric data
    if reasons:
        rs = [(r[0], r[1]) for r in reasons]
        raw.setdefault("qa", {})["reasons"] = dict(rs)
        specs.append(
            {
                "type": "bar",
                "title": "QA reasons",
                "categories": [a for a, _ in rs],
                "series": [{"name": "episodes", "values": [b for _, b in rs]}],
                "horizontal": True,
            }
        )
        lines.append("QA reasons: " + ", ".join("{}={}".format(*x) for x in rs[:12]))
    elif counts and counts.get("flag", 0) + counts.get("reject", 0) == 0:
        lines.append("There are no QA failures: no episode is flagged or rejected.")
    batch = _generation_batch(ds, q)
    if batch:  # simulator data: failures of the generation batch, not QA
        owner, bq = batch
        fl = bq["failures"]
        funnel = bq.get("funnel", [])
        att = next((n for a, n in funnel if "chạy" in a.lower()), None)
        failed = sum(n for _, n in fl)
        scope = (
            f"generation batch recorded on {owner}"
            if owner != ds
            else f"generation batch recorded on {ds}, shared with its sibling cuts"
        )
        raw["generation_failures"] = {
            "scope": scope,
            "owner": owner,
            "attempts": att,
            "failed": failed,
            "reasons": {a: n for a, n in fl},
        }
        specs.append(
            table("gen failures", cols("reason", "n"), [{"reason": a, "n": n} for a, n in fl])
        )
        specs.append({"type": "text", "text": "scope: " + scope})
        if funnel:
            specs.append(
                table("Funnel", cols("stage", "n"), [{"stage": a, "n": b} for a, b in funnel])
            )
        lines.append(
            "%s (%s attempts, %d failed; these are NOT QA results): %s"  # noqa: UP031
            % (scope, att, failed, ", ".join("{}={}".format(*tuple(x)) for x in fl))
        )
        lines.append("funnel: " + " > ".join(f"{a}={b}" for a, b in funnel))
    if not specs:
        s = row.get("qa") or "no QA recorded"
        specs.append({"type": "text", "text": f"QA for {ds}: {s}"})
        if not lines:
            lines.append(f"QA for {ds}: {s}")
    res = result({"type": "group", "items": specs}, "\n".join(lines))
    res["raw"] = raw
    return res


def lineage(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ds, err = want_dataset(args, ctx)
    if err or ds is None:
        return err or fail("dataset_id is required.")
    direction = str(args.get("direction") or "both").lower()
    edges = catalog().get("edges", [])
    seen, rows, frontier = {ds}, [], [ds]
    for _ in range(3):
        nxt = []
        for a, b in edges:
            if direction in ("up", "parents", "both") and b in frontier and a not in seen:
                rows.append({"from": a, "to": b})
                seen.add(a)
                nxt.append(a)
            if direction in ("down", "children", "both") and a in frontier and b not in seen:
                rows.append({"from": a, "to": b})
                seen.add(b)
                nxt.append(b)
        frontier = nxt
    ui = table("Lineage of " + ds, cols("from", "to"), rows, link="#/data/" + ds + "?tab=lineage")
    return result(
        ui,
        "lineage of {} ({}): {}".format(
            ds,
            direction,
            "; ".join("{} -> {}".format(r["from"], r["to"]) for r in rows) or "no edges",
        ),
    )
