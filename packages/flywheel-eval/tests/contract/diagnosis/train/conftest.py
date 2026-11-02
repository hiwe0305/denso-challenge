"""A train job on disk, for the tests that drive `fw eval diag-train` (DA-08 task 6).

The command is tested the way an engineer runs it: a directory with a log and
probe results in it, a threshold file, and a store to append to. The job is
written here rather than taken from `flywheel.testkit`, because the shipped
examples are a few records each - enough to show the shape of a signal, not
enough to fill the step windows the thresholds count over.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.training import TrainingMetric

CONFIGS = Path(__file__).resolve().parents[6] / "configs" / "eval" / "diagnosis"
TRAIN_YAML = CONFIGS / "train.yaml"
PROBE_SHA = "b" * 64

JobWriter = Callable[..., Path]


@pytest.fixture
def write_job(tmp_path: Path) -> JobWriter:
    """Write a job directory; `faults` names the records to append to a learning log."""

    def build(name: str = "job", faults: list[dict[str, Any]] | None = None) -> Path:
        directory = tmp_path / name
        directory.mkdir(parents=True, exist_ok=True)
        records = _learning_records() + list(faults or [])
        (directory / "metrics.jsonl").write_text(
            "\n".join(
                json.dumps(TrainingMetric.model_validate(one).model_dump()) for one in records
            ),
            encoding="utf-8",
        )
        _write(directory / "action_layout.json", _layout())
        _write(directory / "probe_p3.json", _p3("ckpt_example"))
        _write(directory / "probe_p4.json", _p4("ckpt_example", "ckpt_parent"))
        _write(directory / "probe_p4_parent.json", _p4("ckpt_parent", "ckpt_grandparent"))
        return directory

    return build


def record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_plan_id": "rp_example",
        "job_id": "job_example",
        "checkpoint_id": "ckpt_example",
        "release_id": "rel_example",
        "attempt": 0,
        "step": 0,
        "epoch": 0,
        "split": "train",
        "loss": 1.0,
        "lr": 1e-3,
        "vlm_frozen": True,
        "wall_time_s": 1.0,
    }
    return base | overrides


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _learning_records() -> list[dict[str, Any]]:
    train = [
        record(
            step=step,
            loss=1.0 - 0.0002 * step,
            loss_by_group={"arm": 1.0 - 0.0003 * step, "hand": 1.0 - 0.0003 * step},
            pred_var_by_dim=[0.2, 0.3, 0.1],
            pred_std=[0.45, 0.55, 0.3],
            target_std=[0.5, 0.6, 0.3],
            grad_norm_vlm=0.0,
            grad_norm_action=0.1,
        )
        for step in range(0, 3001, 10)
    ]
    val = [
        record(step=step, split="val", loss=1.05 - 0.0002 * step) for step in range(0, 3001, 500)
    ]
    return train + val


def _layout() -> dict[str, Any]:
    limits = {"limit_low": -1.0, "limit_high": 1.0}
    return {
        "dimensions": [
            {"name": "arm_0", "group": "arm", "masked": False, **limits},
            {"name": "arm_1", "group": "arm", "masked": False, **limits},
            {"name": "pad_0", "group": "pad", "masked": True},
        ]
    }


def _p3(checkpoint_id: str) -> dict[str, Any]:
    return {
        "probe": "P3",
        "checkpoint_id": checkpoint_id,
        "dataset_sha256": PROBE_SHA,
        "error_by_group": {"arm": 0.10, "hand": 0.12},
        "error_by_chunk_pos": [0.10, 0.10, 0.11, 0.10],
        "hand_event_offset_steps": 0.0,
        "out_of_limit_dims": [],
    }


def _p4(checkpoint_id: str, parent_checkpoint_id: str) -> dict[str, Any]:
    return {
        "probe": "P4",
        "checkpoint_id": checkpoint_id,
        "parent_checkpoint_id": parent_checkpoint_id,
        "p1": {
            "probe": "P1",
            "checkpoint_id": checkpoint_id,
            "dataset_sha256": PROBE_SHA,
            "accuracy_by_question_type": {"where": 0.80},
        },
        "p3": _p3(checkpoint_id),
    }
