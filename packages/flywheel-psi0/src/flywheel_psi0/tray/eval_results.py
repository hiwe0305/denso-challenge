"""Read an `eval_batch` directory into the result of a tray RunPlan's eval (DA-34 task 3.4).

One rollout per eval condition: the **earliest finished** one, by attempt, of each
episode. A rerun of a chunk starts at its first missing episode, so an episode that had
already finished after a gap runs again; rollouts are not reproducible on EGL
(docs/he/tray.md 13.2), so the later rollout may differ. It is counted as an extra
rollout and never chosen, whatever its outcome (main-session review of #147).

Per level: episodes, successes, p and its bootstrap CI (the plan's `stats`), failure
kinds, the pass rate of each of the scorer's seven steps (`scorer_steps` of the
outcome rows, in order), and the yaw error of DA-38's traces: target_yaw (cmd) minus
base yaw (meas), raw and wrapped to [-pi, pi]. The headline is the levels marked
`headline` in the plan, pooled, with the bootstrap resampling inside each level
(docs/he/tray.md 8.2); level 0 is resampled by replicate the same way. Rule 0 of the
tier 2 rules (tray.md 9) is reported as the plain test `p_headline < 0.10`; reading it
is the RunPlan's interpretation doc, not this module.

    python -m flywheel_psi0.tray.eval_results configs/runplans/tray/he-tray-v2.yaml \
        --set <eval set> --out <eval_batch dir> --json results.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_psi0.tray.eval_batch import Chunk, attempts, chunk_plan, finished
from flywheel_psi0.tray.runplan import TrayRunPlan

# flywheel_simple.tray.predicates.STEP_NAMES; SIMPLE's venv is not this package's.
STEP_NAMES = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")
RULE0_P = 0.10  # tier 2 rule 0: p_C < 10% on the headline levels
YAW = 6  # index of yaw in TraceStep.cmd_lower / meas_lower (flywheel.contracts.trace)
YAW_LARGE = 2.5  # rad, the threshold the yaw counts are reported against


@dataclass(frozen=True)
class Rollout:
    level: int
    seed: int
    episode: int  # index in dr-level-<level>
    chunk: str
    attempt: int
    row: dict[str, Any]  # the outcome row


def collect(
    out: Path, chunks: Sequence[Chunk]
) -> tuple[list[Rollout], dict[tuple[int, int], int], list[tuple[int, int]]]:
    """(chosen rollouts in chunk order, extra rollouts per (level, seed), missing ones)."""
    chosen, extra, missing = [], {}, []
    for chunk in chunks:
        runs: dict[int, list[tuple[int, dict[str, Any]]]] = {}
        for attempt in attempts(out, chunk):
            k = int(attempt.name.split("-")[1])
            for episode, row in finished(chunk, attempt).items():
                runs.setdefault(episode, []).append((k, row))
        for i, seed in enumerate(chunk.seeds):
            episode = chunk.start + i
            done = sorted(runs.get(episode, []), key=lambda run: run[0])
            if not done:
                missing.append((chunk.level, seed))
                continue
            k, row = done[0]
            chosen.append(Rollout(chunk.level, seed, episode, chunk.id, k, row))
            if len(done) > 1:
                extra[(chunk.level, seed)] = len(done) - 1
    return chosen, extra, missing


def bootstrap_ci(
    groups: Sequence[Sequence[int]], resamples: int, seed: int, ci: float
) -> tuple[float, float]:
    """Percentile CI of the pooled mean, each group resampled within itself."""
    rng = np.random.default_rng(seed)
    total = sum(len(g) for g in groups)
    sums = np.zeros(resamples)
    for group in groups:
        values = np.asarray(group, dtype=float)
        picks = rng.integers(0, len(values), size=(resamples, len(values)))
        sums += values[picks].sum(axis=1)
    means = sums / total
    tail = (1 - ci) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_errors(steps: Path) -> dict[str, float]:
    """Cycles, raw and wrapped |target_yaw - yaw| over YAW_LARGE, largest wrapped error."""
    raw = wrapped = cycles = 0
    largest = 0.0
    for line in steps.read_text().splitlines():
        row = json.loads(line)
        cmd, meas = row["cmd_lower"][YAW], row["meas_lower"][YAW]
        if not all(isinstance(v, (int, float)) for v in (cmd, meas)):
            continue  # "NaN" and friends of the contract
        d = float(cmd) - float(meas)
        cycles += 1
        raw += abs(d) > YAW_LARGE
        wrapped += abs(wrap(d)) > YAW_LARGE
        largest = max(largest, abs(wrap(d)))
    return {"cycles": cycles, "raw_over": raw, "wrapped_over": wrapped, "max_wrapped": largest}


def trace_of(out: Path, rollout: Rollout) -> Path | None:
    """steps.jsonl of the rollout's DA-38 trace, matched by `episode_<i>`."""
    for result in (out / rollout.chunk / f"attempt-{rollout.attempt}" / "traces").glob(
        "*/rollout_result.json"
    ):
        steps = result.parent / "steps.jsonl"
        if not steps.exists():
            continue
        first = steps.open().readline()
        if first and json.loads(first).get("episode_id") == f"episode_{rollout.episode}":
            return steps
    return None


def level_summary(rollouts: Sequence[Rollout]) -> dict[str, Any]:
    success = [int(bool(r.row["success"])) for r in rollouts]
    steps = [r.row.get("scorer_steps") for r in rollouts]
    known = [s for s in steps if s is not None]
    return {
        "n": len(rollouts),
        "successes": sum(success),
        "p": sum(success) / len(rollouts) if rollouts else None,
        "failures": dict(Counter(r.row["failure"] for r in rollouts if not r.row["success"])),
        "step_pass": {
            name: (sum(bool(s[k]) for s in known) / len(known) if known else None)
            for k, name in enumerate(STEP_NAMES)
        },
        "steps_unknown": len(steps) - len(known),
    }


def summarize(
    plan: TrayRunPlan,
    chosen: Sequence[Rollout],
    extra: dict[tuple[int, int], int],
    missing: Sequence[tuple[int, int]],
    yaw: dict[tuple[int, int], dict[str, float]] | None = None,
) -> dict[str, Any]:
    if plan.eval.by_level is None:
        raise ValueError("eval_results reads a version 2 plan (eval.by_level)")
    stats = plan.stats
    by_level = {c.level: [r for r in chosen if r.level == c.level] for c in plan.eval.by_level}
    levels = {}
    for c in plan.eval.by_level:
        summary = level_summary(by_level[c.level])
        summary["unit"] = c.unit
        if by_level[c.level]:
            summary["ci"] = bootstrap_ci(
                [[int(bool(r.row["success"])) for r in by_level[c.level]]],
                stats.resamples,
                stats.seed,
                stats.ci,
            )
        levels[str(c.level)] = summary
    headline_levels = [c.level for c in plan.eval.by_level if c.headline]
    headline_rollouts = [r for level in headline_levels for r in by_level[level]]
    headline = level_summary(headline_rollouts)
    headline["levels"] = headline_levels
    groups = [[int(bool(r.row["success"])) for r in by_level[lv]] for lv in headline_levels]
    if all(groups):
        headline["ci"] = bootstrap_ci(groups, stats.resamples, stats.seed, stats.ci)
    p = headline["p"]
    result: dict[str, Any] = {
        "levels": levels,
        "headline": headline,
        "rule0": {"threshold": RULE0_P, "p": p, "fires": p is not None and p < RULE0_P},
        "rollouts": len(chosen),
        "missing": [list(m) for m in missing],
        "extra_rollouts": sum(extra.values()),
        "extra_by_condition": {f"{lv}:{seed}": n for (lv, seed), n in sorted(extra.items())},
        "reruns": sum(1 for r in chosen if r.attempt > 0),
        "stats": {"method": stats.method, "resamples": stats.resamples, "seed": stats.seed},
        "label": "preliminary, on dev",
    }
    if yaw is not None:
        traced = list(yaw.values())
        result["yaw"] = {
            "episodes": len(traced),
            "cycles": sum(t["cycles"] for t in traced),
            "raw_over": sum(t["raw_over"] for t in traced),
            "wrapped_over": sum(t["wrapped_over"] for t in traced),
            "max_wrapped": max((t["max_wrapped"] for t in traced), default=None),
            "threshold_rad": YAW_LARGE,
        }
    return result


def table(result: dict[str, Any]) -> str:
    """Markdown table of the result, one row per level and one for the headline."""

    def pct(x: float | None) -> str:
        return "–" if x is None else f"{100 * x:.1f}"

    lines = [
        "| Mức | n | Thành công | p (%) | CI 95 % (%) | "
        + " | ".join(STEP_NAMES)
        + " | Loại lỗi |",
        "|---" * (6 + len(STEP_NAMES)) + "|",
    ]
    rows = [(k, v) for k, v in result["levels"].items()]
    rows.append(("1–2 gộp", result["headline"]))
    for name, s in rows:
        ci = s.get("ci")
        ci_text = "–" if ci is None else f"{pct(ci[0])}–{pct(ci[1])}"
        failures = ", ".join(f"{k} {v}" for k, v in sorted(s["failures"].items()))
        lines.append(
            f"| {name} | {s['n']} | {s['successes']} | {pct(s['p'])} | {ci_text} | "
            + " | ".join(pct(s["step_pass"][n]) for n in STEP_NAMES)
            + f" | {failures or '–'} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--out", type=Path, required=True, help="eval_batch directory")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--json", type=Path, help="write the result here")
    parser.add_argument("--no-yaw", action="store_true", help="skip reading the traces")
    args = parser.parse_args(argv)
    plan = TrayRunPlan.load(args.plan)
    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    chosen, extra, missing = collect(args.out, chunk_plan(rows, args.chunk))
    yaw = None
    if not args.no_yaw:
        yaw = {}
        for r in chosen:
            if (steps := trace_of(args.out, r)) is not None:
                yaw[(r.level, r.seed)] = yaw_errors(steps)
    result = summarize(plan, chosen, extra, missing, yaw)
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    print(table(result))
    counts = {"missing": len(result["missing"]), "yaw": result.get("yaw")}
    print(json.dumps({k: result[k] for k in ("rule0", "rollouts", "extra_rollouts")} | counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
