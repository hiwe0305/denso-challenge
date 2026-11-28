"""``story.json · jig``: the round on the jig scene (``tray-jig-r1``, story DA-53).

The round is the one of ``seed/tasks.yaml`` listing ``story.jig``; without it the block is ``{}``.
Its eval numbers are **copied** from the ``results.json`` that
``python -m flywheel_psi0.tray.eval_results ... --repeats 3 --json results.json`` writes beside
each run's outcome folder (shape of ``eval_results.py`` at commit 2b67d2ba, 26/11/2026). The
console never recomputes a rate or an interval (the console imports no adapter; import-linter
"Console reads files, never lanes or adapters"). The index only compares a copied CI lower bound
with a threshold declared in ``tasks.yaml`` and writes a code ("met", "not_met", "better",
"worse", "not_distinguished"); the sentences are the pages'. Words that compare these runs with the
DA-34 runs are never written here (rule 4 of ``jig-m-rules``).

Shape::

    jig = {
      "round": "tray-jig-r1", "scene": "jig2", "doc": ..., "source": "seed/tasks.yaml ...",
      "rules": {whole_task, per_level, place, read_at, source{vi,en}},   # from tasks.yaml
      "eval_set": {"path", "conditions_sha256", "sha_ok"}, "rollouts_expected", "scorer_version",
      "runs": [train entries in manifest order (story.round_runs)],
      "train_log_tail": [...], "vm_phases": {...},                      # of log_run
      "evals": [one per run, manifest order:
        {"run", "role", "status": "ready" | "missing" | "blocked" | "withheld",
         "results_source": "fwdata/<outcome>/results.json",
         "command": results_cmd                 # only when "missing"
         "problems": [codes, e.g. "rollouts 179 != 180"],
         "headline": {n, conditions, successes, p, ci, wilson, wilson_method, failures,
                      step_pass},               # copied verbatim
         "levels": {"1": {...same...}, "2": {...}},
         "place": {"p", "successes", "n", "ci": None},   # headline step_pass.place
         "bootstrap_seed", "scorer_version", "plan_mismatch",
         "readings": [{"rule": "1", "scope": "whole_task", "threshold", "lower", "verdict"},
                      {"rule": "2", "scope": "level", "level": "1", ...}, {... "level": "2"},
                      {"rule": "3", "scope": "place", "threshold", "lower": None,
                       "verdict": None, "why": "no_ci"}]}],
      "paired": {"variant", "baseline", "status", "source", "command" (when missing), "problems",
                 "headline", "by_level",         # copied from paired.repeats of the variant
                 "readings": [{"rule": "n2", "scope": "whole_task", "diff", "ci", "ci_vs_0",
                               "verdict": "better" | "worse" | "not_distinguished" | None},
                              {"rule": "n3", "scope": "level", "level": "2", ...}]},
      "featured": after_round's run id if its eval is ready, else the baseline's, else None,
      # descriptive, from the runs' outcome folders (scores.jsonl, outcomes.jsonl): no interval
      "steps", "outcomes": [per run: counts, step pass, repeat spread, relaxed placement],
      "rollouts", "conditions", "live_evals", "agentqa", "cuts", "m_cut", "next_cut",
      "n_ckpt_done", "active_sessions",
    }

A reading is given only when the file meets every condition before reading (story DA-53 "Luật
đọc"): ``rollouts`` equals the round's ``rollouts_expected``, ``missing`` is empty, the eval set's
``conditions.sha256`` file holds the declared value, ``bootstrap_seed`` equals the run's declared
seed and ``scorer_version`` the round's. Otherwise the status is "blocked", ``problems`` names
each broken condition, the numbers stay (copied) and every verdict is None with ``why``
"blocked". No ``results.json`` gives status "missing" with the command that writes it and no
number (never 0). A run listed in the round's ``withhold_eval`` gives only
``{"run", "role", "status": "withheld"}`` and none of its rollouts.

Rules 1 and 2 say "met" when the lower bound is **at or above** the threshold
(``docs/he/tray-jig.md`` §2: "từ 0,80 trở lên"). The lower bound is compared after rounding to 9
decimals, which only absorbs float noise of a mean of per-condition rates. ``results.json`` has no
interval for the ``place`` step, so rule 3 shows the rate and gives no verdict (story DA-53,
"Điều chỉnh" point 3).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from flywheel.console.index.tasks import Round, Run

RESULTS = "results.json"
# copied verbatim from results.json (headline and each level)
FIGURE_KEYS = (
    "n", "conditions", "successes", "p", "ci", "wilson", "wilson_method", "failures", "step_pass",
)  # fmt: skip
CI_VS_0 = {"above": "better", "below": "worse", "contains": "not_distinguished"}
# jig-n-rules rule 3: N against M on level 2 alone ("Đây là nơi dữ liệu thêm nhắm tới")
PAIRED_LEVEL = "2"
_RELAXED_CM = (5.0, 7.5, 10.0, 15.0, 20.0)


# ------------------------------------------------------------------ file helpers
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


def _dict(p: Path) -> dict[str, Any]:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _obj(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _ci(v: Any) -> list[float] | None:
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return [float(v[0]), float(v[1])]
    return None


# ------------------------------------------------------------------ eval set
def _sha_ok(fw: Path, rnd: Round) -> tuple[bool, str | None]:
    """The eval set's ``conditions.sha256`` file holds the declared value; else the problem."""
    f = fw / (rnd.eval_set or "") / "conditions.sha256"
    try:
        text = f.read_text(encoding="utf-8").split()
    except OSError:
        return False, "conditions.sha256 absent"
    if not text or text[0].lower() != rnd.conditions_sha256:
        return False, "conditions.sha256 mismatch"
    return True, None


# ------------------------------------------------------------------ one run's results.json
def _figures(d: Any) -> dict[str, Any]:
    return {k: d.get(k) for k in FIGURE_KEYS} if isinstance(d, dict) else {}


def _verdict(lower: float | None, threshold: float) -> str | None:
    if lower is None:
        return None
    return "met" if round(lower, 9) >= threshold else "not_met"


def _readings(
    rnd: Round, headline: dict[str, Any], levels: dict[str, Any], blocked: bool
) -> list[dict[str, Any]]:
    rules = rnd.rules or {}

    def one(rule: str, scope: str, threshold: float, ci: Any, **extra: Any) -> dict[str, Any]:
        bounds = _ci(ci)
        lower = bounds[0] if bounds else None
        r: dict[str, Any] = {"rule": rule, "scope": scope, **extra, "threshold": threshold}
        r["lower"] = lower
        if blocked:
            r |= {"verdict": None, "why": "blocked"}
        elif lower is None:
            r |= {"verdict": None, "why": "no_ci"}
        else:
            r["verdict"] = _verdict(lower, threshold)
        return r

    out = [one("1", "whole_task", rules.get("whole_task", 0.0), headline.get("ci"))]
    for lv in sorted(levels):
        out.append(one("2", "level", rules.get("per_level", 0.0), levels[lv].get("ci"), level=lv))
    place = rules.get("place", 0.0)
    out.append(
        {"rule": "3", "scope": "place", "threshold": place, "lower": None, "verdict": None,
         "why": "blocked" if blocked else "no_ci"}
    )  # fmt: skip
    return out


def _place(headline: dict[str, Any]) -> dict[str, Any]:
    p = (headline.get("step_pass") or {}).get("place")
    n = headline.get("n")
    if isinstance(p, (int, float)) and isinstance(n, int) and not isinstance(n, bool):
        return {"p": p, "successes": round(p * n), "n": n, "ci": None}
    return {"p": None, "successes": None, "n": None, "ci": None}


def _eval(fw: Path, rnd: Round, run: Run, sha_problem: str | None) -> dict[str, Any]:
    src = f"{run.outcome}/{RESULTS}"
    head: dict[str, Any] = {"run": run.id, "role": run.role}
    if run.id in rnd.withhold_eval:
        return head | {"status": "withheld"}
    head["results_source"] = f"fwdata/{src}"
    f = fw / src
    if not f.is_file():
        return head | {"status": "missing", "command": run.results_cmd, "problems": []}
    doc = _dict(f)
    problems: list[str] = []
    if not doc:
        problems.append("results.json unreadable")
    rollouts = doc.get("rollouts")
    if rollouts != rnd.rollouts_expected:
        problems.append(f"rollouts {rollouts} != {rnd.rollouts_expected}")
    missing = doc.get("missing")
    if not isinstance(missing, list) or missing:
        problems.append("missing rollouts")
    if sha_problem:
        problems.append(sha_problem)
    seed = doc.get("bootstrap_seed")
    if seed != run.bootstrap_seed:
        problems.append(f"bootstrap_seed {seed} != {run.bootstrap_seed}")
    version = doc.get("scorer_version")
    if version != rnd.scorer_version:
        problems.append(f"scorer_version {version} != {rnd.scorer_version}")
    headline = _figures(doc.get("headline"))
    if _ci(headline.get("ci")) is None:
        problems.append("headline without ci")
    raw_levels = _obj(doc.get("levels"))
    want = [str(x) for x in rnd.raw.get("eval", {}).get("levels") or []]
    levels = {
        lv: _figures(raw_levels.get(lv)) for lv in want if isinstance(raw_levels.get(lv), dict)
    }
    if want and len(levels) != len(want):
        problems.append(f"levels {sorted(levels)} != {want}")
    blocked = bool(problems)
    return head | {
        "status": "blocked" if blocked else "ready",
        "problems": problems,
        "headline": headline,
        "levels": levels,
        "place": _place(headline),
        "bootstrap_seed": seed,
        "scorer_version": version,
        "plan_mismatch": doc.get("plan_mismatch"),
        "readings": _readings(rnd, headline, levels, blocked),
    }


# ------------------------------------------------------------------ N against M
def _paired_reading(rule: str, scope: str, d: Any, blocked: bool, **extra: Any) -> dict[str, Any]:
    d = d if isinstance(d, dict) else {}
    where = d.get("ci_vs_0")
    r: dict[str, Any] = {"rule": rule, "scope": scope, **extra, "diff": d.get("diff"),
                         "ci": d.get("ci"), "ci_vs_0": where}  # fmt: skip
    if blocked:
        return r | {"verdict": None, "why": "blocked"}
    if where not in CI_VS_0:
        return r | {"verdict": None, "why": "no_ci"}
    return r | {"verdict": CI_VS_0[where]}


def _paired(fw: Path, rnd: Round, evals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """``paired.repeats`` of the after-round run's results.json (written with ``--baseline``)."""
    var, base = rnd.after_round, rnd.baseline
    head: dict[str, Any] = {"variant": var, "baseline": base}
    ev, eb = evals.get(var) or {}, evals.get(base) or {}
    if "withheld" in (ev.get("status"), eb.get("status")):
        return head | {"status": "withheld"}
    run = next(r for r in rnd.runs if r.id == var)
    src = f"{run.outcome}/{RESULTS}"
    head["source"] = f"fwdata/{src}"
    rep = _obj(_obj(_dict(fw / src).get("paired")).get("repeats"))
    if ev.get("status") == "missing" or not rep.get("headline"):
        return head | {"status": "missing", "command": run.results_cmd, "problems": []}
    problems = [f"{var}: {p}" for p in ev.get("problems") or []]
    problems += [f"{base}: {p}" for p in eb.get("problems") or []]
    if eb.get("status") == "missing":
        problems.append(f"{base}: results.json missing")
    blocked = bool(problems)
    by_level = _obj(rep.get("by_level"))
    return head | {
        "status": "blocked" if blocked else "ready",
        "problems": problems,
        "headline": rep.get("headline"),
        "by_level": by_level,
        "readings": [
            _paired_reading("n2", "whole_task", rep.get("headline"), blocked),
            _paired_reading("n3", "level", by_level.get(PAIRED_LEVEL), blocked, level=PAIRED_LEVEL),
        ],  # fmt: skip
    }


# ------------------------------------------------------------------ descriptive outcome rows
def _outcome(
    fw: Path, run: Run, step_ids: tuple[str, ...]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Counts, step pass, repeat spread and per-rollout physics of one run's outcome folder.

    Descriptive only: no interval and no verdict (those come from ``results.json``).
    """
    folder = fw / (run.outcome or "")
    srows = _jl(folder / "scores.jsonl")
    if not srows:
        return None, [], []
    orows = _jl(folder / "outcomes.jsonl")
    n = len(srows)
    rollouts: list[dict[str, Any]] = []
    by_lvl: dict[str, dict[str, Any]] = {}
    lvl_hits: dict[str, list[int]] = {}
    lvl_fails: dict[str, Counter[str]] = defaultdict(Counter)
    fails: Counter[str] = Counter()
    hits = [0] * len(step_ids)
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    relaxed = {str(t): 0 for t in _RELAXED_CM}
    reach_b = 0
    reach_idx = step_ids.index("reach_b") if "reach_b" in step_ids else 4
    for i, sr in enumerate(srows):
        orr = orows[i] if i < len(orows) else {}
        lv_int = int(sr.get("level") or orr.get("level") or 0)
        lv = str(lv_int or "?")
        seed = int(orr.get("seed") or 0)
        raw_rep = orr.get("repeat")
        rep = int(raw_rep) if isinstance(raw_rep, (int, float, str)) else i % 3
        ok = sr.get("success") is True
        fk = None if ok else str(sr.get("failure_kind") or sr.get("failure_class") or "OTHER")
        slot = by_lvl.setdefault(lv, {"n": 0, "successes": 0})
        slot["n"] += 1
        if ok:
            slot["successes"] += 1
        elif fk:
            fails[fk] += 1
            lvl_fails[lv][fk] += 1
        status = sr.get("step_status")
        lh = lvl_hits.setdefault(lv, [0] * len(step_ids))
        passed: list[bool] = []
        if isinstance(status, list):
            for k in range(min(len(step_ids), len(status))):
                passed.append(status[k] == "pass")
                if passed[-1]:
                    hits[k] += 1
                    lh[k] += 1
        reached_b = reach_idx < len(passed) and passed[reach_idx]
        reach_b += reached_b
        fin = _obj(orr.get("final"))
        dist_m, yaw, tpos = (
            fin.get("place_distance_m"), fin.get("place_yaw_error_deg"), fin.get("tray_pos_m")
        )  # fmt: skip
        dist_cm = round(float(dist_m) * 100.0, 2) if isinstance(dist_m, (int, float)) else None
        yaw_deg = round(float(yaw), 2) if isinstance(yaw, (int, float)) else None
        tray_z = (
            round(float(tpos[2]), 4)
            if isinstance(tpos, list) and len(tpos) >= 3 and isinstance(tpos[2], (int, float))
            else None
        )
        if ok:
            for t in _RELAXED_CM:
                relaxed[str(t)] += 1
        elif fk == "L-PLACE-POSE" and reached_b and dist_cm is not None and yaw_deg is not None:
            for t in _RELAXED_CM:
                if yaw_deg <= 10.0 and dist_cm <= t:
                    relaxed[str(t)] += 1
        verdict = _obj(orr.get("verdict"))
        latch = verdict.get("step_latch_t")
        rec = {
            "i": i,
            "ep": str(sr.get("episode_id") or f"{run.id}/{i}"),
            "run": run.id,
            "level": lv_int,
            "seed": seed,
            "repeat": rep,
            "success": ok,
            "failure": fk,
            "sim_s": round(float(orr["sim_time_s"]), 2)
            if isinstance(orr.get("sim_time_s"), (int, float))
            else None,
            "dist_cm": dist_cm,
            "yaw_deg": yaw_deg,
            "tray_z": tray_z,
            "steps": passed,
            "latch_t": [round(float(x), 2) if isinstance(x, (int, float)) else None for x in latch]
            if isinstance(latch, list)
            else [],
        }
        rollouts.append(rec)
        if seed:
            groups[(lv_int, seed)].append(rec)
    for lv, slot in by_lvl.items():
        slot["p"] = round(slot["successes"] / slot["n"], 4) if slot["n"] else None
        slot["failures"] = dict(lvl_fails[lv].most_common())
    conditions: list[dict[str, Any]] = []
    spread: dict[str, list[int]] = {}
    for (lv_int, seed), items in sorted(groups.items()):
        k_ok = sum(1 for x in items if x["success"])
        bucket = spread.setdefault(str(lv_int), [0, 0, 0, 0])
        if 0 <= k_ok <= 3:
            bucket[3 - k_ok] += 1
        dists = [x["dist_cm"] for x in items if x["dist_cm"] is not None]
        yaws = [x["yaw_deg"] for x in items if x["yaw_deg"] is not None]
        fc = Counter(x["failure"] for x in items if x["failure"])
        conditions.append(
            {
                "run": run.id,
                "level": lv_int,
                "seed": seed,
                "pass_k": k_ok,
                "n_rep": len(items),
                "dist_cm_mean": round(sum(dists) / len(dists), 2) if dists else None,
                "yaw_deg_mean": round(sum(yaws) / len(yaws), 2) if yaws else None,
                "top_failure": fc.most_common(1)[0][0] if fc else None,
                "trials": [
                    {
                        k: x[k]
                        for k in ("repeat", "success", "dist_cm", "yaw_deg", "sim_s", "failure")
                    }
                    for x in sorted(items, key=lambda z: z["repeat"])
                ],  # fmt: skip
            }
        )
    succ = sum(1 for r in rollouts if r["success"])
    row = {
        "run": run.id,
        "eval_id": folder.name,
        "source": f"fwdata/{run.outcome}/scores.jsonl",
        "scorer_version": str(srows[0].get("scorer_version") or ""),
        "n": n,
        "successes": succ,
        "p": round(succ / n, 4),
        "levels": dict(sorted(by_lvl.items())),
        "step_pass": {s: round(hits[k] / n, 4) for k, s in enumerate(step_ids)},
        "levels_step_pass": {
            lv: {s: round(h[k] / max(1, int(by_lvl[lv]["n"])), 4) for k, s in enumerate(step_ids)}
            for lv, h in sorted(lvl_hits.items())
        },
        "repeat_dist": spread,
        "reach_b": reach_b,
        "relaxed": relaxed,
        "failures": dict(fails.most_common()),
    }
    return row, rollouts, conditions


def live_eval_watchers(fw: Path) -> list[dict[str, Any]]:
    """Eval watchers running on Colab (``colab/*eval*/watch.log``), last line of each."""
    watchers: list[dict[str, Any]] = []
    for wlog in sorted(fw.glob("colab/*eval*/watch.log")):
        try:
            lines = [ln.strip() for ln in wlog.read_text(errors="replace").splitlines()]
            lines = [ln for ln in lines if ln]
        except OSError:
            continue
        if not lines:
            continue
        m = re.search(r"lanes=(\d+)\s+complete=(\d+)\s+rows=(\d+)", lines[-1])
        serve = list(wlog.parent.glob("*serve*.json"))
        sdoc = _dict(serve[0]) if serve else {}
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


def agentqa_assemblies(fw: Path) -> list[dict[str, Any]]:
    """Agent QA cases on the jig runs (``agentqa/cases/jig-*/assembly.json``)."""
    out: list[dict[str, Any]] = []
    for af in sorted(fw.glob("agentqa/cases/jig-*/assembly.json")):
        asm = _dict(af)
        run_doc = _dict(af.parent / "run.json")
        if not asm:
            continue
        clusters: list[dict[str, Any]] = []
        for item in asm.get("clusters") or []:
            if not isinstance(item, dict):
                continue
            cl = item.get("cluster") or {}
            hyps = [h for h in (item.get("hypotheses") or []) if isinstance(h, dict)]
            top = hyps[0] if hyps else {}
            clusters.append(
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
                "clusters": clusters,
                "not_judged": not_judged[:8],
            }
        )
    out.sort(key=lambda x: (x.get("status") == "complete", str(x.get("started_at") or "")))
    return out


def _cut(fw: Path, run: Run) -> dict[str, Any] | None:
    doc = _dict(fw / run.cut) if run.cut else {}
    if not doc:
        return None
    return {k: doc.get(k) for k in ("name", "files", "bytes")} | {"source": f"fwdata/{run.cut}"}


# ------------------------------------------------------------------ the block
def build(
    fw: Path,
    rnd: Round | None,
    runs: list[dict[str, Any]],
    train_log_tail: list[str],
    vm_phases: dict[str, float],
    step_ids: tuple[str, ...],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    """The ``jig`` block of ``story.json`` for the round listing ``story.jig`` (``{}`` if none).

    ``runs``, ``train_log_tail`` and ``vm_phases`` are the round's training runs and VM log read
    by ``story.round_runs`` and ``story._train_log``.
    """
    if rnd is None:
        return {}
    sha_ok, sha_problem = _sha_ok(fw, rnd)
    evals = [_eval(fw, rnd, r, sha_problem) for r in rnd.runs]
    by_id = {e["run"]: e for e in evals}
    ready = {e["run"] for e in evals if e["status"] == "ready"}
    featured = next((x for x in (rnd.after_round, rnd.baseline) if x in ready), None)
    outcomes: list[dict[str, Any]] = []
    rollouts: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    for r in rnd.runs:
        if r.id in rnd.withhold_eval:
            continue
        row, rr, cc = _outcome(fw, r, step_ids)
        if row is not None:
            outcomes.append(row)
            rollouts += rr
            conditions += cc
    cuts = {r.id: c for r in rnd.runs if (c := _cut(fw, r)) is not None}
    after = next((e for e in runs if e.get("branch") == rnd.after_round), {})
    return {
        "round": rnd.id,
        "scene": rnd.scene,
        "doc": rnd.raw.get("doc"),
        "source": f"seed/tasks.yaml round {rnd.id}; fwdata/<outcome>/{RESULTS}",
        "rules": rnd.rules,
        "eval_set": {
            "path": f"fwdata/{rnd.eval_set}",
            "conditions_sha256": rnd.conditions_sha256,
            "sha_ok": sha_ok,
        },
        "rollouts_expected": rnd.rollouts_expected,
        "scorer_version": rnd.scorer_version,
        "runs": runs,
        "train_log_tail": train_log_tail,
        "vm_phases": vm_phases,
        "evals": evals,
        "paired": _paired(fw, rnd, by_id),
        "featured": featured,
        "steps": list(step_ids),
        "outcomes": outcomes,
        "rollouts": rollouts,
        "conditions": conditions,
        "live_evals": live_eval_watchers(fw),
        "agentqa": agentqa_assemblies(fw),
        "cuts": cuts,
        "m_cut": cuts.get(rnd.baseline),  # kept for the pages until task 2.4
        "next_cut": cuts.get(rnd.after_round),
        "n_ckpt_done": after.get("ckpt_step"),
        "active_sessions": [s for s in sessions if s.get("state") == "running"],
    }
