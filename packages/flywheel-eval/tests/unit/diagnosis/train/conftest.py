"""What the F-TRAIN detector tests share (DA-08 task 2).

`series_from` builds a `TrainSeries` out of step-to-loss points, so a detector
test states the curve it means and nothing else. The questions only a real
`metrics.jsonl` can raise - a resumed job logging the same step twice, a loss
written as the string `"NaN"`, two logging rates in one file - belong to
`test_reader.py`, which drives `read_series`, and are not restated here.

`cfg` is the threshold file the repo ships, not a mapping written in the test:
a number changed in `configs/eval/diagnosis/train.yaml` has to show up as a
changed verdict somewhere, and these tests are where it does.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.eval.config import TrainThresholds, load_train_thresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import LayoutView, TrainSeries

TRAIN_YAML = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis" / "train.yaml"

Points = Mapping[int, float] | Sequence[tuple[int, float]]
PerDimPoints = Sequence[float] | Mapping[int, Sequence[float]]
SeriesBuilder = Callable[..., TrainSeries]


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
