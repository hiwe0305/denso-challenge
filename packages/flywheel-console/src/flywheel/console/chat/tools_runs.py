"""Chat tools of the Runs, Eval and Loop page groups: training runs, logs, eval, cost."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.paths import active

from .common import (
    Result,
    cols,
    fail,
    jload,
    jsonl,
    norm,
    result,
    rows_text,
    story,
    table,
    tail_lines,
    to_int,
)
from .resolve import ledgers_dir, resolve_job, resolve_run, run_index

_MCACHE: dict[str, tuple[tuple[float, int], list[dict[str, Any]]]] = {}


def _metrics(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Parsed metrics.jsonl of a run, re-read only when the file changes."""
    f: Path = run["metrics"]
    st = f.stat()
    key = (st.st_mtime, st.st_size)
    hit = _MCACHE.get(str(f))
    if hit and hit[0] == key:
        return hit[1]
    rows = jsonl(f)
    _MCACHE[str(f)] = (key, rows)
    return rows


def _ema(vals: list[float], n: int = 50) -> float | None:
    vals = vals[-n * 4 :]
    if not vals:
        return None
    a, e = 2.0 / (n + 1), vals[0]
    for v in vals[1:]:
        e = a * v + (1 - a) * e
    return e


def _config(run: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ln = jload(run["dir"] / "launch.json", {}) or {}
    flags: dict[str, str] = {}
    for a in ln.get("argv", []):
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            flags[k] = v
    ident = ln.get("identity") or {}
    cfg = {
        "global_batch_size": ln.get("global_batch_size"), "rtc_prefix": ln.get("rtc_prefix"),
        "trainer": ln.get("trainer_module"), "release_id": ident.get("release_id"),
        "run_plan_id": ident.get("run_plan_id"), "flags": flags,
    }  # fmt: skip
    return cfg, ln


def _machine(run: dict[str, Any], ln: dict[str, Any]) -> str:
    sess = "da34-" + run["branch"].lower().replace("_", "-")
    cs: dict[str, Any] = next(
        (c for c in story().get("colab_sessions", []) if c.get("session") == sess), {}
    )
    host = "colab" if str(ln.get("psi0_root", "")).startswith("/content") else "unknown"
    return "{} {}".format(host, cs.get("gpu", "")) if cs.get("gpu") else host


def run_list(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    want = str(args.get("state") or "").lower()
    now_ts = datetime.now().timestamp()
    rows: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    for r in run_index():
        ms = _metrics(r)
        tr = [
            x for x in ms if x.get("split") == "train" and isinstance(x.get("loss"), (int, float))
        ]
        last = ms[-1] if ms else {}
        mt = r["metrics"].stat().st_mtime
        st = "running" if now_ts - mt < 1200 else "stopped"
        if want and want not in st:
            continue
        cfg, ln = _config(r)
        ema = _ema([x["loss"] for x in tr])
        row = {
            "run": r["id"], "branch": r["branch"], "state": st, "step": last.get("step"),
            "max_steps": 60000, "loss_ema50": round(ema, 3) if ema is not None else None,
            "mtime": datetime.fromtimestamp(mt).astimezone().isoformat(timespec="seconds"),
            "machine": _machine(r, ln),
        }  # fmt: skip
        rows.append(row)
        raw.append(dict(row, config=cfg, loss_last=tr[-1]["loss"] if tr else None,
                        throughput=last.get("throughput"), vram_gb=last.get("vram_gb"),
                        wall_time_s=last.get("wall_time_s")))  # fmt: skip
    keys = ["run", "branch", "state", "step", "max_steps", "loss_ema50", "machine"]
    ui = table(
        "Runs", cols(*keys), rows, total=len(rows), link="#/runs", row_link="#/runs?sel={branch}"
    )
    res = result(
        ui,
        "%d runs (loss_ema50 = EMA over the last 50 train steps; running = file touched < 20 min ago).\n%s"  # noqa: E501, UP031
        % (len(rows), rows_text(rows, keys)),
    )
    res["raw"] = {"runs": raw}
    return res


def _want_run(v: Any, ctx: dict[str, Any]) -> tuple[dict[str, Any] | None, Result | None]:
    if (not v or str(v).lower() in ("this", "current", "selected")) and ctx.get("run_ids"):
        v = ctx["run_ids"][0]
    st, r = resolve_run(v)
    if st == "ok":
        return next(x for x in run_index() if x["id"] == r), None
    if st == "ambiguous":
        return None, fail(f"Ambiguous run '{v}'.", r)
    return None, fail(f"No run matches '{v}'.")


LIVE_KEYS = [
    "loss", "val_loss", "loss_by_group.hand", "loss_by_group.arm", "loss_by_group.torso_rpy",
    "loss_by_group.height", "loss_by_group.base_velocity", "loss_by_group.turn",
    "loss_by_group.target_yaw", "throughput", "vram_gb", "grad_norm_action",
]  # fmt: skip
MAX_POINTS = 2000


def _pts(rows: list[dict[str, Any]], key: str, from_step: int = 0) -> list[tuple[Any, float]]:
    """[(step, value)] for a key; ``val_loss`` is the loss of split=val rows, ``a.b`` is nested."""
    out: list[tuple[Any, float]] = []
    for r in rows:
        v: Any
        if key == "val_loss":
            v = r.get("loss") if r.get("split") == "val" else None
        else:
            if r.get("split") == "val":
                continue
            v = r
            for part in key.split("."):
                v = v.get(part) if isinstance(v, dict) else None
        if isinstance(v, (int, float)) and r.get("step") is not None and r["step"] >= from_step:
            out.append((r["step"], v))
    return out


def _down(pts: list[tuple[Any, float]], n: int) -> list[list[Any]]:
    if len(pts) > n:
        stride = (len(pts) - 1) / float(n - 1)
        pts = [pts[int(round(i * stride))] for i in range(n)]
    return [[a, round(b, 5)] for a, b in pts]


def _series(rows: list[dict[str, Any]], key: str, from_step: int, points: int) -> list[list[Any]]:
    return _down(_pts(rows, key, from_step), points)


def run_metrics(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    run, err = _want_run(args.get("run_id"), ctx)
    if err or run is None:
        return err or fail("run_id is required.")
    keys = args.get("keys") or ["loss"]
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(",") if k.strip()]
    if keys == ["all"]:
        keys = list(LIVE_KEYS)
    rows = _metrics(run)
    if not rows:
        return fail("No metrics for {}.".format(run["id"]))
    fs = to_int(args.get("from_step"), 0, 0, 10**9)
    n = to_int(args.get("points"), 60, 5, MAX_POINTS)
    series: list[dict[str, Any]] = []
    raw: dict[str, Any] = {}
    lines = [
        "run %s (branch %s): %d logged rows, last step %s"  # noqa: UP031
        % (run["id"], run["branch"], len(rows), rows[-1].get("step"))
    ]
    for k in keys:
        pts = _series(rows, k, fs, n)
        if not pts:
            lines.append(f"{k}: no data")
            continue
        vals = [v for _, v in pts]
        series.append({"name": k, "points": pts})
        raw[k] = pts
        lines.append(
            f"{k}: first={vals[0]} last={vals[-1]} min={min(vals)} max={max(vals)} (step {pts[0][0]}..{pts[-1][0]})"  # noqa: E501
        )
    if not series:
        return fail(
            "None of {} exist in {}. Keys: {}".format(keys, run["id"], ", ".join(LIVE_KEYS))
        )
    ui = {
        "type": "line", "title": run["id"], "x_label": "step",
        "y_label": ",".join(keys) if len(keys) < 3 else "metrics", "series": series,
        "log_y": keys == ["loss"],
    }  # fmt: skip
    res = result(ui, "\n".join(lines[:14]))
    res["raw"] = raw
    return res


def run_compare(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ids = args.get("run_ids") or []
    if isinstance(ids, str):
        ids = [x.strip() for x in ids.split(",") if x.strip()]
    if len(ids) < 2 and ctx.get("run_ids"):
        ids = ctx["run_ids"]
    if len(ids) < 2:
        return fail("run_ids needs 2 to 4 runs.")
    metric = str(args.get("metric") or "loss")
    runs: list[dict[str, Any]] = []
    for i in ids[:4]:
        r, err = _want_run(i, ctx)
        if err or r is None:
            return err or fail(f"No run matches '{i}'.")
        runs.append(r)
    sr = {r.get("job"): r for r in story().get("runs", [])}
    series: list[dict[str, Any]] = []
    lines: list[str] = []
    argvs: dict[str, list[str]] = {}
    raw: dict[str, Any] = {}
    for r in runs:
        rows = _metrics(r)
        pts = _series(rows, metric, 0, to_int(args.get("points"), 60, 5, MAX_POINTS))
        series.append({"name": r["branch"], "points": pts})
        raw[r["branch"]] = pts
        last = rows[-1] if rows else {}
        lv = last.get(metric)
        lines.append(
            "{} ({}): step={} {}_last={}".format(
                r["branch"],
                r["id"],
                last.get("step"),
                metric,
                round(lv, 4) if isinstance(lv, (int, float)) else None,
            )
        )
        argvs[r["branch"]] = (
            sr.get(r["id"], {}).get("argv")
            or (jload(r["dir"] / "launch.json", {}) or {}).get("argv")
            or []
        )
    base = argvs[runs[0]["branch"]]
    diff = []
    for r in runs[1:]:
        o = argvs[r["branch"]]
        a, b = sorted(set(base) - set(o)), sorted(set(o) - set(base))
        diff.append(
            {
                "vs": r["branch"],
                "only_in_{}".format(runs[0]["branch"]): ", ".join(a)[:160] or "-",
                "only_in_other": ", ".join(b)[:160] or "-",
            }
        )
        lines.append(
            "config diff {} vs {}: {} | {}".format(
                runs[0]["branch"],
                r["branch"],
                ", ".join(a)[:200] or "none",
                ", ".join(b)[:200] or "none",
            )
        )
    specs = [
        {
            "type": "line",
            "title": f"{metric} by step",
            "x_label": "step",
            "y_label": metric,
            "series": series,
            "log_y": metric == "loss",
        },
        table(
            "Config diff", cols("vs", "only_in_{}".format(runs[0]["branch"]), "only_in_other"), diff
        ),
    ]
    res = result({"type": "group", "items": specs}, "\n".join(lines))
    res["raw"] = raw
    return res


def log_tail(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    v = args.get("job_id") or args.get("run_id") or args.get("id")
    if not v and ctx.get("job_id"):
        v = ctx["job_id"]
    if not v and ctx.get("run_ids"):
        v = ctx["run_ids"][0]
    if not v:
        return fail("job_id or run_id is required.")
    n = to_int(args.get("n"), 80, 5, 300)
    grep = args.get("grep") or None
    st, jid = resolve_job(v)
    path: Path | None = None
    label = ""
    if st == "ok":
        path, label = active().jobs / jid / "log.txt", jid
    else:
        st2, rid = resolve_run(v)
        if st2 == "ok":
            run = next(x for x in run_index() if x["id"] == rid)
            for name in ("train.log", "setup.log"):
                if (run["dir"] / "vm-logs" / name).is_file():
                    path, label = run["dir"] / "vm-logs" / name, f"{rid}/{name}"
                    break
    if path is None:
        return fail(f"No job or run matches '{v}'.", jid if st == "ambiguous" else None)
    text, cut = tail_lines(path, n, grep)
    if text is None:
        return fail("Log not readable.")
    text = text[-3500:]
    return result(
        {"type": "log", "job_id": label, "text": text, "truncated": cut},
        "last %d lines of %s%s:\n%s" % (n, label, f" (grep {grep})" if grep else "", text[-2800:]),  # noqa: UP031
    )


# ------------------------------------------------------------------ eval and loop
def eval_data() -> dict[str, Any] | None:
    """``story.json["eval"]`` (cited numbers of docs/he/tray.md); None when the index has none."""
    ev = story().get("eval")
    return ev if isinstance(ev, dict) and ev.get("levels") else None


def eval_summary(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ev = eval_data()
    if not ev:
        return fail("No eval data available (story.json has no eval block).")
    eid = str(args.get("eval_id") or "C")
    if "plus" in norm(eid) or ("+" in eid and norm(eid) == "c"):
        return fail("Eval of C+ has not been run yet; only policy C has results.")
    lv = ev["levels"]
    g = next((x for x in lv if x["level"] == "L1-2"), lv[-1])
    stages = ev["stages"]
    place = stages.index("place") if "place" in stages else 5
    reach = place - 1
    items = [
        {
            "label": x["level"],
            "value": "%.1f%%" % (100.0 * x["successes"] / x["n"]),
            "delta": "%d/%d" % (x["successes"], x["n"]),  # noqa: UP031
        }
        for x in lv
    ]
    funnel = {
        "type": "line", "title": "Pass rate by stage", "x_label": "stage", "y_label": "% passing",
        "series": [{"name": x["level"], "points": [[i, v] for i, v in enumerate(x["steps_pct"])]} for x in lv],  # noqa: E501
    }  # fmt: skip
    fl = ev["failure_labels"]
    rows = [
        {"label": k, "L0": v["L0"], "L1": v["L1"], "L2": v["L2"], "L1-2": v["L1"] + v["L2"]}
        for k, v in fl.items()
    ]
    specs = [
        {"type": "stat", "items": items},
        funnel,
        table("Failure labels", cols("label", "L0", "L1", "L2", "L1-2"), rows),
    ]
    lines = ["eval policy {} on dev ({})".format(ev.get("policy", "C"), ev.get("source", ""))]
    for x in lv:
        lines.append(
            "%s: %d/%d success = %.1f%%; stage pass %% = %s"  # noqa: UP031
            % (
                x["level"],
                x["successes"],
                x["n"],
                100.0 * x["successes"] / x["n"],
                dict(zip(stages, x["steps_pct"])),
            )
        )
    lines.append(
        "L1-2 biggest drop: {} {:.1f}% -> {} {:.1f}%".format(
            stages[reach], g["steps_pct"][reach], stages[place], g["steps_pct"][place]
        )
    )
    if rows:
        top = max(rows, key=lambda r: r["L1-2"])
        lines.append("top failure label at L1-2: %s %d of %d" % (top["label"], top["L1-2"], g["n"]))  # noqa: UP031
    return result({"type": "group", "items": specs}, "\n".join(lines))


def eval_failures(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ev = eval_data()
    if not ev:
        return fail("No eval data available.")
    label = str(args.get("label") or "").upper()
    limit = to_int(args.get("limit"), 12)
    fl = ev["failure_labels"]
    rows = [
        {"label": k, "L0": v["L0"], "L1": v["L1"], "L2": v["L2"], "total": sum(v.values())}
        for k, v in fl.items()
        if not label or label in k
    ]
    rows.sort(key=lambda r: -r["total"])
    specs = [table("Failures by label", cols("label", "L0", "L1", "L2", "total"), rows[:limit])]
    lines = [
        "failures (all levels): "
        + "; ".join(
            "%s=%d (L0 %d, L1 %d, L2 %d)" % (r["label"], r["total"], r["L0"], r["L1"], r["L2"])  # noqa: UP031
            for r in rows
        )
    ]
    if (not label or "PLACE" in label) and ev.get("place_error_cm"):
        pe = ev["place_error_cm"]
        specs.append(
            table(
                "Placement error (cm)",
                cols("level", "min", "p10", "p50", "p90", "max"),
                [dict(level=k, **v) for k, v in pe.items()],
            )
        )
        lines.append(
            "L-PLACE-POSE placement error cm: "
            + "; ".join(
                "{} p50={} p90={} max={}".format(k, v["p50"], v["p90"], v["max"])
                for k, v in pe.items()
            )
            + " (tolerance 5 cm)"
        )
    lines.append("rollout thumbnails are not stored on this laptop")
    return result({"type": "group", "items": specs}, "\n".join(lines))


def loop_proposals(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    ev = eval_data()
    if not ev or not ev.get("clusters"):
        return fail("No loop data available.")
    fl = ev.get("failure_labels") or {}

    def n_l12(label: str) -> int | None:  # failures of the label at L1-2, as the loop page shows
        lv = fl.get(label)
        return lv["L1"] + lv["L2"] if lv else None

    rows = [
        {
            "cluster": c["label"],
            "stage": c.get("stage"),
            "n": n_l12(c["label"]),
            "diagnosis": c.get("diagnosis"),
            "intervention": c.get("intervention"),
            "episodes": c.get("episodes"),
        }
        for c in ev["clusters"]
    ]
    ui = table(
        "Failure clusters",
        cols("cluster", "stage", "n", "diagnosis", "intervention", "episodes"),
        rows,
        link="#/loop",
    )
    head = "clusters on eval {} (n of 240 rollouts at L1-2): ".format(ev.get("policy", "C"))
    return result(
        ui,
        head
        + "; ".join(
            "{} n={} diagnosis={} intervention={} episodes={}".format(
                r["cluster"], r["n"], r["diagnosis"], r["intervention"], r["episodes"]
            )
            for r in rows
        ),
    )


def _ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for f in sorted(ledgers_dir().glob("*/*/ledger.jsonl")):
        for d in jsonl(f):
            d["_run"] = f.parent.parent.name
            rows.append(d)
    return rows


def ledger_query(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    g = str(args.get("group_by") or "story").lower()
    mk = str(args.get("measure_kind") or "").lower()
    since = str(args.get("since") or "")
    if g == "story":
        st = story().get("ledger", [])
        rows: list[dict[str, Any]] = []
        for name, est, meas in st:
            if not (est or meas):
                continue
            if mk in ("", "estimated"):
                rows.append({"story": name, "measure_kind": "estimated", "usd": est})
            if mk in ("", "measured"):
                rows.append({"story": name, "measure_kind": "measured", "usd": meas})
        te = round(sum(r[1] for r in st), 2)
        tm = round(sum(r[2] for r in st), 2)
        ui = table(
            "Ledger by story (USD)", cols("story", "measure_kind", "usd"), rows, link="#/jobs"
        )
        return result(
            ui,
            "ledger by story, estimate and measured are separate rows. total estimated={} USD, total measured={} USD.\n{}".format(  # noqa: E501
                te, tm, rows_text(rows, ["story", "measure_kind", "usd"], 24)
            ),
        )
    led = _ledger_rows()
    if since:
        led = [d for d in led if d.get("_run", "") >= since or str(d.get("id", "")) >= since]
    if mk:
        led = [d for d in led if d.get("measure_kind") == mk]
    key = "activity" if g == "kind" else "resource_type"
    agg: dict[tuple[Any, Any, Any], list[float]] = {}
    for d in led:
        k = (d.get(key) or "?", d.get("measure_kind"), d.get("unit"))
        a = agg.setdefault(k, [0, 0.0, 0.0])
        a[0] += 1
        a[1] += d.get("quantity") or 0
        a[2] += d.get("usd_amount") or 0
    out = [
        {
            g: k[0],
            "measure_kind": k[1],
            "unit": k[2],
            "entries": int(v[0]),
            "quantity": round(v[1], 2),
            "usd": round(v[2], 2),
        }
        for k, v in sorted(agg.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))
    ]
    ui = table(f"Ledger by {g}", cols(g, "measure_kind", "unit", "entries", "quantity", "usd"), out)
    note = (
        "host is not recorded in the ledger, grouped by resource_type instead. "
        if g == "host"
        else ""
    )
    return result(
        ui,
        "{}ledger entries grouped by {} (estimated and measured kept apart):\n{}".format(
            note,
            key,
            rows_text(out, [g, "measure_kind", "unit", "entries", "quantity", "usd"], 20),
        ),
    )
