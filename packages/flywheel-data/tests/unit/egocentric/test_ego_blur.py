"""DA-04 subtask 8: `fw egocentric deid` covers faces before any other step (AC 2, NFR13).

The detector is a fake that knows where the face is; the real YuNet run is in
docs/g0/egocentric.md section 3. CPU only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from ego_data import FRAMES, K, make_videos, synthetic_pose
from flywheel.contracts.entities import LedgerEntry
from flywheel.data import egocentric_cli
from flywheel.data.annotate.deid.blur import (
    BlurParams,
    Box,
    Frame,
    YuNet,
    deid_video,
    held_boxes,
    mosaic,
    pad_box,
)
from flywheel.data.annotate.deid.gate import DeidBlocked
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.episodes import POSE, bundle_dir, read_bundle, read_episodes
from flywheel.data.ingest.egocentric.pose import save_pose
from flywheel.data.ingest.egocentric.video_source import register_videos
from flywheel.store.paths import StorePaths
from typer.testing import CliRunner

cv2 = pytest.importorskip("cv2")
PARAMS = BlurParams(score_threshold=0.6, nms_threshold=0.3, detect_side_px=960, pad=0.0,
                    hold_frames=2, mosaic_cells=4)
FACE: Box = (16, 8, 24, 24)  # x, y, w, h inside a 64x36 frame
MODEL = {"name": "fake-face", "revision": "0", "sha256": "0", "runtime": "test"}


def face_frame(seed: int = 0) -> Frame:
    """A 64x36 frame: flat background, a sharp 'face' (noise with two dark eyes) in FACE."""
    frame = np.full((36, 64, 3), 120, dtype=np.uint8)
    x, y, w, h = FACE
    rng = np.random.default_rng(seed)
    frame[y:y + h, x:x + w] = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    cv2.circle(frame, (x + 7, y + 8), 3, (0, 0, 0), -1)
    cv2.circle(frame, (x + 17, y + 8), 3, (0, 0, 0), -1)
    return frame


class FaceWhereMarked:
    """A fake detector: FACE in every frame whose top-left pixel is white."""

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, frame: Frame) -> list[Box]:
        self.calls += 1
        return [FACE] if frame[:4, :4].mean() > 200 else []


def detail(frame: Frame) -> float:
    """Mean absolute difference of neighbouring pixels inside FACE: high when sharp."""
    x, y, w, h = FACE
    roi = frame[y:y + h, x:x + w].astype(np.float64)
    return float(np.abs(np.diff(roi, axis=1)).mean())


def test_a_face_in_a_synthetic_frame_is_covered_and_nothing_else() -> None:
    frame = face_frame()
    out = mosaic(frame, [FACE], PARAMS.mosaic_cells)
    x, y, w, h = FACE
    assert detail(out) < detail(frame) / 4  # the face is a smooth mosaic now
    outside = np.ones(frame.shape[:2], dtype=bool)
    outside[y:y + h, x:x + w] = False
    assert np.array_equal(out[outside], frame[outside])
    assert np.array_equal(frame, face_frame())  # the input is not touched


def test_boxes_grow_clip_and_hold_either_side() -> None:
    assert pad_box((10, 10, 20, 20), 0.25, 64, 36) == (5, 5, 30, 30)
    assert pad_box((50, 30, 20, 20), 0.5, 64, 36) == (40, 20, 24, 16)
    assert pad_box((70, 40, 5, 5), 0.0, 64, 36) is None
    held = held_boxes([[], [], [], [FACE], [], [], [], []], hold=2)
    assert [bool(b) for b in held] == [False, True, True, True, True, True, False, False]


def write_marked(path: Path, frames: int, marked: range) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (64, 36))
    for i in range(frames):
        frame = face_frame(i)
        if i in marked:
            frame[:4, :4] = 255
        writer.write(frame)
    writer.release()


def decoded(path: Path) -> list[Frame]:
    capture = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    return frames


def test_deid_video_covers_the_detections_and_their_hold(tmp_path: Path) -> None:
    raw, copy = tmp_path / "0.mp4", tmp_path / "0.deid.mp4"
    write_marked(raw, 20, range(8, 10))
    detector = FaceWhereMarked()
    video = deid_video(raw, copy, detector, PARAMS)
    assert detector.calls == 20
    assert (video.frames, video.width, video.height) == (20, 64, 36)
    assert (video.frames_with_faces, video.frames_blurred, video.detections) == (2, 6, 2)
    before, after = decoded(raw), decoded(copy)
    assert len(after) == 20
    covered = [detail(a) < detail(b) / 2 for a, b in zip(after, before)]
    assert covered == [6 <= i <= 11 for i in range(20)]  # 8, 9 and two frames each side
    assert not list(tmp_path.glob(".*tmp*"))


def test_a_face_model_with_another_sha256_is_refused(tmp_path: Path) -> None:
    model = tmp_path / "yunet.onnx"
    model.write_bytes(b"not the pinned model")
    with pytest.raises(ValueError, match="is not the pinned"):
        YuNet(model, "0" * 64, PARAMS)
    with pytest.raises(FileNotFoundError):
        YuNet(tmp_path / "missing.onnx", "0" * 64, PARAMS)


def blurred_work(tmp_path: Path, store: Path, cfg: EgoConfig) -> tuple[Path, Path]:
    work, root = tmp_path / "work", make_videos(tmp_path / "rec", frames=FRAMES)
    api.ingest(register_videos(root, cfg), work, cfg, store)
    done = api.deid(work, FaceWhereMarked(), PARAMS, MODEL)
    assert [d.copy for d in done] == ["two_table/0.deid.mp4"]
    return work, root


def test_deid_points_every_later_step_at_the_copy(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work, root = blurred_work(tmp_path, store, cfg)
    source = api.read_source(work)
    copy = root / "two_table" / "0.deid.mp4"
    assert source.deid_copies == {"two_table/0.deid.mp4":
                                  hashlib.sha256(copy.read_bytes()).hexdigest()}
    assert source.deid_method["model"] == MODEL and source.deid_method["status"] == "blurred"
    assert source.deid_method["videos"]["two_table/0.deid.mp4"]["raw"] == "two_table/0.mp4"
    assert set(source.files) == {"device.json", "two_table/0.mp4"}  # same source_id
    (episode,) = read_episodes(work)
    assert episode.deid_status == "blurred"
    bundle = read_bundle(work, episode.episode_id)
    assert bundle.mp4 == str(copy) and bundle.video_frames == FRAMES == bundle.frames
    (job,) = api.estimate_jobs(work, source)
    assert job["mp4"] == "two_table/0.deid.mp4"
    # past the gate: annotate cuts the episode once it has a pose
    save_pose(synthetic_pose(), bundle_dir(work, episode.episode_id) / POSE, K.astype(float))
    assert api.annotate(work, cfg)[episode.episode_id].segments
    (report,) = api.qa(work, cfg)
    assert {c.name: c.passed for c in report.checks}["deid_gate"]


def test_a_changed_or_missing_copy_is_refused(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work, root = blurred_work(tmp_path, store, cfg)
    copy = root / "two_table" / "0.deid.mp4"
    copy.write_bytes(copy.read_bytes() + b"\0")
    with pytest.raises(DeidBlocked, match="no de-identified copy with the sha256"):
        api.estimate_jobs(work, api.read_source(work))
    with pytest.raises(DeidBlocked):
        api.annotate(work, cfg)
    copy.unlink()
    with pytest.raises(DeidBlocked, match="two_table/0.mp4"):
        api.estimate_jobs(work, api.read_source(work))


def test_a_bundle_pointed_back_at_the_raw_video_is_refused(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work, root = blurred_work(tmp_path, store, cfg)
    (episode,) = read_episodes(work)
    path = bundle_dir(work, episode.episode_id) / "bundle.json"
    data = json.loads(path.read_text())
    data["mp4"] = str(root / "two_table" / "0.mp4")
    path.write_text(json.dumps(data))
    with pytest.raises(DeidBlocked, match="not a de-identified copy"):
        api.estimate_jobs(work, api.read_source(work))


def test_ingesting_again_makes_the_source_raw_again(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work, root = blurred_work(tmp_path, store, cfg)
    record = register_videos(root, cfg)
    assert set(record.files) == {"device.json", "two_table/0.mp4"}  # the copy is not a take
    api.ingest(record, work, cfg, store)
    assert read_episodes(work)[0].deid_status == "raw"
    with pytest.raises(DeidBlocked, match="not waived"):
        api.estimate_jobs(work, api.read_source(work))


def test_a_size_other_than_the_device_file_is_refused(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work, root = tmp_path / "work", make_videos(tmp_path / "rec")
    device = json.loads((root / "device.json").read_text())
    (root / "device.json").write_text(json.dumps({**device, "width": 36, "height": 64}))
    api.ingest(register_videos(root, cfg), work, cfg, store)
    with pytest.raises(ValueError, match="64x36 after OpenCV's rotation"):
        api.deid(work, FaceWhereMarked(), PARAMS, MODEL)
    assert read_episodes(work)[0].deid_status == "raw"
    assert not api.read_source(work).deid_copies


def test_a_waived_egodex_source_is_left_as_it_is(store: Path, cfg: EgoConfig) -> None:
    from flywheel.data.ingest.egocentric.source import register_egodex

    work = store / "w"
    api.ingest(register_egodex(store, cfg), work, cfg, store)
    assert api.deid(work, FaceWhereMarked(), PARAMS, MODEL) == []
    assert all(e.deid_status == "raw" for e in read_episodes(work))


runner = CliRunner()


def test_fw_egocentric_deid_then_pose_job(
    tmp_path: Path, store: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = ["--config", str(config_path)]
    root = make_videos(tmp_path / "rec")
    result = runner.invoke(egocentric_cli.app, ["ingest", "video", "--root", str(root), *config])
    assert result.exit_code == 0, result.output
    work = result.output.split("work: ")[1].split()[0]
    refused = runner.invoke(egocentric_cli.app, ["deid", work, *config])
    assert refused.exit_code == 2 and "no face model; fetch it once" in refused.output
    monkeypatch.setattr(egocentric_cli, "_detector", lambda cfg: FaceWhereMarked())
    result = runner.invoke(egocentric_cli.app, ["deid", work, *config])
    assert result.exit_code == 0, result.output
    assert "1 videos blurred" in result.output
    jobs = tmp_path / "jobs.json"
    result = runner.invoke(egocentric_cli.app, ["pose", work, "--job", str(jobs)])
    assert result.exit_code == 0, result.output
    assert json.loads(jobs.read_text())[0]["mp4"] == "two_table/0.deid.mp4"
    rows = [LedgerEntry.model_validate_json(line)
            for path in sorted(StorePaths(store).runs_dir.glob("*/*/ledger.jsonl"))
            for line in path.read_text().splitlines()]
    deid_rows = [r for r in rows if "ego_deid" in r.model_dump_json()]
    assert len(deid_rows) == 4  # the refused job and the run, each estimate + measured
