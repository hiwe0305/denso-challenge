"""Story index: runs, eval, loop, cost. Ported from the v5 ``build_story.py`` spike.

Every input may be missing on a laptop; a missing input gives an empty value, never an error.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from flywheel.console.index import cited, demo
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


def _runs(fw: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    runs: list[dict[str, Any]] = []
    dirs: list[Path] = []
    for f in sorted(fw.glob("tray/pair60k/*/*/metrics.jsonl")):
        rows = _jl(f)
        train = [r for r in rows if r.get("split") == "train" and "step" in r]
        if not train:
            continue
        val = [r for r in rows if r.get("split") == "val" and "step" in r]
        tail = train[-50:]
        groups: dict[str, list[float]] = defaultdict(list)
        for r in tail:
            for g, v in (r.get("loss_by_group") or {}).items():
                groups[g].append(_num(v))
        first = train[0].get("loss_by_group") or {}
        launch = _dict(f.parent / "launch.json")
        argv = launch.get("argv")
        dirs.append(f.parent)
        runs.append(
            {
                "job": f.parent.name,
                "branch": f.parent.parent.name,
                "release": train[-1].get("release_id"),
                "run_plan_id": train[-1].get("run_plan_id"),
                "step": train[-1]["step"],
                "max_steps": 60000,
                "loss_last": round(sum(_num(r.get("loss")) for r in tail) / len(tail), 3),
                "loss": _series(train, "loss", 4),
                "val": [[r["step"], round(_num(r.get("loss")), 4)] for r in val],
                "thr": _series(train, "throughput"),
                "vram": _series(train, "vram_gb"),
                "gn": _series(train, "grad_norm_action"),
                "groups_last": {g: round(sum(v) / len(v), 4) for g, v in groups.items()},
                "groups_first": {g: round(_num(v), 4) for g, v in first.items()},
                "argv": argv[:14] if isinstance(argv, list) else [],
            }
        )
    return runs, dirs


def _train_log(run_dirs: list[Path]) -> tuple[list[str], dict[str, float]]:
    """Log tail and VM phase seconds of the C_70 run, else of the last run that has a VM log."""
    pick = [d for d in run_dirs if d.parent.name == "C_70" and (d / "vm-logs").is_dir()]
    pick = pick or [d for d in run_dirs if (d / "vm-logs").is_dir()]
    if not pick:
        return [], {}
    logs = pick[0] / "vm-logs"
    tail: list[str] = []
    try:
        text = (logs / "train.log").read_text(errors="replace")
        lines = [seg.split("\r")[-1].strip() for seg in text.splitlines()]
        tail = [ln[:170] for ln in lines if ln][-14:]
    except OSError:
        pass
    phases = _dict(logs / "report.json").get("phases") or {}
    return tail, {
        k: round(_num(v.get("seconds")), 1) for k, v in phases.items() if isinstance(v, dict)
    }


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
_PAIR_ORDER = ("C_ALL", "C_70", "B_ALL", "B_70", "C70_R1")


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


def _pair(fw: Path) -> dict[str, Any]:
    """Stage-1 reads of the pair60k runs at 60k steps; empty when the folder is absent."""
    folder = fw / "tray" / "pair60k" / "stage1-60k"
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
    rank = {r: i for i, r in enumerate(_PAIR_ORDER)}
    ordered = sorted(runs.values(), key=lambda r: (rank.get(r["run"], len(rank)), r["run"]))
    best = max(ordered, key=lambda r: _num(r["successes"]))
    return {
        "source": "fwdata/tray/pair60k/stage1-60k",
        "steps": list(ordered[0]["step_pass"]),
        "runs": ordered,
        "best": best["run"],
        "comparisons": comps,
    }


# the trial that "Follow one failure" walks through (one-site design 6.7)
FOLLOW = (1, 1000107)
_FOLLOW_KEYS = ("success", "failure", "reach_b", "distance_m", "yaw_error_deg")


def _follow(fw: Path) -> dict[str, Any]:
    """One eval trial across every pair60k run, plus the targeted / other split (``r3.json``)."""
    folder = fw / "tray" / "pair60k" / "stage1-60k"
    runs: dict[str, dict[str, Any]] = {}
    tol: dict[str, Any] = {}
    for f in sorted(folder.glob("place-error-*.json")):
        d = _dict(f)
        for r in d.get("rows") or []:
            if isinstance(r, dict) and (r.get("level"), r.get("seed")) == FOLLOW:
                runs[f.stem[len("place-error-") :]] = {k: r.get(k) for k in _FOLLOW_KEYS}
                tol = tol or dict(d.get("tolerance") or {})
    if not runs:
        return {}
    return {
        "source": "fwdata/tray/pair60k/stage1-60k",
        "level": FOLLOW[0],
        "seed": FOLLOW[1],
        "tol": tol,
        "runs": runs,
        "r3": _dict(folder / "r3.json"),
    }


def _catalog(out: Path) -> dict[str, Any]:
    doc = _dict(out / "catalog.json")
    return doc or {"generated": "", "rows": [], "edges": [], "runs": []}


def build(paths: ConsolePaths, out: Path) -> dict[str, int]:
    """Write ``out/story.json``; return the size of each list-valued part."""
    fw = paths.fw_root
    runs, run_dirs = _runs(fw)
    tail, phases = _train_log(run_dirs)
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
    pair = _pair(fw)
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
        "follow": _follow(fw),
        "demo": demo.build(fw, pair, round_cited, h1m, demo_cited),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "story.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return {
        k: len(v)
        for k, v in data.items()
        if isinstance(v, (list, dict))
        and k not in ("ds", "eval", "pair", "round", "follow", "demo")
    } | {"ds_rows": len(ds.get("rows", [])), "pair_runs": len(data["pair"].get("runs", []))}
