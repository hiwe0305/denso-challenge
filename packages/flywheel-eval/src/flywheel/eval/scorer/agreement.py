"""Check the scorer against SIMPLE's own success flag (DA-37 AC 1, 2, 6).

The scorer is the second opinion, not the metric: the main number on every
holdout is SIMPLE's `check_success` (03 ADR-14). What the scorer adds is *where*
an episode failed, and that is only worth trusting if, on the whole task, it
says what SIMPLE says. G1 asks for at least 95 % agreement on a set of episodes
that holds both successes and failures (04 section 4.2).

This module is the pure half. It takes `Score` records and the `RolloutResult`
of the same episodes, already in memory, and returns a report. It reads no
file and no clock, so the same episodes under the same scorer always give the
same report, byte for byte, and the same hash (AC 6).

Pairing. A `Score` names its episode by `episode_id`; a `RolloutResult` names
its trace by `trace_ref.trace_id` (`<job_id>-<uuid>`, unique across jobs). The
two meet when the episode was scored with `--episode-id <trace_id>`. The
`episode_N` name SIMPLE prints restarts at every eval run, so two jobs would
both have an `episode_3` and pairing on it would be a guess; a `Score` or a
rollout that finds no partner is listed in the report, not dropped.

Which episodes count:

* A rollout whose `infra_status` is not `ok` says nothing about the policy, and
  a rollout that is `ok` but whose `sim_success` is `None` gave no flag to
  check against. Both are listed under `excluded`, with the reason, and kept
  out of the rate.
* Every other paired episode counts. A scorer that answered "chưa rõ" (`None`)
  did not agree with SIMPLE: it is a mismatch of its own kind, because a
  scorer that hedges on every episode would otherwise never disagree.

One report is about one scorer: one `task_id`, one `scorer_version`, one
`config_sha256`. A set that mixes them is refused, since a rate over two
scorers belongs to neither.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from flywheel.contracts import RolloutResult
from flywheel.contracts.entities import Score
from flywheel.eval.scorer.status import ScorerError
from pydantic import BaseModel, ConfigDict, Field

#: The bar of G1 (04 section 4.2): the scorer's whole-task verdict matches
#: SIMPLE's flag on at least this share of the counted episodes.
AGREEMENT_BAR = 0.95

MismatchKind = Literal["scorer_fail_sim_pass", "scorer_pass_sim_fail", "scorer_unknown"]


class Mismatch(BaseModel):
    """One episode where the scorer did not say what SIMPLE said, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    trace_sha256: str
    job_id: str
    sim_success: bool
    scorer_success: bool | None
    kind: MismatchKind
    reason: str
    first_failed_step: int | None = None
    failure_kind: str | None = None
    step_status: list[str] = Field(default_factory=list)


class Excluded(BaseModel):
    """A paired episode kept out of the rate, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    infra_status: str
    reason: str


class AgreementReport(BaseModel):
    """The calibration report of FR18: the rate, and every episode behind it.

    No time and no path in it: two runs over the same episodes write the same
    bytes, so the report's hash is a statement about the episodes and the
    scorer, not about when somebody looked (AC 6).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    scorer_version: str
    config_sha256: str
    # The release the evaluated checkpoint was trained on; the caller names it,
    # because neither a `Score` nor a `RolloutResult` carries it.
    release_id: str
    bar: float = AGREEMENT_BAR
    counted: int
    agreed: int
    # None where nothing could be counted: a rate over zero episodes is not
    # 100 %, and not 0 % either.
    agreement: float | None
    passed: bool | None
    sim_successes: int
    sim_failures: int
    mismatches: list[Mismatch]
    excluded: list[Excluded]
    unpaired_scores: list[str]
    unpaired_rollouts: list[str]

    def canonical(self) -> bytes:
        """The bytes the report is stored and hashed as."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


@dataclass(frozen=True)
class _Pair:
    score: Score
    rollout: RolloutResult


def compare(
    scores: Iterable[Score], rollouts: Iterable[RolloutResult], release_id: str
) -> AgreementReport:
    """Pair every `Score` with its rollout and count where they agree (AC 1, 2)."""
    if not release_id:
        raise ScorerError("thiếu release của checkpoint đã chấm; báo cáo phải nói nó (AC 2)")
    by_episode = _scores_by_episode(scores)
    by_trace = _rollouts_by_trace(rollouts)
    identity = _identity(by_episode.values())

    pairs = [
        _Pair(by_episode[key], by_trace[key]) for key in sorted(by_episode.keys() & by_trace.keys())
    ]
    excluded: list[Excluded] = []
    counted: list[_Pair] = []
    for pair in pairs:
        reason = _excluded(pair)
        if reason is None:
            counted.append(pair)
        else:
            excluded.append(reason)
    mismatches = [item for pair in counted if (item := _mismatch(pair)) is not None]
    agreed = len(counted) - len(mismatches)
    rate = agreed / len(counted) if counted else None
    return AgreementReport(
        task_id=identity[0],
        scorer_version=identity[1],
        config_sha256=identity[2],
        release_id=release_id,
        counted=len(counted),
        agreed=agreed,
        agreement=rate,
        passed=None if rate is None else rate >= AGREEMENT_BAR,
        sim_successes=sum(1 for pair in counted if pair.rollout.sim_success is True),
        sim_failures=sum(1 for pair in counted if pair.rollout.sim_success is False),
        mismatches=mismatches,
        excluded=excluded,
        unpaired_scores=sorted(by_episode.keys() - by_trace.keys()),
        unpaired_rollouts=sorted(by_trace.keys() - by_episode.keys()),
    )


def _scores_by_episode(scores: Iterable[Score]) -> dict[str, Score]:
    """One `Score` per episode; the same record twice is one, two different ones refuse.

    `Score` is content-addressed, so a re-score that changed nothing has the
    same id and is the same record appended twice. A different id for the same
    episode is a second opinion, and picking one would be choosing the answer.
    """
    found: dict[str, Score] = {}
    for score in scores:
        held = found.get(score.episode_id)
        if held is not None and held.id != score.id:
            raise ScorerError(
                f"episode `{score.episode_id}` có hai `Score` khác nhau ({held.id}, {score.id}); "
                "lọc về một lần chấm trước khi đối chiếu"
            )
        found[score.episode_id] = score
    if not found:
        raise ScorerError("không có `Score` nào để đối chiếu")
    return found


def _rollouts_by_trace(rollouts: Iterable[RolloutResult]) -> dict[str, RolloutResult]:
    found: dict[str, RolloutResult] = {}
    for rollout in rollouts:
        if rollout.trace_ref is None:
            # Without a trace there is nothing the scorer could have read, so
            # the rollout cannot be paired; it is not a mismatch either.
            continue
        trace_id = rollout.trace_ref.trace_id
        if trace_id in found and found[trace_id] != rollout:
            raise ScorerError(
                f"trace `{trace_id}` có hai `RolloutResult` khác nhau; không biết cờ nào là của nó"
            )
        found[trace_id] = rollout
    return found


def _identity(scores: Iterable[Score]) -> tuple[str, str, str]:
    seen = sorted({(s.task_id, s.scorer_version, s.config_sha256) for s in scores})
    if len(seen) != 1:
        raise ScorerError(
            f"các `Score` thuộc {len(seen)} bộ (task, scorer_version, config_sha256) khác "
            f"nhau: {seen}; một báo cáo chỉ nói về một scorer"
        )
    return seen[0]


def _excluded(pair: _Pair) -> Excluded | None:
    rollout = pair.rollout
    if rollout.infra_status != "ok":
        reason = f"lỗi hạ tầng `{rollout.infra_status}`: episode không nói gì về policy"
    elif rollout.sim_success is None:
        reason = "SIMPLE không trả cờ `check_success` cho episode này"
    else:
        return None
    return Excluded(
        episode_id=pair.score.episode_id, infra_status=rollout.infra_status, reason=reason
    )


def _mismatch(pair: _Pair) -> Mismatch | None:
    score, sim = pair.score, pair.rollout.sim_success
    assert sim is not None  # excluded before this point
    if score.success is sim:
        return None
    names = _step_names(score)
    if score.success is None:
        kind: MismatchKind = "scorer_unknown"
        reason = _unknown_reason(score, names, sim)
    elif score.success is False:
        kind = "scorer_fail_sim_pass"
        reason = _fail_reason(score, names)
    else:
        kind = "scorer_pass_sim_fail"
        reason = (
            f"scorer báo đạt cả {len(score.step_status)} bước nhưng SIMPLE báo trượt: vị từ "
            "của scorer lỏng hơn `check_success`, hoặc SIMPLE xét một điều kiện scorer không có"
        )
    return Mismatch(
        episode_id=score.episode_id,
        trace_sha256=score.trace_sha256,
        job_id=pair.rollout.job_id,
        sim_success=sim,
        scorer_success=score.success,
        kind=kind,
        reason=reason,
        first_failed_step=score.first_failed_step,
        failure_kind=score.failure_kind,
        step_status=list(score.step_status),
    )


def _step_names(score: Score) -> Sequence[str]:
    names = score.meta.get("step_names") if isinstance(score.meta, dict) else None
    if isinstance(names, list) and len(names) == len(score.step_status):
        return [str(name) for name in names]
    return [str(index) for index in range(len(score.step_status))]


def _fail_reason(score: Score, names: Sequence[str]) -> str:
    parts: list[str] = []
    if score.first_failed_step is not None:
        step = score.first_failed_step
        name = names[step] if step < len(names) else str(step)
        kind = f" ({score.failure_kind})" if score.failure_kind else ""
        parts.append(f"scorer báo trượt ở bước {step} `{name}`{kind}")
    if score.balance_violated:
        parts.append("điều kiện thăng bằng vỡ")
    if not parts:
        parts.append("scorer báo trượt mà không chỉ ra bước nào")
    return "; ".join(parts) + " nhưng SIMPLE báo đạt"


def _unknown_reason(score: Score, names: Sequence[str], sim: bool) -> str:
    reasons = score.unknown_reason or [None] * len(score.step_status)
    unknown = [
        f"`{names[index]}` ({reasons[index] or 'không rõ lý do'})"
        for index, status in enumerate(score.step_status)
        if status == "unknown"
    ]
    where = ", ".join(unknown) if unknown else "toàn task"
    flag = "đạt" if sim else "trượt"
    return f"scorer chưa rõ ở {where}; SIMPLE báo {flag}"
