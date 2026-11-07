"""DA-04: a step that fails half way leaves the work dir as it was (review of PR 152)."""

from __future__ import annotations

import hashlib
import urllib.error
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.source import register_egodex

K = np.array([[50.0, 0, 32], [0, 50, 18], [0, 0, 1]])


def files(work: Path, pattern: str) -> dict[str, str]:
    return {p.relative_to(work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(work.glob(pattern))}


@pytest.fixture
def work(store: Path, cfg: EgoConfig) -> Path:
    out = store / "work"
    api.ingest(register_egodex(store, cfg), out, cfg, store)
    api.write_eb_poses(out)
    api.annotate(out, cfg)
    return out


class DyingLabeler:
    """Answers a few segments, then the endpoint goes away."""

    def __init__(self, answers: int) -> None:
        self.left = answers

    def describe(self, images: Sequence[bytes], step: str, instruction: str) -> str | None:
        if self.left == 0:
            raise urllib.error.URLError("connection refused")
        self.left -= 1
        return "a sentence from the model"


def test_a_model_that_stops_answering_leaves_the_old_segments(
    work: Path, cfg: EgoConfig
) -> None:
    before = files(work, "egocentric/*/*")
    with pytest.raises(urllib.error.URLError):
        api.annotate(work, cfg, api.Models(labeler=DyingLabeler(3)))
    assert files(work, "egocentric/*/*") == before
