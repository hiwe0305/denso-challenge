"""Score one episode: the whole computation, and nothing else (DA-36 AC 5).

This is the pure step of the lane. It takes a signal table that is already in
memory and a task definition, and returns a verdict. It does not open a file,
start a simulator, call a model or read a clock, so the same trace scores the
same every time it is scored - NFR1, and the reason a `Score` can be compared
against a `Score` written last week.

The order matters and is fixed here: state the steps, name the failure from the
steps, then fold in the condition that ran the whole episode. Balance comes
last because it can overrule a verdict the steps reached, and because an
unchecked balance condition can take away a pass the steps appeared to earn.
"""

from __future__ import annotations

from dataclasses import dataclass

from flywheel.contracts import ScorerParams, TaskDefinition
from flywheel.eval.config import ScorerConfig
from flywheel.eval.scorer.balance import BalanceVerdict, apply_balance, check_balance
from flywheel.eval.scorer.failure import FailureVerdict, judge_failure
from flywheel.eval.scorer.reader import Trace
from flywheel.eval.scorer.status import ScorerError, StepScore, StepStatus
from flywheel.eval.scorer.steps import first_failed_step, score_steps


@dataclass(frozen=True)
class EpisodeScore:
    """Everything the scorer concluded about one episode."""

    episode_id: str
    task_id: str
    scorer_version: str
    config_sha256: str
    steps: tuple[StepScore, ...]
    failure: FailureVerdict
    balance: BalanceVerdict
    missing_signals: tuple[str, ...]

    @property
    def success(self) -> bool | None:
        """Scored success, which is not the main metric: that is `sim_success`.

        `None` where the scorer could not tell, which is a third answer and not
        a failure (03 ADR-14, FR39).
        """
        return self.failure.success

    @property
    def unknown_steps(self) -> tuple[StepScore, ...]:
        return tuple(step for step in self.steps if step.status is StepStatus.UNKNOWN)


def score_episode(
    trace: Trace, task: TaskDefinition, config: ScorerConfig, config_sha256: str
) -> EpisodeScore:
    """Score one recorded episode against one task definition."""
    if config.task_id != task.task_id:
        raise ScorerError(
            f"cấu hình viết cho task `{config.task_id}` nhưng đang chấm task "
            f"`{task.task_id}`; ngưỡng của task khác không dùng được"
        )
    stages = tuple(task.stages())
    if not stages:
        raise ScorerError("`stages()` của task không khai bước nào")

    evaluation = task.evaluate(trace.signals, ScorerParams(thresholds=dict(config.thresholds)))
    steps = score_steps(evaluation, stages, trace.missing_signals)
    failure = judge_failure(
        evaluation, steps, tuple(task.failure_kinds()), first_failed_step(evaluation)
    )
    balance = check_balance(trace.signals, config.balance)
    return EpisodeScore(
        episode_id=trace.episode_id,
        task_id=task.task_id,
        scorer_version=config.scorer_version,
        config_sha256=config_sha256,
        steps=steps,
        failure=apply_balance(failure, balance),
        balance=balance,
        missing_signals=tuple(trace.missing_signals),
    )
