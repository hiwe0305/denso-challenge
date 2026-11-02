"""All twelve codes, each on a job that carries its fault (DA-08 task 7, AC 6).

Every case runs the whole chain through `diagnose_all`, not the one detector
under test. That is the point of this file: a detector that swallowed another
detector's signal, or a reader change that quietly emptied one series, passes
twelve single-detector tests and fails here.

The clean control is the other half, and it is checked twice. A job with no
finding could be a healthy checkpoint or a job nobody could judge, so the
control also has to skip nothing - which means it carries `vlm_frozen`, a
parent probe, probe results and a positive `target_std`. Without that second
assertion AC 6 would be satisfied by a diagnosis that measured nothing (FR21).

**On the `flywheel.testkit` examples.** The plan expected seven of these rows
to come from `fixtures/training/t*.jsonl`. Only `t1_nan.jsonl` raises its own
code under the shipped thresholds, so that one is used as it ships and the
rest are built here. The examples are not wrong as examples - they are three
to six records long, and the windows of `train.yaml` count 500 to 2000 steps -
but the gap is real and belongs to whoever owns them, so it is reported under
PR #22 rather than closed by loosening a threshold (plan, task 7, step 3):

* `t2_val_high.jsonl` and `t5_low_variance.jsonl` hold no train record at all,
  so every F-TRAIN code skips on them.
* `t6_std_mismatch.jsonl` and `t8_vlm_gradient.jsonl` put their fault on the
  last record, which is a `val` record. A gradient norm and a prediction std
  come out of a train batch, so the detectors read them off train records and
  never see these.
* `t3_overfit.jsonl` rises twice; `t3.m_measurements` is three.
* `t4_group_loss.jsonl` spans four steps against a 2000-step window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.artifacts import ProbeP3, ProbeP4
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.artifact import JobInputs, diagnose_all
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import LayoutView, TrainSeries, read_series

TESTKIT = (
    Path(__file__).resolve().parents[5]
    / "flywheel-testkit"
    / "src"
    / "flywheel"
    / "testkit"
    / "fixtures"
    / "training"
)
TRAIN_STEPS = range(0, 3001, 10)
VAL_STEPS = range(0, 3001, 500)

Codes = Callable[[DetectorResult], list[str]]
SeriesBuilder = Callable[..., TrainSeries]
P3Builder = Callable[..., ProbeP3]
P4Builder = Callable[..., ProbeP4]


def falling(rate: float = 0.0002, start: float = 1.0) -> dict[int, float]:
    return {step: start - rate * step for step in TRAIN_STEPS}


def flat(value: float = 1.0) -> dict[int, float]:
    return {step: value for step in TRAIN_STEPS}


# Every signal of a job that is learning. One case replaces one entry of this.
LEARNING: dict[str, Any] = {
    "train": falling(),
    "val": {step: 1.05 - 0.0002 * step for step in VAL_STEPS},
    "groups": {"arm": falling(0.0003), "hand": falling(0.0003)},
    "pred_var": [0.2, 0.3, 0.1],
    "pred_std": [0.45, 0.55, 0.3],
    "target_std": [0.5, 0.6, 0.3],
    "grad_vlm": 0.0,
    "grad_action": 0.1,
    "vlm_frozen": True,
}


@dataclass(frozen=True)
class Kit:
    """The builders an injected case needs, and the clean job it starts from."""

    series_from: SeriesBuilder
    p3_from: P3Builder
    p4_from: P4Builder
    layout: LayoutView
    clean: JobInputs

    def job(self, **signals: Any) -> JobInputs:
        """The clean job with one train signal replaced."""
        return replace(self.clean, series=self.series_from(**{**LEARNING, **signals}))

    def with_p3(self, **fields: Any) -> JobInputs:
        """The clean job with one offline probe measurement replaced."""
        return replace(self.clean, probe_p3=self.p3_from(**fields))


@pytest.fixture
def kit(
    series_from: SeriesBuilder,
    p3_from: P3Builder,
    p4_from: P4Builder,
    layout: LayoutView,
    clean_p3: ProbeP3,
    clean_p4_pair: tuple[ProbeP4, ProbeP4],
) -> Kit:
    child, parent = clean_p4_pair
    clean = JobInputs(
        series=series_from(**LEARNING),
        layout=layout,
        probe_p3=clean_p3,
        probe_p4=child,
        probe_p4_parent=parent,
    )
    return Kit(series_from, p3_from, p4_from, layout, clean)


def t1_divergence(kit: Kit) -> JobInputs:
    """A loss that stopped being a number: the one code allowed to stop a job."""
    return kit.job(train={**falling(), 3010: float("nan")})


def t2_no_learning(kit: Kit) -> JobInputs:
    return kit.job(val={step: 1.0 for step in VAL_STEPS})


def t3_overfitting(kit: Kit) -> JobInputs:
    """Val up at every measurement while the train loss keeps falling."""
    return kit.job(val={step: 0.8 + 0.0002 * step for step in VAL_STEPS})


def t4_group_imbalance(kit: Kit) -> JobInputs:
    return kit.job(groups={"arm": falling(0.0003), "hand": flat()})


def t5_dead_dimension(kit: Kit) -> JobInputs:
    """Dimension 1 of the layout is unmasked, so a flat prediction there is a fault."""
    return kit.job(pred_var=[0.2, 0.0, 0.1])


def t6_mode_collapse(kit: Kit) -> JobInputs:
    return kit.job(pred_std=[0.45, 0.05, 0.3])


def t7_forgetting(kit: Kit) -> JobInputs:
    """The child answers the probe far worse than the checkpoint it came from."""
    child = kit.p4_from(accuracy={"where": 0.50}, probe_set="shared")
    parent = kit.p4_from(checkpoint_id="ckpt-parent", accuracy={"where": 0.90}, probe_set="shared")
    return replace(kit.clean, probe_p4=child, probe_p4_parent=parent)


def t8_gradient_fault(kit: Kit) -> JobInputs:
    """Gradient through a VLM the job declares frozen."""
    return kit.job(grad_vlm=1.0)


def o1_group_error(kit: Kit) -> JobInputs:
    return kit.with_p3(error_by_group={"arm": 0.10, "hand": 0.90, "waist": 0.10})


def o2_chunk_error(kit: Kit) -> JobInputs:
    return kit.with_p3(error_by_chunk_pos=[0.1, 0.2, 0.4, 0.8])


def o3_hand_event(kit: Kit) -> JobInputs:
    return kit.with_p3(hand_event_offset_steps=9.0)


def o4_joint_limit(kit: Kit) -> JobInputs:
    return kit.with_p3(out_of_limit_dims=[1])


INJECTED_CASES = [
    ("T1", t1_divergence),
    ("T2", t2_no_learning),
    ("T3", t3_overfitting),
    ("T4", t4_group_imbalance),
    ("T5", t5_dead_dimension),
    ("T6", t6_mode_collapse),
    ("T7", t7_forgetting),
    ("T8", t8_gradient_fault),
    ("O1", o1_group_error),
    ("O2", o2_chunk_error),
    ("O3", o3_hand_event),
    ("O4", o4_joint_limit),
]


class TestInjectedFaults:
    @pytest.mark.parametrize(("code", "build"), INJECTED_CASES, ids=[c for c, _ in INJECTED_CASES])
    def test_each_code_is_detected(
        self, code: str, build: Callable[[Kit], JobInputs], kit: Kit, cfg: TrainThresholds
    ) -> None:
        result = diagnose_all(build(kit), cfg)

        assert code in {finding.code for finding in result.findings}

    @pytest.mark.parametrize(("code", "build"), INJECTED_CASES, ids=[c for c, _ in INJECTED_CASES])
    def test_no_code_is_raised_and_skipped_at_once(
        self, code: str, build: Callable[[Kit], JobInputs], kit: Kit, cfg: TrainThresholds
    ) -> None:
        """A code that both fired and went unmeasured would be two answers to one question."""
        result = diagnose_all(build(kit), cfg)

        assert code not in {skip.code for skip in result.skipped}

    def test_only_t1_may_stop_a_job(self, kit: Kit, cfg: TrainThresholds) -> None:
        for code, build in INJECTED_CASES:
            result = diagnose_all(build(kit), cfg)
            stopping = {finding.code for finding in result.findings if finding.stop_job}
            assert stopping <= {"T1"}, f"{code} case asked to stop the job"


class TestCleanControl:
    def test_a_learning_job_raises_no_code(self, kit: Kit, cfg: TrainThresholds) -> None:
        result = diagnose_all(kit.clean, cfg)

        assert [finding.code for finding in result.findings] == []

    def test_a_learning_job_with_every_signal_skips_no_code(
        self, kit: Kit, cfg: TrainThresholds
    ) -> None:
        """Without this, the test above would pass on a job nobody could judge."""
        result = diagnose_all(kit.clean, cfg)

        assert [skip.code for skip in result.skipped] == []


class TestShippedExample:
    def test_the_testkit_divergence_example_raises_t1_as_it_ships(
        self, kit: Kit, cfg: TrainThresholds
    ) -> None:
        """`t1_nan.jsonl` is read as it ships, with no threshold adapted to it."""
        job = replace(kit.clean, series=read_series(TESTKIT / "t1_nan.jsonl"))

        result = diagnose_all(job, cfg)

        assert "T1" in {finding.code for finding in result.findings}
        assert any(finding.stop_job for finding in result.findings)
