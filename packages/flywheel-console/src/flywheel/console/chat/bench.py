"""Chat bench: runs every item of ``bench.jsonl`` through the live model and scores it.

Scores: tool accuracy (expected tool names, in order, nothing extra; order ignored for the
``cross`` group), arg accuracy (after id resolution, page-context defaults accepted), guardrail
pass (no tool, no confirm card), grounded-number rate, p50/p95 latency. Never starts a job:
``propose_job`` only returns cards. The model is reached through the loopback tunnel.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.paths import active
from flywheel.console.server import runner

from . import llm, registry
from .resolve import resolve_dataset, resolve_job, resolve_run

BENCH_FILE = Path(__file__).with_name("bench.jsonl")
Event = tuple[str, dict[str, Any]]


def load_items(groups: str = "", limit: int = 0) -> list[dict[str, Any]]:
    items = [
        json.loads(ln) for ln in BENCH_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    if groups:
        items = [i for i in items if i["group"] in groups.split(",")]
    return items[:limit] if limit else items


def _norm_id(key: str, v: Any) -> Any:
    if key == "dataset_id":
        st, r = resolve_dataset(v)
        return r if st == "ok" else str(v).lower()
    if key == "run_id":
        st, r = resolve_run(v)
        return r if st == "ok" else str(v).lower()
    if key == "job_id":
        st, r = resolve_job(v)
        return r if st == "ok" else str(v).lower()
    if key == "episode_id":
        return str(v).lower().replace("ep", "").strip(" _#")
    if key == "route":
        return str(v).lstrip("#/").split("/")[0].lower()
    if key == "run_ids":
        return [_norm_id("run_id", x) for x in (v if isinstance(v, list) else str(v).split(","))]
    return str(v).lower().strip()


def args_match(expect: dict[str, Any], actual: dict[str, Any], ctx: dict[str, Any]) -> bool:
    d = registry.context_defaults(ctx)
    d["run_id"] = (d.get("run_ids") or [None])[0]
    for k, v in expect.items():
        got = actual.get(k)
        if got in (None, "", []):
            got = d.get(k)
        if got in (None, "", []):
            return False
        want = v if isinstance(v, list) else [v]  # a list means any of
        if _norm_id(k, got) not in [_norm_id(k, x) for x in want]:
            return False
    return True


def _names_match(group: str, names: list[str], expected: list[str]) -> bool:
    return sorted(names) == sorted(expected) if group == "cross" else names == expected


def score(item: dict[str, Any], events: list[Event]) -> dict[str, Any]:
    calls = [(d["name"], d.get("args") or {}) for e, d in events if e == "tool_start"]
    results = [d for e, d in events if e == "tool_result"]
    done = next((d for e, d in events if e == "done"), {})
    err = next((d for e, d in events if e == "error"), None)
    names = [c[0] for c in calls]
    exp = item["expect_tools"]
    en = [x["name"] for x in exp]
    out: dict[str, Any] = {
        "id": item["id"], "group": item["group"], "question": item["question"], "tools": names,
        "expected": en, "error": err["message"] if err else None, "ms_total": done.get("ms_total"),
        "answer": "".join(d["text"] for e, d in events if e == "token"),
    }  # fmt: skip
    if item["group"] in ("guard", "none"):
        confirm = any((r.get("ui") or {}).get("type") == "confirm" for r in results)
        out["tool_ok"] = not names
        out["arg_ok"] = None
        out["no_action_ok"] = (not names) and not confirm and bool(out["answer"].strip())
    else:
        out["tool_ok"] = _names_match(item["group"], names, en)
        out["arg_ok"] = bool(out["tool_ok"]) and _args_ok(item, exp, calls)
        out["no_action_ok"] = None
    out["markup_leak"] = "<|" in out["answer"] or "tool_call" in out["answer"]
    if out["markup_leak"]:
        out["tool_ok"] = out["arg_ok"] = False
        if out["no_action_ok"] is not None:
            out["no_action_ok"] = False
    nums = done.get("numbers") or []
    out["numbers"] = len(nums)
    out["grounded"] = sum(1 for n in nums if n["grounded"])
    out["guard"] = done.get("guard")
    return out


def _args_ok(
    item: dict[str, Any], exp: list[dict[str, Any]], calls: list[tuple[str, dict[str, Any]]]
) -> bool:
    if item["group"] != "cross":
        return all(
            args_match(x["args_subset"], calls[i][1], item["context"]) for i, x in enumerate(exp)
        )
    pool = list(calls)  # any order: each expectation needs one distinct matching call
    for x in exp:
        hit = next(
            (
                c
                for c in pool
                if c[0] == x["name"] and args_match(x["args_subset"], c[1], item["context"])
            ),
            None,
        )
        if hit is None:
            return False
        pool.remove(hit)
    return True


def summarize(rows: list[dict[str, Any]], lat: list[float], tag: str = "") -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    tool_items = [r for r in rows if r["group"] not in ("guard", "none")]
    guard = [r for r in rows if r["group"] == "guard"]
    none = [r for r in rows if r["group"] == "none"]
    scored = [r for r in rows if not r.get("guard")]
    ls = sorted(lat)

    def p(q: float) -> float:
        return ls[min(len(ls) - 1, int(q * len(ls)))] if ls else 0.0

    return {
        "markup_leaks": sum(1 for r in rows if r.get("markup_leak")),
        "time": datetime.now().isoformat(timespec="seconds"), "n": len(rows), "tag": tag,
        "tool_accuracy": [sum(1 for r in tool_items if r["tool_ok"]), len(tool_items)],
        "arg_accuracy": [sum(1 for r in tool_items if r["arg_ok"]), len(tool_items)],
        "guardrail_pass": [sum(1 for r in guard if r["no_action_ok"]), len(guard)],
        "no_tool_pass": [sum(1 for r in none if r["no_action_ok"]), len(none)],
        "grounded_numbers": [sum(r["grounded"] for r in scored), sum(r["numbers"] for r in scored)],
        "latency_p50_s": round(statistics.median(lat), 2) if lat else 0,
        "latency_p95_s": round(p(0.95), 2),
        "by_group": {g: [sum(1 for r in v if r.get("tool_ok")), len(v)] for g, v in by.items()},
    }  # fmt: skip


def run_item(item: dict[str, Any]) -> tuple[list[Event], float]:
    t0 = time.time()
    body = {"messages": [{"role": "user", "content": item["question"]}], "context": item["context"]}
    return list(llm.events(body)), time.time() - t0


def run(tag: str | None = None, limit: int = 0, groups: str = "") -> dict[str, Any]:
    """Run the bench against the live model; writes ``<chat>/bench-<ts>.json`` for a full run."""
    if not runner.TUNNEL.ensure(15):
        raise RuntimeError("model tunnel to rtx3060 is down; bench not run, no file written")
    rows: list[dict[str, Any]] = []
    lat: list[float] = []
    for it in load_items(groups, limit):
        try:
            events, wall = run_item(it)
            r = score(it, events)
        except Exception as e:
            wall = 0.0
            r = {"id": it["id"], "group": it["group"], "question": it["question"], "tools": [], "expected": [x["name"] for x in it["expect_tools"]], "tool_ok": False, "arg_ok": False, "no_action_ok": False, "error": str(e), "numbers": 0, "grounded": 0, "answer": ""}  # fmt: skip  # noqa: E501
        r["wall_s"] = round(wall, 2)
        lat.append(wall)
        rows.append(r)
        print(
            "%s %-5s tool=%s %5.1fs  %s -> %s"  # noqa: UP031
            % (
                r["id"],
                r["group"],
                "Y" if r.get("tool_ok") else "n",
                wall,
                r["question"][:44],
                ",".join(r["tools"]) or "-",
            ),
            flush=True,
        )
    summary = summarize(rows, lat, tag or "")
    if not groups and not limit:
        d = active().chat
        d.mkdir(parents=True, exist_ok=True)
        f = d / ("bench-{}.json".format(datetime.now().strftime("%Y%m%d-%H%M%S")))
        f.write_text(
            json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print("written", f)
    return summary
