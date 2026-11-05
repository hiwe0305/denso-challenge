"""The whole-episode balance condition (DA-36 task 4, AC 1, 3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from flywheel.contracts import StageEvaluation, TaskDefinition
from flywheel.eval.config import BalanceLimits, ConfigError, load_scorer_config
from flywheel.eval.scorer.balance import BALANCE_KIND, apply_balance, check_balance
from flywheel.eval.scorer.failure import UNKNOWN_KIND, judge_failure
from flywheel.eval.scorer.reader import read_signals
from flywheel.eval.scorer.steps import first_failed_step, score_steps

MakeRows = Callable[..., list[dict[str, object]]]
CONFIG = Path("configs") / "eval" / "scorer" / "two-table.yaml"


@pytest.fixture
def limits() -> BalanceLimits:
    return load_scorer_config(CONFIG)[0].balance


def test_a_clean_episode_holds_its_limits(make_rows: MakeRows, limits: BalanceLimits) -> None:
    verdict = check_balance(read_signals(make_rows()), limits)

    # The control has to be checked twice over: no violation *and* nothing
    # unknown, because an episode nobody could check also violates nothing.
    assert verdict.violated is False
    assert verdict.unknown is False


@pytest.mark.parametrize(
    ("signal", "value"),
    [("torso_height", 0.4), ("torso_tilt", 0.9), ("torso_tilt", -0.9)],
)
def test_a_body_outside_its_limits_is_a_violation(
    make_rows: MakeRows, limits: BalanceLimits, sig: object, signal: str, value: float
) -> None:
    rows = make_rows(**{signal: sig.switch(11, 0.05 if "tilt" in signal else 0.95, value)})  # type: ignore[attr-defined]

    verdict = check_balance(read_signals(rows), limits)

    assert verdict.violated is True
    assert verdict.row == 11
    assert verdict.signal == signal
    assert verdict.value == value


def test_a_violation_at_the_last_step_still_counts(
    make_rows: MakeRows, limits: BalanceLimits, sig: object
) -> None:
    # Falling after the object is down passes all six steps, which is why the
    # condition cannot live in the per-step predicates (AC 1).
    rows = make_rows(torso_height=sig.switch(19, 0.95, 0.3))  # type: ignore[attr-defined]

    assert check_balance(read_signals(rows), limits).row == 19


def test_missing_balance_signals_are_unknown_not_upright(
    make_rows: MakeRows, limits: BalanceLimits
) -> None:
    rows = [
        {key: value for key, value in row.items() if key != "torso_tilt"} for row in make_rows()
    ]

    verdict = check_balance(read_signals(rows), limits)

    assert verdict.violated is False
    assert verdict.unknown_reason == "thiếu tín hiệu: torso_tilt"


def test_a_gap_in_a_balance_signal_is_unknown(make_rows: MakeRows, limits: BalanceLimits) -> None:
    rows = make_rows()
    del rows[7]["torso_height"]

    verdict = check_balance(read_signals(rows), limits)

    assert verdict.unknown_reason == "tín hiệu có khoảng trống: torso_height"


def test_a_nan_in_a_balance_signal_is_unknown_not_upright(
    make_rows: MakeRows, limits: BalanceLimits
) -> None:
    # `nan < min_height` and `abs(nan) > max_tilt` are both false, so a NaN that
    # survived the read would clear both limits and report an episode nobody
    # measured as one that stayed upright (FR21).
    rows = [{**row, "torso_height": float("nan")} for row in make_rows()]

    verdict = check_balance(read_signals(rows), limits)

    assert verdict.violated is False
    assert verdict.unknown_reason == "tín hiệu có khoảng trống: torso_height"


def test_an_empty_trace_is_unknown(limits: BalanceLimits) -> None:
    assert check_balance(read_signals([]), limits).unknown is True


def verdict_for(evaluation: StageEvaluation, task: TaskDefinition):  # noqa: ANN201
    stages = tuple(task.stages())
    steps = score_steps(evaluation, stages)
    return judge_failure(
        evaluation, steps, tuple(task.failure_kinds()), first_failed_step(evaluation), stages
    )


def test_a_violation_renames_a_passing_episode(
    make_rows: MakeRows, task: TaskDefinition, limits: BalanceLimits, sig: object
) -> None:
    passed = verdict_for(StageEvaluation(stage_success=(True,) * 6), task)
    rows = make_rows(torso_height=sig.switch(15, 0.95, 0.2))  # type: ignore[attr-defined]

    folded = apply_balance(passed, check_balance(read_signals(rows), limits))

    assert folded.failure_kind == BALANCE_KIND
    assert folded.failure_class == "balance"
    assert folded.success is False


def test_a_violation_leaves_a_named_failure_alone(
    make_rows: MakeRows, task: TaskDefinition, limits: BalanceLimits, sig: object
) -> None:
    # The grasp slipped at step 2 and the robot then fell. It is still a slip:
    # renaming it would move the episode out of the carry cluster DA-13 and the
    # evidence cards are built from. `balance_violated` keeps the fall (PO
    # decision of 3/11/2026).
    evaluation = StageEvaluation(
        stage_success=(True, True, False, False, False, False),
        first_failed_stage=2,
        failure_kind="L-SLIP",
        failure_class="carry",
    )
    rows = make_rows(torso_tilt=sig.const(0.8))  # type: ignore[attr-defined]
    balance = check_balance(read_signals(rows), limits)

    folded = apply_balance(verdict_for(evaluation, task), balance)

    assert folded.failure_kind == "L-SLIP"
    assert folded.first_failed_step == 2
    assert balance.violated is True


def test_a_violation_on_an_unscorable_episode_stays_unknown(
    make_rows: MakeRows, task: TaskDefinition, limits: BalanceLimits, sig: object
) -> None:
    # `L-BALANCE` says the fall is what went wrong, which is not known while a
    # step could not be judged at all.
    evaluation = StageEvaluation(stage_success=(None,) * 6)
    rows = make_rows(torso_tilt=sig.const(0.8))  # type: ignore[attr-defined]

    folded = apply_balance(verdict_for(evaluation, task), check_balance(read_signals(rows), limits))

    assert folded.failure_kind == UNKNOWN_KIND


def test_an_uncheckable_condition_costs_a_clean_episode_its_pass(
    make_rows: MakeRows, task: TaskDefinition, limits: BalanceLimits
) -> None:
    passed = verdict_for(StageEvaluation(stage_success=(True,) * 6), task)
    rows = [
        {key: value for key, value in row.items() if key != "torso_height"} for row in make_rows()
    ]

    folded = apply_balance(passed, check_balance(read_signals(rows), limits))

    # Six steps passed with nobody watching the torso is not a success.
    assert folded.failure_kind == UNKNOWN_KIND
    assert folded.success is None
    assert "thăng bằng" in (folded.reason or "")


def test_an_uncheckable_condition_leaves_a_named_failure_alone(
    make_rows: MakeRows, task: TaskDefinition, limits: BalanceLimits
) -> None:
    evaluation = StageEvaluation(
        stage_success=(True, False, False, False, False, False),
        first_failed_stage=1,
        failure_kind="L-GRASP",
        failure_class="grasp",
    )
    rows = [
        {key: value for key, value in row.items() if key != "torso_height"} for row in make_rows()
    ]

    folded = apply_balance(verdict_for(evaluation, task), check_balance(read_signals(rows), limits))

    assert folded.failure_kind == "L-GRASP"


def test_the_shipped_config_is_the_one_the_tests_score_against() -> None:
    config, digest = load_scorer_config(CONFIG)

    # A number changed in the file has to show up as a changed verdict
    # somewhere, and these tests are where it does.
    assert config.task_id == "two-table"
    assert set(config.thresholds) == {"r_reach", "h_grasp", "h_place", "T_stable"}
    assert config.balance.height_signal == "torso_height"
    assert config.episode_signals == ("collision",)
    assert len(digest) == 64
    assert load_scorer_config(CONFIG)[1] == digest


BALANCE_SECTION = "balance: {min_height: 0.6, max_tilt: 0.3, height_signal: h, tilt_signal: t}\n"
STEP_SECTION = "episode_signals: []\n"
HEAD = "task_id: t\nscorer_version: '1'\nthresholds: {a: 1}\n"


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        (HEAD + STEP_SECTION, "balance"),
        (
            "task_id: t\nscorer_version: '1'\nthresholds: {}\n" + BALANCE_SECTION + STEP_SECTION,
            "không được rỗng",
        ),
        (
            HEAD + "balance: {min_height: 0.6, max_tilt: 0.3, height_signal: h}\n" + STEP_SECTION,
            "tilt_signal",
        ),
        (
            "task_id: ''\nscorer_version: '1'\nthresholds: {a: 1}\n"
            + BALANCE_SECTION
            + STEP_SECTION,
            "task_id",
        ),
        (HEAD + "extra: 2\n" + BALANCE_SECTION + STEP_SECTION, "unknown key"),
        # The sections of the review fixes are not optional either: a config
        # without them cannot keep a missing signal from scoring as a pass, so
        # it is refused rather than defaulted.
        (HEAD + BALANCE_SECTION, "episode_signals"),
        (HEAD + BALANCE_SECTION + "episode_signals: a\n", "must be a list of names"),
        (HEAD + BALANCE_SECTION + "episode_signals: [a, a]\n", "repeats"),
        # Step signals and the failed-step class rule live on the task since
        # #101: a config still carrying either old key is a config written for
        # the old scorer, and is refused rather than half-read.
        (HEAD + BALANCE_SECTION + "step_signals: {s0: [a]}\n" + STEP_SECTION, "unknown key"),
        (HEAD + BALANCE_SECTION + "class_from_failed_step: []\n" + STEP_SECTION, "unknown key"),
    ],
)
def test_a_config_that_cannot_be_trusted_raises(tmp_path: Path, body: str, fragment: str) -> None:
    path = tmp_path / "scorer.yaml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ConfigError, match=fragment):
        load_scorer_config(path)
