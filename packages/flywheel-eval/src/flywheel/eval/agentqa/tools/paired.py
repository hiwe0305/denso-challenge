"""`paired_compare`: two runs on the same conditions, paired (DA-43 task 2.2).

The arithmetic of the team's reading rules (docs/he/tray.md 18.2, 19.2 a'):
d_i = s_a,i - s_b,i per condition; the difference is the mean of d_i; its CI resamples
d_i within each level (percentile bootstrap, the plan's resamples, seed and level);
the exact two-sided McNemar p on the discordant pairs; a Wilson 95 % interval of each
run's success. The same computation as `flywheel_psi0.tray.eval_results`, which a lane
may not import; a test checks both give the published numbers.

Reading a rule (E1, E3, F, "non-inferior") belongs to the RunPlan, not to the agent:
the tool only states where the CI lies against 0.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import Row, RunScores, ToolResult, not_judged

TOOL = "paired_compare"
Z95 = 1.959963984540054


@dataclass(frozen=True)
class BootstrapStats:
    """The `stats` block of a RunPlan; the pair60k plan's values by default."""

    resamples: int = 10_000
    seed: int = 20261103
    ci: float = 0.95


def bootstrap_ci(groups: Sequence[Sequence[int]], stats: BootstrapStats) -> tuple[float, float]:
    """Percentile CI of the pooled mean, each group resampled within itself."""
    rng = np.random.default_rng(stats.seed)
    total = sum(len(g) for g in groups)
    sums = np.zeros(stats.resamples)
    for group in groups:
        values = np.asarray(group, dtype=float)
        picks = rng.integers(0, len(values), size=(stats.resamples, len(values)))
        sums += values[picks].sum(axis=1)
    means = sums / total
    tail = (1 - stats.ci) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def mcnemar_exact(a_only: int, b_only: int) -> float:
    n = a_only + b_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(a_only, b_only) + 1))
    return min(1.0, 2.0 * tail / float(2**n))


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def paired_compare(book: FactBook, a: RunScores, b: RunScores,
                   levels: Sequence[int] | None = None,
                   stats: BootstrapStats = BootstrapStats()) -> ToolResult:
    """Run `a` minus run `b`, over the conditions of `levels` (all levels of `a` if None)."""
    ref = f"{a.ref} vs {b.ref}"
    chosen = list(levels) if levels is not None else a.levels()
    sa = {(s.level, a.key(s)): int(bool(s.success)) for s in a.scores if s.level in chosen}
    sb = {(s.level, b.key(s)): int(bool(s.success)) for s in b.scores if s.level in chosen}
    if sa.keys() != sb.keys():
        only = sorted(str(k) for k in sa.keys() ^ sb.keys())[:5]
        return not_judged(book, TOOL, f"{a.run} and {b.run} cover different conditions, "
                          f"e.g. {', '.join(only)}", ref, f"{a.run}_vs_{b.run}")
    if not sa:
        return not_judged(book, TOOL, f"no condition at levels {chosen}", ref,
                          f"{a.run}_vs_{b.run}")
    # Condition order fixes the bootstrap draws: (level, condition), as eval_results does.
    groups = [[sa[k] - sb[k] for k in sorted(sa) if k[0] == level]
              for level in chosen]
    groups = [g for g in groups if g]
    n = sum(len(g) for g in groups)
    a_only = sum(1 for k in sa if sa[k] > sb[k])
    b_only = sum(1 for k in sa if sa[k] < sb[k])
    low, high = bootstrap_ci(groups, stats)
    diff = sum(sum(g) for g in groups) / n
    name = f"{a.run}_vs_{b.run}_l{'+'.join(str(lv) for lv in chosen)}"
    wa, wb = wilson(sum(sa.values()), n), wilson(sum(sb.values()), n)
    facts = [
        book.add(f"{name}_conditions", n, ref, "conditions"),
        book.add(f"{name}_{a.run}_successes", sum(sa.values()), ref, "conditions"),
        book.add(f"{name}_{b.run}_successes", sum(sb.values()), ref, "conditions"),
        book.add(f"{name}_diff", round(diff, 4), ref, "fraction"),
        book.add(f"{name}_ci_low", round(low, 4), ref, "fraction"),
        book.add(f"{name}_ci_high", round(high, 4), ref, "fraction"),
        book.add(f"{name}_ci_level", stats.ci, ref, "fraction"),
        book.add(f"{name}_ci_vs_0",
                 "above" if low > 0 else "below" if high < 0 else "contains", ref),
        book.add(f"{name}_{a.run}_only", a_only, ref, "conditions"),
        book.add(f"{name}_{b.run}_only", b_only, ref, "conditions"),
        book.add(f"{name}_mcnemar_exact_p", round(mcnemar_exact(a_only, b_only), 4), ref),
        book.add(f"{name}_{a.run}_wilson_low", round(wa[0], 4), ref, "fraction"),
        book.add(f"{name}_{a.run}_wilson_high", round(wa[1], 4), ref, "fraction"),
        book.add(f"{name}_{b.run}_wilson_low", round(wb[0], 4), ref, "fraction"),
        book.add(f"{name}_{b.run}_wilson_high", round(wb[1], 4), ref, "fraction"),
    ]
    row: Row = {"a": a.run, "b": b.run, "conditions": n, "diff": round(diff, 4),
           "ci_low": round(low, 4), "ci_high": round(high, 4)}
    return ToolResult(TOOL, tuple(facts), (row,))
