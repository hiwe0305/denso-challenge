"""What `read_series` does with a real `metrics.jsonl` (DA-08 task 1, AC 1, 2).

The detector tests state a loss curve and judge it. This file owns the
questions only a file raises - a resumed job logging a step twice, a loss
written as the string `"NaN"`, a signal logged at a slower rate than the loss,
and a log written under the wrong action layout - so that no detector has to
ask them again.

The examples of `flywheel.testkit` are read as they ship: a field renamed in
`flywheel.contracts` has to break here, which is the whole point of the reader
being the one module that names a contract type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.diagnosis.train.reader import (
    LayoutView,
    ReaderError,
    build_series,
    read_action_layout,
    read_probe_p3,
    read_probe_p4,
    read_series,
)

FIXTURES = (
    Path(__file__).resolve().parents[5]
    / "flywheel-testkit"
    / "src"
    / "flywheel"
    / "testkit"
    / "fixtures"
)
TRAINING = FIXTURES / "training"
ARTIFACTS = FIXTURES / "artifacts"


def record(**overrides: Any) -> TrainingMetric:
    """One valid `TrainingMetric`, with only the fields a test cares about named."""
    base: dict[str, Any] = {
        "run_plan_id": "rp",
        "job_id": "job",
        "checkpoint_id": "ckpt",
        "release_id": "rel",
        "attempt": 0,
        "step": 0,
        "epoch": 0,
        "split": "train",
        "loss": 1.0,
        "lr": 1e-3,
        "vlm_frozen": True,
        "wall_time_s": 1.0,
    }
    return TrainingMetric.model_validate(base | overrides)


class TestShippedExamples:
    """The reader runs on the files of `flywheel.testkit` without being adapted."""

    def test_clean_log_splits_train_from_val(self) -> None:
        series = read_series(TRAINING / "clean.jsonl")

        assert series.step.size > 0
        assert series.val_step.size > 0
        assert np.all(np.isfinite(series.loss_train))
        assert np.all(np.diff(series.step) > 0)
        assert np.all(np.diff(series.val_step) > 0)
        assert series.job_id == "job_example"
        assert series.checkpoint_id == "ckpt_example"
        assert series.n_dropped_duplicates == 0

    def test_nan_string_becomes_a_float(self) -> None:
        """`"NaN"` in the file is a float by the time any detector sees it."""
        series = read_series(TRAINING / "t1_nan.jsonl")

        assert series.loss_train.dtype == np.float64
        assert np.isnan(series.loss_train).sum() == 1

    @pytest.mark.parametrize(
        "name",
        [
            "t2_val_high.jsonl",
            "t3_overfit.jsonl",
            "t4_group_loss.jsonl",
            "t5_low_variance.jsonl",
            "t6_std_mismatch.jsonl",
            "t8_vlm_gradient.jsonl",
        ],
    )
    def test_every_injected_example_reads(self, name: str) -> None:
        series = read_series(TRAINING / name)

        assert series.step.size or series.val_step.size

    def test_probes_and_layout_read(self) -> None:
        assert read_probe_p3(ARTIFACTS / "ProbeP3.json").probe == "P3"
        assert read_probe_p4(ARTIFACTS / "ProbeP4.json").parent_checkpoint_id
        assert read_action_layout(ARTIFACTS / "ActionLayout.json").dimensions


class TestResumedJob:
    """A restarted job logs the steps it redid again (issue #5, point 2c)."""

    def test_highest_attempt_wins_whatever_the_line_order(self) -> None:
        later_line_first = build_series(
            [
                record(step=10, loss=0.5, attempt=1),
                record(step=10, loss=9.0, attempt=0),
            ]
        )
        earlier_line_first = build_series(
            [
                record(step=10, loss=9.0, attempt=0),
                record(step=10, loss=0.5, attempt=1),
            ]
        )

        assert later_line_first.loss_train.tolist() == [0.5]
        assert earlier_line_first.loss_train.tolist() == [0.5]
        assert later_line_first.n_dropped_duplicates == 1

    def test_the_same_step_in_two_splits_is_not_a_duplicate(self) -> None:
        series = build_series([record(step=10, loss=0.4), record(step=10, loss=0.6, split="val")])

        assert series.loss_train.tolist() == [0.4]
        assert series.loss_val.tolist() == [0.6]
        assert series.n_dropped_duplicates == 0


class TestLoggingRate:
    """A signal logged more rarely than the loss must not shift the step axis."""

    def test_a_record_without_per_dim_stats_is_a_nan_row(self) -> None:
        series = build_series(
            [
                record(step=0, pred_std=[0.4, 0.5], target_std=[0.4, 0.5]),
                record(step=10),
                record(step=20, pred_std=[0.2, 0.3], target_std=[0.4, 0.5]),
            ]
        )

        assert series.pred_std.shape == (3, 2)
        assert np.all(np.isnan(series.pred_std[1]))
        assert series.step.tolist() == [0, 10, 20]

    def test_a_record_without_a_group_loss_is_nan_for_that_group(self) -> None:
        series = build_series(
            [
                record(step=0, loss_by_group={"arm": 0.2, "hand": 0.3}),
                record(step=10, loss_by_group={"arm": 0.1}),
            ]
        )

        assert series.loss_by_group["arm"].tolist() == [0.2, 0.1]
        assert np.isnan(series.loss_by_group["hand"][1])

    def test_a_missing_optional_gradient_is_nan_not_zero(self) -> None:
        """nan is "not measured"; 0.0 is what T8 reads as a frozen VLM."""
        series = build_series([record(step=0), record(step=10, grad_norm_vlm=0.0)])

        assert np.isnan(series.grad_norm_vlm[0])
        assert series.grad_norm_vlm[1] == 0.0


class TestLogsNoDetectorMayRunOn:
    """What the reader refuses, rather than hand a detector a wrong verdict."""

    def test_two_jobs_in_one_file(self) -> None:
        with pytest.raises(ReaderError, match="đúng một job"):
            build_series([record(job_id="a"), record(job_id="b", step=10)])

    def test_no_record_at_all(self) -> None:
        with pytest.raises(ReaderError, match="không có bản ghi"):
            build_series([])

    def test_per_dim_width_changing_mid_log(self) -> None:
        with pytest.raises(ReaderError, match="số chiều khác nhau"):
            build_series([record(step=0, pred_std=[0.1, 0.2]), record(step=10, pred_std=[0.1])])

    def test_a_line_that_is_not_a_training_metric(self, tmp_path: Path) -> None:
        log = tmp_path / "metrics.jsonl"
        log.write_text('{"job_id": "job"}\n', encoding="utf-8")

        with pytest.raises(ReaderError, match="sai schema"):
            read_series(log)

    def test_a_blank_line_is_not_an_error(self, tmp_path: Path) -> None:
        log = tmp_path / "metrics.jsonl"
        log.write_text(record(step=0).model_dump_json() + "\n\n", encoding="utf-8")

        assert read_series(log).step.tolist() == [0]

    def test_a_probe_file_that_is_not_json(self, tmp_path: Path) -> None:
        broken = tmp_path / "p3.json"
        broken.write_text("not json", encoding="utf-8")

        with pytest.raises(ReaderError, match="không đọc được ProbeP3"):
            read_probe_p3(broken)


class TestVlmFrozen:
    """T8 branch (a) needs one answer from the log, or none at all."""

    def test_records_that_agree_give_the_answer(self) -> None:
        assert build_series([record(vlm_frozen=True)]).vlm_frozen is True
        assert build_series([record(vlm_frozen=False)]).vlm_frozen is False

    def test_records_that_disagree_give_no_answer(self) -> None:
        """None, so T8 skips with a reason instead of reading it as unfrozen."""
        series = build_series([record(step=0, vlm_frozen=True), record(step=10, vlm_frozen=False)])

        assert series.vlm_frozen is None


class TestLayoutView:
    """The detectors ask the layout, and never hold a number of their own (AC 2)."""

    @pytest.fixture
    def view(self) -> LayoutView:
        return LayoutView(
            ActionLayout(
                dimensions=[
                    ActionDimension(
                        name="arm_0", group="arm", masked=False, limit_low=-1.0, limit_high=1.0
                    ),
                    ActionDimension(name="arm_1", group="arm", masked=True),
                    ActionDimension(
                        name="hand_0", group="hand", masked=False, limit_low=0.0, limit_high=2.0
                    ),
                ]
            )
        )

    def test_masked_dimensions_are_the_ones_t5_must_leave_alone(self, view: LayoutView) -> None:
        assert view.unmasked.tolist() == [True, False, True]

    def test_groups_keep_the_order_of_the_layout(self, view: LayoutView) -> None:
        assert view.groups == ["arm", "hand"]

    def test_limits_are_nan_where_the_layout_sets_none(self, view: LayoutView) -> None:
        low, high = view.limits()

        assert low.tolist()[0] == -1.0
        assert np.isnan(low[1]) and np.isnan(high[1])
        assert high.tolist()[2] == 2.0

    def test_a_log_of_the_wrong_width_is_refused(self, view: LayoutView) -> None:
        with pytest.raises(ReaderError, match="action_layout có 3"):
            view.check_width(np.zeros((2, 4)), "pred_std")

    def test_an_unlogged_signal_passes_the_width_check(self, view: LayoutView) -> None:
        """An empty array is "not logged", which is task 3's skip, not an error."""
        view.check_width(np.zeros((2, 0)), "pred_std")

    def test_the_shipped_layout_names_its_dimensions(self) -> None:
        view = LayoutView(read_action_layout(ARTIFACTS / "ActionLayout.json"))

        assert view.name(0)
        assert view.unmasked.size == view.n_dims


def test_the_shipped_examples_stay_valid_json() -> None:
    """A guard on the fixture files themselves, not on the reader."""
    for path in sorted(TRAINING.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
