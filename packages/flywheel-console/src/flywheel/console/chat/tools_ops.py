# ruff: noqa: E501, UP031
"""Chat tools of the Jobs and QA page groups, navigation, and the one proposal tool.

Nothing here writes a file or starts a process: ``propose_job`` returns a confirm card, and the
browser posts the existing ``POST /api/jobs`` after a human presses Run.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Any

from flywheel.console.paths import active
from flywheel.console.server import runner

from .common import (
    DENY_PARTS,
    Result,
    cols,
    dur_s,
    fail,
    jload,
    jsonl,
    result,
    rows_text,
    story,
    table,
    tail_lines,
    to_int,
)
from .resolve import _pick, job_dirs, resolve_dataset, resolve_job

PAGES = ("home", "data", "jobs", "runs", "eval", "loop", "qa")
KINDS = (
    "ego.ingest", "ego.deid", "ego.ea", "ego.pose", "ego.annotate", "ego.qa", "ego.report",
    "ego.pipeline", "ego.human1m", "export.zip", "agentqa.run", "agentqa.review",
)  # fmt: skip
GPU_KINDS = ("ego.annotate", "agentqa.run")


def all_jobs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in job_dirs():
        j = jload(d / "job.json")
        if isinstance(j, dict):
            j = dict(j)
            j["_dur"] = dur_s(j)
            out.append(j)
    out.sort(key=lambda j: j.get("created", ""), reverse=True)
    return out


def est_seconds(kind: str) -> float | None:
    ds = [
        j["_dur"]
        for j in all_jobs()
        if j.get("kind") == kind and j.get("state") == "ok" and j.get("_dur")
    ]
    return round(statistics.median(ds), 1) if ds else None


def job_list(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    st, kind = str(args.get("state") or "").lower(), str(args.get("kind") or "").lower()
    limit = to_int(args.get("limit"), 20)
    js = [
        j
        for j in all_jobs()
        if (not st or j.get("state") == st) and (not kind or kind in j.get("kind", ""))
    ]
    rows = [
        {"job_id": j["id"], "kind": j["kind"], "state": j["state"], "host": j.get("host"),
         "created": j.get("created", "")[5:19],
         "duration_s": round(j["_dur"], 1) if j.get("_dur") is not None else None, "rc": j.get("rc")}
        for j in js[:limit]
    ]  # fmt: skip
    ui = table(
        "Jobs",
        cols("job_id", "kind", "state", "host", "created", "duration_s", "rc"),
        rows,
        total=len(js),
        link="#/jobs",
        row_link="#/jobs?job={job_id}",
    )
    return result(
        ui,
        "%d jobs match; showing the first %d.\n%s"
        % (
            len(js),
            len(rows),
            rows_text(rows, ["job_id", "kind", "state", "duration_s", "rc"], 15),
        ),
    )


def job_get(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    v = args.get("job_id") or args.get("id") or ctx.get("job_id")
    if not v:
        return fail("job_id is required.")
    st, jid = resolve_job(v)
    if st != "ok":
        return fail(
            f"No job matches '{v}'." if st == "none" else f"Ambiguous job '{v}'.",
            jid if st == "ambiguous" else None,
        )
    jdir = active().jobs / jid
    j = jload(jdir / "job.json") or {}
    tail, _ = tail_lines(jdir / "log.txt", 3)
    d = dur_s(j)
    items = [
        {"label": "state", "value": j.get("state")},
        {"label": "kind", "value": j.get("kind")},
        {"label": "host", "value": j.get("host")},
        {"label": "rc", "value": j.get("rc")},
    ]
    if d is not None:
        items.append({"label": "duration", "value": round(d, 1), "unit": "s"})
    specs = [
        {"type": "stat", "items": [i for i in items if i["value"] is not None]},
        {"type": "text", "text": "argv: " + " ".join(j.get("argv", []))[:300]},
        {"type": "log", "job_id": jid, "text": tail or ""},
    ]
    return result(
        {"type": "group", "items": specs},
        "job {} kind={} state={} rc={} host={} duration_s={} created={} note={}\nlast log lines:\n{}".format(
            jid,
            j.get("kind"),
            j.get("state"),
            j.get("rc"),
            j.get("host"),
            round(d, 1) if d else None,
            j.get("created"),
            j.get("note") or "",
            tail,
        ),
    )


def findings(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    src, status, inp = (
        str(args.get("source") or "").lower(),
        str(args.get("status") or "").lower(),
        str(args.get("input") or "").lower(),
    )
    aqa = runner.aqa_dir()
    reviews: dict[tuple[Any, Any], Any] = {}
    rdir = aqa / "reviews"
    for p in sorted(rdir.glob("*.review.json")) if rdir.is_dir() else []:
        rv = jload(p) or {}
        for dcs in rv.get("decisions", []):
            reviews[(rv.get("report_id"), dcs.get("finding_id"))] = dcs.get("decision")
    rows: list[dict[str, Any]] = []
    if src in ("", "llm"):
        for rf in sorted(aqa.glob("*/reports.jsonl")):
            for rep in jsonl(rf):
                ref = rep.get("subject_ref", "")
                if inp and inp not in ref.lower() and inp not in rf.parent.name.lower():
                    continue
                for f in rep.get("findings", []):
                    stt = {"agree": "accepted", "override": "rejected"}.get(
                        str(reviews.get((rep["report_id"], f["finding_id"]))), "open"
                    )
                    if status and status != stt:
                        continue
                    rows.append(
                        {
                            "source": "llm",
                            "code": f.get("code"),
                            "target": f.get("target_ref"),
                            "status": stt,
                            "insight": (f.get("insight") or "")[:140],
                            "report": rep["report_id"][-8:],
                            "finding": f["finding_id"],
                        }
                    )
    if src in ("", "rule"):
        for reason, n, _eps in story().get("reasons", []):
            if inp and inp not in reason.lower():
                continue
            if status and status not in ("open", "flag"):
                continue
            rows.append(
                {
                    "source": "rule",
                    "code": reason,
                    "target": "egocentric QA, all sources",
                    "status": "flag",
                    "insight": f"{n} episodes flagged by the rule layer",
                    "report": "-",
                    "finding": "-",
                }
            )
    ui = table(
        "Findings",
        cols("source", "code", "target", "status", "insight"),
        rows,
        total=len(rows),
        link="#/qa",
    )
    return result(
        ui,
        "%d findings (rule-layer statuses are final; LLM findings are suggestions).\n%s"
        % (len(rows), rows_text(rows, ["source", "code", "target", "status", "insight"], 10)),
    )


def open_page(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    r = str(args.get("route") or "").strip().lstrip("#").lstrip("/")
    head = r.split("/", 1)[0].split("?", 1)[0]
    if head not in PAGES or not re.fullmatch(r"[A-Za-z0-9_./:#+,=&?%-]*", r):
        return fail("Unknown page '{}'. Pages: {}.".format(args.get("route"), ", ".join(PAGES)))
    parts = r.split("/")
    if head == "data" and len(parts) > 1 and parts[1] and not parts[1].startswith("?"):
        st, rid = resolve_dataset(parts[1].split("?")[0])
        if st == "ok":
            parts[1] = rid + (("?" + parts[1].split("?", 1)[1]) if "?" in parts[1] else "")
            r = "/".join(parts)
    route = "#/" + r
    return {
        "ok": True,
        "ui": {"type": "text", "text": f"Open {route}"},
        "model": f"navigated to {route}",
        "navigate": route,
    }


def _argv_preview(kind: str, params: dict[str, Any]) -> list[str]:
    if kind == "ego.pipeline":  # a chain of jobs: the runner plans each step when it runs
        return ["fw", "egocentric", "ingest/deid/pose/annotate/qa/report (chain)"] + [
            "{}={}".format(*kv) for kv in params.items()
        ]
    return list(runner.plan(kind, params, "preview")["argv"])  # pure: starts nothing


def propose_job(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    kind = str(args.get("kind") or "").strip()
    params: Any = args.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    if kind not in KINDS or kind not in runner.KINDS:
        return fail(
            "kind '{}' is not allowed. Allowed: {}. Training, holdout and shell are never available.".format(
                kind, ", ".join(KINDS)
            )
        )
    if not isinstance(params, dict):
        return fail("params must be an object.")
    for v in params.values():
        for s in v if isinstance(v, list) else [v]:
            if isinstance(s, str) and any(p in s.lower() for p in DENY_PARTS):
                return fail("Paths under vault/ or holdout are never allowed.")
    fw = active().fw_root
    if params.get("work"):
        w = str(params["work"])
        pdir = fw / "pipeline"
        hits = [d.name for d in pdir.iterdir()] if pdir.is_dir() else []
        st, wid = _pick(w, [(h, []) for h in hits])
        if st == "ok":
            params["work"] = str(pdir / wid)
        elif st == "ambiguous":
            return fail(f"Ambiguous work dir '{w}'.", wid)
    try:
        argv = _argv_preview(kind, params)
    except Exception as e:  # preview must never raise into the chat loop
        return fail(f"Cannot propose {kind}: {e}")
    host = "rtx3060 (ssh tunnel)" if kind in GPU_KINDS else "laptop"
    est = est_seconds(kind)
    inputs = [
        str(v)
        for k, v in params.items()
        if k in ("work", "input", "path", "root", "works", "reports") and v
    ]
    spec = {
        "type": "confirm",
        "kind": kind,
        "params": params,
        "argv_preview": argv,
        "host": host,
        "est_seconds": est,
        "inputs": inputs,
    }
    return result(
        spec,
        f"Proposed (not started): {kind} on {host}, estimate {est} s from past jobs. A human must press Run.",
    )
