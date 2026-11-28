"""Story index: runs, eval, loop, cost. Ported from the v5 ``build_story.py`` spike.

Every input may be missing on a laptop; a missing input gives an empty value, never an error.
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from flywheel.console.index import cited, demo, tasks
from flywheel.console.paths import ConsolePaths

_SERIES_CAP = 400


def downsample(points: list[tuple[float, float]], cap: int = 2000) -> list[tuple[float, float]]:
    """Keep at most ``cap`` points by even stride; the first and last point are always kept."""
    n = len(points)
    if n <= cap or cap < 2:
        return list(points)
    step = (n - 1) / (cap - 1)
    picked = [points[round(i * step)] for i in range(cap)]
    picked[0], picked[-1] = points[0], points[-1]
    return picked


def _jl(p: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        pass
    return rows


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dict(p: Path) -> dict[str, Any]:
    obj = _json(p)
    return obj if isinstance(obj, dict) else {}


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _series(rows: list[dict[str, Any]], key: str, nd: int | None = None) -> list[list[Any]]:
    pts = [(r["step"], r.get(key)) for r in rows if "step" in r]
    cut = downsample(pts, _SERIES_CAP)  # type: ignore[arg-type]
    return [
        [s, round(v, nd) if nd is not None and isinstance(v, (int, float)) else v] for s, v in cut
    ]


def _stat_max_plus_one(stats_doc: dict[str, Any], key: str) -> int | None:
    slot = stats_doc.get(key)
    if not isinstance(slot, dict):
        return None
    mx = slot.get("max")
    if isinstance(mx, list) and mx and isinstance(mx[0], (int, float)):
        return int(mx[0]) + 1
    if isinstance(mx, (int, float)):
        return int(mx) + 1
    return None


def _wilson_ci(succ: int, n: int, z: float = 1.959964) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    p = succ / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def _phase_seconds(report: dict[str, Any]) -> dict[str, float]:
    """Seconds per VM phase of a ``vm-logs/report.json``.

    ``setup*`` and ``train`` are their own durations and stay as written. ``persist`` is not: it
    runs in ``--watch`` mode beside ``train`` (``flywheel_psi0.trainer.colab.persist``) from the
    start of training, so its seconds cover the whole training plus the sync after it. When
    ``persist >= train`` the page shows ``persist - train``, the sync after training (C_70:
    38262.6 - 38049.2 = 213.4 s); otherwise the raw value. Story DA-53, "Điều chỉnh" point 2.
    """
    phases = report.get("phases") or {}
    out = {k: round(_num(v.get("seconds")), 1) for k, v in phases.items() if isinstance(v, dict)}
    if "persist" in out and "train" in out and out["persist"] >= out["train"]:
        out["persist"] = round(out["persist"] - out["train"], 1)
    return out


def _read_vm_log(job_dir: Path) -> tuple[list[str], dict[str, float]]:
    """Last 14 lines of ``vm-logs/train.log`` and the VM phase seconds (``_phase_seconds``)."""
    logs = job_dir / "vm-logs"
    if not logs.is_dir():
        return [], {}
    tail: list[str] = []
    try:
        text = (logs / "train.log").read_text(errors="replace")
        lines = [seg.split("\r")[-1].strip() for seg in text.splitlines()]
        tail = [ln[:170] for ln in lines if ln][-14:]
    except OSError:
        pass
    return tail, _phase_seconds(_dict(logs / "report.json"))


def _parse_metrics_dir(
    f: Path, branch: str, max_steps: int, stats: Path | None = None
) -> tuple[dict[str, Any] | None, Path | None]:
    """One training run from its ``metrics.jsonl``; episode and frame counts from ``stats``
    (default ``<job>/../<branch>-stats_psi0.json``)."""
    rows = _jl(f)
    train = [r for r in rows if r.get("split") == "train" and "step" in r]
    if not train:
        return None, None
    val = [r for r in rows if r.get("split") == "val" and "step" in r]
    tail = train[-50:]
    groups: dict[str, list[float]] = defaultdict(list)
    for r in tail:
        for g, v in (r.get("loss_by_group") or {}).items():
            groups[g].append(_num(v))
    first = train[0].get("loss_by_group") or {}
    launch = _dict(f.parent / "launch.json")
    argv = launch.get("argv")
    res_doc = _dict(f.parent / "result.json")
    exp_doc = _dict(f.parent / "expected-100000.json")
    ckpt_step = (
        res_doc.get("checkpoint_step")
        if isinstance(res_doc.get("checkpoint_step"), int)
        else exp_doc.get("ckpt_step")
        if isinstance(exp_doc.get("ckpt_step"), int)
        else None
    )
    report_phases = _dict(f.parent / "vm-logs" / "report.json").get("phases") or {}
    fallback_plan = exp_doc.get("run_plan_id") or next(
        (
            v.get("run_plan_id")
            for v in report_phases.values()
            if isinstance(v, dict) and v.get("run_plan_id")
        ),
        None,
    )
    stats_file = stats or f.parent.parent / f"{branch}-stats_psi0.json"
    stats_doc = _dict(stats_file) if stats_file.is_file() else {}
    ep_count = _stat_max_plus_one(stats_doc, "episode_index")
    fr_count = _stat_max_plus_one(stats_doc, "index")
    thr_vals = [_num(r.get("throughput")) for r in tail if r.get("throughput") is not None]
    vram_vals = [_num(r.get("vram_gb")) for r in tail if r.get("vram_gb") is not None]
    run_tail, run_phases = _read_vm_log(f.parent)
    return (
        {
            "job": f.parent.name,
            "branch": branch,
            "release": train[-1].get("release_id"),
            "run_plan_id": train[-1].get("run_plan_id") or fallback_plan,
            "step": train[-1]["step"],
            "ckpt_step": ckpt_step,
            "max_steps": max_steps,
            "episodes": ep_count,
            "frames": fr_count,
            "loss_last": round(sum(_num(r.get("loss")) for r in tail) / len(tail), 3),
            "val_last": round(_num(val[-1].get("loss")), 4) if val else None,
            "thr_med": round(statistics.median(thr_vals), 2) if thr_vals else None,
            "vram_max": round(max(vram_vals), 2) if vram_vals else None,
            "loss": _series(train, "loss", 4),
            "val": [[r["step"], round(_num(r.get("loss")), 4)] for r in val],
            "thr": _series(train, "throughput"),
            "vram": _series(train, "vram_gb"),
            "gn": _series(train, "grad_norm_action"),
            "groups_last": {g: round(sum(v) / len(v), 4) for g, v in groups.items()},
            "groups_first": {g: round(_num(v), 4) for g, v in first.items()},
            "vm_phases": run_phases,
            "log_tail": run_tail,
            "argv": argv[:14] if isinstance(argv, list) else [],
        },
        f.parent,
    )


def _runs(fw: Path, train_dir: str, max_steps: int) -> tuple[list[dict[str, Any]], list[Path]]:
    """Training runs of a round (``<train_dir>/<run>/<job>/metrics.jsonl``)."""
    runs: list[dict[str, Any]] = []
    dirs: list[Path] = []
    for f in sorted(fw.glob(f"{train_dir}/*/*/metrics.jsonl")):
        entry, d = _parse_metrics_dir(f, f.parent.parent.name, max_steps)
        if entry is not None and d is not None:
            dirs.append(d)
            runs.append(entry)
    return runs, dirs


def round_runs(fw: Path, rnd: tasks.Round) -> tuple[list[dict[str, Any]], list[Path]]:
    """Training runs of a round that names a train job folder per run (``tray-jig-r1``).

    Same entry as ``_parse_metrics_dir`` with ``branch`` = the run id of the manifest (``M``,
    not the folder name ``jig-m``), plus ``scene`` (the round's) and what ``<job>/fetched.json``
    says about the local copy: ``fetched_final`` (its ``final``) and ``fetched_step`` (its
    ``progress.step``), both None without the file. A run whose ``metrics.jsonl`` is absent or
    empty is left out. Runs come in manifest order.
    """
    runs: list[dict[str, Any]] = []
    dirs: list[Path] = []
    for run in rnd.runs:
        if not run.train:
            continue
        job = fw / run.train
        stats = fw / run.stats if run.stats else None
        entry, d = _parse_metrics_dir(job / "metrics.jsonl", run.id, rnd.max_steps, stats)
        if entry is None or d is None:
            continue
        fetched = _dict(job / "fetched.json")
        progress = fetched.get("progress")
        step = progress.get("step") if isinstance(progress, dict) else None
        final = fetched.get("final")
        entry["scene"] = rnd.scene
        entry["fetched_final"] = final if isinstance(final, bool) else None
        whole = isinstance(step, int) and not isinstance(step, bool)
        entry["fetched_step"] = step if whole else None
        runs.append(entry)
        dirs.append(d)
    return runs, dirs


def _train_log(
    run_dirs: list[Path], log_run: str | None, names: list[str] | None = None
) -> tuple[list[str], dict[str, float]]:
    """Log tail and VM phase seconds of the round's ``log_run``, else of a run with a VM log.

    A run is named by ``names`` (same order as ``run_dirs``) or by its job's parent folder.
    Phase seconds as in ``_phase_seconds`` (``persist`` is the sync after training).
    """
    named = list(zip(names or [d.parent.name for d in run_dirs], run_dirs, strict=True))
    pick = [d for n, d in named if n == log_run and (d / "vm-logs").is_dir()]
    pick = pick or [d for _, d in named if (d / "vm-logs").is_dir()]
    if not pick:
        return [], {}
    return _read_vm_log(pick[0])


def _sources(fw: Path) -> dict[str, Any]:
    srcs: list[dict[str, Any]] = []
    heat: list[list[Any]] = []
    reasons: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    sample: dict[str, Any] | None = None
    for p in sorted(fw.glob("pipeline/src_*")):
        r = _dict(p / "report" / "egocentric.json")
        if not r:
            continue
        src = _dict(p / "source.json")
        dec = r.get("decisions") or {}
        sid = p.name[4:12]
        srcs.append(
            {
                "id": sid,
                "name": src.get("name") or src.get("source_kind") or p.name,
                "licence": src.get("licence") or src.get("license"),
                "data_class": src.get("data_class"),
                "episodes": r.get("episodes"),
                "seconds": round(_num(r.get("seconds"))),
                "pass": dec.get("pass", 0),
                "flag": dec.get("flag", 0),
                "reject": dec.get("reject", 0),
            }
        )
        for c, v in (r.get("checks") or {}).items():
            n = sum(_num(v.get(k)) for k in ("flag", "reject", "quarantine"))
            heat.append([c, sid, int(n) if n == int(n) else n])
        for row in _jl(p / "qa" / "egocentric.jsonl"):
            sample = sample or row
            for rs in row.get("reasons") or []:
                key = str(rs).split(":")[0]
                reasons[key] += 1
                if len(examples[key]) < 3 and "episode_id" in row:
                    examples[key].append(row["episode_id"])
    return {
        "sources": srcs,
        "heat": heat,
        "reasons": [[k, v, examples[k]] for k, v in reasons.most_common(8)],
        "qa_sample": json.dumps(sample, ensure_ascii=False)[:900] if sample else "",
    }


def _h1m(fw: Path) -> dict[str, Any]:
    for p in sorted(fw.glob("human1m/ego-h1m-*/summary.json"), reverse=True):
        allv = _dict(p).get("all")
        if isinstance(allv, dict):
            return allv
    return {}


def _ledger(repo: Path) -> list[list[Any]]:
    out: list[list[Any]] = []
    for f in sorted((repo / "docs" / "g0" / "ledger").glob("*.csv")):
        est = mea = 0.0
        try:
            with f.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    amt = _num(row.get("amount_usd"))
                    if row.get("estimated_or_measured") == "measured":
                        mea += amt
                    else:
                        est += amt
        except OSError:
            continue
        out.append([f.stem, round(est, 2), round(mea, 2)])
    return out


def _guards(fw: Path) -> Iterator[dict[str, Any]]:
    for g in sorted(fw.glob("colab/*/guard.jsonl")):
        yield from _jl(g)


def _colab(fw: Path) -> tuple[list[list[Any]], list[dict[str, Any]]]:
    bal = sorted(
        [r["time"], round(_num(r["balance"]), 2)]
        for r in _guards(fw)
        if r.get("balance") is not None and "time" in r
    )
    batches = sorted(p for p in fw.glob("colab/batch-*") if p.is_dir())
    sessions: list[dict[str, Any]] = []
    for s in sorted(batches[-1].glob("*.json")) if batches else []:
        j = _dict(s)
        if j:
            sessions.append(
                {
                    "session": s.stem,
                    "gpu": j.get("gpu"),
                    "state": j.get("state"),
                    "cap": j.get("cap"),
                }
            )
    return bal, sessions


# stage1-C_ALL-table.json, stage1-a-B_70-vs-C_70.json: the headline is the first-named run's
_STAGE1 = re.compile(r"^stage1-(?:([a-z])-)?([A-Za-z0-9_]+?)(?:-vs-([A-Za-z0-9_]+)|-table)$")


def _run_row(name: str, h: dict[str, Any], levels: dict[str, Any]) -> dict[str, Any]:
    return {
        "run": name,
        "n": h.get("n"),
        "successes": h.get("successes"),
        "p": h.get("p"),
        "wilson": h.get("wilson"),
        "failures": dict(sorted((h.get("failures") or {}).items(), key=lambda kv: -_num(kv[1]))),
        "step_pass": h.get("step_pass") or {},
        "levels": {
            lv: {"n": v.get("n"), "successes": v.get("successes")}
            for lv, v in sorted(levels.items())
            if isinstance(v, dict)
        },
    }


def _pair(fw: Path, eval_dir: str, order: tuple[str, ...]) -> dict[str, Any]:
    """Stage-1 reads of a round's runs (``eval_dir``); empty when the folder is absent."""
    folder = fw / eval_dir
    runs: dict[str, dict[str, Any]] = {}
    comps: list[dict[str, Any]] = []
    for f in sorted(folder.glob("stage1-*.json")):
        m = _STAGE1.match(f.stem)
        d = _dict(f)
        h = d.get("headline")
        if not m or not isinstance(h, dict):
            continue
        tag, first, second = m.groups()
        runs.setdefault(first, _run_row(first, h, d.get("levels") or {}))
        ph = (d.get("paired") or {}).get("headline")
        if second and isinstance(ph, dict):
            comps.append(
                {
                    "tag": tag,
                    "variant": first,
                    "baseline": second,
                    "n": ph.get("n"),
                    "variant_succ": ph.get("variant"),
                    "baseline_succ": ph.get("baseline"),
                    "diff": ph.get("diff"),
                    "ci": ph.get("ci"),
                    "mcnemar_p": ph.get("mcnemar_exact_p"),
                    "variant_only": ph.get("variant_only"),
                    "baseline_only": ph.get("baseline_only"),
                    "outcome": (d.get("stage1") or {}).get("outcome"),
                }
            )
    if not runs:
        return {}
    rank = {r: i for i, r in enumerate(order)}
    ordered = sorted(runs.values(), key=lambda r: (rank.get(r["run"], len(rank)), r["run"]))
    best = max(ordered, key=lambda r: _num(r["successes"]))
    return {
        "source": f"fwdata/{eval_dir}",
        "steps": list(ordered[0]["step_pass"]),
        "runs": ordered,
        "best": best["run"],
        "comparisons": comps,
    }


_FOLLOW_KEYS = ("success", "failure", "reach_b", "distance_m", "yaw_error_deg")


def _follow(fw: Path, eval_dir: str, case: tuple[int, int] | None) -> dict[str, Any]:
    """One eval trial (the round's follow case) across its runs, plus ``r3.json``."""
    if case is None:
        return {}
    folder = fw / eval_dir
    runs: dict[str, dict[str, Any]] = {}
    tol: dict[str, Any] = {}
    for f in sorted(folder.glob("place-error-*.json")):
        d = _dict(f)
        for r in d.get("rows") or []:
            if isinstance(r, dict) and (r.get("level"), r.get("seed")) == case:
                runs[f.stem[len("place-error-") :]] = {k: r.get(k) for k in _FOLLOW_KEYS}
                tol = tol or dict(d.get("tolerance") or {})
    if not runs:
        return {}
    return {
        "source": f"fwdata/{eval_dir}",
        "level": case[0],
        "seed": case[1],
        "tol": tol,
        "runs": runs,
        "r3": _dict(folder / "r3.json"),
    }


def _live_eval_watchers(fw: Path) -> list[dict[str, Any]]:
    watchers: list[dict[str, Any]] = []
    for wlog in sorted(fw.glob("colab/*eval*/watch.log")):
        try:
            text = wlog.read_text(errors="replace")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        except OSError:
            continue
        if not lines:
            continue
        last = lines[-1]
        m = re.search(r"lanes=(\d+)\s+complete=(\d+)\s+rows=(\d+)", last)
        serve_jsons = list(wlog.parent.glob("*serve*.json"))
        sdoc = _dict(serve_jsons[0]) if serve_jsons else {}
        watchers.append(
            {
                "folder": wlog.parent.name,
                "session": sdoc.get("name") or wlog.parent.name,
                "state": sdoc.get("state") or "running",
                "gpu": sdoc.get("gpu") or "L4",
                "lanes": int(m.group(1)) if m else None,
                "complete": int(m.group(2)) if m else None,
                "rows": int(m.group(3)) if m else None,
            }
        )
    return watchers


def _agentqa_assemblies(fw: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for af in sorted(fw.glob("agentqa/cases/jig-*/assembly.json")):
        asm = _dict(af)
        run_doc = _dict(af.parent / "run.json")
        if not asm:
            continue
        clusters_out: list[dict[str, Any]] = []
        for item in asm.get("clusters") or []:
            if not isinstance(item, dict):
                continue
            cl = item.get("cluster") or {}
            hyps = [h for h in (item.get("hypotheses") or []) if isinstance(h, dict)]
            top = hyps[0] if hyps else {}
            clusters_out.append(
                {
                    "cluster_id": cl.get("cluster_id"),
                    "run": cl.get("run"),
                    "step": cl.get("step"),
                    "label": cl.get("label"),
                    "level": cl.get("level"),
                    "size": cl.get("size"),
                    "hypothesis_id": top.get("hypothesis_id"),
                    "rule_id": top.get("rule_id"),
                    "title": top.get("title"),
                    "diagnosis": top.get("diagnosis"),
                    "group": top.get("group"),
                    "support_count": len(top.get("support") or []),
                }
            )
        not_judged = [
            {"what": nj.get("what"), "reason": nj.get("reason")}
            for nj in (asm.get("not_judged") or [])
            if isinstance(nj, dict) and nj.get("fact_id")
        ]
        out.append(
            {
                "case_id": af.parent.name,
                "run_id": asm.get("run_id") or run_doc.get("run_id"),
                "status": asm.get("status") or run_doc.get("status"),
                "started_at": run_doc.get("started_at"),
                "source": f"fwdata/{af.relative_to(fw)}",
                "clusters": clusters_out,
                "not_judged": not_judged[:8],
            }
        )
    out.sort(
        key=lambda x: (1 if x.get("status") == "complete" else 0, str(x.get("started_at") or ""))
    )
    return out


def _jig(fw: Path, step_ids: tuple[str, ...], sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Latest jig2 training/eval outcomes, rollout physics, and next-round status under fwdata."""
    eval_runs: list[dict[str, Any]] = []
    all_rollouts: list[dict[str, Any]] = []
    all_conditions: list[dict[str, Any]] = []

    for sf in sorted(fw.glob("tray/outcomes/jig-*/scores.jsonl")):
        srows = _jl(sf)
        if not srows:
            continue
        orows = _jl(sf.parent / "outcomes.jsonl")
        n = len(srows)
        succ = sum(1 for r in srows if r.get("success") is True)
        ep0 = str(srows[0].get("episode_id") or "")
        run_id = ep0.split("/", 1)[0] if "/" in ep0 else sf.parent.name
        by_lvl: dict[str, dict[str, Any]] = {}
        lvl_step_hits: dict[str, list[int]] = {}
        fails: Counter[str] = Counter()
        lvl_fails: dict[str, Counter[str]] = defaultdict(Counter)
        step_hits: list[int] = [0] * len(step_ids)
        scorer_ver = str(srows[0].get("scorer_version") or "")
        cond_groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        relaxed_thresholds = (5.0, 7.5, 10.0, 15.0, 20.0)
        relaxed_hits = {str(t): 0 for t in relaxed_thresholds}
        reach_b_count = 0

        for idx_row, sr in enumerate(srows):
            orr = orows[idx_row] if idx_row < len(orows) else {}
            lv_int = int(sr.get("level") or orr.get("level") or 0)
            lv = str(lv_int or "?")
            seed_val = int(orr.get("seed") or 0)
            raw_rep = orr.get("repeat")
            rep_val = int(raw_rep) if isinstance(raw_rep, (int, float, str)) else (idx_row % 3)
            is_ok = sr.get("success") is True
            fk = (
                None if is_ok else str(sr.get("failure_kind") or sr.get("failure_class") or "OTHER")
            )

            slot = by_lvl.setdefault(lv, {"n": 0, "successes": 0})
            slot["n"] += 1
            if is_ok:
                slot["successes"] += 1
            elif fk:
                fails[fk] += 1
                lvl_fails[lv][fk] += 1

            st_list = sr.get("step_status")
            l_hits = lvl_step_hits.setdefault(lv, [0] * len(step_ids))
            passed_bools: list[bool] = []
            if isinstance(st_list, list):
                for s_idx in range(min(len(step_ids), len(st_list))):
                    ok_s = st_list[s_idx] == "pass"
                    passed_bools.append(ok_s)
                    if ok_s:
                        step_hits[s_idx] += 1
                        l_hits[s_idx] += 1

            reach_b_idx = step_ids.index("reach_b") if "reach_b" in step_ids else 4
            reached_b = reach_b_idx < len(passed_bools) and passed_bools[reach_b_idx]
            if reached_b:
                reach_b_count += 1

            raw_fin = orr.get("final")
            fin: dict[str, Any] = raw_fin if isinstance(raw_fin, dict) else {}
            dist_m = fin.get("place_distance_m")
            yaw_d = fin.get("place_yaw_error_deg")
            tpos = fin.get("tray_pos_m")
            dist_cm = round(float(dist_m) * 100.0, 2) if isinstance(dist_m, (int, float)) else None
            yaw_deg = round(float(yaw_d), 2) if isinstance(yaw_d, (int, float)) else None
            tray_z = (
                round(float(tpos[2]), 4)
                if isinstance(tpos, list) and len(tpos) >= 3 and isinstance(tpos[2], (int, float))
                else None
            )

            if is_ok:
                for thr in relaxed_thresholds:
                    relaxed_hits[str(thr)] += 1
            elif (
                fk == "L-PLACE-POSE"
                and reached_b
                and dist_cm is not None
                and yaw_deg is not None
                and yaw_deg <= 10.0
            ):
                for thr in relaxed_thresholds:
                    if dist_cm <= thr:
                        relaxed_hits[str(thr)] += 1

            raw_verdict = orr.get("verdict")
            verdict_doc: dict[str, Any] = raw_verdict if isinstance(raw_verdict, dict) else {}
            raw_latch = verdict_doc.get("step_latch_t")
            latch_t = (
                [round(float(x), 2) if isinstance(x, (int, float)) else None for x in raw_latch]
                if isinstance(raw_latch, list)
                else []
            )
            sim_s = (
                round(float(orr["sim_time_s"]), 2)
                if isinstance(orr.get("sim_time_s"), (int, float))
                else None
            )

            rec = {
                "i": idx_row,
                "ep": str(sr.get("episode_id") or f"{run_id}/{idx_row}"),
                "run": run_id,
                "level": lv_int,
                "seed": seed_val,
                "repeat": rep_val,
                "success": is_ok,
                "failure": fk,
                "sim_s": sim_s,
                "dist_cm": dist_cm,
                "yaw_deg": yaw_deg,
                "tray_z": tray_z,
                "steps": passed_bools,
                "latch_t": latch_t,
            }
            all_rollouts.append(rec)
            if seed_val:
                cond_groups[(lv_int, seed_val)].append(rec)

        for lv, slot in by_lvl.items():
            ln = int(slot["n"])
            lsucc = int(slot["successes"])
            slot["p"] = round(lsucc / ln, 4) if ln else 0.0
            slot["wilson"] = _wilson_ci(lsucc, ln)
            slot["failures"] = dict(lvl_fails[lv].most_common())

        repeat_dist: dict[str, list[int]] = {}
        for (lv_int, seed_val), items in sorted(cond_groups.items()):
            k_ok = sum(1 for x in items if x["success"])
            bucket = repeat_dist.setdefault(str(lv_int), [0, 0, 0, 0])
            if 0 <= k_ok <= 3:
                bucket[3 - k_ok] += 1
            dists = [x["dist_cm"] for x in items if x["dist_cm"] is not None]
            yaws = [x["yaw_deg"] for x in items if x["yaw_deg"] is not None]
            fail_c = Counter(x["failure"] for x in items if x["failure"])
            all_conditions.append(
                {
                    "run": run_id,
                    "level": lv_int,
                    "seed": seed_val,
                    "pass_k": k_ok,
                    "n_rep": len(items),
                    "dist_cm_mean": round(sum(dists) / len(dists), 2) if dists else None,
                    "yaw_deg_mean": round(sum(yaws) / len(yaws), 2) if yaws else None,
                    "top_failure": fail_c.most_common(1)[0][0] if fail_c else None,
                    "trials": [
                        {
                            "repeat": x["repeat"],
                            "success": x["success"],
                            "dist_cm": x["dist_cm"],
                            "yaw_deg": x["yaw_deg"],
                            "sim_s": x["sim_s"],
                            "failure": x["failure"],
                        }
                        for x in sorted(items, key=lambda z: z["repeat"])
                    ],
                }
            )

        step_pass = {step_ids[idx]: round(step_hits[idx] / n, 4) for idx in range(len(step_ids))}
        levels_step_pass = {
            lv: {
                step_ids[idx]: round(l_hits[idx] / max(1, int(by_lvl[lv]["n"])), 4)
                for idx in range(len(step_ids))
            }
            for lv, l_hits in sorted(lvl_step_hits.items())
        }
        eval_runs.append(
            {
                "run": run_id,
                "eval_id": sf.parent.name,
                "source": f"fwdata/{sf.relative_to(fw)}",
                "scorer_version": scorer_ver,
                "n": n,
                "successes": succ,
                "p": round(succ / n, 4),
                "wilson": _wilson_ci(succ, n),
                "levels": dict(sorted(by_lvl.items())),
                "step_pass": step_pass,
                "levels_step_pass": levels_step_pass,
                "repeat_dist": repeat_dist,
                "reach_b": reach_b_count,
                "relaxed": relaxed_hits,
                "failures": dict(fails.most_common()),
            }
        )

    m_cut = _dict(fw / "da48" / "cuts" / "M.tar.json")
    n_cut = _dict(fw / "tray" / "jig-n" / "N.tar.json")
    n_exp = _dict(fw / "tray" / "jig-n" / "da50-ft-n-s0" / "expected-100000.json")
    live_evals = _live_eval_watchers(fw)
    assemblies = _agentqa_assemblies(fw)
    active_colab = [s for s in sessions if s.get("state") == "running"]
    if not eval_runs and not m_cut and not n_cut and not live_evals and not assemblies:
        return {}
    best = max(eval_runs, key=lambda r: _num(r.get("successes"))) if eval_runs else None
    return {
        "scene": "jig2",
        "steps": list(step_ids),
        "runs": eval_runs,
        "best": best["run"] if best else None,
        "rollouts": all_rollouts,
        "conditions": all_conditions,
        "live_evals": live_evals,
        "agentqa": assemblies,
        "n_ckpt_done": int(n_exp["ckpt_step"]) if isinstance(n_exp.get("ckpt_step"), int) else None,
        "m_cut": {
            "name": m_cut.get("name"),
            "files": m_cut.get("files"),
            "bytes": m_cut.get("bytes"),
            "source": "fwdata/da48/cuts/M.tar.json",
        }
        if m_cut
        else None,
        "next_cut": {
            "name": n_cut.get("name"),
            "files": n_cut.get("files"),
            "bytes": n_cut.get("bytes"),
            "source": "fwdata/tray/jig-n/N.tar.json",
        }
        if n_cut
        else None,
        "active_sessions": active_colab,
    }


def _catalog(out: Path) -> dict[str, Any]:
    doc = _dict(out / "catalog.json")
    return doc or {"generated": "", "rows": [], "edges": [], "runs": []}


def build(paths: ConsolePaths, out: Path) -> dict[str, int]:
    """Write ``out/story.json``; return the size of each list-valued part."""
    fw = paths.fw_root
    manifest = tasks.load(paths)
    rnd = manifest.story_round()
    tray_steps: tuple[str, ...] = ()
    try:
        tray_steps = tuple(s.id for s in manifest.task("tray").stages)
    except KeyError:
        pass
    if rnd is not None and rnd.train_dir:
        runs, run_dirs = _runs(fw, rnd.train_dir, rnd.max_steps)
        tail, phases = _train_log(run_dirs, rnd.log_run)
    else:
        runs, run_dirs, tail, phases = [], [], [], {}
    ego = _sources(fw)
    bal, sessions = _colab(fw)
    try:
        eval_block: dict[str, Any] = cited.eval_block(paths)
        chain: list[int] = cited.loop_chain(paths)
        detail: dict[str, int] = cited.loop_detail(paths)
    except (OSError, KeyError, TypeError, ValueError):
        eval_block, chain, detail = {}, [], {}
    try:
        round_cited: dict[str, Any] = cited.round_block(paths)
    except (OSError, KeyError, TypeError, ValueError):
        round_cited = {}
    ds = _catalog(out)
    try:
        demo_cited = cited.demo_groups(paths)
    except (OSError, KeyError, TypeError, ValueError):
        demo_cited = {}
    eval_dir = rnd.eval_dir if rnd else None  # a story.pair round always names it (tasks.py)
    pair = _pair(fw, eval_dir, rnd.run_ids) if rnd and eval_dir else {}
    jig = _jig(fw, tray_steps, sessions)
    h1m = _h1m(fw)
    data: dict[str, Any] = {
        "runs": runs,
        "train_log_tail": tail,
        "vm_phases": phases,
        **ego,
        "h1m": h1m,
        "ledger": _ledger(paths.repo),
        "colab_balance": bal,
        "colab_sessions": sessions,
        "ds": ds,
        "eval": eval_block,
        "loop_chain": chain,
        "loop_detail": detail,
        "pair": pair,
        "round": round_cited,
        "follow": _follow(fw, eval_dir, rnd.follow) if rnd and eval_dir else {},
        "demo": demo.build(fw, pair, round_cited, h1m, demo_cited, rnd),
        "jig": jig,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "story.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return {
        k: len(v)
        for k, v in data.items()
        if isinstance(v, (list, dict))
        and k not in ("ds", "eval", "pair", "round", "follow", "demo", "jig")
    } | {"ds_rows": len(ds.get("rows", [])), "pair_runs": len(data["pair"].get("runs", []))}
