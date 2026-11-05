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

Before any of it, the task and the config are checked against each other:
every stage has to declare its signals, those signals have to be ones the task
asks for, every signal the task asks for has to be watched by some step, by
the episode or by a limit. A config that
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
from flywheel.eval.scorer.status import ScorerError, StepScore
from flywheel.eval.scorer.steps import first_failed_step, score_steps, step_signals


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
    null_signals: tuple[str, ...] = ()
    # One entry per step where the task reported times, `None` where it did
    # not: the scorer never makes a time up (03 section 4.3).
    step_enter_s: tuple[float | None, ...] | None = None
    step_exit_s: tuple[float | None, ...] | None = None

    @property
    def success(self) -> bool | None:
        """Scored success, which is not the main metric: that is `sim_success`.

        `None` where the scorer could not tell, which is a third answer and not
        a failure (03 ADR-14, FR39).
        """
        return self.failure.success

    @property
    def unknown_steps(self) -> tuple[StepScore, ...]:
        return tuple(step for step in self.steps if step.status == "unknown")


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
        evaluation,
        stages,
        trace.missing_signals,
        trace.null_signals,
        empty=trace.num_steps == 0,
    )
    failure = judge_failure(
        evaluation,
        steps,
        tuple(task.failure_kinds()),
        first_failed_step(evaluation),
        stages,
    )
    balance = check_balance(trace.signals, config.balance)
    episode_gaps = tuple(
        signal
        for signal in (*trace.missing_signals, *trace.null_signals)
        if signal in config.episode_signals
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
        null_signals=tuple(trace.null_signals),
        step_enter_s=_times(evaluation.step_enter_s, steps, "enter_s"),
        step_exit_s=_times(evaluation.step_exit_s, steps, "exit_s"),
    )


def _times(
    reported: Sequence[float | None] | None, steps: Sequence[StepScore], which: str
) -> tuple[float | None, ...] | None:
    """The times the task reported, blanked for steps that were not judged."""
    if reported is None:
        return None
    return tuple(getattr(step, which) for step in steps)


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
    """Refuse a task without step signals, or a config that is not this task's."""
    names = [stage.name for stage in stages]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ScorerError(
            f"`stages()` của task khai trùng tên bước {repeated}; bản ghi gọi bước "
            "theo tên nên tên phải phân biệt được"
        )
    by_step = {signal for stage in stages for signal in step_signals(stage)}
    required = {signal.name for signal in task.required_signals()}
    unwatched = sorted(required - by_step - config.declared_signals())
    if unwatched:
        raise ScorerError(
            f"tín hiệu {unwatched} task có đòi mà không bước nào khai trong "
            "`StageSpec.signals`, cấu hình cũng không khai ở `episode_signals` hay "
            "`balance`; thiếu chúng thì không bước nào thành chưa rõ được (AC 2)"
        )
    invented = sorted(by_step - required)
    if invented:
        raise ScorerError(
            f"`StageSpec.signals` khai tín hiệu {invented} mà `required_signals()` của "
            "task không có"
        )
