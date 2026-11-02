"""What the F-TRAIN detector tests share (DA-08 task 2).

`series_from` builds a `TrainSeries` out of step-to-loss points, so a detector
test states the curve it means and nothing else. The reader and its
`metrics_builder` are task 1 and wait on the contracts of DA-25 (PR #22); the
questions only a real `metrics.jsonl` can raise - a resumed job logging the
same step twice, a loss written as the string `"NaN"`, two logging rates in one
file - belong to that test and are not restated here.

`cfg` is the threshold file the repo ships, not a mapping written in the test:
a number changed in `configs/eval/diagnosis/train.yaml` has to show up as a
changed verdict somewhere, and these tests are where it does.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pytest
from flywheel.eval.config import TrainThresholds, load_train_thresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult
from flywheel.eval.diagnosis.train.reader import TrainSeries

TRAIN_YAML = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis" / "train.yaml"

Points = Mapping[int, float] | Sequence[tuple[int, float]]
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
def series_from() -> SeriesBuilder:
    def build(train: Points = (), val: Points = ()) -> TrainSeries:
        train_step, loss_train = _arrays(train)
        val_step, loss_val = _arrays(val)
        return TrainSeries(
            step=train_step,
            loss_train=loss_train,
            val_step=val_step,
            loss_val=loss_val,
        )

    return build


@pytest.fixture
def clean_series(series_from: SeriesBuilder) -> TrainSeries:
    """A job that is learning: train and val both fall, val measured to step 3000.

    Every detector of this story must be silent on it *and* skip nothing. An
    empty `findings` list alone would also come out of a job nobody could judge,
    so this is the control that tells the two apart (FR21, PO review of the plan).
    """
    return series_from(
        train={step: 1.0 - 0.0002 * step for step in range(0, 3001, 10)},
        val={step: 1.05 - 0.0002 * step for step in range(0, 3001, 500)},
    )


def _arrays(points: Points) -> tuple[np.ndarray, np.ndarray]:
    pairs = sorted(points.items() if isinstance(points, Mapping) else points)
    steps = np.asarray([step for step, _ in pairs], dtype=np.int64)
    values = np.asarray([value for _, value in pairs], dtype=np.float64)
    return steps, values
