"""`trace_stats`: does the tracking threshold tell failed rollouts from succeeded ones? (task 3.1)

For each run, the rollouts of its trace files are told apart and split by their `Score`.
A file whose sha256 is the `trace_sha256` of exactly one `Score` of the run is that one
rollout (real data: one `steps.jsonl` per rollout, whatever its `TraceStep.episode_id` says,
a name local to a chunk). Any other file is split by `TraceStep.episode_id` and joined to the
scores by `episode_id`. Both groups get the same measurements, because a threshold that
the successes also cross says nothing about the failures (H2, tray.md 20.11):

- the statistic of R3 (`flywheel.eval.diagnosis.system`): the norm of (command - measured)
  per control cycle for the upper and the lower body, at the percentile `system.yaml`
  gives, against the tolerance `tau_track_*` of the same file, so this tool and the F-SYS
  check cannot disagree on what "tracked" means;
- the same statistic per channel, with the worst channel by name (an angle on the circle
  is wrapped as in R3);
- the share of cycles whose command carries a velocity (`cmd_lower` vx or vy not zero);
- the path length, the integral of the measured planar speed over `t_state`.

Never computed: the turn-around time. This is a limit of the contract, not a missing input
of a round: `TraceStep` holds the base yaw and speed but no world position and no turn
event, so any definition of it would be invented.

A value that is not finite is counted (`*_nonfinite_cycles`) and never scored: its cycle
leaves the statistic, and a group with nothing finite is not judged rather than clean.
"""

from __future__ import annotations

import math
import posixpath
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY, FloatOrNonFinite, TraceStep
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import (
    Row,
    RunScores,
    RunTrace,
    ToolResult,
    TraceFile,
    not_judged,
)
from flywheel.eval.config import R3Thresholds
from flywheel.eval.diagnosis.system.reader import PERIODIC_CHANNELS, TraceLog, Values, percentile

TOOL = "trace_stats"
GROUPS = (("succeeded", True), ("failed", False))
CHANNELS = {"upper": UPPER_BODY, "lower": LOWER_BODY}
_CHANNEL_UNIT = {"base_height": "m", "vx": "m/s", "vy": "m/s"}
_TRACKED = ("cmd_upper", "meas_upper", "cmd_lower", "meas_lower")


def _number(value: FloatOrNonFinite) -> float:
    return math.nan if isinstance(value, str) else float(value)


def _matrix(steps: Sequence[TraceStep], name: str) -> Values:
    return np.array([[_number(v) for v in getattr(s, name)] for s in steps], dtype=np.float64)


def channel_errors(steps: Sequence[TraceStep], part: str) -> Values:
    """|command - measured| per cycle (rows) and channel (columns), nan where a gap is."""
    names = CHANNELS[part]
    diff = _matrix(steps, f"cmd_{part}") - _matrix(steps, f"meas_{part}")
    for k, name in enumerate(names):
        if name in PERIODIC_CHANNELS:
            diff[:, k] = np.arctan2(np.sin(diff[:, k]), np.cos(diff[:, k]))
    return np.abs(diff)


def _gap_cycles(steps: Sequence[TraceStep]) -> int:
    """Cycles with a non-finite value in any command or measurement."""
    return sum(any(isinstance(v, str) for name in _TRACKED for v in getattr(s, name))
               for s in steps)


def _by_episode(steps: Sequence[TraceStep]) -> dict[str, list[TraceStep]]:
    out: dict[str, list[TraceStep]] = {}
    for s in sorted(steps, key=lambda s: (s.episode_id, s.step)):
        out.setdefault(s.episode_id, []).append(s)
    return out


def _source_ref(files: Sequence[TraceFile]) -> str:
    """The file the numbers come from; with several files, the directory they share."""
    if len(files) == 1:
        return files[0].ref
    return posixpath.commonpath([f.ref for f in files]) or "."


@dataclass(frozen=True)
class Rollout:
    """What the groups need of one rollout's cycles, so the cycles themselves are not kept."""

    cycles: int
    gaps: int  # cycles with a non-finite value (`_gap_cycles`)
    norms: dict[str, Values]  # part -> tracking error norm per cycle (R3)
    errors: dict[str, Values]  # part -> |command - measured| per cycle and channel
    moving: int  # `_velocity_share`
    judged: int
    path: float  # `_path_length`


def summarize(key: str, steps: Sequence[TraceStep]) -> Rollout:
    """The numbers of one rollout, its cycles in step order."""
    moving, judged = _velocity_share(steps)
    return Rollout(
        cycles=len(steps), gaps=_gap_cycles(steps),
        norms={part: TraceLog(key, key, tuple(steps), {}, 0, "").tracking_error(part)
               for part in CHANNELS},
        errors={part: channel_errors(steps, part) if steps
                else np.empty((0, len(names)), dtype=np.float64)
                for part, names in CHANNELS.items()},
        moving=moving, judged=judged, path=_path_length(steps))


def _rollouts(book: FactBook, run: RunScores, trace: RunTrace,
              facts: list[str], reasons: list[str]) -> dict[str, Rollout]:
    """Rollout key -> its numbers, over all files of the run.

    A file that is the `trace_sha256` of exactly one score is that rollout; any other file
    is split by `TraceStep.episode_id`. A file that claims a rollout an earlier file holds
    is skipped whole and named in a fact, never merged. Files are read one at a time and
    only the numbers of their rollouts are kept (real data: 1.5 GB of cycles).
    """
    by_sha: dict[str, list[str]] = {}
    for sc in run.scores:
        by_sha.setdefault(sc.trace_sha256, []).append(sc.episode_id)
    held: dict[str, tuple[str, Rollout]] = {}
    for file in trace.files:
        steps = file.read()
        owners = by_sha.get(file.sha256, [])
        if len(owners) == 1:
            found = {owners[0]: sorted(steps, key=lambda s: s.step)}
        else:
            found = _by_episode(steps)
        del steps
        clash = sorted(k for k in found if k in held)
        if clash:
            reason = (f"run {run.run}: {file.ref} claims rollout(s) {', '.join(clash)} already "
                      f"held by {', '.join(sorted({held[k][0] for k in clash}))}; file skipped")
            facts.append(book.add(f"{TOOL}_{run.run}_{file.ref}_duplicate_not_judged", reason,
                                  file.ref))
            reasons.append(reason)
            continue
        for key, cycles in found.items():
            held[key] = (file.ref, summarize(key, cycles))
    return {k: rollout for k, (_, rollout) in held.items()}


def _velocity_share(steps: Sequence[TraceStep]) -> tuple[int, int]:
    """(cycles whose command moves the base, cycles with a finite velocity command)."""
    moving = judged = 0
    for s in steps:
        vx, vy = (_number(v) for v in s.cmd_lower[4:6])
        if math.isfinite(vx) and math.isfinite(vy):
            judged += 1
            moving += vx != 0.0 or vy != 0.0
    return moving, judged


def _path_length(steps: Sequence[TraceStep]) -> float:
    """Sum of measured planar speed x dt between consecutive cycles with finite values."""
    total = 0.0
    for a, b in zip(steps, steps[1:], strict=False):
        dt = _number(b.t_state) - _number(a.t_state)
        vx, vy = (_number(v) for v in a.meas_lower[4:6])
        if math.isfinite(dt) and dt > 0 and math.isfinite(vx) and math.isfinite(vy):
            total += math.hypot(vx, vy) * dt
    return total


def _unit(part: str, channel: str) -> str:
    if part == "upper":
        return "rad"
    return _CHANNEL_UNIT.get(channel, "rad")


def _group(book: FactBook, prefix: str, ref: str, rollouts: dict[str, Rollout],
           cfg: R3Thresholds, tau_ref: str, group: str) -> tuple[list[str], dict[str, float],
                                                                 list[str]]:
    """Facts of one group; the part statistics (for the separation test); what was not judged."""
    cycles = sum(r.cycles for r in rollouts.values())
    facts = [book.add(f"{prefix}_rollouts", len(rollouts), ref, "rollouts"),
             book.add(f"{prefix}_cycles", cycles, ref, "cycles"),
             book.add(f"{prefix}_nonfinite_cycles", sum(r.gaps for r in rollouts.values()), ref,
                      "cycles")]
    stats: dict[str, float] = {}
    reasons: list[str] = []
    if not cycles:
        reason = f"{prefix}: no {group} rollout has a trace"
        facts.append(book.add(f"{prefix}_not_judged", reason, ref))
        return facts, stats, [reason]
    for part, names in CHANNELS.items():
        norms = np.concatenate([r.norms[part] for r in rollouts.values()])
        stat = percentile(norms, cfg.percentile)
        if not math.isfinite(stat):
            reason = f"{prefix}_{part}: every cycle has a non-finite command or measurement"
            facts.append(book.add(f"{prefix}_{part}_not_judged", reason, ref))
            reasons.append(reason)
            continue
        tau = cfg.tau_track_upper if part == "upper" else cfg.tau_track_lower
        stats[part] = stat
        unit = "rad" if part == "upper" else "mixed"  # the lower norm mixes rad, m and m/s
        errors = np.concatenate([r.errors[part] for r in rollouts.values()])
        by_channel = [percentile(errors[:, k], cfg.percentile) for k in range(len(names))]
        worst = max((k for k, v in enumerate(by_channel) if math.isfinite(v)),
                    key=lambda k: by_channel[k])
        facts += [book.add(f"{prefix}_track_error_{part}", stat, ref, unit),
                  book.add(f"{prefix}_exceeds_tau_{part}", stat > tau, tau_ref),
                  book.add(f"{prefix}_worst_channel_{part}", names[worst], ref),
                  book.add(f"{prefix}_worst_channel_error_{part}", by_channel[worst], ref,
                           _unit(part, names[worst]))]
    moving = sum(r.moving for r in rollouts.values())
    judged = sum(r.judged for r in rollouts.values())
    if judged:
        facts.append(book.add(f"{prefix}_velocity_command_share", moving / judged, ref))
    else:
        reason = f"{prefix}: no cycle has a finite velocity command"
        facts.append(book.add(f"{prefix}_velocity_command_not_judged", reason, ref))
        reasons.append(reason)
    lengths = [r.path for r in rollouts.values()]
    facts.append(book.add(f"{prefix}_path_length_mean", sum(lengths) / len(lengths), ref, "m"))
    return facts, stats, reasons


def trace_stats(book: FactBook, runs: Sequence[RunScores], traces: dict[str, RunTrace],
                cfg: R3Thresholds, tau_ref: str) -> ToolResult:
    """Facts and a table of the tracking of failed and succeeded rollouts, run by run."""
    facts: list[str] = [book.add("track_percentile", cfg.percentile, tau_ref, "%"),
                        book.add("tau_track_upper", cfg.tau_track_upper, tau_ref, "rad"),
                        book.add("tau_track_lower", cfg.tau_track_lower, tau_ref, "mixed")]
    rows: list[Row] = []
    reasons: list[str] = []
    for run in runs:
        trace = traces.get(run.run)
        if trace is None:
            reason = f"run {run.run}: no trace entry in the pack"
            facts.append(book.add(f"{TOOL}_{run.run}_not_judged", reason, "pack.json"))
            reasons.append(reason)
            continue
        outcome = {s.episode_id: s.success for s in run.scores}
        episodes = _rollouts(book, run, trace, facts, reasons)
        ref = _source_ref(trace.files)
        undecided = [e for e in episodes if outcome.get(e) is None]
        facts += [book.add(f"{run.run}_trace_undecided_rollouts", len(undecided), ref,
                           "rollouts"),
                  book.add(f"{run.run}_scored_without_trace",
                           sum(1 for e in outcome if e not in episodes), run.ref, "rollouts")]
        stats: dict[str, dict[str, float]] = {}
        for group, flag in GROUPS:
            chosen = {e: ep for e, ep in episodes.items() if outcome.get(e) is flag}
            new, stats[group], why = _group(book, f"{run.run}_{group}", ref, chosen, cfg,
                                            tau_ref, group)
            facts += new
            reasons += why
        for part in CHANNELS:
            failed, ok = stats["failed"].get(part), stats["succeeded"].get(part)
            tau = cfg.tau_track_upper if part == "upper" else cfg.tau_track_lower
            if failed is None or ok is None:
                continue
            facts.append(book.add(f"{run.run}_tau_separates_{part}", failed > tau >= ok,
                                  tau_ref))
            rows.append({"run": run.run, "part": part, "failed": failed, "succeeded": ok,
                         "tau": tau, "separates": failed > tau >= ok})
    return ToolResult(TOOL, tuple(facts), tuple(rows), tuple(reasons))


def no_tolerance(book: FactBook, reason: str) -> ToolResult:
    return not_judged(book, TOOL, reason, "-", "tolerance")
