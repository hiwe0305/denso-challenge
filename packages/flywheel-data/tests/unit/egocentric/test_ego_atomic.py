"""DA-04: a step that fails half way leaves the work dir as it was (review of PR 152)."""

from __future__ import annotations

import hashlib
import urllib.error
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from ego_data import FRAMES, synthetic_pose
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric import pose as pose_module
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.pose import load_pose, save_pose
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


def test_a_comparison_that_raises_writes_no_e_a_file(
    work: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estimates = tmp_path / "ea"
    estimates.mkdir()
    for folder in sorted((work / "egocentric").iterdir())[:2]:
        (estimates / f"{folder.name}.npz").write_bytes(b"")

    class Estimate:
        meta: dict[str, Any] = {}

    class Deviation:
        def to_dict(self) -> dict[str, Any]:
            return {"ok": True}

    calls = []

    def compare(*args: Any) -> Deviation:
        calls.append(args)
        if len(calls) == 2:
            raise ValueError("E-A and E-B disagree on the frame count")
        return Deviation()

    monkeypatch.setattr(api, "read_estimate", lambda path: Estimate())
    monkeypatch.setattr(api, "to_pose", lambda estimate, frame="world": synthetic_pose())
    monkeypatch.setattr(api, "compare", compare)
    before = files(work, "egocentric/*/*")
    with pytest.raises(ValueError, match="frame count"):
        api.import_estimates(work, estimates)
    assert files(work, "egocentric/*/*") == before
    assert not list(work.glob("egocentric/*/pose_ea.npz"))


def test_save_pose_replaces_the_file_whole(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pose.npz"
    save_pose(synthetic_pose(), path, K)
    before = path.read_bytes()

    def broken(file: Any, **arrays: Any) -> None:
        file.write(b"half a file")
        raise OSError("disk full")

    monkeypatch.setattr(pose_module.np, "savez", broken)
    with pytest.raises(OSError, match="disk full"):
        save_pose(synthetic_pose(FRAMES), path, K)
    assert path.read_bytes() == before and load_pose(path).frames == FRAMES
    assert [p.name for p in tmp_path.iterdir()] == ["pose.npz"]
