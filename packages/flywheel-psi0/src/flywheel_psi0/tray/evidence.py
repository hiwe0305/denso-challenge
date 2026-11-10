"""Evidence pack of the paired tray plan: one command, re-run as each result lands (DA-34 6).

Hiếu needs the success numbers of the four runs (B_ALL, C_ALL, B_70, C_70) on 12/11/2026
(docs/he/tray.md 19.6).
This module writes the whole pack from whatever exists, and names what is still missing
in place of each part it cannot fill yet, so the same command runs before the first
checkpoint and after the last rollout:

    python -m flywheel_psi0.tray.evidence configs/runplans/tray/he-tray-pair60k.yaml \\
        --set <eval set rp_a04c14e79dfd-2e57f60> \\
        --eval B_ALL@40000=<eval_batch dir> --eval C_ALL@40000=<eval_batch dir> \\
        --eval B_ALL@60000=<eval_batch dir> --eval C_ALL@60000=<eval_batch dir> \\
        --eval B_70@60000=<eval_batch dir> --eval C_70@60000=<eval_batch dir> \\
        --train B_ALL=<job dir from Drive> --train C_ALL=<job dir from Drive> \\
        --train B_70=<job dir from Drive> --train C_70=<job dir from Drive> \\
        --out fwdata/tray/evidence/<run_plan_id>

`<out>` gets README.md (Vietnamese, as the docs), evidence.json, loss.csv, loss.svg and
videos/. The parts, in the order of the reading rules (19.2):

- provenance: run_plan_id and lock, code and psi-model pins, both parents' VLM pins, the
  cut's releases and stats, the rules' sha256, this checkout's commit, each job's last
  checkpoint step;
- per checkpoint read (rule e: `checkpoints.primary` is the metric, `checkpoints.early`
  an early read and labelled so): per run, the widest stage its rollouts cover (stage 1,
  the first 6 chunks, or all 27), success on levels 1-2 with Wilson 95 % against 80 %
  and on level 1 and level 2 apart against 70 % (rule b); per comparison of the plan
  (`comparisons`), on the widest stage both its runs cover, the paired difference with
  its bootstrap CI and exact McNemar and its reading: CI against 0, or for a
  noninferiority one CI low against -margin; the stage 1 outcome E1/E3/F/continue of the
  primary comparison at the primary checkpoint only, and there the joint readings of
  rule f (egocentric makes up for the cut demos: f holds and the primary's CI low > 0)
  and rule g (the baseline VLM alone keeps up on the subset); failure labels and per-step
  pass rates, and the relaxed success by tolerance (rule c, always "nới");
- the loss curves of every job (`metrics.jsonl`), a few rollout videos of each run (the
  successes and one failure per label first), and the plan's ledger rows.

Eval results are read through the frozen plan of `eval_of`: `pairplan.check` holds the
pair's eval, stats and conditions equal to it, and `eval_results` reads that plan's type.
`flywheel_simple` (the target pose of rule c) is imported only when that part runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import statistics
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flywheel_psi0.tray.eval_batch import Chunk, chunk_plan, phases_for
from flywheel_psi0.tray.eval_results import (
    STAGE1_CHUNKS,
    Rollout,
    collect,
    paired_diff,
    stage1_outcome,
    summarize,
)
from flywheel_psi0.tray.pairplan import TrayPairPlan, balance_needed
from flywheel_psi0.tray.place_error import RELAXED_M, rows_for, tolerance_curve
from flywheel_psi0.tray.runplan import REPO, Parent, TrayRunPlan, lock_path, run_plan_id

GOAL = 0.80  # Hiếu's target success rate (rule b)
LEVEL_GOAL = 0.70  # the organisers' level 3 bar, read on level 1 and level 2 apart (rule b)
LOSS_BIN = 500  # steps per point of the train loss curve (median of the bin)
LEDGER = "docs/g0/ledger/DA-34.csv"
TargetOf = Callable[[int, int], "tuple[float, float, float]"]


@dataclass
class Inputs:
    plan_path: Path
    eval_set: Path
    evals: dict[tuple[str, int], Path] = field(default_factory=dict)  # (branch, step) -> dir
    trains: dict[str, Path] = field(default_factory=dict)  # branch -> job dir
    ledger: Path = REPO / LEDGER
    videos: int = 3
    chunk: int = 10


def parse_pairs(values: Sequence[str], keyed: bool) -> dict[Any, Path]:
    """`B_ALL@60000=dir` (keyed by branch and step) or `B_ALL=dir`."""
    out: dict[Any, Path] = {}
    for value in values:
        key, sep, path = value.partition("=")
        if not sep or not path:
            raise ValueError(f"{value!r}: expected NAME=PATH")
        if keyed:
            branch, at, step = key.partition("@")
            if not at or not step.isdigit():
                raise ValueError(f"{value!r}: expected BRANCH@STEP=PATH")
            out[(branch, int(step))] = Path(path)
        else:
            out[key] = Path(path)
    return out


def git_head(repo: Path = REPO) -> str | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def provenance(plan: TrayPairPlan, trains: dict[str, Path], repo: Path = REPO) -> dict[str, Any]:
    parents: dict[str, Any] = {}
    for name, branch in sorted(plan.branches.items()):
        parent = plan.parents[branch.parent]
        if isinstance(parent, Parent):
            parents[name] = {"parent": branch.parent, "vlm_sha256": parent.vlm.sha256}
        else:
            vlm = parent.vlm_stage1
            parents[name] = {
                "parent": branch.parent,
                "stage1_job": vlm.job_id,
                "vlm_weights_sha256": vlm.weights_sha256,
                "vlm_manifest_sha256": vlm.manifest_sha256,
            }
        parents[name]["action_header_sha256"] = parent.action_header.sha256
        parents[name]["data"] = plan.data_of(branch)
    jobs = {}
    for name, job in sorted(trains.items()):
        result = job / "result.json"
        jobs[name] = json.loads(result.read_text(encoding="utf-8")) if result.is_file() else None
    return {
        "run_plan_id": run_plan_id(plan),
        "status": plan.status or "ready",
        "code": {k: v.commit for k, v in plan.code.items()},
        "psi_model": plan.psi_model.revision,
        "parents": parents,
        "cut": {
            "name": plan.cut.name,
            "visuals_revision": plan.cut.visuals_revision,
            "parts": [
                {
                    "regenerates": p.regenerates,
                    "release": p.release.id if p.release else None,
                    "release_hash": p.release.release_hash if p.release else None,
                    "set": p.set_name,
                }
                for p in plan.cut.parts
            ],
            "episodes": plan.cut.episodes,
            "frames": plan.cut.frames,
            "stats_sha256": plan.cut.stats_sha256,
        },
        "subsets": [s.model_dump(mode="json") for s in plan.subsets or []],
        "steps": plan.steps(),
        "checkpoints": plan.checkpoints.model_dump(),
        "rules_sha256": plan.interpretation.rules_sha256,
        "eval_of": plan.eval_of.model_dump(),
        "repo_commit": git_head(repo),
        "jobs": {
            name: (
                {k: r.get(k) for k in ("checkpoint_step", "checkpoint_dir", "error")}
                if r is not None
                else None
            )
            for name, r in jobs.items()
        },
        "balance_needed_cu": balance_needed(plan),
    }


def stage_of(
    outs: dict[str, Path], chunks: Sequence[Chunk]
) -> tuple[str, list[Chunk], dict[str, list[Rollout]], dict[str, int]]:
    """The widest stage every run covers: `full` (all chunks), `stage1` or `incomplete`."""
    for name, part in (("full", list(chunks)), ("stage1", list(chunks[:STAGE1_CHUNKS]))):
        got = {b: collect(out, part) for b, out in outs.items()}
        if all(not missing for _, _, missing in got.values()):
            return name, part, {b: g[0] for b, g in got.items()}, {}
    first = list(chunks[:STAGE1_CHUNKS])
    done = {b: len(collect(out, first)[0]) for b, out in outs.items()}
    return "incomplete", first, {}, done


def against_goal(wilson: Sequence[float], goal: float = GOAL) -> str:
    low, high = wilson
    return f"đạt mốc {100 * goal:g} %" if low >= goal else "chưa đạt" if high < goal else "chưa rõ"


@dataclass(frozen=True)
class Comparison:
    rule: str
    variant: str
    baseline: str
    kind: str  # primary, noninferiority or secondary
    margin: float | None = None


def comparisons_of(plan: TrayPairPlan) -> list[Comparison]:
    """The plan's comparisons; a plain pair without them compares stage 1 against C (a)."""
    if plan.comparisons is None:
        variant, baseline = pair_roles(plan)
        return [Comparison("a", variant, baseline, "primary")]
    return [Comparison(c.rule, c.variant, c.baseline, c.kind, c.margin) for c in plan.comparisons]


def reading(c: Comparison, diff: dict[str, Any]) -> str:
    """CI against 0, or for a noninferiority comparison CI low against -margin."""
    if c.margin is None:
        return str(diff["ci_vs_0"])
    low, high = diff["ci"]
    return "không kém" if low > -c.margin else "kém" if high < -c.margin else "chưa rõ"


def read_checkpoint(
    plan: TrayPairPlan,
    base: TrayRunPlan,
    step: int,
    outs: dict[str, Path],
    chunks: Sequence[Chunk],
    target_of: TargetOf | None,
    tolerance: tuple[float, float] | None,
) -> dict[str, Any]:
    """Rules (a′)-(c), (f), (g) at one checkpoint: each run and each comparison on the
    widest stage its rollouts cover, so a second wave lagging behind holds back no read."""
    primary = step == plan.checkpoints.primary
    read: dict[str, Any] = {
        "step": step,
        "role": "primary" if primary else "early",
        "label": "số chính" if primary else "đọc sớm, 40k" if step == 40000 else "đọc sớm",
        "runs": sorted(outs),
    }
    missing_runs = sorted(set(plan.branches) - set(outs))
    if missing_runs:
        read["pending"] = f"chưa có eval của {', '.join(missing_runs)}"
    headline = [c.level for c in base.eval.by_level or [] if c.headline]
    runs, incomplete = {}, {}
    for name, out in sorted(outs.items()):
        stage, _, chosen, done = stage_of({name: out}, chunks)
        if stage == "incomplete":
            incomplete[name] = done[name]
            continue
        rollouts = chosen[name]
        result = summarize(base, rollouts, {}, [], None, full=stage == "full")
        h = result["headline"]
        runs[name] = {
            "stage": stage,
            "n": h["n"],
            "successes": h["successes"],
            "p": h["p"],
            "wilson": h["wilson"],
            "goal": against_goal(h["wilson"]),
            "by_level": {
                str(lv): {
                    "n": result["levels"][str(lv)]["n"],
                    "successes": result["levels"][str(lv)]["successes"],
                    "wilson": result["levels"][str(lv)]["wilson"],
                    "goal": against_goal(result["levels"][str(lv)]["wilson"], LEVEL_GOAL),
                }
                for lv in headline
                if result["levels"].get(str(lv), {}).get("n")
            },
            "failures": h["failures"],
            "step_pass": h["step_pass"],
            "level0": result["levels"].get("0") if stage == "full" else None,
        }
        if target_of is not None and tolerance is not None:
            rows = rows_for([r for r in rollouts if r.level in headline], target_of, *tolerance)
            runs[name]["relaxed"] = tolerance_curve(rows, tolerance[1])
    if incomplete:
        read["incomplete"] = incomplete
    if runs:
        read["by_run"] = runs
    compared = []
    for c in comparisons_of(plan):
        if c.variant not in outs or c.baseline not in outs:
            continue
        entry: dict[str, Any] = {
            "rule": c.rule, "variant": c.variant, "baseline": c.baseline,
            "kind": c.kind, "margin": c.margin,
        }  # fmt: skip
        pair = {n: outs[n] for n in (c.variant, c.baseline)}
        stage, part, chosen, done = stage_of(pair, chunks)
        entry["stage"] = stage
        if stage == "incomplete":
            entry["done_stage1"] = done
            compared.append(entry)
            continue
        diff = paired_diff(chosen[c.variant], chosen[c.baseline], headline, base.stats)
        counts = {"variant_successes": diff["variant"], "baseline_successes": diff["baseline"]}
        rest = {k: v for k, v in diff.items() if k not in ("variant", "baseline")}
        entry.update(rest, **counts, reading=reading(c, diff), chunks=[ch.id for ch in part])
        if primary and c.kind == "primary":
            # The stop rule reads the first 6 chunks even once all 27 have run: an E1, E3
            # or F there is the verdict, and the 240-condition rule is then descriptive.
            first = diff
            if stage == "full":
                part1 = list(chunks[:STAGE1_CHUNKS])
                v1, b1 = (collect(outs[n], part1)[0] for n in (c.variant, c.baseline))
                first = paired_diff(v1, b1, headline, base.stats)
            entry["stage1_outcome"] = stage1_outcome(first)
            if stage == "full":
                rule = {"above": 1, "contains": 2, "below": 3}[diff["ci_vs_0"]]
                verdict = entry["stage1_outcome"] == "continue"
                entry["rule_of_240" if verdict else "rule_descriptive"] = rule
        compared.append(entry)
    if compared:
        read["comparisons"] = compared
    if primary:
        read.update(joint_readings(compared))
    return read


def joint_readings(compared: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Rule f with (a′), and rule g, at the primary checkpoint (tray.md 19.2).

    "Egocentric makes up for the cut demos" only when the noninferiority comparison of
    the primary's variant holds and the primary's CI low is above 0. When the primary's
    baseline keeps up as well (its own noninferiority comparison holds), f holding is not
    the egocentric data's doing, and the pack says so.
    """
    done = {e["rule"]: e for e in compared if "reading" in e}
    prim = next((e for e in done.values() if e["kind"] == "primary"), None)
    out: dict[str, Any] = {}
    if prim is None:
        return out
    out["stage1_outcome"] = prim["stage1_outcome"]
    for key in ("rule_of_240", "rule_descriptive"):
        if key in prim:
            out["rule" if key == "rule_of_240" else key] = prim[key]
    for e in done.values():
        if e["kind"] != "noninferiority":
            continue
        if e["variant"] == prim["variant"]:
            out["compensates"] = {
                "rules": [e["rule"], prim["rule"]],
                "holds": e["reading"] == "không kém" and prim["ci"][0] > 0,
            }
        elif e["variant"] == prim["baseline"] and e["reading"] == "không kém":
            out["data_not_bottleneck"] = e["rule"]
    return out


def pair_roles(plan: TrayPairPlan) -> tuple[str, str]:
    """(variant, baseline): the stage 1 branch against the release-parent branch."""
    names = sorted(plan.branches)
    stage1 = [n for n in names if not isinstance(plan.parents[plan.branches[n].parent], Parent)]
    variant = stage1[0] if stage1 else names[0]
    return variant, next(n for n in names if n != variant)


def loss_points(job: Path) -> dict[str, list[tuple[int, float]]]:
    """Train loss as the median of steps 1-500, 501-1000, … (LOSS_BIN), val loss as logged."""
    path = job / "metrics.jsonl"
    if not path.is_file():
        return {}
    bins: dict[int, list[float]] = {}
    val: list[tuple[int, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        loss = row.get("loss")
        if not isinstance(loss, (int, float)):
            continue
        if row.get("split") == "val":
            val.append((int(row["step"]), float(loss)))
        else:
            bins.setdefault((int(row["step"]) - 1) // LOSS_BIN, []).append(float(loss))
    train = [((k + 1) * LOSS_BIN, statistics.median(v)) for k, v in sorted(bins.items())]
    return {"train": train, "val": sorted(val)}


def loss_svg(curves: dict[str, dict[str, list[tuple[int, float]]]]) -> str:
    """One line per (run, split); no plotting library on the eval host."""
    points = [p for run in curves.values() for line in run.values() for p in line]
    width, height, pad = 720, 360, 40
    if not points:
        return ""
    x_max = max(p[0] for p in points) or 1
    y_min, y_max = min(p[1] for p in points), max(p[1] for p in points)
    span = (y_max - y_min) or 1.0

    def xy(p: tuple[int, float]) -> str:
        x = pad + (width - 2 * pad) * p[0] / x_max
        y = height - pad - (height - 2 * pad) * (p[1] - y_min) / span
        return f"{x:.1f},{y:.1f}"

    colours = ["#1f6feb", "#d1242f", "#8250df", "#bf8700"]
    lines, legend = [], []
    for i, (name, line) in enumerate(
        (f"{run} {split}", pts)
        for run, splits in sorted(curves.items())
        for split, pts in sorted(splits.items())
        if pts
    ):
        colour = colours[i % len(colours)]
        dash = ' stroke-dasharray="4 3"' if name.endswith("val") else ""
        pts = " ".join(xy(p) for p in line)
        lines.append(f'<polyline fill="none" stroke="{colour}"{dash} points="{pts}"/>')
        legend.append(
            f'<text x="{pad + 10}" y="{pad + 16 * (i + 1)}" fill="{colour}" '
            f'font-size="12">{name}</text>'
        )
    axes = (
        f'<text x="{pad}" y="{height - 10}" font-size="12">bước 0 … {x_max}</text>'
        f'<text x="4" y="{pad - 10}" font-size="12">loss {y_min:.3g} … {y_max:.3g}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="100%" height="100%" fill="white"/>{axes}{"".join(lines)}'
        f"{''.join(legend)}</svg>\n"
    )


def video_of(out: Path, rollout: Rollout) -> Path | None:
    """SIMPLE's head-camera video of a rollout: data/evals/…/episode_<i>/head_stereo_left_*."""
    attempt = out / rollout.chunk / f"attempt-{rollout.attempt}" / "data" / "evals"
    found = sorted(
        attempt.glob(
            f"*/*/dr-level-{rollout.level}/episode_{rollout.episode}/head_stereo_left_*.mp4"
        )
    )
    return found[0] if found else None


def pick_videos(rollouts: Sequence[Rollout], n: int) -> list[Rollout]:
    """Up to n successes, and up to n failures with one per label before any repeat."""
    wins = [r for r in rollouts if r.row.get("success")][:n]
    losses, seen = [], set()
    for r in rollouts:
        label = r.row.get("failure")
        if not r.row.get("success") and label not in seen:
            losses.append(r)
            seen.add(label)
    rest = [r for r in rollouts if not r.row.get("success") and r not in losses]
    return wins + (losses + rest)[:n]


def ledger_rows(path: Path, branches: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("branch") in branches]


def build(
    inputs: Inputs,
    out: Path,
    target_of: TargetOf | None = None,
    tolerance: tuple[float, float] | None = None,
    repo: Path = REPO,
) -> dict[str, Any]:
    plan = TrayPairPlan.load(inputs.plan_path)
    base = TrayRunPlan.load(repo / plan.eval_of.plan)
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        json.loads(line) for line in (inputs.eval_set / "conditions.jsonl").read_text().splitlines()
    ]
    chunks = chunk_plan(rows, inputs.chunk, phases_for(rows))
    reads_at = [s for s in (plan.checkpoints.early, plan.checkpoints.primary) if s is not None]
    unknown = sorted({step for _, step in inputs.evals} - set(reads_at))
    if unknown:
        raise ValueError(f"steps {unknown} are not read by the plan (checkpoints: {reads_at})")
    unknown_runs = sorted(({b for b, _ in inputs.evals} | set(inputs.trains)) - set(plan.branches))
    if unknown_runs:
        raise ValueError(f"{unknown_runs} are not branches of the plan {sorted(plan.branches)}")
    pack: dict[str, Any] = {
        "provenance": provenance(plan, inputs.trains, repo),
        "lock": lock_path(inputs.plan_path).is_file(),
        "reads": [],
    }
    for step in reads_at:
        outs = {b: d for (b, s), d in inputs.evals.items() if s == step}
        if not outs:
            label = "số chính" if step == plan.checkpoints.primary else "đọc sớm"
            pack["reads"].append({"step": step, "label": label, "pending": "chưa có eval nào"})
            continue
        pack["reads"].append(read_checkpoint(plan, base, step, outs, chunks, target_of, tolerance))
    curves = {name: loss_points(job) for name, job in sorted(inputs.trains.items())}
    pack["loss"] = {name: {k: len(v) for k, v in c.items()} for name, c in curves.items()}
    with (out / "loss.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run", "split", "step", "loss"])
        for name, c in curves.items():
            for split, pts in c.items():
                writer.writerows([name, split, s, round(v, 6)] for s, v in pts)
    svg = loss_svg(curves)
    if svg:
        (out / "loss.svg").write_text(svg, encoding="utf-8")
    pack["videos"] = copy_videos(plan, inputs, chunks, out)
    pack["ledger"] = ledger_rows(inputs.ledger, sorted(plan.branches))
    (out / "evidence.json").write_text(json.dumps(pack, indent=1) + "\n", encoding="utf-8")
    (out / "README.md").write_text(render(plan, pack), encoding="utf-8")
    return pack


def copy_videos(
    plan: TrayPairPlan, inputs: Inputs, chunks: Sequence[Chunk], out: Path
) -> dict[str, list[str]]:
    """Videos of the latest checkpoint read of each run, under videos/<run>-<step>/."""
    copied: dict[str, list[str]] = {}
    for branch in sorted(plan.branches):
        steps = sorted(s for b, s in inputs.evals if b == branch)
        if not steps:
            continue
        step = steps[-1]
        source = inputs.evals[(branch, step)]
        rollouts, _, _ = collect(source, chunks)
        target = out / "videos" / f"{branch}-{step}"
        names = []
        for r in pick_videos(rollouts, inputs.videos):
            video = video_of(source, r)
            if video is None:
                continue
            label = "success" if r.row.get("success") else str(r.row.get("failure"))
            name = f"l{r.level}-{r.seed}-{label}.mp4"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video, target / name)
            names.append(f"videos/{branch}-{step}/{name}")
        copied[f"{branch}@{step}"] = names
    return copied


SCOPE = {"stage1": "giai đoạn 1, 60 điều kiện", "full": "đủ 240 điều kiện"}
KIND = {"primary": "so sánh chính", "noninferiority": "không kém", "secondary": "so sánh phụ"}


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f} %"


def render(plan: TrayPairPlan, pack: dict[str, Any]) -> str:
    """README.md of the pack, in Vietnamese like docs/he/tray.md."""
    prov = pack["provenance"]
    lines = [
        f"# Gói bằng chứng {plan.name} ({prov['run_plan_id']})",
        "",
        "Sơ bộ, trên dev: 1 seed train mỗi run, 1 rollout mỗi điều kiện; chỉ trong sim, "
        "renderer MuJoCo. Luật đọc: docs/he/tray.md 19.2 "
        f"(`rules_sha256` `{str(prov['rules_sha256'])[:12]}…`). Sinh bởi "
        "`python -m flywheel_psi0.tray.evidence`; chạy lại khi có thêm kết quả.",
        "",
        "## Nguồn gốc",
        "",
        "| Mục | Giá trị |",
        "|---|---|",
        f"| run_plan_id | `{prov['run_plan_id']}` ({prov['status']}; "
        f"{'đã đóng băng' if pack['lock'] else 'chưa đóng băng'}) |",
        f"| Commit repo | `{prov['repo_commit']}` |",
        f"| Code | {', '.join(f'{k} `{v[:12]}`' for k, v in prov['code'].items())} |",
        f"| psi-model | `{prov['psi_model'][:12]}` |",
        f"| Cut {prov['cut']['name']} | "
        + "; ".join(
            f"{p['regenerates']} → {p['release'] or 'chưa ghim'}" for p in prov["cut"]["parts"]
        )
        + f"; {prov['cut']['episodes'] or '?'} episode, {prov['cut']['frames'] or '?'} frame; "
        f"stats `{str(prov['cut']['stats_sha256'] or 'chưa ghim')[:12]}` |",
        f"| Số bước, checkpoint đọc | {prov['steps']}; số chính "
        f"{prov['checkpoints']['primary']}, đọc sớm {prov['checkpoints']['early'] or 'không'} |",
    ]
    for sub in prov["subsets"]:
        lines.append(
            f"| Tập con {sub['name']} | {100 * sub['fraction']:g} % mỗi phần, theo sha256 seed; "
            + "; ".join(
                f"{sp['regenerates']} → {sp['episodes'] or '?'} episode, danh sách "
                f"`{str(sp['seeds_sha256'] or 'chưa ghim')[:12]}`"
                for sp in sub["parts"]
            )
            + f"; stats của cut {prov['cut']['name']} |"
        )
    for name, parent in prov["parents"].items():
        vlm = parent.get("vlm_sha256") or parent.get("vlm_weights_sha256")
        lines.append(
            f"| VLM {name} (dữ liệu {parent['data']}) | `{parent['parent']}`: "
            f"`{str(vlm or 'chưa ghim')[:12]}` |"
        )
    for name, job in prov["jobs"].items():
        state = "chưa có `result.json`" if job is None else f"bước {job['checkpoint_step']}"
        lines.append(f"| Job {name} | {state} |")
    for read in pack["reads"]:
        lines += ["", f"## Checkpoint {read['step']} ({read.get('label', '')})", ""]
        if "runs" not in read:
            lines.append(f"Chưa có: {read['pending']}.")
            continue
        if read.get("pending"):
            lines.append(f"Chưa đủ: {read['pending']}.")
        for name, done in read.get("incomplete", {}).items():
            lines.append(f"{name}: giai đoạn 1 mới {done}/60 điều kiện, chưa đọc.")
        if "by_run" not in read:
            continue
        lines += [
            "",
            "Mỗi run trên phạm vi rộng nhất nó đã chạy đủ (giai đoạn 1: 60 điều kiện; đủ: 240);"
            " mức 1–2 gộp so với 80 %, từng mức so với 70 % (luật b).",
            "",
            "| Run | Phạm vi | Thành công | Wilson 95 % | So với 80 % | Mức 1, 2 so với 70 % |",
            "|---|---|---|---|---|---|",
        ]
        for name, run in read["by_run"].items():
            low, high = run["wilson"]
            levels = "; ".join(
                f"mức {lv}: {v['successes']}/{v['n']}, {pct(v['wilson'][0])} – "
                f"{pct(v['wilson'][1])}, {v['goal']}"
                for lv, v in run["by_level"].items()
            )
            lines.append(
                f"| {name} | {SCOPE[run['stage']]} | {run['successes']}/{run['n']} "
                f"({pct(run['p'])}) | {pct(low)} – {pct(high)} | {run['goal']} | {levels} |"
            )
        for e in read.get("comparisons", []):
            head = f"**({e['rule']}) {e['variant']} − {e['baseline']}**, {KIND[e['kind']]}"
            if e["stage"] == "incomplete":
                done = ", ".join(f"{b} {n}/60" for b, n in e["done_stage1"].items())
                lines += ["", f"{head}: giai đoạn 1 chưa đủ ({done}), chưa đọc."]
                continue
            margin = f", biên −{100 * e['margin']:g} điểm %" if e["margin"] is not None else ""
            lines += [
                "",
                f"{head} ({SCOPE[e['stage']]}): hiệu {e['diff']:+.3f}, CI 95 % "
                f"{e['ci'][0]:+.3f} … {e['ci'][1]:+.3f}; đọc: **{e['reading']}**{margin}; "
                f"cặp bất đồng b = {e['variant_only']}, c = {e['baseline_only']}; McNemar "
                f"chính xác p = {e['mcnemar_exact_p']}.",
            ]
            if "stage1_outcome" in e:
                lines.append(f"Kết quả giai đoạn 1: **{e['stage1_outcome']}** (bảng 19.2).")
            if "rule_of_240" in e:
                lines.append(f"Đọc trên 240 điều kiện: **luật {e['rule_of_240']}** (bảng 19.2).")
            elif "rule_descriptive" in e:
                lines.append(
                    f"Trên 240 điều kiện CI ứng với luật {e['rule_descriptive']}, chỉ để mô tả:"
                    " giai đoạn 1 đã dừng, kết luận là của giai đoạn 1."
                )
        if "compensates" in read:
            f_rule, a_rule = read["compensates"]["rules"]
            holds = "có" if read["compensates"]["holds"] else "không đọc được"
            lines += [
                "",
                f"Egocentric bù phần demo bị cắt: **{holds}** (cần ({f_rule}) không kém"
                f" và cận dưới CI của ({a_rule}) > 0).",
            ]
        if "data_not_bottleneck" in read:
            f_rule = read["compensates"]["rules"][0] if "compensates" in read else "f"
            lines.append(
                f"({read['data_not_bottleneck']}) không kém: VLM gốc trên tập con cũng theo kịp,"
                f" nên lượng dữ liệu không phải nút thắt; ({f_rule}) đạt cũng không nhờ"
                " egocentric."
            )
        if read["role"] == "early":
            lines.append("")
            lines.append(
                "Đọc sớm: không cho E1, E3, F hay đi tiếp, không kết luận (f), (g) (luật e)."
            )
        lines += [
            "",
            "| Run | Nhãn lỗi | Qua từng bước (approach … release_stand) |",
            "|---|---|---|",
        ]
        for name, run in read["by_run"].items():
            fails = ", ".join(f"{k} {v}" for k, v in sorted(run["failures"].items())) or "—"
            steps = " / ".join(pct(v) for v in run["step_pass"].values())
            lines.append(f"| {name} | {fails} | {steps} |")
        if any("relaxed" in run for run in read["by_run"].values()):
            lines += [
                "",
                "Thành công **nới** (luật c, không phải chỉ số chính; góc giữ 10°):",
                "",
                "| Run | n | " + " | ".join(f"{100 * t:g} cm" for t in RELAXED_M) + " |",
                "|---|---|" + "---|" * len(RELAXED_M),
            ]
            for name, run in read["by_run"].items():
                if "relaxed" in run:
                    cells = " | ".join(str(c["relaxed_successes"]) for c in run["relaxed"])
                    lines.append(f"| {name} | {run['n']} | {cells} |")
        else:
            lines += ["", "Thành công nới (luật c): chưa tính (cần `flywheel_simple`)."]
    lines += ["", "## Loss", ""]
    if pack["loss"] and any(pack["loss"].values()):
        lines.append("![loss](loss.svg) — số liệu ở `loss.csv` (train: trung vị mỗi 500 bước).")
    else:
        lines.append("Chưa có `metrics.jsonl` của job nào.")
    lines += ["", "## Video rollout", ""]
    videos = [v for vs in pack["videos"].values() for v in vs]
    lines += [f"- [{v}]({v})" for v in videos] or ["Chưa có video."]
    lines += [
        "",
        "## Sổ chi phí",
        "",
        "| Ngày | Job | Loại | Lượng | USD |",
        "|---|---|---|---|---|",
    ]
    for row in pack["ledger"]:
        lines.append(
            f"| {row['date']} | {row['job']} | {row['estimated_or_measured']} | "
            f"{row['quantity']} {row['unit']} | {row['amount_usd']} |"
        )
    return "\n".join(lines) + "\n"


def simple_targets() -> tuple[TargetOf, tuple[float, float]] | None:
    """Target pose and tolerances from flywheel_simple, or None where it is not installed."""
    try:
        from flywheel_simple.tray.config import TrayConfig
        from flywheel_simple.tray.randomize import sample_episode
    except ImportError:
        return None
    cfg = TrayConfig.load()

    def target_of(level: int, seed: int) -> tuple[float, float, float]:
        t = sample_episode(cfg, level, seed).target_pose
        return float(t.x), float(t.y), float(t.yaw)

    return target_of, (float(cfg.target_pos_tol), float(cfg.target_yaw_tol_deg))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--eval", action="append", default=[], help="BRANCH@STEP=eval_batch dir")
    parser.add_argument("--train", action="append", default=[], help="BRANCH=job dir")
    parser.add_argument("--ledger", type=Path, default=REPO / LEDGER)
    parser.add_argument("--videos", type=int, default=3, help="successes and failures per run")
    parser.add_argument("--no-relaxed", action="store_true", help="skip rule (c)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = Inputs(
        plan_path=args.plan,
        eval_set=args.set,
        evals=parse_pairs(args.eval, keyed=True),
        trains=parse_pairs(args.train, keyed=False),
        ledger=args.ledger,
        videos=args.videos,
    )
    targets = None if args.no_relaxed else simple_targets()
    target_of, tolerance = targets if targets else (None, None)
    pack = build(inputs, args.out, target_of, tolerance)
    for read in pack["reads"]:
        compared = {e["rule"]: e.get("reading", e["stage"]) for e in read.get("comparisons", [])}
        state = compared or read.get("pending")
        print(f"ckpt {read['step']}: {state}", read.get("stage1_outcome", read.get("rule", "")))
    print(f"wrote {args.out / 'README.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
