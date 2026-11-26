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
rollout of repeat 0 in them, the repeat the pairing reads, is an error; missing later
repeats are only listed. `stage1.outcome` applies the stage 1 stop rule to the
paired headline: E1 and E3 stop on a clear difference, F stops when B shows no gain,
`continue` runs the remaining chunks. It is the rule's arithmetic for a run against C;
against C+ (rule 5) it is not read.

Repeats (DA-42): with `--repeats N` (as given to eval_batch) each condition has N
rollouts, repeat r of chunk c in `<out>/<c>.r<r>/`. Per level, `n` counts rollouts and
`conditions` conditions; `per_condition` gives successes and rollouts of each. The
rollouts of one condition share its scene and are not independent: the statistical unit
is the condition, and the bootstrap CI, which resamples conditions (their mean success)
within each level, is the primary CI (docs/he/tray-jig.md 2). `wilson` is descriptive
only: with more than one rollout per condition it is the Wilson interval of the pooled p
at n_eff = the number of conditions (`wilson_n_eff`), so it moves continuously with the
successes. `wilson_design_effect` is the design effect estimated from the
between-condition variance of a ratio estimator, at least 1, descriptive beside it; null
when p is 0 or 1 or there are fewer than two conditions. With one rollout per condition
n_eff is n and `wilson` is the plain Wilson interval of before. `paired` and
`paired_diff` pair repeat 0 of each condition only, the rollout an old
one-per-condition run has. With `--baseline` and `--repeats` above 1 (not `--stage1`),
`paired.repeats` adds the reading of docs/he/tray-jig.md 6 (`jig-n-rules`) on every
repeat: per condition the variant's success rate minus the baseline's, the same
rollouts per condition on both sides, its mean and bootstrap CI resampled within each
level (`paired_diff_repeats`), for the headline levels pooled and for each level; the
baseline is read with the same `--repeats`, and a missing rollout on either side skips
the block. `--bootstrap-seed` replaces the plan's stats seed in every bootstrap CI
printed and is recorded as `bootstrap_seed`. `missing` lists (level, seed, repeat) of
each rollout not found. A directory holding more repeats than `--repeats` reads is named
in the summary (`repeats_note`), never read silently short.

Scorer version (DA-42): every result names the version of the tray scorer that labelled
its rollouts (`scorer_version` of the outcome rows, written by `eval_driver` since
DA-42; rows without it are reported as unrecorded, `None`, never as a version). A
directory whose rows mix versions is refused, and so is pairing two sides scored by
different versions, unless `--cross-scorer` is given; the paired result then names both.
Rows that carry `scorer_v1` (version 1 run beside version 2 on the same rollout) add
`scorer_v1_vs_v2`: successes under each, label changes and approach_a latches.
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
from typing import Any, NamedTuple

import numpy as np

from flywheel_psi0.tray.eval_batch import (
    Chunk,
    attempts,
    chunk_plan,
    finished,
    phases_for,
    with_repeats,
)
from flywheel_psi0.tray.runplan import Stats, TrayRunPlan, run_plan_id

# flywheel_simple.tray.predicates.STEP_NAMES; SIMPLE's venv is not this package's.
STEP_NAMES = ("approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand")
RULE0_P = 0.10  # tier 2 rule 0: p_C < 10% on the headline levels
YAW = 6  # index of yaw in TraceStep.cmd_lower / meas_lower (flywheel.contracts.trace)
YAW_LARGE = 2.5  # rad, the threshold the yaw counts are reported against
Z95 = 1.959963984540054  # two-sided 95 % normal quantile, for the Wilson interval
STAGE1_CHUNKS = 6  # branch B's stage 1 (tray.md 18.2): 3 chunks of level 1, 3 of level 2
STAGE1_P = 0.001  # stage 1 stops on a clear difference: exact McNemar p below this
UNRECORDED = (
    "scorer version not recorded: rows written before DA-42 (scorer version 1) or "
    "outside eval_driver"
)


@dataclass(frozen=True)
class Rollout:
    level: int
    seed: int
    episode: int  # index in dr-level-<level>
    chunk: str  # directory of the chunk's repeat under the eval_batch dir (Chunk.dir_id)
    attempt: int
    row: dict[str, Any]  # the outcome row
    repeat: int = 0  # DA-42: rollout index of the condition


class Missing(NamedTuple):
    """A rollout `collect` did not find: condition (level, seed) and its repeat."""

    level: int
    seed: int
    repeat: int


def collect(
    out: Path, chunks: Sequence[Chunk]
) -> tuple[list[Rollout], dict[tuple[int, int], int], list[Missing]]:
    """(chosen rollouts in chunk order, extra rollouts per (level, seed), missing ones).

    One rollout per (condition, repeat): the chunks may include repeats (with_repeats);
    extra rollouts of all repeats of a condition add up, and `missing` names the repeat
    of each rollout not found.
    """
    chosen: list[Rollout] = []
    extra: dict[tuple[int, int], int] = {}
    missing: list[Missing] = []
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
                missing.append(Missing(chunk.level, seed, chunk.repeat))
                continue
            k, row = done[0]
            chosen.append(Rollout(chunk.level, seed, episode, chunk.dir_id, k, row, chunk.repeat))
            if len(done) > 1:
                key = (chunk.level, seed)
                extra[key] = extra.get(key, 0) + len(done) - 1
    return chosen, extra, missing


def repeats_found(out: Path, chunks: Sequence[Chunk]) -> int:
    """Repeats on disk: 1 + the largest k of a `<chunk>.r<k>` directory of the chunks."""
    ids = {c.id for c in chunks}
    found = 0
    for folder in out.glob("*.r*") if out.is_dir() else []:
        chunk_id, _, k = folder.name.rpartition(".r")
        if folder.is_dir() and chunk_id in ids and k.isdigit():
            found = max(found, int(k))
    return found + 1


def repeats_note(out: Path, chunks: Sequence[Chunk], repeats: int) -> str | None:
    """A line for the summary when `out` holds more repeats than are read; else None."""
    found = repeats_found(out, chunks)
    if found <= repeats:
        return None
    return f"{out} holds {found} repeats per condition, {repeats} read (--repeats {found} for all)"


def scorer_version(rollouts: Sequence[Rollout]) -> int | None:
    """The one scorer version of the rollouts' outcome rows; None when none records it.

    Refuses rows of two versions, and recorded rows mixed with unrecorded ones: results of
    two scorer versions are not comparable (docs/g0/tray/scorer-v2.md).
    """
    versions = {r.row.get("scorer_version") for r in rollouts}
    if len(versions) > 1:
        shown = sorted(versions, key=lambda v: (v is None, v or 0))
        raise ValueError(f"rollouts mix scorer versions {shown} (None: not recorded)")
    return versions.pop() if versions else None


def scorer_versions(
    variant: Sequence[Rollout], baseline: Sequence[Rollout], cross_scorer: bool
) -> dict[str, int | None]:
    """Both sides' scorer versions; different versions only with `cross_scorer`."""
    versions = {"variant": scorer_version(variant), "baseline": scorer_version(baseline)}
    if versions["variant"] != versions["baseline"] and not cross_scorer:
        raise ValueError(
            f"variant scored by version {versions['variant']}, baseline by "
            f"{versions['baseline']}: not comparable; --cross-scorer to pair them anyway"
        )
    return versions


def bootstrap_ci(
    groups: Sequence[Sequence[float]], resamples: int, seed: int, ci: float
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
    variant: Sequence[Rollout],
    baseline: Sequence[Rollout],
    levels: Sequence[int],
    stats: Stats,
    cross_scorer: bool = False,
) -> dict[str, Any]:
    """Paired success difference variant - baseline over the conditions of `levels`.

    d_i = s_variant,i - s_baseline,i per condition (level, seed); the difference is the
    mean of d_i and its CI resamples d_i within each level, with the plan's resamples,
    seed and level, so the two sides stay paired (docs/he/tray.md 2, 9 and 18.2).
    """
    single(variant)
    single(baseline)
    versions = scorer_versions(variant, baseline, cross_scorer)
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
        "scorer_versions": versions,
    }


def paired_diff_repeats(
    variant: Sequence[Rollout],
    baseline: Sequence[Rollout],
    levels: Sequence[int],
    resamples: int,
    seed: int,
    ci: float,
    cross_scorer: bool = False,
) -> dict[str, Any]:
    """Paired difference variant - baseline over the conditions of `levels`, all repeats.

    The condition is the unit (docs/he/tray-jig.md 6, `jig-n-rules`): d_i is the mean
    success of the variant's rollouts of condition i minus the baseline's. Both sides must
    cover the same conditions with the same number of rollouts each. The CI resamples d_i
    within each level (bootstrap_ci), so pooled levels keep their weights. Identical sides
    give d_i = 0, the CI (0, 0) and `ci_vs_0` "contains": no difference shown.
    """
    versions = scorer_versions(variant, baseline, cross_scorer)
    a = by_condition([r for r in variant if r.level in levels])
    b = by_condition([r for r in baseline if r.level in levels])
    if a.keys() != b.keys():
        raise ValueError("variant and baseline cover different conditions")
    if not a:
        raise ValueError(f"no condition at levels {list(levels)}")
    per_side = {}
    for side, conditions in (("variant", a), ("baseline", b)):
        counts = sorted({len(ok) for ok in conditions.values()})
        if len(counts) > 1:
            raise ValueError(f"{side} has uneven rollouts per condition: {counts}")
        per_side[side] = counts[0]
    if per_side["variant"] != per_side["baseline"]:
        raise ValueError(
            f"variant has {per_side['variant']} rollouts per condition, baseline "
            f"{per_side['baseline']}: not paired"
        )
    keys = sorted(a)
    mean_a = {k: sum(a[k]) / len(a[k]) for k in keys}
    mean_b = {k: sum(b[k]) / len(b[k]) for k in keys}
    d = {k: mean_a[k] - mean_b[k] for k in keys}
    groups = [[d[k] for k in keys if k[0] == level] for level in levels]
    groups = [g for g in groups if g]
    n = len(keys)
    low, high = bootstrap_ci(groups, resamples, seed, ci)
    return {
        "levels": list(levels),
        "conditions": n,
        "repeats": per_side["variant"],
        "variant_rate": round(sum(mean_a.values()) / n, 4),
        "baseline_rate": round(sum(mean_b.values()) / n, 4),
        "diff": round(sum(d.values()) / n, 4),
        "ci": (round(low, 4), round(high, 4)),
        "ci_vs_0": "above" if low > 0 else "below" if high < 0 else "contains",
        "conditions_variant_higher": sum(1 for v in d.values() if v > 0),
        "conditions_baseline_higher": sum(1 for v in d.values() if v < 0),
        "conditions_equal": sum(1 for v in d.values() if v == 0),
        "resamples": resamples,
        "seed": seed,
        "scorer_versions": versions,
        "cross_scorer": versions["variant"] != versions["baseline"],
    }


def repeats_line(name: str, diff: dict[str, Any], ci: float) -> str:
    """One Vietnamese line of `paired_diff_repeats` for the printed summary."""
    where = {"above": "nằm hẳn trên 0", "below": "nằm hẳn dưới 0", "contains": "chứa 0"}
    low, high = diff["ci"]
    return (
        f"Cặp theo điều kiện, mọi lượt ({diff['repeats']} lượt/điều kiện), mức {name}: "
        f"{diff['conditions']} điều kiện, biến thể {100 * diff['variant_rate']:.1f} %, "
        f"gốc {100 * diff['baseline_rate']:.1f} %, hiệu {100 * diff['diff']:+.1f} điểm, "
        f"CI {100 * ci:.0f} % {100 * low:+.1f} đến {100 * high:+.1f} "
        f"(bootstrap {diff['resamples']} lần, seed {diff['seed']}): {where[diff['ci_vs_0']]}; "
        f"điều kiện biến thể cao hơn {diff['conditions_variant_higher']}, "
        f"gốc cao hơn {diff['conditions_baseline_higher']}, bằng {diff['conditions_equal']}"
    )


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


def wilson(k: float, n: float, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval of k successes in n trials (n may be an effective size)."""
    if n == 0:
        raise ValueError("no trials")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def by_condition(rollouts: Sequence[Rollout]) -> dict[tuple[int, int], list[int]]:
    """Successes (0/1) of each condition's rollouts, keyed (level, seed), in rollout order."""
    out: dict[tuple[int, int], list[int]] = {}
    for r in rollouts:
        out.setdefault((r.level, r.seed), []).append(int(bool(r.row["success"])))
    return out


def clustered_wilson(groups: Sequence[Sequence[int]], z: float = Z95) -> dict[str, Any]:
    """Descriptive Wilson interval of the pooled success rate of clustered rollouts.

    `groups` are the 0/1 successes of each condition. One rollout per condition: the plain
    Wilson interval, design effect 1. More than one: the condition is the unit, so the
    interval is Wilson's of the pooled p at n_eff = conditions, whatever p is (continuous
    in the successes). `design_effect` is descriptive: the ratio estimator's
    between-condition variance, C / (C - 1) * sum (k_i - p m_i)^2 / n^2, over the binomial
    p (1 - p) / n, at least 1; None when p is 0 or 1 or C < 2 (not estimable).
    """
    groups = [g for g in groups if g]
    n = sum(len(g) for g in groups)
    if n == 0:
        raise ValueError("no trials")
    k = sum(sum(g) for g in groups)
    c = len(groups)
    p = k / n
    deff: float | None
    if c == n:
        method, n_eff, deff = "independent: one rollout per condition", float(n), 1.0
    else:
        method, n_eff = "clustered: n_eff = conditions, descriptive (CI: bootstrap)", float(c)
        deff = None
        if c >= 2 and 0.0 < p < 1.0:
            between = c / (c - 1) * sum((sum(g) - p * len(g)) ** 2 for g in groups) / n**2
            deff = max(1.0, between / (p * (1 - p) / n))
    low, high = wilson(p * n_eff, n_eff, z)
    return {
        "interval": (low, high),
        "n_eff": round(n_eff, 3),
        "design_effect": None if deff is None else round(deff, 3),
        "method": method,
    }


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
    """steps.jsonl of the rollout's DA-38 trace, matched by `episode_<i>`, in its repeat's dir."""
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
    conditions = by_condition(rollouts)
    interval = clustered_wilson(list(conditions.values())) if rollouts else None
    return {
        "n": len(rollouts),
        "conditions": len(conditions),
        "successes": sum(success),
        "p": sum(success) / len(rollouts) if rollouts else None,
        "wilson": interval["interval"] if interval else None,
        "wilson_n_eff": interval["n_eff"] if interval else None,
        "wilson_method": interval["method"] if interval else None,
        "wilson_design_effect": interval["design_effect"] if interval else None,
        "failures": dict(Counter(r.row["failure"] for r in rollouts if not r.row["success"])),
        "step_pass": {
            name: (sum(bool(s[k]) for s in known) / len(known) if known else None)
            for k, name in enumerate(STEP_NAMES)
        },
        "steps_unknown": len(steps) - len(known),
        "reached": dict(sorted(Counter(reached(s) for s in known).items())),
    }


def label(success: Any, failure: Any) -> str:
    return "success" if success else str(failure)


def scorer_v1_vs_v2(rollouts: Sequence[Rollout]) -> dict[str, Any] | None:
    """Version 1 against the row's own version on the same rollouts (rows with `scorer_v1`).

    `labels` counts each (version 1 -> own) label pair that differs; `v1_tilt_released`
    counts version 1 L-TRAY-TILT with no hand on the tray at its failure time, the case
    version 2 no longer labels (docs/g0/tray/scorer-v2.md 3).
    """
    rows = [r.row for r in rollouts if isinstance(r.row.get("scorer_v1"), dict)]
    if not rows:
        return None
    v1 = [row["scorer_v1"] for row in rows]
    changes = Counter(
        f"{label(a['success'], a['failure'])} -> {label(row['success'], row['failure'])}"
        for a, row in zip(v1, rows, strict=True)
        if label(a["success"], a["failure"]) != label(row["success"], row["failure"])
    )
    released = sum(
        1
        for a in v1
        if a["failure"] == "L-TRAY-TILT"
        and a.get("at_failure")
        and not any(a["at_failure"]["hand_contacts"].values())
    )
    return {
        "rollouts": len(rows),
        "versions": sorted({row.get("scorer_version") for row in rows}, key=str),
        "successes": {
            "v1": sum(bool(a["success"]) for a in v1),
            "own": sum(bool(row["success"]) for row in rows),
        },
        "labels": dict(sorted(changes.items())),
        "v1_tilt_released": released,
        "approach_a": {
            "v1": sum(bool(a["steps"][0]) for a in v1),
            "own": sum(bool((row.get("scorer_steps") or [False])[0]) for row in rows),
        },
    }


def condition_means(rollouts: Sequence[Rollout]) -> list[float]:
    """Mean success of each condition: what the bootstrap resamples (one value per condition)."""
    return [sum(ok) / len(ok) for ok in by_condition(rollouts).values()]


def repeat_0(rollouts: Sequence[Rollout]) -> list[Rollout]:
    """The first rollout of each condition: what `paired` and `paired_diff` read."""
    return [r for r in rollouts if r.repeat == 0]


def single(rollouts: Sequence[Rollout]) -> None:
    if any(r.repeat != 0 for r in rollouts):
        raise ValueError("pairing reads repeat 0 of each condition: pass repeat_0(rollouts)")


def summarize(
    plan: TrayRunPlan,
    chosen: Sequence[Rollout],
    extra: dict[tuple[int, int], int],
    missing: Sequence[Missing],
    yaw: dict[tuple[int, int, int], dict[str, float]] | None = None,
    full: bool = True,
) -> dict[str, Any]:
    """With `full` False (a smaller set, tray.md 14), levels without rollouts are left out
    and rule 0 is not reported: it reads the plan's whole eval set only."""
    if plan.eval.by_level is None:
        raise ValueError("eval_results reads a version 2 plan (eval.by_level)")
    stats = plan.stats
    present = {r.level for r in chosen} | {m.level for m in missing}
    by_level_cfg = [c for c in plan.eval.by_level if full or c.level in present]
    by_level = {c.level: [r for r in chosen if r.level == c.level] for c in by_level_cfg}
    levels = {}
    for c in by_level_cfg:
        summary = level_summary(by_level[c.level])
        summary["unit"] = c.unit
        if by_level[c.level]:
            summary["ci"] = bootstrap_ci(
                [condition_means(by_level[c.level])], stats.resamples, stats.seed, stats.ci
            )
        levels[str(c.level)] = summary
    headline_levels = [c.level for c in by_level_cfg if c.headline]
    headline_rollouts = [r for level in headline_levels for r in by_level[level]]
    headline = level_summary(headline_rollouts)
    headline["levels"] = headline_levels
    groups = [condition_means(by_level[lv]) for lv in headline_levels]
    if all(groups):
        headline["ci"] = bootstrap_ci(groups, stats.resamples, stats.seed, stats.ci)
    everything = level_summary(chosen)
    everything["levels"] = [c.level for c in by_level_cfg]
    p = headline["p"]
    version = scorer_version(chosen)
    result: dict[str, Any] = {
        "scorer_version": version,
        "scorer_version_note": UNRECORDED if version is None else None,
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
        "scorer_v1_vs_v2": scorer_v1_vs_v2(chosen),
        "repeats": 1 + max((r.repeat for r in chosen), default=0),
        "per_condition": {
            f"{lv}:{seed}": {"successes": sum(ok), "rollouts": len(ok)}
            for (lv, seed), ok in sorted(by_condition(chosen).items())
        },
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


def paired(
    variant: Sequence[Rollout], baseline: Sequence[Rollout], cross_scorer: bool = False
) -> dict[str, Any]:
    """Per condition (level, seed) of both: success and each step, variant against baseline.

    Each side is one rollout per condition (EGL rollouts are not reproducible, tray.md
    13.2), so a pair compares two rollouts, not two measurements of one.
    """
    single(variant)
    single(baseline)
    versions = scorer_versions(variant, baseline, cross_scorer)
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
        "scorer_versions": versions,
        "cross_scorer": versions["variant"] != versions["baseline"],
    }


def table(result: dict[str, Any]) -> str:
    """Markdown table of the result, one row per level and one for the headline."""

    def pct(x: float | None) -> str:
        return "–" if x is None else f"{100 * x:.1f}"

    version = result.get("scorer_version")
    lines = [
        f"Bộ chấm khay: phiên bản {version}"
        if version is not None
        else "Bộ chấm khay: không ghi phiên bản (dòng trước DA-42 là bản 1)",
        "",
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


def paired_repeats(
    plan: TrayRunPlan,
    chosen: Sequence[Rollout],
    missing: Sequence[Missing],
    baseline_out: Path,
    chunks: Sequence[Chunk],
    headline: Sequence[int],
    cross_scorer: bool,
) -> dict[str, Any]:
    """`paired.repeats`: `paired_diff_repeats` on every repeat of both sides, the headline
    levels pooled and each level. The baseline is read with the variant's repeats; a
    missing rollout on either side skips the block (named in `skipped`), it never pairs
    uneven conditions."""
    block: dict[str, Any] = {"on": "all repeats of each condition"}
    base, _, base_missing = collect(baseline_out, chunks)
    if missing or base_missing:
        block["skipped"] = f"missing: variant {len(missing)}, baseline {len(base_missing)}"
        return block
    stats = plan.stats

    def diff(levels: Sequence[int]) -> dict[str, Any]:
        return paired_diff_repeats(
            chosen, base, levels, stats.resamples, stats.seed, stats.ci, cross_scorer
        )

    block["headline"] = diff(headline)
    block["by_level"] = {
        str(c.level): diff([c.level])
        for c in plan.eval.by_level or []
        if any(r.level == c.level for r in chosen)
    }
    return block


def plan_mismatch(
    plan: TrayRunPlan, plan_path: Path, rows: Sequence[dict[str, Any]]
) -> dict[str, Any] | None:
    """The set's run_plan_id(s) against the plan read with, or None when they agree or are unknown.

    Not an error: older batches are read with another plan on purpose. The result only says
    the plan's settings (stats seed, headline levels) are not the ones the set was built for.
    """
    ids = sorted(
        {
            str(r["environment_config"]["flywheel"]["run_plan_id"])
            for r in rows
            if ((r.get("environment_config") or {}).get("flywheel") or {}).get("run_plan_id")
        }
    )
    own = run_plan_id(plan)
    if not ids or ids == [own]:
        return None
    return {
        "set_run_plan_id": ids[0] if len(ids) == 1 else ids,
        "plan_run_plan_id": own,
        "plan": plan_path.name,
    }


def mismatch_warning(mismatch: dict[str, Any], seed_note: str | None = None) -> str:
    """One Vietnamese line: the set was built for another plan than the one read with."""
    line = (
        f"CẢNH BÁO: bộ điều kiện được dựng cho kế hoạch {mismatch['set_run_plan_id']} "
        f"nhưng đang đọc với thiết lập của kế hoạch {mismatch['plan_run_plan_id']} "
        f"({mismatch['plan']})"
    )
    return line if seed_note is None else f"{line}; {seed_note}"


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
    parser.add_argument(
        "--repeats", type=int, default=1, help="rollouts per condition, as run (DA-42)"
    )
    parser.add_argument(
        "--cross-scorer",
        action="store_true",
        help="pair with a baseline scored by another scorer version (not comparable)",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        help="seed of every bootstrap CI printed, in place of the plan's stats seed",
    )
    args = parser.parse_args(argv)
    if args.stage1 and args.baseline is None:
        parser.error("--stage1 pairs with a baseline: give --baseline")
    plan = TrayRunPlan.load(args.plan)
    loaded = plan  # as on disk: `--bootstrap-seed` below changes the copy's run_plan_id
    if args.bootstrap_seed is not None:
        stats = plan.stats.model_copy(update={"seed": args.bootstrap_seed})
        plan = plan.model_copy(update={"stats": stats})
    rows = [json.loads(line) for line in (args.set / "conditions.jsonl").read_text().splitlines()]
    chunks = chunk_plan(rows, args.chunk, phases_for(rows))
    if args.stage1:
        chunks = chunks[:STAGE1_CHUNKS]
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    chunks = with_repeats(chunks, args.repeats)
    chosen, extra, missing = collect(args.out, chunks)
    unread = [m for m in missing if m.repeat == 0]  # stage 1 pairs repeat 0 only
    if args.stage1 and unread:
        raise ValueError(f"stage 1 misses {unread}: do not read it (tray.md 18.2)")
    full = not args.stage1 and sorted((int(r["level"]), int(r["seed"])) for r in rows) == sorted(
        plan.eval_conditions()
    )
    yaw = None
    if not args.no_yaw:
        yaw = {}
        for r in chosen:
            if (steps := trace_of(args.out, r)) is not None:
                yaw[(r.level, r.seed, r.repeat)] = yaw_errors(steps)
    result = summarize(plan, chosen, extra, missing, yaw, full)
    result["repeats_note"] = repeats_note(args.out, chunks, args.repeats)
    if args.bootstrap_seed is not None:
        result["bootstrap_seed"] = plan.stats.seed
    mismatch = plan_mismatch(loaded, args.plan, rows)
    warning = None
    if mismatch is not None:
        mismatch["bootstrap_seed_from"] = (
            "plan" if args.bootstrap_seed is None else "--bootstrap-seed"
        )
        result["plan_mismatch"] = mismatch
        warning = mismatch_warning(
            mismatch,
            f"seed bootstrap {plan.stats.seed} lấy từ kế hoạch đang đọc, không phải kế hoạch của "
            "bộ; --bootstrap-seed đặt lại seed này"
            if args.bootstrap_seed is None
            else f"seed bootstrap {plan.stats.seed} do --bootstrap-seed đặt",
        )
    if args.baseline is not None:
        first = [c for c in chunks if c.repeat == 0]
        base, _, base_missing = collect(args.baseline, first)
        if base_missing:
            raise ValueError(f"baseline misses {base_missing}")
        variant = repeat_0(chosen)
        result["paired"] = paired(variant, base, args.cross_scorer)
        result["paired"]["on"] = "repeat 0 of each condition"
        if plan.eval.by_level is not None:
            headline = [c.level for c in plan.eval.by_level if c.headline]
            result["paired"]["headline"] = paired_diff(
                variant, base, headline, plan.stats, args.cross_scorer
            )
            result["paired"]["by_level"] = {
                str(c.level): paired_diff(variant, base, [c.level], plan.stats, args.cross_scorer)
                for c in plan.eval.by_level
                if any(r.level == c.level for r in variant)
            }
            if args.repeats > 1 and not args.stage1:
                result["paired"]["repeats"] = paired_repeats(
                    plan, chosen, missing, args.baseline, chunks, headline, args.cross_scorer
                )
            if args.stage1:
                result["stage1"] = {
                    "chunks": [chunk.id for chunk in first],
                    "conditions": result["paired"]["headline"]["n"],
                    "p_threshold": STAGE1_P,
                    "outcome": stage1_outcome(result["paired"]["headline"]),
                }
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    if warning is not None:
        print(warning)
        print(warning, file=sys.stderr)
    print(table(result))
    if result["repeats_note"] is not None:
        print(result["repeats_note"])
    repeats = result.get("paired", {}).get("repeats")
    if repeats is not None:
        if "skipped" in repeats:
            print(f"Cặp theo điều kiện, mọi lượt: không đọc ({repeats['skipped']})")
        else:
            print(repeats_line("1+2 gộp", repeats["headline"], plan.stats.ci))
            for level, diff in repeats["by_level"].items():
                print(repeats_line(level, diff, plan.stats.ci))
    counts: dict[str, Any] = {
        "scorer_version": result["scorer_version"],
        "scorer_v1_vs_v2": result["scorer_v1_vs_v2"],
        "missing": len(result["missing"]),
        "repeats_note": result["repeats_note"],
        "yaw": result.get("yaw"),
    }
    if "paired" in result:
        brief = {
            k: result["paired"][k]
            for k in ("success_gain", "place_gain", "scorer_versions", "cross_scorer")
        }
        if "headline" in result["paired"]:
            brief["headline"] = result["paired"]["headline"]
        counts["paired"] = brief
    if "stage1" in result:
        counts["stage1"] = result["stage1"]
    if "plan_mismatch" in result:
        counts["plan_mismatch"] = result["plan_mismatch"]
    print(json.dumps({k: result[k] for k in ("rule0", "rollouts", "extra_rollouts")} | counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
