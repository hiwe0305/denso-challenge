"""What the F-TRAIN and F-OFF detector tests share (DA-08 tasks 2, 3, 4).

`series_from` builds a `TrainSeries` out of step-to-loss points, so a detector
test states the curve it means and nothing else. The questions only a real
`metrics.jsonl` can raise - a resumed job logging the same step twice, a loss
written as the string `"NaN"`, two logging rates in one file - belong to
`test_reader.py`, which drives `read_series`, and are not restated here.

`p3_from` and `p4_from` do the same for the probe results T7 and O1-O4 read.
They fill in the fields a test does not mention with values every detector is
silent on, so each test states one fault; `clean_p3` and `clean_p4_pair` are
the controls that must come out with neither a finding nor a skip.

`cfg` is the threshold file the repo ships, not a mapping written in the test:
a number changed in `configs/eval/diagnosis/train.yaml` has to show up as a
changed verdict somewhere, and these tests are where it does.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts.artifacts import ActionDimension, ActionLayout, ProbeP1, ProbeP3, ProbeP4
from flywheel.eval.config import TrainThresholds, load_train_thresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import LayoutView, TrainSeries

TRAIN_YAML = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis" / "train.yaml"

Points = Mapping[int, float] | Sequence[tuple[int, float]]
PerDimPoints = Sequence[float] | Mapping[int, Sequence[float]]
SeriesBuilder = Callable[..., TrainSeries]
P3Builder = Callable[..., ProbeP3]
P4Builder = Callable[..., ProbeP4]


@pytest.fixture(scope="session")
def cfg() -> TrainThresholds:
    thresholds, _ = load_train_thresholds(TRAIN_YAML)
    return thresholds


@pytest.fixture
def codes() -> Callable[[DetectorResult], list[str]]:
    return lambda result: [finding.code for finding in result.findings]


@pytest.fixture
def skipped_codes() -> Callable[[DetectorResult], list[str]]:
    return lambda result: [skip.code for skip in result.skipped]


@pytest.fixture
def layout() -> LayoutView:
    """Three action dimensions, one of them masked, as T4-T6 and O4 read them.

    The masked dimension is what keeps the AC 2 rule honest: a test that sets a
    dead variance on it must still come out clean.
    """
    return LayoutView(
        ActionLayout(
            dimensions=[
                ActionDimension(
                    name="arm_0", group="arm", masked=False, limit_low=-1.0, limit_high=1.0
                ),
                ActionDimension(
                    name="arm_1", group="arm", masked=False, limit_low=-1.0, limit_high=1.0
                ),
                ActionDimension(name="hand_0", group="hand", masked=True),
            ]
        )
    )


@pytest.fixture
def series_from() -> SeriesBuilder:
    """Build a `TrainSeries` from the signals one test cares about, nan elsewhere.

    Per-dimension and gradient signals take either one value broadcast over
    every train record, or a step-keyed mapping when the test is about a signal
    logged at its own rate.
    """

    def build(
        train: Points = (),
        val: Points = (),
        groups: Mapping[str, Points] | None = None,
        pred_var: PerDimPoints | None = None,
        pred_std: PerDimPoints | None = None,
        target_std: PerDimPoints | None = None,
        grad_vlm: float | Points | None = None,
        grad_action: float | Points | None = None,
        vlm_frozen: bool | None = None,
    ) -> TrainSeries:
        train_step, loss_train = _arrays(train)
        val_step, loss_val = _arrays(val)
        return TrainSeries(
            step=train_step,
            loss_train=loss_train,
            val_step=val_step,
            loss_val=loss_val,
            loss_by_group={
                name: _on_steps(train_step, points) for name, points in (groups or {}).items()
            },
            pred_var_by_dim=_per_dim(train_step, pred_var),
            pred_std=_per_dim(train_step, pred_std),
            target_std=_per_dim(train_step, target_std),
            grad_norm_vlm=_scalar(train_step, grad_vlm),
            grad_norm_action=_scalar(train_step, grad_action),
            vlm_frozen=vlm_frozen,
        )

    return build


@pytest.fixture
def clean_series(series_from: SeriesBuilder) -> TrainSeries:
    """A job that is learning, in every signal this story reads.

    Train and val both fall, both action groups improve, no dimension is flat
    or collapsed, the frozen VLM gets no gradient and the action head does not
    spike. Every detector of this story must be silent on it *and* skip
    nothing. An empty `findings` list alone would also come out of a job nobody
    could judge, so this is the control that tells the two apart (FR21, PO
    review of the plan).
    """
    return series_from(
        train={step: 1.0 - 0.0002 * step for step in range(0, 3001, 10)},
        val={step: 1.05 - 0.0002 * step for step in range(0, 3001, 500)},
        groups={
            "arm": {step: 1.0 - 0.0003 * step for step in range(0, 3001, 10)},
            "hand": {step: 1.0 - 0.0003 * step for step in range(0, 3001, 10)},
        },
        pred_var=[0.2, 0.3, 0.1],
        pred_std=[0.45, 0.55, 0.3],
        target_std=[0.5, 0.6, 0.3],
        grad_vlm=0.0,
        grad_action=0.1,
        vlm_frozen=True,
    )


@pytest.fixture
def p3_from() -> P3Builder:
    """A P3 probe result; every field a test leaves out is one no detector flags.

    `probe_set` becomes the `dataset_sha256` of the record: T7 refuses to
    compare two checkpoints probed on different datasets, so a test about that
    says so by giving the two probes different probe sets.
    """

    def build(
        checkpoint_id: str = "ckpt-child",
        error_by_group: Mapping[str, float] | None = None,
        error_by_chunk_pos: Sequence[float] | None = None,
        hand_event_offset_steps: float = 0.0,
        out_of_limit_dims: Sequence[int] = (),
        probe_set: str = "probe-set-1",
    ) -> ProbeP3:
        return ProbeP3(
            checkpoint_id=checkpoint_id,
            dataset_sha256=_sha256(probe_set),
            error_by_group=dict(
                error_by_group if error_by_group is not None else {"arm": 0.10, "hand": 0.12}
            ),
            error_by_chunk_pos=list(
                error_by_chunk_pos if error_by_chunk_pos is not None else [0.10, 0.10, 0.11, 0.10]
            ),
            hand_event_offset_steps=hand_event_offset_steps,
            out_of_limit_dims=list(out_of_limit_dims),
        )

    return build


@pytest.fixture
def p4_from(p3_from: P3Builder) -> P4Builder:
    """A P4 probe result, which is P1 and P3 of one checkpoint plus its parent."""

    def build(
        checkpoint_id: str = "ckpt-child",
        parent_checkpoint_id: str = "ckpt-parent",
        accuracy: Mapping[str, float] | None = None,
        probe_set: str = "probe-set-1",
        **p3_fields: object,
    ) -> ProbeP4:
        return ProbeP4(
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            p1=ProbeP1(
                checkpoint_id=checkpoint_id,
                dataset_sha256=_sha256(probe_set),
                accuracy_by_question_type=dict(
                    accuracy if accuracy is not None else {"where": 0.80, "what": 0.75}
                ),
            ),
            p3=p3_from(checkpoint_id=checkpoint_id, probe_set=probe_set, **p3_fields),  # type: ignore[arg-type]
        )

    return build


@pytest.fixture
def clean_p3(p3_from: P3Builder) -> ProbeP3:
    """An offline probe every F-OFF detector must pass without skipping anything."""
    return p3_from()


@pytest.fixture
def clean_p4_pair(p4_from: P4Builder) -> tuple[ProbeP4, ProbeP4]:
    """Child and parent of a fine-tune that forgot nothing: the T7 control.

    The child is a little better than the parent everywhere, which is what a
    fine-tune that worked looks like, and it is probed on the same probe set.
    """
    child = p4_from(
        checkpoint_id="ckpt-child",
        parent_checkpoint_id="ckpt-parent",
        accuracy={"where": 0.82, "what": 0.76},
        error_by_group={"arm": 0.09, "hand": 0.11},
    )
    parent = p4_from(
        checkpoint_id="ckpt-parent",
        parent_checkpoint_id="ckpt-grandparent",
        accuracy={"where": 0.80, "what": 0.75},
        error_by_group={"arm": 0.10, "hand": 0.12},
    )
    return child, parent


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _arrays(points: Points) -> tuple[np.ndarray, np.ndarray]:
    pairs = sorted(points.items() if isinstance(points, Mapping) else points)
    steps = np.asarray([step for step, _ in pairs], dtype=np.int64)
    values = np.asarray([value for _, value in pairs], dtype=np.float64)
    return steps, values


def _on_steps(step: np.ndarray, points: Points) -> np.ndarray:
    """A signal measured at its own steps, read off at the train steps."""
    pairs = dict(points.items() if isinstance(points, Mapping) else points)
    return np.asarray([pairs.get(int(value), float("nan")) for value in step], dtype=np.float64)


def _scalar(step: np.ndarray, value: float | Points | None) -> np.ndarray:
    if value is None:
        return np.full(step.size, np.nan, dtype=np.float64)
    if isinstance(value, (int, float)):
        return np.full(step.size, float(value), dtype=np.float64)
    return _on_steps(step, value)


def _per_dim(step: np.ndarray, value: PerDimPoints | None) -> np.ndarray:
    if value is None:
        return np.zeros((step.size, 0), dtype=np.float64)
    if isinstance(value, Mapping):
        width = len(next(iter(value.values())))
        rows = [value.get(int(one), [float("nan")] * width) for one in step]
        return np.asarray(rows, dtype=np.float64)
    return np.tile(np.asarray(value, dtype=np.float64), (step.size, 1))
