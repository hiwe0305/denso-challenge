"""Read an `eval_batch` directory into the result of a tray RunPlan's eval (DA-34 task 3.4).

One rollout per eval condition: the **earliest finished** one, by attempt, of each
episode. A rerun of a chunk starts at its first missing episode, so an episode that had
already finished after a gap runs again; rollouts are not reproducible on EGL
(docs/he/tray.md 13.2), so the later rollout may differ. It is counted as an extra
rollout and never chosen, whatever its outcome (main-session review of #147).

Per level: episodes, successes, p and its bootstrap CI (the plan's `stats`) next to a
Wilson 95 % interval (the bootstrap CI collapses to a point at 0 or n successes),
failure kinds, the pass rate of each of the scorer's seven steps (`scorer_steps` of the
outcome rows, in order), how many steps each rollout reached in a row from the first
(the scorer latches steps in order), and the yaw error of DA-38's traces: target_yaw (cmd) minus
base yaw (meas), raw and wrapped to [-pi, pi]. The headline is the levels marked
`headline` in the plan, pooled, with the bootstrap resampling inside each level
(docs/he/tray.md 8.2); level 0 is resampled by replicate the same way. Rule 0 of the
tier 2 rules (tray.md 9) is reported as the plain test `p_headline < 0.10`; reading it
is the RunPlan's interpretation doc, not this module.

    python -m flywheel_psi0.tray.eval_results configs/runplans/tray/he-tray-v2.yaml \
        --set <eval set> --out <eval_batch dir> --json results.json

With `--baseline <eval_batch dir of the same set>`, `paired` adds the per-condition
counts and, for the headline levels pooled and for each level, the paired difference
variant - baseline with its bootstrap CI (the per-condition differences resampled within
each level, the plan's `stats`) and the exact two-sided McNemar p on the discordant
pairs: the measures of branch B's reading rules (docs/he/tray.md 18.2). `ci_vs_0` says
where the CI lies; reading it is the doc's.

With `--stage1` (needs `--baseline`), only the first STAGE1_CHUNKS chunks of the run
order are read, on both sides: stage 1 of branch B's two-stage eval (tray.md 18.2, Hiếu
10/11/2026), l1-000, l2-000, l1-010, l2-010, l1-020, l2-020, 60 conditions. A missing
rollout in them is an error. `stage1.outcome` applies the stage 1 stop rule to the
paired headline: E1 and E3 stop on a clear difference, F stops when B shows no gain,
`continue` runs the remaining chunks. It is the rule's arithmetic for a run against C;
against C+ (rule 5) it is not read.
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

from flywheel_psi0.tray.eval_batch import Chunk, attempts, chunk_plan, finished, phases_for
from flywheel_psi0.tray.runplan import Stats, TrayRunPlan

# flywheel_simple.tray.predicates.STEP_NAMES; SIMPLE's venv is not this package's.
STEP_NAMES = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")
RULE0_P = 0.10  # tier 2 rule 0: p_C < 10% on the headline levels
YAW = 6  # index of yaw in TraceStep.cmd_lower / meas_lower (flywheel.contracts.trace)
YAW_LARGE = 2.5  # rad, the threshold the yaw counts are reported against
Z95 = 1.959963984540054  # two-sided 95 % normal quantile, for the Wilson interval
STAGE1_CHUNKS = 6  # branch B's stage 1 (tray.md 18.2): 3 chunks of level 1, 3 of level 2
STAGE1_P = 0.001  # stage 1 stops on a clear difference: exact McNemar p below this


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


def mcnemar_exact(variant_only: int, baseline_only: int) -> float:
    """Exact two-sided McNemar p: the smaller discordant count under Binomial(n, 1/2)."""
    n = variant_only + baseline_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(variant_only, baseline_only) + 1))
    return min(1.0, 2.0 * tail / float(2**n))


def paired_diff(
    variant: Sequence[Rollout], baseline: Sequence[Rollout], levels: Sequence[int], stats: Stats
) -> dict[str, Any]:
    """Paired success difference variant - baseline over the conditions of `levels`.

    d_i = s_variant,i - s_baseline,i per condition (level, seed); the difference is the
    mean of d_i and its CI resamples d_i within each level, with the plan's resamples,
    seed and level, so the two sides stay paired (docs/he/tray.md 2, 9 and 18.2).
    """
    a = {(r.level, r.seed): int(bool(r.row["success"])) for r in variant if r.level in levels}
    b = {(r.level, r.seed): int(bool(r.row["success"])) for r in baseline if r.level in levels}
    if a.keys() != b.keys():
        raise ValueError("variant and baseline cover different conditions")
    groups = [[a[k] - b[k] for k in sorted(a) if k[0] == level] for level in levels]
    groups = [g for g in groups if g]
    n = sum(len(g) for g in groups)
    if n == 0:
        raise ValueError(f"no condition at levels {list(levels)}")
    variant_only = sum(1 for k in a if a[k] > b[k])
    baseline_only = sum(1 for k in a if a[k] < b[k])
    low, high = bootstrap_ci(groups, stats.resamples, stats.seed, stats.ci)
    return {
        "levels": list(levels),
        "n": n,
        "variant": sum(a.values()),
        "baseline": sum(b.values()),
        "diff": round(sum(sum(g) for g in groups) / n, 4),
        "ci": (round(low, 4), round(high, 4)),
        "ci_vs_0": "above" if low > 0 else "below" if high < 0 else "contains",
        "variant_only": variant_only,
        "baseline_only": baseline_only,
        "mcnemar_exact_p": round(mcnemar_exact(variant_only, baseline_only), 4),
    }


def stage1_outcome(diff: dict[str, Any]) -> str:
    """Branch B's stage 1 stop rule (tray.md 18.2) on `paired_diff` of its 60 conditions.

    b and c are the discordant pairs (variant only, baseline only). E1: p < STAGE1_P,
    b > c and the CI above 0. E3: p < STAGE1_P, b < c and the CI below 0. F: otherwise
    with b <= c. `continue`: otherwise (b > c). p is recomputed: the rounded p of
    `paired_diff` would put 11 against 0 (p 0.00098) at 0.001.
    """
    b, c = diff["variant_only"], diff["baseline_only"]
    low, high = diff["ci"]
    clear = mcnemar_exact(b, c) < STAGE1_P
    if clear and b > c and low > 0:
        return "E1"
    if clear and b < c and high < 0:
        return "E3"
    return "F" if b <= c else "continue"


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval of k successes in n trials."""
    if n == 0:
        raise ValueError("no trials")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def reached(steps: Sequence[bool]) -> int:
    """Steps passed in a row from the first."""
    n = 0
    for passed in steps:
        if not passed:
            break
        n += 1
    return n


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
        "wilson": wilson(sum(success), len(success)) if rollouts else None,
        "failures": dict(Counter(r.row["failure"] for r in rollouts if not r.row["success"])),
        "step_pass": {
            name: (sum(bool(s[k]) for s in known) / len(known) if known else None)
            for k, name in enumerate(STEP_NAMES)
        },
        "steps_unknown": len(steps) - len(known),
        "reached": dict(sorted(Counter(reached(s) for s in known).items())),
    }


def summarize(
    plan: TrayRunPlan,
    chosen: Sequence[Rollout],
    extra: dict[tuple[int, int], int],
    missing: Sequence[tuple[int, int]],
    yaw: dict[tuple[int, int], dict[str, float]] | None = None,
    full: bool = True,
) -> dict[str, Any]:
    """With `full` False (a smaller set, tray.md 14), levels without rollouts are left out
    and rule 0 is not reported: it reads the plan's whole eval set only."""
    if plan.eval.by_level is None:
        raise ValueError("eval_results reads a version 2 plan (eval.by_level)")
    stats = plan.stats
    present = {r.level for r in chosen} | {level for level, _ in missing}
    by_level_cfg = [c for c in plan.eval.by_level if full or c.level in present]
    by_level = {c.level: [r for r in chosen if r.level == c.level] for c in by_level_cfg}
    levels = {}
    for c in by_level_cfg:
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
    headline_levels = [c.level for c in by_level_cfg if c.headline]
    headline_rollouts = [r for level in headline_levels for r in by_level[level]]
    headline = level_summary(headline_rollouts)
    headline["levels"] = headline_levels
    groups = [[int(bool(r.row["success"])) for r in by_level[lv]] for lv in headline_levels]
    if all(groups):
        headline["ci"] = bootstrap_ci(groups, stats.resamples, stats.seed, stats.ci)
    everything = level_summary(chosen)
    everything["levels"] = [c.level for c in by_level_cfg]
    p = headline["p"]
    result: dict[str, Any] = {
        "levels": levels,
        "headline": headline,
        "all": everything,
        "rule0": (
            {"threshold": RULE0_P, "p": p, "fires": p is not None and p < RULE0_P} if full else None
        ),
        "full_eval_set": full,
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


def paired(variant: Sequence[Rollout], baseline: Sequence[Rollout]) -> dict[str, Any]:
    """Per condition (level, seed) of both: success and each step, variant against baseline.

    Each side is one rollout per condition (EGL rollouts are not reproducible, tray.md
    13.2), so a pair compares two rollouts, not two measurements of one.
    """
    a = {(r.level, r.seed): r.row for r in variant}
    b = {(r.level, r.seed): r.row for r in baseline}
    if a.keys() != b.keys():
        raise ValueError("variant and baseline cover different conditions")

    def counts(get: Any) -> dict[str, int]:
        pairs = [(bool(get(a[k])), bool(get(b[k]))) for k in a]
        return {
            "both": sum(x and y for x, y in pairs),
            "variant_only": sum(x and not y for x, y in pairs),
            "baseline_only": sum(y and not x for x, y in pairs),
            "neither": sum(not x and not y for x, y in pairs),
        }

    steps = {
        name: counts(lambda row, k=k: (row.get("scorer_steps") or [False] * 7)[k])
        for k, name in enumerate(STEP_NAMES)
    }
    success = counts(lambda row: row["success"])
    return {
        "conditions": len(a),
        "success": success,
        "steps": steps,
        "success_gain": success["variant_only"] - success["baseline_only"],
        "place_gain": steps["place"]["variant_only"] - steps["place"]["baseline_only"],
    }


def table(result: dict[str, Any]) -> str:
    """Markdown table of the result, one row per level and one for the headline."""

    def pct(x: float | None) -> str:
        return "–" if x is None else f"{100 * x:.1f}"

    lines = [
        "| Mức | n | Thành công | p (%) | CI bootstrap (%) | Wilson 95 % (%) | "
        + " | ".join(STEP_NAMES)
        + " | Loại lỗi |",
        "|---" * (7 + len(STEP_NAMES)) + "|",
    ]
    rows = [(k, v) for k, v in result["levels"].items()]
    if result.get("full_eval_set", True):
        rows.append(("1–2 gộp", result["headline"]))
    rows.append(("cả lô", result["all"]))
    for name, s in rows:
        ci = s.get("ci")
        ci_text = "–" if ci is None else f"{pct(ci[0])}–{pct(ci[1])}"
        w = s.get("wilson")
        wilson_text = "–" if w is None else f"{pct(w[0])}–{pct(w[1])}"
        failures = ", ".join(f"{k} {v}" for k, v in sorted(s["failures"].items()))
        lines.append(
            f"| {name} | {s['n']} | {s['successes']} | {pct(s['p'])} | {ci_text} | {wilson_text} | "
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
    parser.add_argument(
        "--baseline", type=Path, help="eval_batch directory of the same set to pair with"
    )
    parser.add_argument(
        "--stage1",
        action="store_true",
        help=f"read the first {STAGE1_CHUNKS} chunks only: stage 1 of branch B (tray.md 18.2)",
    )
    args = parser.parse_args(argv)
    if args.stage1 and args.baseline is None:
        parser.error("--stage1 pairs with a baseline: give --baseline")
    plan = TrayRunPlan.load(args.plan)
    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    chunks = chunk_plan(rows, args.chunk, phases_for(rows))
    if args.stage1:
        chunks = chunks[:STAGE1_CHUNKS]
    chosen, extra, missing = collect(args.out, chunks)
    if args.stage1 and missing:
        raise ValueError(f"stage 1 misses {missing}: do not read it (tray.md 18.2)")
    full = not args.stage1 and sorted((int(r["level"]), int(r["seed"])) for r in rows) == sorted(
        plan.eval_conditions()
    )
    yaw = None
    if not args.no_yaw:
        yaw = {}
        for r in chosen:
            if (steps := trace_of(args.out, r)) is not None:
                yaw[(r.level, r.seed)] = yaw_errors(steps)
    result = summarize(plan, chosen, extra, missing, yaw, full)
    if args.baseline is not None:
        base, _, base_missing = collect(args.baseline, chunks)
        if base_missing:
            raise ValueError(f"baseline misses {base_missing}")
        result["paired"] = paired(chosen, base)
        if plan.eval.by_level is not None:
            headline = [c.level for c in plan.eval.by_level if c.headline]
            result["paired"]["headline"] = paired_diff(chosen, base, headline, plan.stats)
            result["paired"]["by_level"] = {
                str(c.level): paired_diff(chosen, base, [c.level], plan.stats)
                for c in plan.eval.by_level
                if any(r.level == c.level for r in chosen)
            }
            if args.stage1:
                result["stage1"] = {
                    "chunks": [chunk.id for chunk in chunks],
                    "conditions": result["paired"]["headline"]["n"],
                    "p_threshold": STAGE1_P,
                    "outcome": stage1_outcome(result["paired"]["headline"]),
                }
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    print(table(result))
    counts: dict[str, Any] = {"missing": len(result["missing"]), "yaw": result.get("yaw")}
    if "paired" in result:
        brief = {k: result["paired"][k] for k in ("success_gain", "place_gain")}
        if "headline" in result["paired"]:
            brief["headline"] = result["paired"]["headline"]
        counts["paired"] = brief
    if "stage1" in result:
        counts["stage1"] = result["stage1"]
    print(json.dumps({k: result[k] for k in ("rule0", "rollouts", "extra_rollouts")} | counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
