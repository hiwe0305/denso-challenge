"""Probe results and the shipped table, for the stage attribution (DA-13 AC 6).

The probe fixtures of `flywheel.testkit` are the shape of the artifacts; what
the tests need is the same shape with one number moved, so they are built here
from the testkit values rather than copied.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import ProbeP1, ProbeP3, ProbeP4
from flywheel.eval.config import StageTable, load_stage_table
from flywheel.eval.diagnosis.stage.attribute import EVIDENCE_RULES

DATASET = "a" * 64
STAGE_CONFIG = Path("configs") / "eval" / "diagnosis" / "stage.yaml"

P1Builder = Callable[..., ProbeP1]
P3Builder = Callable[..., ProbeP3]
P4Builder = Callable[..., ProbeP4]


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


@pytest.fixture
def stage_config() -> Path:
    """The table as it ships in `configs/`, read by path so a test can copy it."""
    return _repo_root() / STAGE_CONFIG


@pytest.fixture
def table(stage_config: Path) -> StageTable:
    """The table as it ships, so a test cannot pass against a table nobody uses."""
    return load_stage_table(stage_config, EVIDENCE_RULES)[0]


@pytest.fixture
def p1_from() -> P1Builder:
    def build(accuracy: float = 0.95, kind: str = "object") -> ProbeP1:
        return ProbeP1(
            checkpoint_id="ckpt_1",
            dataset_sha256=DATASET,
            accuracy_by_question_type={kind: accuracy},
        )

    return build


@pytest.fixture
def p3_from() -> P3Builder:
    def build(error_by_group: dict[str, float] | None = None) -> ProbeP3:
        return ProbeP3(
            checkpoint_id="ckpt_1",
            dataset_sha256=DATASET,
            error_by_group=error_by_group if error_by_group is not None else {"arm": 0.05},
            error_by_chunk_pos=[0.1, 0.12],
            hand_event_offset_steps=1.0,
            out_of_limit_dims=[],
        )

    return build


@pytest.fixture
def p4_from(p1_from: P1Builder, p3_from: P3Builder) -> P4Builder:
    def build(accuracy: float = 0.95, error_by_group: dict[str, float] | None = None) -> ProbeP4:
        return ProbeP4(
            checkpoint_id="ckpt_1",
            parent_checkpoint_id="ckpt_0",
            p1=p1_from(accuracy=accuracy),
            p3=p3_from(error_by_group=error_by_group),
        )

    return build
