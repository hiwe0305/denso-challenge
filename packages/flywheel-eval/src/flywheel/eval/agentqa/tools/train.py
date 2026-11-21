"""`train_window`: what the loss and the gradients did around one point of a job (task 3.2).

The window is never a free number. It is one of a closed set (`window_of`):

- `all`: every logged row of the job;
- `last`: the validation interval of the last logged step;
- a logged step `s` of the job: the validation interval `s` falls in, that is the rows
  after the last validation step before `s` (the start, if none) up to the first
  validation step at or after `s` (the last logged step, if none).

So a finding's `start_step` (a logged step) names the stretch between two validation
points around it, and nothing in the plan says how wide that is.

Facts per job and window: train loss (first, last, min, median, non-finite count), val loss
(first, last, count), the mean and last loss of each group, the median and p99 of both
gradient norms, and the validation cadence (median gap between validation steps of the
window; of the whole log when the window holds fewer than two). A norm the log does not
carry, or a split with no row in the window, is `not_judged` with the reason.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import JobMetrics, Row, ToolResult, not_judged
from flywheel.eval.diagnosis.system.reader import percentile

TOOL = "train_window"
GRADS = ("grad_norm_vlm", "grad_norm_action")


@dataclass(frozen=True)
class Window:
    label: str
    lo: int  # rows with lo < step <= hi
    hi: int


def logged_steps(job: JobMetrics) -> list[int]:
    return sorted({r.step for r in job.rows})


def window_of(job: JobMetrics, which: str | int) -> Window | None:
    """The window `which` names in `job`; None when `val` has no step to end it."""
    steps = logged_steps(job)
    val = sorted({r.step for r in job.rows if r.split == "val"})
    if which == "all":
        return Window("all", steps[0] - 1, steps[-1])
    anchor = steps[-1] if which == "last" else int(which)
    label = "last" if which == "last" else f"s{anchor}"
    lo = max((v for v in val if v < anchor), default=steps[0] - 1)
    hi = min((v for v in val if v >= anchor), default=steps[-1])
    return Window(label, lo, hi)


def _loss(row: TrainingMetric) -> float:
    return float(row.loss)


def _gap(steps: Sequence[int]) -> float | None:
    gaps = np.diff(np.array(steps, dtype=np.float64))
    return float(np.median(gaps)) if gaps.size else None


def train_window(book: FactBook, job: JobMetrics, which: str | int) -> ToolResult:
    """Facts and a one-row table of `job` over the window `which`."""
    window = window_of(job, which)
    ref = job.ref
    if window is None or not job.rows:
        return not_judged(book, TOOL, f"job {job.job}: no logged row", ref, job.job)
    prefix = f"train_{job.job}_{window.label}"
    rows = [r for r in job.rows if window.lo < r.step <= window.hi]
    train = [r for r in rows if r.split == "train"]
    val = [r for r in rows if r.split == "val"]
    facts = [book.add(f"{prefix}_first_step", min(r.step for r in rows), ref, "steps"),
             book.add(f"{prefix}_last_step", max(r.step for r in rows), ref, "steps"),
             book.add(f"{prefix}_rows", len(rows), ref, "rows")]
    reasons: list[str] = []

    def skip(name: str, why: str) -> None:
        reason = f"{prefix}_{name}: {why}"
        facts.append(book.add(f"{prefix}_{name}_not_judged", reason, ref))
        reasons.append(reason)

    losses = np.array([_loss(r) for r in train], dtype=np.float64)
    if losses.size == 0:
        skip("train_loss", "no train row in the window")
    else:
        finite = losses[np.isfinite(losses)]
        facts += [book.add(f"{prefix}_train_loss_first", float(losses[0]), ref),
                  book.add(f"{prefix}_train_loss_last", float(losses[-1]), ref),
                  book.add(f"{prefix}_train_nonfinite_losses", int(losses.size - finite.size),
                           ref, "rows")]
        if finite.size:
            facts += [book.add(f"{prefix}_train_loss_min", float(np.min(finite)), ref),
                      book.add(f"{prefix}_train_loss_median", float(np.median(finite)), ref)]
        for group in sorted({g for r in train for g in r.loss_by_group}):
            values = [r.loss_by_group[group] for r in train if group in r.loss_by_group]
            facts += [book.add(f"{prefix}_loss_{group}_mean", sum(values) / len(values), ref),
                      book.add(f"{prefix}_loss_{group}_last", values[-1], ref)]
        for name in GRADS:
            norms = np.array([getattr(r, name) for r in train if getattr(r, name) is not None],
                             dtype=np.float64)
            if norms.size == 0:
                skip(name, "the log carries no value of it in the window")
                continue
            facts += [book.add(f"{prefix}_{name}_median", percentile(norms, 50.0), ref),
                      book.add(f"{prefix}_{name}_p99", percentile(norms, 99.0), ref)]
    val_losses = [_loss(r) for r in val]
    facts.append(book.add(f"{prefix}_val_rows", len(val), ref, "rows"))
    if val_losses:
        facts += [book.add(f"{prefix}_val_loss_first", val_losses[0], ref),
                  book.add(f"{prefix}_val_loss_last", val_losses[-1], ref)]
    else:
        skip("val_loss", "no val row in the window")
    in_window = _gap(sorted({r.step for r in val}))
    whole = _gap(sorted({r.step for r in job.rows if r.split == "val"}))
    if in_window is not None:
        facts.append(book.add(f"{prefix}_val_gap_median", in_window, ref, "steps"))
    elif whole is not None:
        facts.append(book.add(f"{prefix}_val_gap_median_whole_log", whole, ref, "steps"))
    else:
        skip("val_gap", "fewer than two validation steps in the log")
    last = float(losses[-1]) if losses.size else "-"
    row: Row = {"job": job.job, "window": window.label, "first_step": window.lo + 1,
                "last_step": window.hi, "rows": len(rows), "val_rows": len(val),
                "train_loss_last": last if isinstance(last, str) or math.isfinite(last)
                else str(last)}
    return ToolResult(TOOL, tuple(facts), (row,), tuple(reasons))
