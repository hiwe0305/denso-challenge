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
rollout that finds no partner is listed in the report, not dropped. A set where
**no** score finds a partner is refused instead of reported: it is the mark of
scores keyed on the wrong id, and a report of "0 episodes" would read as a run
that had nothing to say (review of #158 at `a062d47`, point 2).

Choosing the scorer. `<store>/scorer/score.jsonl` is append-only, so an episode
scored again under a new `scorer_version` or config has two `Score` records in
it. The caller names the scorer to check (`ScorerKey`); scores of any other
scorer are left out before pairing, so the file the help points to can be read
as it is (same review, point 1). Without a key, a file holding two scorers is
refused with the scorers it holds listed.

Which episodes count:

* A rollout whose `infra_status` is not `ok` says nothing about the policy, and
  a rollout that is `ok` but whose `sim_success` is `None` gave no flag to
  check against. Both are listed under `excluded`, with the reason, and kept
  out of the rate.
* A rollout with no `trace_ref` (the simulator died before writing a trace,
  the commonest infra failure) has nothing to pair on. It is listed under
  `untraced_rollouts` by `job_id`, never dropped (review of #158, point 2).
* Every other paired episode counts. A scorer that answered "chưa rõ" (`None`)
  did not agree with SIMPLE: it is a mismatch of its own kind, because a
  scorer that hedges on every episode would otherwise never disagree.

A rate is not a pass. G1 asks for the bar on **100 episodes holding both
successes and failures** (AC 1, 04 section 4.2): a set that is smaller, or
where SIMPLE never passed or never failed, can show a rate but not a verdict,
so `passed` is `None` there and `unjudged` says why (review of #158, point 1).

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
#: The size of the set G1 is judged on (AC 1): fewer counted episodes give a
#: rate, never a pass.
MIN_EPISODES = 100

MismatchKind = Literal["scorer_fail_sim_pass", "scorer_pass_sim_fail", "scorer_unknown"]
#: Why a rate was not turned into a pass or a fail of G1.
UnjudgedReason = Literal["no_episodes", "not_enough_episodes", "no_sim_success", "no_sim_failure"]


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


class Untraced(BaseModel):
    """A rollout with no trace: nothing to pair a `Score` with, listed by its job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    infra_status: str
    sim_success: bool | None
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
    # The G1 verdict, only on a set G1 can be judged on; None otherwise, with
    # the reasons in `unjudged`.
    passed: bool | None
    unjudged: list[UnjudgedReason]
    min_episodes: int = MIN_EPISODES
    sim_successes: int
    sim_failures: int
    mismatches: list[Mismatch]
    excluded: list[Excluded]
    unpaired_scores: list[str]
    unpaired_rollouts: list[str]
    untraced_rollouts: list[Untraced]

    def canonical(self) -> bytes:
        """The bytes the report is stored and hashed as."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


@dataclass(frozen=True)
class ScorerKey:
    """Which scorer's `Score` records to check; a field left `None` matches any."""

    task_id: str | None = None
    scorer_version: str | None = None
    config_sha256: str | None = None

    def matches(self, score: Score) -> bool:
        return (
            self.task_id in (None, score.task_id)
            and self.scorer_version in (None, score.scorer_version)
            and self.config_sha256 in (None, score.config_sha256)
        )


@dataclass(frozen=True)
class _Pair:
    score: Score
    rollout: RolloutResult


def compare(
    scores: Iterable[Score],
    rollouts: Iterable[RolloutResult],
    release_id: str,
    scorer: ScorerKey | None = None,
) -> AgreementReport:
    """Pair every `Score` of one scorer with its rollout and count where they agree (AC 1, 2)."""
    if not release_id:
        raise ScorerError("thiếu release của checkpoint đã chấm; báo cáo phải nói nó (AC 2)")
    chosen = _select(list(scores), scorer or ScorerKey())
    # The scorer first: a file holding two scorers is the common way to have
    # two scores of one episode, and naming the scorers says how to fix it.
    identity = _identity(chosen)
    by_episode = _scores_by_episode(chosen)
    rollouts = list(rollouts)
    by_trace = _rollouts_by_trace(rollouts)

    keys = sorted(by_episode.keys() & by_trace.keys())
    if not keys:
        raise ScorerError(_no_pair_message(by_episode.keys(), by_trace.keys()))
    pairs = [_Pair(by_episode[key], by_trace[key]) for key in keys]
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
    successes = sum(1 for pair in counted if pair.rollout.sim_success is True)
    failures = sum(1 for pair in counted if pair.rollout.sim_success is False)
    unjudged = _unjudged(len(counted), successes, failures)
    return AgreementReport(
        task_id=identity[0],
        scorer_version=identity[1],
        config_sha256=identity[2],
        release_id=release_id,
        counted=len(counted),
        agreed=agreed,
        agreement=rate,
        passed=None if rate is None or unjudged else rate >= AGREEMENT_BAR,
        unjudged=unjudged,
        sim_successes=successes,
        sim_failures=failures,
        mismatches=mismatches,
        excluded=excluded,
        unpaired_scores=sorted(by_episode.keys() - by_trace.keys()),
        unpaired_rollouts=sorted(by_trace.keys() - by_episode.keys()),
        untraced_rollouts=_untraced(rollouts),
    )


def _unjudged(counted: int, successes: int, failures: int) -> list[UnjudgedReason]:
    """Why this set cannot carry a G1 verdict; empty when it can (AC 1)."""
    if counted == 0:
        return ["no_episodes"]
    reasons: list[UnjudgedReason] = []
    if counted < MIN_EPISODES:
        reasons.append("not_enough_episodes")
    if successes == 0:
        reasons.append("no_sim_success")
    if failures == 0:
        reasons.append("no_sim_failure")
    return reasons


def _untraced(rollouts: Iterable[RolloutResult]) -> list[Untraced]:
    items = [
        Untraced(
            job_id=rollout.job_id,
            infra_status=rollout.infra_status,
            sim_success=rollout.sim_success,
            reason="rollout không có trace (`trace_ref` rỗng): không có gì để ghép với `Score`",
        )
        for rollout in rollouts
        if rollout.trace_ref is None
    ]
    return sorted(items, key=lambda item: (item.job_id, item.infra_status, str(item.sim_success)))


#: How many ids an error message shows from each side before "…".
_SHOWN_IDS = 3


def _select(scores: list[Score], key: ScorerKey) -> list[Score]:
    """The scores of the scorer `key` names; refuse when none, naming what there is."""
    if not scores:
        raise ScorerError("không có `Score` nào để đối chiếu")
    chosen = [score for score in scores if key.matches(score)]
    if not chosen:
        raise ScorerError(
            f"không `Score` nào thuộc scorer đã chọn ({_key_text(key)}); "
            f"file có: {_identities(scores)}"
        )
    return chosen


def _key_text(key: ScorerKey) -> str:
    fields = {
        "task_id": key.task_id,
        "scorer_version": key.scorer_version,
        "config_sha256": key.config_sha256,
    }
    return ", ".join(f"{name}={value}" for name, value in fields.items() if value is not None)


def _identities(scores: Iterable[Score]) -> list[tuple[str, str, str]]:
    return sorted({(s.task_id, s.scorer_version, s.config_sha256) for s in scores})


def _no_pair_message(score_ids: Iterable[str], trace_ids: Iterable[str]) -> str:
    episodes, traces = sorted(score_ids), sorted(trace_ids)
    if not traces:
        return "không rollout nào có trace (`trace_ref`) để ghép với `Score`"
    return (
        "không `Score` nào ghép được với rollout nào: `Score.episode_id` phải là "
        "`trace_ref.trace_id` của rollout (`fw eval score --episode-id <trace_id>`), "
        "không phải `episode_N` của SIMPLE; "
        f"Score có {_sample(episodes)}, rollout có {_sample(traces)}"
    )


def _sample(ids: Sequence[str]) -> str:
    shown = ", ".join(f"`{item}`" for item in ids[:_SHOWN_IDS])
    more = f", … ({len(ids)} id)" if len(ids) > _SHOWN_IDS else ""
    return shown + more


def _scores_by_episode(scores: Iterable[Score]) -> dict[str, Score]:
    """One `Score` per episode; the same record twice is one, two different ones refuse.

    `Score` is content-addressed, so a re-score that changed nothing has the
    same id and is the same record appended twice. A different id for the same
    episode under the same scorer is a second opinion, and picking one would be
    choosing the answer.
    """
    found: dict[str, Score] = {}
    for score in scores:
        held = found.get(score.episode_id)
        if held is not None and held.id != score.id:
            raise ScorerError(
                f"episode `{score.episode_id}` có hai `Score` khác nhau ({held.id}, {score.id}) "
                "dưới cùng một scorer; lọc về một lần chấm trước khi đối chiếu"
            )
        found[score.episode_id] = score
    return found


def _rollouts_by_trace(rollouts: Iterable[RolloutResult]) -> dict[str, RolloutResult]:
    found: dict[str, RolloutResult] = {}
    for rollout in rollouts:
        if rollout.trace_ref is None:
            # Nothing to pair on; `_untraced` lists it in the report.
            continue
        trace_id = rollout.trace_ref.trace_id
        if trace_id in found and found[trace_id] != rollout:
            raise ScorerError(
                f"trace `{trace_id}` có hai `RolloutResult` khác nhau; không biết cờ nào là của nó"
            )
        found[trace_id] = rollout
    return found


def _identity(scores: Iterable[Score]) -> tuple[str, str, str]:
    seen = _identities(scores)
    if len(seen) != 1:
        raise ScorerError(
            f"các `Score` thuộc {len(seen)} bộ (task, scorer_version, config_sha256) khác "
            f"nhau: {seen}; một báo cáo chỉ nói về một scorer, chọn một bằng "
            "`--task-id`, `--scorer-version`, `--config-sha256`"
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
