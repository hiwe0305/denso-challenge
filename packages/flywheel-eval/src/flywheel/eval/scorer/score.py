"""Score one episode: the whole computation, and nothing else (DA-36 AC 5).

This is the pure step of the lane. It takes a signal table that is already in
memory and a task definition, and returns a verdict. It does not open a file,
start a simulator, call a model or read a clock, so the same trace scores the
same every time it is scored - NFR1, and the reason a `Score` can be compared
against a `Score` written last week.

The order matters and is fixed here: state the steps, name the failure from the
steps, then fold in the two things no single step answers - the balance
condition, and the signals no step owns. Those come last because either can
take away a pass the steps appeared to earn.

Before any of it, the config is checked against the task: the steps it names
have to be the task's steps, every signal the task asks for has to be watched
by some step, by the episode or by a limit, and a kind it marks as taking its
class from the failed step has to be a kind the task declares. A config that
does not line up is a config written for another task, and scoring with it
would produce a `Score` that looks like a result.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flywheel.contracts import ScorerParams, StageEvaluation, StageSpec, TaskDefinition
from flywheel.eval.config import ScorerConfig
from flywheel.eval.scorer.balance import BalanceVerdict, apply_balance, check_balance
from flywheel.eval.scorer.failure import FailureVerdict, apply_episode_signals, judge_failure
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
    trace_sha256: str
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
    _check_config_fits(task, stages, config)

    evaluation = _evaluate(trace, task, config)
    steps = score_steps(
        evaluation, stages, trace.missing_signals, step_signals=config.step_signals
    )
    failure = judge_failure(
        evaluation,
        steps,
        tuple(task.failure_kinds()),
        first_failed_step(evaluation),
        stages,
        config.class_from_failed_step,
    )
    balance = check_balance(trace.signals, config.balance)
    episode_gaps = tuple(
        signal for signal in trace.missing_signals if signal in config.episode_signals
    )
    return EpisodeScore(
        episode_id=trace.episode_id,
        task_id=task.task_id,
        scorer_version=config.scorer_version,
        config_sha256=config_sha256,
        trace_sha256=trace.trace_sha256,
        steps=steps,
        failure=apply_episode_signals(apply_balance(failure, balance), episode_gaps),
        balance=balance,
        missing_signals=tuple(trace.missing_signals),
    )


def _evaluate(trace: Trace, task: TaskDefinition, config: ScorerConfig) -> StageEvaluation:
    """Run the task's predicates, turning a predicate that blew up into a refusal.

    A task whose `evaluate()` raises has not scored the episode badly, it has
    not scored it at all, so it comes back as a scorer error rather than as a
    traceback out of a command the engineer ran.
    """
    try:
        return task.evaluate(trace.signals, ScorerParams(thresholds=dict(config.thresholds)))
    except Exception as error:  # the task is somebody else's code
        raise ScorerError(
            f"`evaluate()` của task `{task.task_id}` lỗi trên trace "
            f"`{trace.episode_id}`: {type(error).__name__}: {error}"
        ) from error


def _check_config_fits(
    task: TaskDefinition, stages: Sequence[StageSpec], config: ScorerConfig
) -> None:
    """Refuse a config whose steps, signals or kinds are not this task's."""
    names = [stage.name for stage in stages]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ScorerError(
            f"`stages()` của task khai trùng tên bước {repeated}; tín hiệu từng bước "
            "đánh theo tên nên tên phải phân biệt được"
        )
    if set(config.step_signals) != set(names):
        raise ScorerError(
            f"`step_signals` khai các bước {sorted(config.step_signals)} nhưng task có "
            f"{sorted(names)}"
        )
    required = {signal.name for signal in task.required_signals()}
    unwatched = sorted(required - config.declared_signals())
    if unwatched:
        raise ScorerError(
            f"tín hiệu {unwatched} task có đòi mà cấu hình không khai ở bước nào, ở "
            "`episode_signals` hay ở `balance`; thiếu chúng thì không bước nào thành "
            "chưa rõ được (AC 2)"
        )
    invented = sorted(
        {signal for signals in config.step_signals.values() for signal in signals} - required
    )
    if invented:
        raise ScorerError(
            f"`step_signals` khai tín hiệu {invented} mà `required_signals()` của task "
            "không có"
        )
    kinds = {spec.kind for spec in task.failure_kinds()}
    undeclared = sorted(set(config.class_from_failed_step) - kinds)
    if undeclared:
        raise ScorerError(
            f"`class_from_failed_step` khai kiểu lỗi {undeclared} mà `failure_kinds()` "
            "của task không có"
        )
