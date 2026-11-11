"""The scorer checked against SIMPLE's flag (DA-37 task 1, AC 1, 2).

Every `Score` here is built by hand, so each test says in its own lines which
episode the scorer passed, failed or could not tell, and what SIMPLE said.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts import RolloutResult
from flywheel.contracts.entities import Score
from flywheel.contracts.v0 import StepStatus
from flywheel.eval.api import check_scorer_agreement, store_scorer_agreement
from flywheel.eval.cli import app
from flywheel.eval.scorer.agreement import (
    AGREEMENT_BAR,
    MIN_EPISODES,
    AgreementReport,
    ScorerKey,
    compare,
)
from flywheel.eval.scorer.calibration import AGREEMENT_RECORDS, CalibrationInputError
from flywheel.eval.scorer.status import ScorerError
from flywheel.store.blobs import get_blob
from flywheel.store.paths import StorePaths
from typer.testing import CliRunner

STEPS = ["approach", "grasp", "walk", "arrive", "place", "release"]
RELEASE = "rel_demo_1"


def score(
    episode: str,
    success: bool | None,
    *,
    failed: int | None = None,
    unknown: int | None = None,
    balance: bool = False,
    version: str = "0.2.0",
    config: str = "c" * 64,
) -> Score:
    """A `Score` the way `build_record` writes one, for a six-step task."""
    status: list[StepStatus] = ["pass"] * len(STEPS)
    reasons: list[Any] = [None] * len(STEPS)
    kind = None
    if failed is not None:
        rest: list[StepStatus] = ["not_attempted"] * (len(STEPS) - failed - 1)
        status = status[:failed] + ["fail"] + rest
        kind = "L-GRASP"
    if unknown is not None:
        status[unknown] = "unknown"
        reasons[unknown] = "missing_signal"
    return Score(
        episode_id=episode,
        task_id="two-table",
        config_sha256=config,
        trace_sha256=hashlib.sha256(episode.encode()).hexdigest(),
        scorer_version=version,
        success=success,
        step_status=status,
        unknown_reason=reasons,
        first_failed_step=failed,
        failure_kind=kind,
        balance_violated=balance,
        meta={"step_names": STEPS, "missing_signals": []},
    )


def rollout(trace_id: str, sim: bool | None, infra: str = "ok") -> RolloutResult:
    return RolloutResult.model_validate(rollout_json(trace_id, sim, infra))


def rollout_json(trace_id: str, sim: bool | None, infra: str = "ok") -> dict[str, Any]:
    return {
        "job_id": trace_id.split("-")[0],
        "trace_ref": {"trace_id": trace_id, "uri": f"traces/{trace_id}", "sha256": None},
        "sim_success": sim,
        "infra_status": infra,
        "usage": {"wall_seconds": 10.0, "gpu_seconds": 0.0},
        "camera_params_hash": None,
        "adapter_info": {
            "name": "simple",
            "version": "0.1.0",
            "image_digest": None,
            "nondeterminism": [],
        },
        "timing": "sync",
    }


def mixed_set(size: int, wrong: int) -> tuple[list[Score], list[RolloutResult]]:
    """`size` episodes, half SIMPLE passes and half it fails; the scorer gets
    the first `wrong` of them backwards."""
    scores, rollouts = [], []
    for i in range(size):
        sim = i % 2 == 0
        said = sim if i >= wrong else not sim
        scores.append(score(f"j1-{i:03d}", said, failed=None if said else 1))
        rollouts.append(rollout(f"j1-{i:03d}", sim))
    return scores, rollouts


def test_twenty_agreeing_episodes_give_a_rate_but_no_g1_verdict() -> None:
    # AC 1 judges G1 on 100 episodes; a perfect rate on 20 is not a pass
    # (review of #158, point 1).
    report = compare(*mixed_set(20, 0), RELEASE)

    assert (report.counted, report.agreed, report.agreement) == (20, 20, 1.0)
    assert report.passed is None
    assert report.unjudged == ["not_enough_episodes"]
    assert (report.sim_successes, report.sim_failures) == (10, 10)
    assert report.mismatches == []


def test_a_hundred_episodes_without_a_sim_failure_are_not_judged() -> None:
    scores = [score(f"j1-{i:03d}", True) for i in range(100)]
    rollouts = [rollout(f"j1-{i:03d}", True) for i in range(100)]

    report = compare(scores, rollouts, RELEASE)

    assert report.agreement == 1.0
    assert report.passed is None
    assert report.unjudged == ["no_sim_failure"]


def test_a_hundred_episodes_without_a_sim_success_are_not_judged() -> None:
    scores = [score(f"j1-{i:03d}", False, failed=0) for i in range(100)]
    rollouts = [rollout(f"j1-{i:03d}", False) for i in range(100)]

    report = compare(scores, rollouts, RELEASE)

    assert report.passed is None
    assert report.unjudged == ["no_sim_success"]


def test_a_small_one_sided_set_names_every_reason() -> None:
    report = compare([score("j1-a", True)], [rollout("j1-a", True)], RELEASE)

    assert report.unjudged == ["not_enough_episodes", "no_sim_failure"]


def test_every_mismatch_is_listed_with_its_reason() -> None:
    scores = [
        score("j1-a", False, failed=1),  # scorer fails, SIMPLE passes
        score("j1-b", True),  # scorer passes, SIMPLE fails
        score("j1-c", None, unknown=3),  # scorer cannot tell
        score("j1-d", True),
    ]
    rollouts = [rollout("j1-a", True), rollout("j1-b", False), rollout("j1-c", True)]
    rollouts.append(rollout("j1-d", True))

    report = compare(scores, rollouts, RELEASE)

    by_episode = {m.episode_id: m for m in report.mismatches}
    assert sorted(by_episode) == ["j1-a", "j1-b", "j1-c"]
    assert by_episode["j1-a"].kind == "scorer_fail_sim_pass"
    assert "bước 1 `grasp` (L-GRASP)" in by_episode["j1-a"].reason
    assert by_episode["j1-b"].kind == "scorer_pass_sim_fail"
    assert by_episode["j1-c"].kind == "scorer_unknown"
    assert "`arrive` (missing_signal)" in by_episode["j1-c"].reason
    assert (report.agreed, report.counted) == (1, 4)


def test_an_unknown_scorer_verdict_is_never_agreement() -> None:
    # A scorer that hedged on every episode would otherwise never disagree.
    report = compare([score("j1-a", None, unknown=0)], [rollout("j1-a", False)], RELEASE)

    assert report.agreed == 0
    assert report.mismatches[0].kind == "scorer_unknown"


def test_a_balance_break_is_named_in_the_reason() -> None:
    report = compare([score("j1-a", False, balance=True)], [rollout("j1-a", True)], RELEASE)

    assert "điều kiện thăng bằng vỡ" in report.mismatches[0].reason


def test_infra_failures_and_missing_flags_are_kept_out_of_the_rate() -> None:
    scores = [score("j1-a", True), score("j1-b", False, failed=0), score("j1-c", True)]
    rollouts = [
        rollout("j1-a", True),
        rollout("j1-b", None, infra="timeout"),
        rollout("j1-c", None),
    ]

    report = compare(scores, rollouts, RELEASE)

    assert (report.counted, report.agreed) == (1, 1)
    assert [(item.episode_id, item.infra_status) for item in report.excluded] == [
        ("j1-b", "timeout"),
        ("j1-c", "ok"),
    ]
    assert "hạ tầng" in report.excluded[0].reason
    assert "check_success" in report.excluded[1].reason


def test_unpaired_scores_and_rollouts_are_listed_not_dropped() -> None:
    report = compare(
        [score("j1-a", True), score("episode_3", True)],
        [rollout("j1-a", True), rollout("j2-x", False)],
        RELEASE,
    )

    assert report.counted == 1
    assert report.unpaired_scores == ["episode_3"]
    assert report.unpaired_rollouts == ["j2-x"]


def test_nothing_countable_is_no_rate_rather_than_zero() -> None:
    report = compare([score("j1-a", True)], [rollout("j1-a", None, infra="timeout")], RELEASE)

    assert report.agreement is None
    assert report.passed is None
    assert report.unjudged == ["no_episodes"]


def test_a_rollout_without_a_trace_is_listed_by_its_job() -> None:
    # The simulator died before writing a trace: the commonest infra failure,
    # and FR18 lists every episode (review of #158, point 2).
    untraced = rollout("j9-zzz", None, infra="simulator_error").model_copy(
        update={"trace_ref": None}
    )

    report = compare([score("j1-a", True)], [rollout("j1-a", True), untraced], RELEASE)

    assert report.counted == 1
    assert report.unpaired_rollouts == []
    (item,) = report.untraced_rollouts
    assert (item.job_id, item.infra_status, item.sim_success) == ("j9", "simulator_error", None)
    assert "trace_ref" in item.reason


def test_the_bar_is_95_percent_on_a_hundred_mixed_episodes() -> None:
    at_bar = compare(*mixed_set(100, 5), RELEASE)
    below = compare(*mixed_set(100, 6), RELEASE)

    assert (AGREEMENT_BAR, MIN_EPISODES) == (0.95, 100)
    assert at_bar.agreement == pytest.approx(0.95)
    assert at_bar.unjudged == []
    assert at_bar.passed is True
    assert below.agreement == pytest.approx(0.94)
    assert below.passed is False


def test_a_set_from_two_scorers_is_refused() -> None:
    with pytest.raises(ScorerError, match="một scorer"):
        compare(
            [score("j1-a", True), score("j1-b", True, version="0.3.0")],
            [rollout("j1-a", True), rollout("j1-b", True)],
            RELEASE,
        )


def test_two_different_scores_of_one_episode_are_refused() -> None:
    with pytest.raises(ScorerError, match="hai `Score` khác nhau"):
        compare(
            [score("j1-a", True), score("j1-a", False, failed=0)],
            [rollout("j1-a", True)],
            RELEASE,
        )


def test_scores_keyed_on_simple_episode_names_are_refused() -> None:
    # SIMPLE's `episode_N` is what DA-38's trace writes as `episode_id`, so it
    # is the easy default; pairing nothing must not pass for a report of 0
    # episodes (review of #158 at a062d47, point 2).
    scores = [score(f"episode_{i}", True) for i in range(5)]
    rollouts = [rollout(f"j1-{i:03d}", True) for i in range(5)]

    with pytest.raises(ScorerError, match="ghép được") as error:
        compare(scores, rollouts, RELEASE)

    message = str(error.value)
    assert "--episode-id <trace_id>" in message
    assert "`episode_0`" in message and "`j1-000`" in message
    assert "(5 id)" in message


def test_rollouts_without_any_trace_are_refused() -> None:
    untraced = rollout("j9-zzz", None, infra="simulator_error").model_copy(
        update={"trace_ref": None}
    )

    with pytest.raises(ScorerError, match="không rollout nào có trace"):
        compare([score("j1-a", True)], [untraced], RELEASE)


def test_a_rescored_store_is_checked_one_scorer_at_a_time() -> None:
    # `score.jsonl` is append-only: an episode scored again under a new
    # scorer has two records (review of #158 at a062d47, point 1).
    scores = [score("j1-a", True), score("j1-a", False, failed=1, version="0.3.0")]
    rollouts = [rollout("j1-a", True)]

    with pytest.raises(ScorerError, match="--scorer-version"):
        compare(scores, rollouts, RELEASE)
    old = compare(scores, rollouts, RELEASE, ScorerKey(scorer_version="0.2.0"))
    new = compare(scores, rollouts, RELEASE, ScorerKey(scorer_version="0.3.0"))

    assert (old.scorer_version, old.agreed) == ("0.2.0", 1)
    assert (new.scorer_version, new.agreed) == ("0.3.0", 0)
    assert new.mismatches[0].kind == "scorer_fail_sim_pass"


def test_the_scorer_can_be_chosen_by_its_config() -> None:
    scores = [score("j1-a", True), score("j1-a", False, failed=0, config="d" * 64)]

    report = compare(scores, [rollout("j1-a", True)], RELEASE, ScorerKey(config_sha256="d" * 64))

    assert report.config_sha256 == "d" * 64
    assert report.agreed == 0


def test_a_scorer_choice_that_matches_nothing_names_what_the_file_holds() -> None:
    with pytest.raises(ScorerError, match="0.2.0") as error:
        compare(
            [score("j1-a", True)],
            [rollout("j1-a", True)],
            RELEASE,
            ScorerKey(task_id="tray", scorer_version="9.9.9"),
        )

    assert "task_id=tray, scorer_version=9.9.9" in str(error.value)


def test_the_same_score_appended_twice_counts_once() -> None:
    report = compare([score("j1-a", True), score("j1-a", True)], [rollout("j1-a", True)], RELEASE)

    assert report.counted == 1


def test_a_report_without_a_release_is_refused() -> None:
    with pytest.raises(ScorerError, match="release"):
        compare([score("j1-a", True)], [rollout("j1-a", True)], "")


def test_the_report_names_the_scorer_config_and_release() -> None:
    report = compare([score("j1-a", True)], [rollout("j1-a", True)], RELEASE)

    assert (report.task_id, report.scorer_version) == ("two-table", "0.2.0")
    assert report.config_sha256 == "c" * 64
    assert report.release_id == RELEASE
    assert len(report.sha256) == 64


# ---------------------------------------------------------------------------
# files: reading the two inputs, storing the report (AC 2)
# ---------------------------------------------------------------------------


def write_inputs(tmp_path: Path, scores: list[Score], rollouts: dict[str, dict[str, Any]]) -> None:
    scores_file = tmp_path / "store" / "scorer" / "score.jsonl"
    scores_file.parent.mkdir(parents=True)
    scores_file.write_text("".join(s.model_dump_json() + "\n" for s in scores), encoding="utf-8")
    for trace_id, payload in rollouts.items():
        folder = tmp_path / "eval" / trace_id
        folder.mkdir(parents=True)
        (folder / "rollout_result.json").write_text(json.dumps(payload), encoding="utf-8")


def test_the_check_reads_stored_scores_and_rollout_files(tmp_path: Path) -> None:
    write_inputs(
        tmp_path,
        [score("j1-a", True), score("j1-b", False, failed=4)],
        {"j1-a": rollout_json("j1-a", True), "j1-b": rollout_json("j1-b", True)},
    )

    report = check_scorer_agreement(
        tmp_path / "store" / "scorer" / "score.jsonl", tmp_path / "eval", RELEASE
    )

    assert (report.counted, report.agreed) == (2, 1)
    assert report.mismatches[0].episode_id == "j1-b"
    assert report.mismatches[0].job_id == "j1"


def test_a_rollout_file_that_breaks_the_contract_stops_the_check(tmp_path: Path) -> None:
    broken = rollout_json("j1-a", True)
    del broken["infra_status"]
    write_inputs(tmp_path, [score("j1-a", True)], {"j1-a": broken})

    with pytest.raises(CalibrationInputError, match="RolloutResult"):
        check_scorer_agreement(
            tmp_path / "store" / "scorer" / "score.jsonl", tmp_path / "eval", RELEASE
        )


def test_the_report_is_stored_as_a_blob_and_listed(tmp_path: Path) -> None:
    report = compare([score("j1-a", True)], [rollout("j1-a", True)], RELEASE)
    store = tmp_path / "store"

    digest, index = store_scorer_agreement(report, store)

    assert digest == report.sha256
    stored = AgreementReport.model_validate_json(get_blob(digest, StorePaths(store)))
    assert stored == report
    (line,) = [json.loads(row) for row in index.read_text(encoding="utf-8").splitlines()]
    assert index == store / AGREEMENT_RECORDS
    assert line["report_sha256"] == digest
    assert (line["release_id"], line["passed"]) == (RELEASE, None)
    assert line["unjudged"] == ["not_enough_episodes", "no_sim_failure"]


def test_storing_again_appends_a_line_and_rewrites_nothing(tmp_path: Path) -> None:
    report = compare([score("j1-a", True)], [rollout("j1-a", True)], RELEASE)
    store = tmp_path / "store"

    first, index = store_scorer_agreement(report, store)
    before = index.read_text(encoding="utf-8")
    second, _ = store_scorer_agreement(report, store)

    assert first == second
    after = index.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(after.splitlines()) == 2


# ---------------------------------------------------------------------------
# the command
# ---------------------------------------------------------------------------


def test_the_command_prints_the_rate_and_every_mismatch(tmp_path: Path) -> None:
    write_inputs(
        tmp_path,
        [score("j1-a", True), score("j1-b", False, failed=1)],
        {"j1-a": rollout_json("j1-a", True), "j1-b": rollout_json("j1-b", True)},
    )

    result = CliRunner().invoke(
        app,
        [
            "agree",
            "--scores",
            str(tmp_path / "store" / "scorer" / "score.jsonl"),
            "--rollouts",
            str(tmp_path / "eval"),
            "--release",
            RELEASE,
            "--store",
            str(tmp_path / "store"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "tỉ lệ trùng: 50.0% (ngưỡng 95%): chưa kết luận G1" in result.output
    assert "not_enough_episodes, no_sim_failure" in result.output
    assert "lệch j1-b [scorer_fail_sim_pass]" in result.output
    assert "report_sha256: " in result.output
    assert (tmp_path / "store" / AGREEMENT_RECORDS).is_file()


def test_the_command_exits_two_on_a_mixed_set(tmp_path: Path) -> None:
    write_inputs(
        tmp_path,
        [score("j1-a", True), score("j1-b", True, config="d" * 64)],
        {"j1-a": rollout_json("j1-a", True), "j1-b": rollout_json("j1-b", True)},
    )

    result = CliRunner().invoke(
        app,
        [
            "agree",
            "--scores",
            str(tmp_path / "store" / "scorer" / "score.jsonl"),
            "--rollouts",
            str(tmp_path / "eval"),
            "--release",
            RELEASE,
            "--store",
            str(tmp_path / "store"),
        ],
    )

    assert result.exit_code == 2
    assert "không đối chiếu được" in result.output
    assert not (tmp_path / "store" / AGREEMENT_RECORDS).exists()


def agree_args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "agree",
        "--scores",
        str(tmp_path / "store" / "scorer" / "score.jsonl"),
        "--rollouts",
        str(tmp_path / "eval"),
        "--release",
        RELEASE,
        "--store",
        str(tmp_path / "store"),
        *extra,
    ]


def test_the_command_exits_two_and_stores_nothing_when_no_episode_pairs(tmp_path: Path) -> None:
    write_inputs(
        tmp_path,
        [score("episode_0", True), score("episode_1", False, failed=1)],
        {"j1-a": rollout_json("j1-a", True), "j1-b": rollout_json("j1-b", False)},
    )

    result = CliRunner().invoke(app, agree_args(tmp_path))

    assert result.exit_code == 2
    assert "không `Score` nào ghép được" in result.output
    assert not (tmp_path / "store" / AGREEMENT_RECORDS).exists()


def test_the_command_reads_a_rescored_store_by_scorer_version(tmp_path: Path) -> None:
    write_inputs(
        tmp_path,
        [score("j1-a", True), score("j1-a", False, failed=1, version="0.3.0")],
        {"j1-a": rollout_json("j1-a", True)},
    )

    mixed = CliRunner().invoke(app, agree_args(tmp_path))
    chosen = CliRunner().invoke(app, agree_args(tmp_path, "--scorer-version", "0.3.0"))

    assert mixed.exit_code == 2
    assert "--scorer-version" in mixed.output
    assert chosen.exit_code == 0, chosen.output
    assert "task: two-table 0.3.0" in chosen.output
    assert "lệch j1-a [scorer_fail_sim_pass]" in chosen.output
