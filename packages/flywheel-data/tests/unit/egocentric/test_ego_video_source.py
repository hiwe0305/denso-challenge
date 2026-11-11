"""DA-04 task 7: EgoVideoSource, the team's recordings through the same pipeline (AC 6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ego_data import make_videos
from flywheel.data.annotate.deid.gate import DeidBlocked
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import read_bundle, read_episodes
from flywheel.data.ingest.egocentric.video_source import read_device, register_videos


def test_a_recording_root_registers_as_public_without_a_waiver(
    tmp_path: Path, cfg: EgoConfig
) -> None:
    record = register_videos(make_videos(tmp_path / "rec"), cfg)
    assert record.source_detail == "ego_video" and record.data_class == "public"
    assert record.deid_waiver is None
    assert [(e.task, e.index, e.hdf5) for e in record.episodes] == [("two_table", 0, None)]
    assert set(record.files) == {"device.json", "two_table/0.mp4"}


def test_ingest_gives_pseudo_episodes_that_wait_for_ea(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work = tmp_path / "work"
    record = register_videos(make_videos(tmp_path / "rec"), cfg)
    (episode,) = api.ingest(record, work, cfg, store, "train")
    assert episode.source_kind == "egocentric" and episode.action_quality == "pseudo"
    bundle = read_bundle(work, episode.episode_id)
    assert bundle.hdf5 is None and bundle.pose_source == "E-A" and bundle.frames == 60
    assert bundle.instruction == "pick the cup and place it on the other table"
    assert bundle.image_size == (64, 36)
    assert read_episodes(work) == [episode]


def test_the_gate_stops_the_recordings_before_pose_and_annotate(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work = tmp_path / "work"
    record = register_videos(make_videos(tmp_path / "rec"), cfg)
    api.ingest(record, work, cfg, store, "train")
    with pytest.raises(DeidBlocked, match="ego_video"):
        api.estimate_jobs(work, api.read_source(work))
    with pytest.raises(DeidBlocked):
        api.annotate(work, cfg)


@pytest.mark.parametrize("edit", [{"drop": "intrinsic"}, {"intrinsic": [[1, 0], [0, 1]]}])
def test_a_bad_device_file_is_refused(tmp_path: Path, edit: dict[str, object]) -> None:
    root = make_videos(tmp_path / "rec")
    device = json.loads((root / "device.json").read_text())
    if "drop" in edit:
        device.pop(str(edit["drop"]))
    else:
        device.update(edit)
    (root / "device.json").write_text(json.dumps(device))
    with pytest.raises(ValueError, match="intrinsic"):
        read_device(root)


def test_a_root_without_recordings_is_refused(tmp_path: Path, cfg: EgoConfig) -> None:
    root = make_videos(tmp_path / "rec")
    (root / "two_table" / "0.mp4").rename(root / "two_table" / "take.mp4")
    with pytest.raises(ValueError, match="no <task>/<i>.mp4"):
        register_videos(root, cfg)
