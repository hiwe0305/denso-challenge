"""``story.json · demo``: every number the 17/11 story pages show, each with its source.

Numbers come from files under FW_ROOT (read here) or from ``seed/cited.yaml`` (a verbatim quote of
the doc). A missing input gives an empty or ``None`` value, never an error, and never a typed-in
number.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flywheel.console.index.tasks import Round

# run order, folders, roles and watcher session names come from the round (seed/tasks.yaml)
_TILT_PLACE = ("L-PLACE-POSE", "L-TRAY-TILT")


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _dict(p: Path) -> dict[str, Any]:
    obj = _json(p)
    return obj if isinstance(obj, dict) else {}


def _jl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _cm(m: Any) -> str:
    """0.075 -> "7.5", 0.05 -> "5" (a tolerance in metres as a cm label)."""
    try:
        return f"{round(float(m) * 100, 1):g}"
    except (TypeError, ValueError):
        return "?"


def _item(c: dict[str, Any] | None, **extra: Any) -> dict[str, Any] | None:
    if not c:
        return None
    return {**c, **extra}


# ------------------------------------------------------------------ 1 · ladder
def ladder(
    fw: Path, pair: dict[str, Any], cites: dict[str, dict[str, Any]], rnd: Round
) -> dict[str, Any]:
    """Runs out of n per model: tray on B (cited), relaxed placement, success at the 5 cm rule."""
    folder = fw / (rnd.eval_dir or "")
    succ = {r["run"]: r.get("successes") for r in pair.get("runs") or []}
    onb = (cites.get("on_table_b") or {}).get("value") or {}
    runs: dict[str, Any] = {}
    tols: list[str] = []
    n_all: set[Any] = set()
    yaws: list[dict[str, Any]] = []
    for run in rnd.run_ids:
        d = _dict(folder / f"place-error-{run}.json")
        curve = [
            c
            for c in (d.get("relaxed_curve") or {}).get(rnd.level_key) or []
            if isinstance(c, dict)
        ]
        if not curve and run not in succ and run not in onb:
            continue
        relaxed = {_cm(c.get("distance_m")): c.get("relaxed_successes") for c in curve}
        n_all |= {c.get("n") for c in curve}
        yaws.extend(curve)
        for k in relaxed:
            if k not in tols:
                tols.append(k)
        runs[run] = {"on_table_b": onb.get(run), "relaxed": relaxed, "success": succ.get(run)}
    if not runs:
        return {}
    tols.sort(key=float, reverse=True)
    # cross-check the cited row of the round's model against its rollout file (onb.py's column)
    after = rnd.after_round
    roll = _jl(folder / rnd.rollouts) if rnd.rollouts else []
    check = {after: sum(1 for r in roll if r.get("on_table_b") is True)} if roll else {}
    yaw = {c.get("yaw_error_deg") for c in yaws}
    return {
        "source": f"fwdata/{rnd.eval_dir}/place-error-<id>.json relaxed_curve['{rnd.level_key}']; "
        "success = story.pair.runs[].successes",
        "n": next(iter(n_all)) if len(n_all) == 1 else None,
        "yaw_tol_deg": next(iter(yaw)) if len(yaw) == 1 else None,
        "rows": ["on_table_b", *tols[:-1], "success"] if tols else ["on_table_b", "success"],
        "relaxed_cm": tols,
        "standard_cm": tols[-1] if tols else None,
        "runs": runs,
        "on_table_b": _item(cites.get("on_table_b"), secondary=True, check_from_rollouts=check),
        "omitted": [
            {
                "row": "placed, released, tray still",
                "reason": "no file or doc gives it for every model (the round's model included)",
            }
        ],
    }


# ------------------------------------------------------------------ 2 · round 1 reading
def round1(fw: Path, cites: dict[str, dict[str, Any]], rnd: Round) -> dict[str, Any]:
    if not cites:
        return {}
    folder = fw / (rnd.eval_dir or "")
    from_file: dict[str, Any] = {}
    for run in (rnd.baseline, rnd.after_round):
        g = (_dict(folder / f"place-error-{run}.json").get("groups") or {}).get(
            "levels 1-2, L-PLACE-POSE"
        ) or {}
        dist = g.get("distance_m")
        if isinstance(dist, list) and len(dist) == 3:
            from_file[run] = round(float(dist[2]) * 100, 2)
    return {
        "source": "docs/he/tray.md §20.18",
        "max_place_error_cm": _item(
            cites.get("max_place_error_cm"),
            check_from_file=from_file,
            check_source=f"fwdata/{rnd.eval_dir}/place-error-<id>.json "
            "groups['levels 1-2, L-PLACE-POSE'].distance_m[2]",
        ),
        "relaxed_7_5cm": _item(cites.get("relaxed_7_5cm")),
        "tilt_at_place": _item(cites.get("tilt_at_place")),
        "not_a_cause": _item(cites.get("not_a_cause")),
        "rule_r1": _item(cites.get("rule_r1")),
        "rule_r2": _item(cites.get("rule_r2")),
        "stop": _item(cites.get("stop")),
    }


# ------------------------------------------------------------------ 3 · QA bench
def qa_bench(cites: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not cites:
        return {}
    bench = (cites.get("code_bench") or {}).get("value") or {}
    caught = (cites.get("code_caught") or {}).get("value") or {}
    fa = (cites.get("code_false_alarms") or {}).get("value") or {}
    agent = cites.get("agent_nemotron")
    psi = cites.get("psi_data_bench")
    return {
        "source": "docs/g0/defect-bench.md §6, docs/g0/agent-qa.md §3.2 and §3.7",
        "code_layer": {
            "caught": caught.get("hit"),
            "planted": bench.get("planted"),
            "kinds": bench.get("kinds"),
            "false_alarms": fa.get("hit"),
            "clean_units": fa.get("of"),
            "false_alarm_is_upper_bound": True,
            "date": (cites.get("code_date") or {}).get("value"),
            "cites": [
                c
                for c in (
                    cites.get("code_date"),
                    cites.get("code_bench"),
                    cites.get("code_caught"),
                    cites.get("code_false_alarms"),
                    cites.get("code_false_alarms_3_2"),
                )
                if c
            ],
        },
        "agent_layer_nemotron": _item(agent),
        "psi_data_bench": _item(
            psi,
            what="dataset copies of the authors' psi-data (episodes), not the job-log bench",
            status=_item(cites.get("psi_data_not_scored")),
        ),
    }


# ------------------------------------------------------------------ 4 · failure share
def fail_share(pair: dict[str, Any], rnd: Round) -> dict[str, Any]:
    """Per base model, (L-PLACE-POSE + L-TRAY-TILT) / failed runs, from ``pair.runs[].failures``."""
    runs: dict[str, Any] = {}
    for r in pair.get("runs") or []:
        if r.get("run") == rnd.after_round:
            continue
        f = r.get("failures") or {}
        failed = sum(int(v) for v in f.values() if isinstance(v, (int, float)))
        hit = sum(int(f.get(k) or 0) for k in _TILT_PLACE)
        if failed:
            runs[r["run"]] = {
                "place_pose": int(f.get("L-PLACE-POSE") or 0),
                "tray_tilt": int(f.get("L-TRAY-TILT") or 0),
                "failed": failed,
                "n": r.get("n"),
                "share": round(hit / failed, 4),
            }
    if not runs:
        return {}
    shares = [v["share"] for v in runs.values()]
    return {
        "source": f"story.pair.runs[].failures (fwdata/{rnd.eval_dir})",
        "labels": list(_TILT_PLACE),
        "runs": runs,
        "min": min(shares),
        "max": max(shares),
    }


# ------------------------------------------------------------------ 5 · diagnose
_TICKET = re.compile(r"DA-\d+")


def diagnose(rnd: dict[str, Any], cites: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not cites and not rnd:
        return {}
    to_data: list[str] = []
    tickets: dict[str, list[str]] = {}
    for c in rnd.get("clusters") or []:
        m = _TICKET.search(str(c.get("intervention") or ""))
        if m:
            tickets.setdefault(m.group(0), []).append(c["id"])
        else:
            to_data.append(c["id"])
    return {
        "source": "docs/he/tray.md §20.3, §20.9, §20.11; clusters from story.round.clusters",
        "checks": [
            {"id": k, **v} for k in ("H1", "H2", "H3", "delay_sync_camera") if (v := cites.get(k))
        ],
        "to_data": to_data,
        "tickets": tickets,
        "cost_cu": _item(cites.get("cost_cu")),
    }


# ------------------------------------------------------------------ 7 · round cost
def round_cost(cites: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lines = [{"id": k, **v} for k in ("train_1", "train_2", "serve") if (v := cites.get(k))]
    if not lines:
        return {}
    total = round(sum(float(x["value"]) for x in lines), 2)
    rate = (cites.get("usd_per_cu") or {}).get("value") or {}
    usd_per_cu = (
        round(float(rate["usd"]) / float(rate["cu"]), 4)
        if rate.get("cu") and rate.get("usd")
        else None
    )
    return {
        "source": "docs/he/tray.md §20.18 'Chi phí của 7.6–7.7' (measured, ledger DA-34)",
        "kind": "measured",
        "lines": lines,
        "total_cu": total,
        "total_note": "sum of the three lines; serve is 'about 23.4' in the doc",
        "serve_waste": _item(cites.get("serve_waste")),
        "eval_client": _item(cites.get("eval_client")),
        "usd_per_cu": usd_per_cu,
        "usd_rate": _item(cites.get("usd_per_cu")),
        "total_usd": round(total * usd_per_cu, 2) if usd_per_cu else None,
    }


# ------------------------------------------------------------------ 6 · design (slide 9)
def colab_sessions(fw: Path, sessions: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Training and one-lane serve sessions of the pair runs: GPU and the watcher's wall CU.

    ``train`` counts only an exit with reason ``ended`` (the run finished); ``serve`` takes the
    last exit event. Sessions without such an event give ``None``.
    """
    out: dict[str, dict[str, Any]] = {}
    for reg in sorted(fw.glob("colab/batch-*/da34-*.json")):
        stem = reg.stem[len("da34-") :]
        kind = "serve" if stem.startswith("serve-") else "train"
        model = sessions.get(stem.removeprefix("serve-"))
        if model is None:
            continue
        exits = [e for e in _jl(reg.with_suffix(".jsonl")) if e.get("event") == "exit"]
        if kind == "train":
            exits = [e for e in exits if e.get("reason") == "ended"]
        last = exits[-1] if exits else {}
        row = out.setdefault(model, {})
        row[kind] = {
            "session": reg.stem,
            "gpu": _dict(reg).get("gpu"),
            "wall_cu": last.get("wall_cu"),
            "file": str(reg.relative_to(fw).with_suffix(".jsonl")),
        }
    return out


def _measured(sessions: dict[str, dict[str, Any]], kind: str) -> dict[str, Any]:
    vals = {m: s[kind]["wall_cu"] for m, s in sessions.items() if s.get(kind, {}).get("wall_cu")}
    gpus = sorted({s[kind]["gpu"] for s in sessions.values() if s.get(kind, {}).get("gpu")})
    return {
        "per_model_cu": vals,
        "min_cu": min(vals.values()) if vals else None,
        "max_cu": max(vals.values()) if vals else None,
        "gpu": gpus,
        "kind": "measured",
        "source": "fwdata/colab/batch-*/da34-*.jsonl, watcher 'exit' event wall_cu",
    }


def _artifact(name: str, source: str, **value: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"id": name, "kind": "artifact", "source": source}
    if value:
        out["value"] = value
    return out


def design(
    fw: Path,
    pair: dict[str, Any],
    h1m: dict[str, Any],
    cites: dict[str, dict[str, Any]],
    rnd: Round,
) -> dict[str, Any]:
    def c(name: str, kind: str, **extra: Any) -> dict[str, Any] | None:
        got = cites.get(name)
        return {"id": name, "kind": kind, **got, **extra} if got else None

    sessions = colab_sessions(fw, rnd.sessions)
    gen = (cites.get("gen_hours") or {}).get("value") or {}
    qa = (cites.get("qa_hours") or {}).get("value") or {}
    gen_h = gen.get("hours")
    qa_h = qa.get("hours")
    machine_h = (
        round(float(gen_h) + float(qa_h), 2) if gen_h is not None and qa_h is not None else None
    )
    clips = h1m.get("clips")
    human: dict[str, Any] | None = None
    if clips:
        human = {
            "id": "human_clips",
            "kind": "measured",
            "value": {"clips": clips, "exported": h1m.get("exported")},
            "source": "story.h1m (fwdata/human1m/ego-h1m-*/summary.json)",
        }
    output: list[dict[str, Any] | None] = []
    if pair:
        output = [
            _artifact("trained_model", "story.pair.runs", models=[r["run"] for r in pair["runs"]]),
            _artifact(
                "step_scores",
                "story.pair.steps, story.pair.runs[].step_pass, .failures",
                steps=len(pair.get("steps") or []),
            ),
            _artifact(
                "recommendation", "story.round (plan, chain, clusters), story.demo.round_cost"
            ),
            _artifact("comparison", "story.pair.comparisons"),
        ]
    train, serve = _measured(sessions, "train"), _measured(sessions, "serve")
    serve["note"] = "one L4 serve lane per model, watcher wall CU incl. idle time"
    gen_total = None
    if machine_h is not None:
        gen_total = {
            "id": "gen_machine_hours",
            "kind": "measured",
            "value": machine_h,
            "source": "gen_hours + qa_hours (docs/he/tray.md §20.16)",
        }
    groups: dict[str, list[dict[str, Any] | None]] = {
        "input": [
            c("task", "description"),
            c("station", "description"),
            c("sim_episodes", "measured"),
            human,
            c("keyboard_teleop", "capability"),
        ],
        "output": output,
        "environment": [
            c("sim_stack", "description"),
            c("robot_model", "description"),
            c("lerobot", "description"),
        ],
        "devices": [
            c("laptop", "description"),
            c("rtx3060", "measured"),
            c("colab_train_gpu", "measured", sessions_gpu=train["gpu"]),
            c("colab_serve_gpu", "measured", sessions_gpu=serve["gpu"]),
            c("head_camera", "description"),
        ],
        "resource": [
            {"id": "train_cu", **train} if sessions else None,
            c("train_cu_estimate", "estimated"),
            {"id": "test_cu", **serve} if sessions else None,
            c("gen_hours", "measured"),
            c("qa_hours", "measured"),
            gen_total,
            c("gen_cu", "measured"),
            c("deid_first", "rule"),
        ],
    }
    out: dict[str, Any] = {k: [x for x in v if x] for k, v in groups.items()}
    out["source"] = "seed/cited.yaml demo.design.*, fwdata/colab, story.h1m, story.pair"
    out["unsourced"] = [
        "the deck's CU for one 60-run test: no ledger or doc line; use test_cu (measured)",
        "human hours for generating the 181 episodes: no ledger or doc line",
    ]
    return out


# ------------------------------------------------------------------ 8 · success clip
def success_clip(fw: Path) -> dict[str, Any]:
    """The first ``console/media/demo/*.mp4`` with a JSON sidecar describing it."""
    folder = fw / "console" / "media" / "demo"
    for mp4 in sorted(folder.glob("*.mp4")):
        meta = _dict(mp4.with_suffix(".json"))
        if not meta:
            continue
        return {
            **meta,
            "path": str(mp4.relative_to(fw)),
            "bytes": mp4.stat().st_size,
            "source": str(mp4.with_suffix(".json").relative_to(fw)),
        }
    return {}


# ------------------------------------------------------------------ 9 · model facts
def models(pair: dict[str, Any], cites: dict[str, dict[str, Any]], rnd: Round) -> dict[str, Any]:
    """Facts to build plain names: episodes, human video, round-1 model. No names here."""
    data = rnd.train_sets
    ep = {k: (cites.get(k) or {}).get("value") or {} for k in sorted(set(data.values()))}
    human = (cites.get("human_video") or {}).get("value") or {}
    used_by = set(human.get("used_by") or [])
    round_models = {
        c["variant"] for c in pair.get("comparisons") or [] if c.get("tag") == rnd.rule_tag
    }
    runs: dict[str, Any] = {}
    for m in rnd.run_ids:
        part = ep.get(data[m]) or {}
        episodes = part.get("episodes")
        if episodes is None and part.get("base") is not None and part.get("targeted") is not None:
            episodes = int(part["base"]) + int(part["targeted"])
        runs[m] = {
            "data": data[m],
            "episodes": episodes,
            "base_episodes": part.get("base"),
            "targeted_episodes": part.get("targeted"),
            "human_video": m in used_by,
            "human_clips": human.get("clips") if m in used_by else 0,
            "round1": m in round_models,
        }
    if not any(v["episodes"] for v in runs.values()):
        return {}
    return {
        "source": "docs/he/tray.md §19.1, §20.6, §20.16; round1 = variant of the 'r' comparisons",
        "runs": runs,
        "cites": {k: v for k, v in cites.items()},
    }


def build(
    fw: Path,
    pair: dict[str, Any],
    rnd_block: dict[str, Any],
    h1m: dict[str, Any],
    groups: dict[str, dict[str, dict[str, Any]]],
    rnd: Round | None = None,
) -> dict[str, Any]:
    g = groups.get
    if rnd is None:  # no round holds the story numbers: nothing round-specific to read
        return {
            "source": "story.demo: no round in seed/tasks.yaml lists story.pair",
            "qa_bench": qa_bench(g("qa") or {}),
            "diagnose": diagnose(rnd_block, g("diagnose") or {}),
            "round_cost": round_cost(g("cost") or {}),
            "success_clip": success_clip(fw),
        }
    return {
        "source": "story.demo: fwdata files read at index time and seed/cited.yaml demo.*",
        "ladder": ladder(fw, pair, g("ladder") or {}, rnd),
        "round1_reading": round1(fw, g("round1") or {}, rnd),
        "qa_bench": qa_bench(g("qa") or {}),
        "fail_share": fail_share(pair, rnd),
        "diagnose": diagnose(rnd_block, g("diagnose") or {}),
        "design": design(fw, pair, h1m, g("design") or {}, rnd),
        "round_cost": round_cost(g("cost") or {}),
        "success_clip": success_clip(fw),
        "models": models(pair, g("models") or {}, rnd),
    }
