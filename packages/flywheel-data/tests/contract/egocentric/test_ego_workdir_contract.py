"""The work directory DA-04 writes and DA-18 reads (plan 6/11/2026 section 4.2a).

DA-18 reads files, never DA-04's modules, so the check is on the files: their
names, the keys of bundle.json, the arrays of pose.npz, the columns of
segments.parquet, and the contract records of episodes.jsonl and the QA reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.contracts.segments import SEGMENT_SCHEMA

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "egocentric"))
from ego_data import config_for, make_egodex, pin_videos  # noqa: E402
from flywheel.data.ingest.egocentric import api  # noqa: E402
from flywheel.data.ingest.egocentric.config import load_config  # noqa: E402
from flywheel.data.ingest.egocentric.source import register_egodex  # noqa: E402

BUNDLE_KEYS = {"episode_id", "hdf5", "mp4", "frames", "fps", "task", "instruction",
               "pose_source", "action_quality", "pose"}
SOURCE_KEYS = {"source_id", "source_detail", "license", "data_class", "root", "files",
               "deid_waiver", "deid_waiver_manifest"}
POSE = {"camera": (4, 4), "left_wrist": (4, 4), "right_wrist": (4, 4), "left_tips": (5, 3),
        "right_tips": (5, 3), "confidence_left": (), "confidence_right": ()}


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "store"
    pin_videos(monkeypatch, make_egodex(store))
    cfg = load_config(config_for(tmp_path))
    out = tmp_path / "work"
    api.ingest(register_egodex(store, cfg), out, cfg, store, "train")
    api.write_eb_poses(out)
    api.annotate(out, cfg)
    api.qa(out, cfg)
    return out


def test_the_files_da18_reads(work: Path) -> None:
    source = json.loads((work / "source.json").read_text())
    assert SOURCE_KEYS <= set(source) and source["source_detail"] == "egodex"
    assert source["deid_waiver"] and source["deid_waiver_manifest"] == "test-pin@000000000000"
    assert all(len(digest) == 64 for digest in source["files"].values())
    episodes = [Episode.model_validate_json(line)
                for line in (work / "episodes.jsonl").read_text().splitlines()]
    assert episodes and {e.source_kind for e in episodes} == {"egocentric"}
    reports = [QAReport.model_validate_json(line)
               for line in (work / "qa" / "egocentric.jsonl").read_text().splitlines()]
    assert {r.episode_id for r in reports} == {e.episode_id for e in episodes}

    for episode in episodes:
        folder = work / "egocentric" / episode.episode_id
        bundle = json.loads((folder / "bundle.json").read_text())
        assert BUNDLE_KEYS <= set(bundle) and bundle["pose"] == "pose.npz"
        assert bundle["fps"] == 30 and Path(bundle["hdf5"]).is_absolute()
        with np.load(folder / "pose.npz") as pose:
            frames = bundle["frames"]
            tracks = [name for name in pose.files if name != "intrinsic"]
            assert {name: pose[name].shape[1:] for name in tracks} == POSE
            assert {pose[name].shape[0] for name in tracks} == {frames}
            assert {pose[name].dtype for name in pose.files} == {np.dtype(np.float32)}
            # DA-18 asked 6/11/2026: an E-A episode has no HDF5 to read the intrinsic from.
            np.testing.assert_allclose(pose["intrinsic"], bundle["intrinsic"], rtol=1e-6)
        table = pq.read_table(folder / "segments.parquet")
        assert table.column_names == [*SEGMENT_SCHEMA.names, "frame_start", "frame_end"]
        rows = table.to_pylist()
        assert rows[0]["frame_start"] == 0 and rows[-1]["frame_end"] == frames
        assert all(a["frame_end"] == b["frame_start"] for a, b in zip(rows, rows[1:]))
