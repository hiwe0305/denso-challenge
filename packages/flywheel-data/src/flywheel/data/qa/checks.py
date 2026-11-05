"""Tier 4 (QA) of the robot sources: one QAReport per episode (DA-03 AC 3).

The checks are the rows of spec 4.4, each split into what one number can say, plus
the source checks of design 6.3. Every check carries the D-code of design 10 its
failure belongs to, and every threshold and every action on failure comes from
`configs/data/qa.yaml` (`flywheel.data.config.load_qa_config`), never from here.

    timestamp_monotonic     D2  steps where timestamp does not increase
    timestamp_step          D2  largest |dt * fps - 1|, in control periods
    frame_index_contiguous  D2  rows whose frame_index is not 0, 1, ..., T-1
    image_state_sync        D2  largest |video frames - rows| over the cameras
    finite_values           D1  NaN or Inf values in timestamp, states, action
    joint_limits            D3  largest step past a joint limit of the action layout (rad)
    action_jump.<group>     D3  largest |a[t+1] - a[t]| of the group, against a clean demo
    lineage                 D6  lineage fields the source needs that the episode lacks
    replay_kinematic        D7  issues of a kinematic ReplayReport (DA-17)
    replay_dynamic          D7  issues of a dynamic ReplayReport
    split_seed              D5  1 when the condition seed lies outside the train range
  by source (`source_checks` of qa.yaml):
    video_rows_match        D2  psi-data: largest |video frames - rows|, exactly 0
    task_instruction        D6  psi-data: 1 when the episode has no task sentence
    task_success            D6  0 when a replay of the episode succeeded, 1 when it failed
    replay_success          D8  generated: the same, for the rollout replayed in sim

Design 10 has no code for missing lineage; D6 (wrong labels) is the nearest, since
lineage is what the episode's metadata says about itself.

The decision is the worst action of the failed checks: reject over quarantine over
flag over pass. Each failed check gives a reason with its code, value and
threshold. A replay check without a ReplayReport does what its `when_missing`
says: `skip` leaves it out of the report, `flag` fails it. An episode of fewer
than `min_frames` frames is rejected with that reason and no other check runs;
nothing raises on data. Checks that need finite numbers are left out when
`finite_values` has already rejected the episode.

`dataset_checks` covers D4, which belongs to a dataset, not to an episode: the
stats files a LeRobot dataset ships against stats recomputed from its own
parquet. psi-data e78fb93's `stats.json` is off for `states` (DA-27 measured
3.63e-4 on the mean), so this is a finding on real data, reported, not fixed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from flywheel.contracts.artifacts import Episode, QACheck, QAReport, ReplayReport
from flywheel.data.config import QAConfig, QADecision
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.ingest.sources import EpisodeLineage
from numpy.typing import NDArray

SEVERITY: dict[str, int] = {"pass": 0, "flag": 1, "quarantine": 2, "reject": 3}
STATS = ("mean", "std", "min", "max")
DESCRIBE = {
    "timestamp_monotonic": "steps where timestamp does not increase",
    "timestamp_step": "largest |dt*fps - 1| in control periods",
    "frame_index_contiguous": "rows whose frame_index is not 0..T-1",
    "image_state_sync": "largest |video frames - rows|",
    "finite_values": "NaN or Inf values",
    "joint_limits": "largest step past a joint limit (rad)",
    "action_jump": "largest |a[t+1] - a[t]|",
    "lineage": "missing lineage fields",
    "replay_kinematic": "kinematic replay issues",
    "replay_dynamic": "dynamic replay issues",
    "split_seed": "condition seed outside the train range",
    "video_rows_match": "largest |video frames - rows|",
    "task_instruction": "episode without a task sentence",
    "task_success": "replay of the episode failed",
    "replay_success": "replayed rollout failed",
    "stats_json": "largest |shipped - recomputed| in meta/stats.json",
    "episodes_stats": "largest |shipped - recomputed| in meta/episodes_stats.jsonl",
}


@dataclass(frozen=True)
class Outcome:
    """One check as run: the contract's QACheck and why it failed, if it did."""

    check: QACheck
    action: QADecision
    reason: str | None


def run_qa(
    frames: EpisodeFrames,
    episode: Episode,
    replay: ReplayReport | Sequence[ReplayReport] | None,
    cfg: QAConfig,
    *,
    fps: float,
    lineage: EpisodeLineage | None = None,
) -> QAReport:
    """The QAReport of one episode. `fps` is the dataset's (meta/info.json); `lineage`
    is what ingest read from the episode's flywheel block (SourceRecord.lineage)."""
    reports = [replay] if isinstance(replay, ReplayReport) else list(replay or [])
    for report in reports:
        if report.episode_id != episode.episode_id:
            raise ValueError(
                f"ReplayReport of {report.episode_id} given for episode {episode.episode_id}"
            )
    rows = len(frames.timestamp)
    if rows < cfg.min_frames:
        check = QACheck(name="min_frames", value=rows, threshold=cfg.min_frames, passed=False)
        reason = f"min_frames: episode has {rows} frame(s), QA needs at least {cfg.min_frames}"
        return _report(episode, cfg, [Outcome(check, "reject", reason)])
    source = episode.meta.source_detail or episode.source_kind
    if source not in cfg.source_checks:
        raise ValueError(f"qa.yaml has no source_checks for {source!r}")
    outcomes = _common(frames, episode, reports, cfg, fps, lineage, source)
    for name in cfg.source_checks[source]:
        outcomes += _source_check(name, frames, reports, cfg)
    return _report(episode, cfg, outcomes)


def episode_action_jumps(
    frames: EpisodeFrames, groups: Sequence[str], wrapped: Sequence[str] = ()
) -> dict[str, float]:
    """Largest |a[t+1] - a[t]| of each action group in one episode (0 under 2 frames).

    A group in `wrapped` is an angle (G1's target heading): its step is taken the
    short way round the circle, so a heading crossing +-pi is no jump.
    """
    steps = np.diff(frames.action.astype(np.float64), axis=0)
    angles = [dim for dim, group in enumerate(groups) if group in wrapped]
    steps[:, angles] = (steps[:, angles] + np.pi) % (2 * np.pi) - np.pi
    steps = np.abs(steps)
    largest = steps.max(axis=0) if len(steps) else np.zeros(len(groups))
    jumps: dict[str, float] = {}
    for dim, group in enumerate(groups):
        jumps[group] = max(jumps.get(group, 0.0), float(largest[dim]))
    return jumps


def calibrate_action_jump(
    episodes: Sequence[EpisodeFrames],
    groups: Sequence[str],
    quantile: float,
    wrapped: Sequence[str] = (),
) -> dict[str, float]:
    """The `action_jump.thresholds` of qa.yaml: per group, the `quantile` over clean demos
    of each episode's largest jump (spec 4.4: p99.9 of the teleop demos)."""
    if not episodes:
        raise ValueError("calibration needs at least one episode")
    per_episode = [episode_action_jumps(f, groups, wrapped) for f in episodes]
    return {
        group: float(np.quantile([jumps[group] for jumps in per_episode], quantile))
        for group in dict.fromkeys(groups)
    }


@dataclass(frozen=True)
class DatasetFinding:
    """A D4 check of a whole dataset, with the feature and statistic that is worst."""

    check: QACheck
    code: str
    detail: str


def dataset_checks(
    root: Path, episodes: Sequence[EpisodeFrames], cfg: QAConfig
) -> list[DatasetFinding]:
    """The stats files the dataset at root ships, against stats of its own frames (D4).

    One finding per file and feature: `stats_json.states` and `stats_json.action`
    over all frames, `episodes_stats.action` and `episodes_stats.timestamp` over
    the episodes (the worst one named). Mean, std, min and max only, since
    quantiles depend on the method; each is computed in the dtype the reader gives
    (float32 states and action), as SIMPLE's `stats_block` computes them, so float32
    rounding is not mistaken for a finding. A file the dataset does not ship, or a
    feature it leaves out, is not checked.
    """
    findings: list[DatasetFinding] = []
    if not episodes:
        return findings
    stats_path = root / "meta" / "stats.json"
    if stats_path.is_file():
        shipped = json.loads(stats_path.read_text())
        for feature in ("states", "action"):
            if isinstance(shipped.get(feature), dict):
                values = np.concatenate([getattr(f, feature) for f in episodes])
                findings.append(
                    _stats_finding("stats_json", feature, {"": (shipped[feature], values)}, cfg)
                )
    rows_path = root / "meta" / "episodes_stats.jsonl"
    if rows_path.is_file():
        rows = {
            int(r["episode_index"]): r["stats"]
            for r in (json.loads(line) for line in rows_path.read_text().splitlines()
                      if line.strip())
        }
        for feature in ("action", "timestamp"):
            pairs = {
                f"episode {f.episode_index} ": (rows[f.episode_index][feature], getattr(f, feature))
                for f in episodes
                if isinstance(rows.get(f.episode_index, {}).get(feature), dict)
            }
            if pairs:
                findings.append(_stats_finding("episodes_stats", feature, pairs, cfg))
    return findings


def _common(
    frames: EpisodeFrames,
    episode: Episode,
    reports: list[ReplayReport],
    cfg: QAConfig,
    fps: float,
    lineage: EpisodeLineage | None,
    source: str,
) -> list[Outcome]:
    rows = len(frames.timestamp)
    arrays = (frames.timestamp, frames.states, frames.action)
    bad = int(sum(int((~np.isfinite(a)).sum()) for a in arrays))
    outcomes = [_judge("finite_values", bad, cfg)]
    if np.isfinite(frames.timestamp).all():
        steps = np.diff(frames.timestamp)
        outcomes.append(_judge("timestamp_monotonic", int((steps <= 0).sum()), cfg))
        outcomes.append(_judge("timestamp_step", float(np.abs(steps * fps - 1.0).max()), cfg))
    off = int((frames.frame_index != np.arange(rows)).sum())
    outcomes.append(_judge("frame_index_contiguous", off, cfg))
    if frames.video_frames:
        gap = max(abs(count - rows) for count in frames.video_frames.values())
        outcomes.append(_judge("image_state_sync", gap, cfg))
    if np.isfinite(frames.action).all():
        outcomes.append(_judge("joint_limits", _past_limits(frames.action, cfg), cfg))
        jumps = episode_action_jumps(frames, cfg.groups, cfg.action_jump_wrapped)
        for group, value in jumps.items():
            outcomes.append(
                _judge("action_jump", value, cfg, f"action_jump.{group}", cfg.action_jump[group])
            )
    missing = _missing_lineage(episode, lineage, cfg.lineage_required[source])
    outcomes.append(_judge("lineage", len(missing), cfg, detail=", ".join(missing)))
    for mode in ("kinematic", "dynamic"):
        name = f"replay_{mode}"
        of_mode = [r for r in reports if r.mode == mode]
        if of_mode:
            issues = sum(len(r.issues) for r in of_mode)
            codes = sorted({i.code for r in of_mode for i in r.issues})
            outcomes.append(_judge(name, issues, cfg, detail=", ".join(codes)))
        else:
            outcomes += _missing_replay(name, cfg)
    if lineage is not None and lineage.seed is not None:
        start, stop = cfg.train_seeds
        outside = not start <= lineage.seed < stop
        detail = f"seed {lineage.seed}, train [{start}, {stop})"
        outcomes.append(_judge("split_seed", int(outside), cfg, detail=detail))
    return outcomes


def _source_check(
    name: str, frames: EpisodeFrames, reports: list[ReplayReport], cfg: QAConfig
) -> list[Outcome]:
    rows = len(frames.timestamp)
    if name == "video_rows_match":
        counts = frames.video_frames.values()
        gap = max((abs(c - rows) for c in counts), default=rows)
        return [_judge(name, gap, cfg, detail=f"{dict(frames.video_frames)} for {rows} rows")]
    if name == "task_instruction":
        return [_judge(name, int(not frames.task.strip()), cfg)]
    # task_success, replay_success: the outcome of a replay that says whether it succeeded.
    known = [r.sim_success for r in reports if r.sim_success is not None]
    if not known:
        return _missing_replay(name, cfg)
    return [_judge(name, int(not all(known)), cfg)]


def _missing_replay(name: str, cfg: QAConfig) -> list[Outcome]:
    rule = cfg.checks[name]
    if rule.when_missing == "skip":
        return []
    check = QACheck(name=name, value=1, threshold=rule.threshold, passed=False)
    return [Outcome(check, "flag", f"{name} ({rule.code}): no ReplayReport for the episode")]


def _judge(
    rule_name: str,
    value: float,
    cfg: QAConfig,
    name: str | None = None,
    threshold: float | None = None,
    detail: str = "",
) -> Outcome:
    rule = cfg.checks[rule_name]
    limit = rule.threshold if threshold is None else threshold
    check = QACheck(name=name or rule_name, value=value, threshold=limit, passed=value <= limit)
    if check.passed:
        return Outcome(check, "pass", None)
    reason = f"{check.name} ({rule.code}): {DESCRIBE[rule_name]} = {value:g} > {limit:g}"
    return Outcome(check, rule.on_fail, f"{reason} ({detail})" if detail else reason)


def _past_limits(action: NDArray[np.float32], cfg: QAConfig) -> float:
    worst = 0.0
    for dim, limit in enumerate(cfg.limits):
        if limit is None:
            continue
        low, high = limit
        values = action[:, dim].astype(np.float64)
        worst = max(worst, float(np.max(low - values)), float(np.max(values - high)))
    return worst


def _missing_lineage(
    episode: Episode, lineage: EpisodeLineage | None, required: Sequence[str]
) -> list[str]:
    have = {
        "source_id": episode.source_id,
        "license": episode.license.strip() or None,
        "seed": None if lineage is None else lineage.seed,
        "generator_version": None if lineage is None else lineage.generator_version,
        "parent_id": episode.parent_id,
    }
    return [name for name in required if have[name] is None]


def _report(episode: Episode, cfg: QAConfig, outcomes: list[Outcome]) -> QAReport:
    actions: list[QADecision] = [o.action for o in outcomes]
    decision: QADecision = max(actions, key=SEVERITY.__getitem__, default="pass")
    key = hashlib.sha256(f"{episode.episode_id}|{cfg.threshold_version}".encode()).hexdigest()
    return QAReport(
        report_id=f"qa_{key[:16]}",
        episode_id=episode.episode_id,
        threshold_version=cfg.threshold_version,
        decision=decision,
        reasons=[o.reason for o in outcomes if o.reason is not None],
        checks=[o.check for o in outcomes],
    )


def _stats_finding(
    name: str,
    feature: str,
    pairs: dict[str, tuple[dict[str, Any], NDArray[Any]]],
    cfg: QAConfig,
) -> DatasetFinding:
    """The largest |shipped - recomputed| over `pairs` (where -> shipped block, values)."""
    worst, at = 0.0, "every value equal"
    for where, (block, values) in pairs.items():
        data = np.asarray(values).reshape(len(values), -1)
        mine = {"mean": data.mean(0), "std": data.std(0), "min": data.min(0), "max": data.max(0)}
        for stat in STATS:
            if stat not in block:
                continue
            theirs = np.asarray(block[stat], dtype=np.float64).reshape(-1)
            if theirs.shape != mine[stat].shape:
                worst, at = float("inf"), f"{where}{feature}.{stat} shape {theirs.shape}"
                continue
            gap = np.abs(theirs - mine[stat].astype(np.float64))
            if float(gap.max()) > worst:
                worst, at = float(gap.max()), f"{where}{feature}.{stat}[{int(gap.argmax())}]"
    rule = cfg.checks[name]
    value = worst if np.isfinite(worst) else 1e300  # QACheck holds finite numbers only
    passed = value <= rule.threshold
    check = QACheck(name=f"{name}.{feature}", value=value, threshold=rule.threshold,
                    passed=passed)
    return DatasetFinding(check, rule.code, f"{DESCRIBE[name]}: {worst:g} at {at}")
