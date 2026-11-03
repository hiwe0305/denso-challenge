"""Points 1-6 of the LeRobot v2.1 checklist (DA-02 AC 1; design 6.4; plan 3/11 section 7)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from checklist_data import (
    CAMERA,
    FPS,
    edit_json,
    edit_jsonl,
    frames_of,
    g1_layout,
    make_tray_dataset,
    video_path,
    write_mp4,
)
from flywheel.contracts.artifacts import ActionLayout, QACheck
from flywheel.data.export import checklist
from flywheel.data.export.checklist import check_lerobot_v21, mp4_sample_entry, run_checklist
from flywheel.data.ingest.lerobot import write_episode
from flywheel.data.inject.stats import stats_block, write_stats

EVERY_CHECK = [
    "v21.1.info.codebase_version", "v21.1.info.fps", "v21.1.info.robot_type",
    "v21.1.info.action_shape", "v21.1.info.action_names", "v21.1.read",
    "v21.2.index.episode_index", "v21.2.index.index", "v21.2.index.frame_index",
    "v21.3.timestamp",
    "v21.4.video.frames", "v21.4.video.codec", "v21.4.video.resolution",
    "v21.5.tasks",
    "v21.6.stats.file", "v21.6.stats.finite", "v21.6.stats.release", "v21.6.stats.constant",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_tray_dataset(tmp_path / "tray")


def set_column(path: Path, name: str, values: Any) -> None:
    """Replace one column of a parquet in place, as a broken export would leave it."""
    table = pq.read_table(path)
    table = table.set_column(table.column_names.index(name), name, pa.array(values))
    pq.write_table(table, path)


def checks(root: Path, layout: ActionLayout | None = None) -> dict[str, QACheck]:
    return {c.name: c for c in check_lerobot_v21(root, layout or g1_layout())}


def failed(root: Path, layout: ActionLayout | None = None) -> list[str]:
    return [name for name, c in checks(root, layout).items() if not c.passed]


def test_a_correct_tray_dataset_passes_all_six_points(root: Path) -> None:
    result = checks(root)
    assert list(result) == EVERY_CHECK
    assert [n for n, c in result.items() if not c.passed] == []
    points = {f.point for f in run_checklist(root, g1_layout())}
    assert points == {1, 2, 3, 4, 5, 6}


def test_every_finding_carries_a_design_10_code(root: Path) -> None:
    codes = {f.check.name: f.code for f in run_checklist(root, g1_layout())}
    assert codes["v21.1.info.action_shape"] == "D1"
    assert codes["v21.3.timestamp"] == "D2"
    assert codes["v21.5.tasks"] == "D6"
    assert codes["v21.6.stats.release"] == "D4"


# Point 1


def test_a_declared_action_width_other_than_the_layout_fails(root: Path) -> None:
    edit_json(root / "meta/info.json", lambda i: i["features"]["action"].update(shape=[37]))
    result = checks(root)
    assert result["v21.1.info.action_shape"].value == 1
    assert failed(root) == ["v21.1.info.action_shape"]


def test_a_parquet_action_wider_than_the_layout_fails_the_read(root: Path) -> None:
    path = root / "data/chunk-000/episode_000001.parquet"
    wide = [row + [0.0] for row in pq.read_table(path).column("action").to_pylist()]
    set_column(path, "action", pa.array(wide, pa.list_(pa.float64())))
    findings = {f.check.name: f for f in run_checklist(root, g1_layout())}
    assert not findings["v21.1.read"].check.passed
    assert "'action' has width [37], expected 36" in findings["v21.1.read"].detail
    # The reader refused the data, so points 2-6 are not run on it.
    assert max(f.point for f in findings.values()) == 1


def test_codebase_version_fps_and_robot_type_are_checked(root: Path) -> None:
    edit_json(root / "meta/info.json", lambda i: i.update(robot_type=""))
    assert failed(root) == ["v21.1.info.robot_type"]
    edit_json(root / "meta/info.json", lambda i: i.update(fps=0))
    assert checks(root)["v21.1.info.fps"].passed is False
    edit_json(root / "meta/info.json", lambda i: i.update(codebase_version="v3.0"))
    assert checks(root)["v21.1.info.codebase_version"].passed is False
    assert "v21.1.read" not in checks(root)


def test_action_names_that_differ_from_the_layout_fail(root: Path) -> None:
    def swap(data: dict[str, Any]) -> None:
        dims = data["dimensions"]
        dims[32]["name"], dims[33]["name"] = dims[33]["name"], dims[32]["name"]

    edit_json(root / "meta/action_layout.json", swap)
    finding = {f.check.name: f for f in run_checklist(root, g1_layout())}["v21.1.info.action_names"]
    assert finding.check.value == 2
    assert "32: 'navigate.vy' != 'navigate.vx'" in finding.detail


def test_names_in_info_json_win_over_the_export_file(root: Path) -> None:
    names = [d.name for d in g1_layout().dimensions]
    edit_json(root / "meta/info.json",
              lambda i: i["features"]["action"].update(shape=[36], names=names[::-1]))
    assert checks(root)["v21.1.info.action_names"].value == 36


def test_undeclared_names_are_reported_not_failed(root: Path) -> None:
    (root / "meta/action_layout.json").unlink()
    finding = {f.check.name: f for f in run_checklist(root, g1_layout())}["v21.1.info.action_names"]
    assert finding.check.passed
    assert "no per-dimension action names declared" in finding.detail


# Point 2


def test_frame_index_not_starting_at_zero_fails(root: Path) -> None:
    set_column(root / "data/chunk-000/episode_000001.parquet", "frame_index", np.arange(1, 10))
    result = checks(root)
    assert result["v21.2.index.frame_index"].value == 9
    assert "v21.2.index.frame_index" in failed(root)


def test_an_index_off_the_running_row_count_fails(root: Path) -> None:
    # psi-data e78fb93 and tray S1 start episode i at 2 x dataset_from_index (DA-03 Q7).
    path = root / "data/chunk-000/episode_000002.parquet"
    set_column(path, "index", pq.read_table(path).column("index").to_numpy() * 2)
    finding = {f.check.name: f for f in run_checklist(root, g1_layout())}["v21.2.index.index"]
    assert finding.check.value == 4
    assert "episode 2 starts at 30, expected 15" in finding.detail


def test_meta_episodes_must_be_numbered_from_zero(root: Path) -> None:
    rows = (root / "meta/episodes.jsonl").read_text().splitlines()
    (root / "meta/episodes.jsonl").write_text("\n".join(rows[:1] + rows[2:]) + "\n")
    assert checks(root)["v21.2.index.episode_index"].value == 1


# Point 3


def test_a_timestamp_off_by_more_than_half_a_period_fails(root: Path) -> None:
    frames = frames_of(0, 6)
    late = replace(frames, timestamp=frames.timestamp + 0.6 / FPS)
    write_episode(root, late)
    result = checks(root)
    assert result["v21.3.timestamp"].value == pytest.approx(0.6, abs=1e-5)
    assert failed(root) == ["v21.3.timestamp"]


def test_a_timestamp_inside_half_a_period_passes(root: Path) -> None:
    frames = frames_of(0, 6)
    early = replace(frames, timestamp=frames.timestamp + 0.4 / FPS)
    write_episode(root, early)
    assert checks(root)["v21.3.timestamp"].passed


# Point 4


def test_video_frames_other_than_the_rows_fail(root: Path) -> None:
    write_mp4(video_path(root, 1), 8)
    assert checks(root)["v21.4.video.frames"].value == 1
    video_path(root, 2).unlink()
    assert checks(root)["v21.4.video.frames"].value == 4


def test_codec_and_size_are_read_from_the_sample_entry(root: Path) -> None:
    assert mp4_sample_entry(video_path(root, 0)) == ("h264", 640, 360)
    write_mp4(video_path(root, 0), 6, codec=b"av01", width=320, height=180)
    assert mp4_sample_entry(video_path(root, 0)) == ("av1", 320, 180)


def test_a_video_size_other_than_declared_fails(root: Path) -> None:
    write_mp4(video_path(root, 0), 6, width=320, height=180)
    assert failed(root) == ["v21.4.video.resolution"]


def test_a_codec_other_than_declared_fails_and_an_undeclared_one_passes(root: Path) -> None:
    write_mp4(video_path(root, 2), 4, codec=b"av01")
    assert checks(root)["v21.4.video.codec"].passed  # video_info is empty, as in SIMPLE's
    edit_json(root / "meta/info.json",
              lambda i: i["features"][CAMERA].update(video_info={"video.codec": "h264"}))
    assert checks(root)["v21.4.video.codec"].value == 1


# Point 5


def test_an_episode_without_tasks_fails(root: Path) -> None:
    def drop(row: dict[str, Any]) -> None:
        if row["episode_index"] == 1:
            row["tasks"] = []

    edit_jsonl(root / "meta/episodes.jsonl", drop)
    assert failed(root) == ["v21.5.tasks"]
    assert checks(root)["v21.5.tasks"].value == 1


def test_a_task_index_missing_from_tasks_jsonl_fails(root: Path) -> None:
    edit_jsonl(root / "meta/tasks.jsonl", lambda r: r.update(task=" "))
    assert checks(root)["v21.5.tasks"].value == 3


# Point 6


def test_stats_with_nan_fail(root: Path) -> None:
    def poison(stats: dict[str, Any]) -> None:
        stats["action"]["mean"][3] = float("nan")

    edit_json(root / "meta/stats_psi0.json", poison)
    assert json.loads((root / "meta/stats_psi0.json").read_text())["action"]["mean"][3] != 0
    result = checks(root)
    assert result["v21.6.stats.finite"].value == 1
    assert not result["v21.6.stats.release"].passed
    assert failed(root) == ["v21.6.stats.finite", "v21.6.stats.release"]


def test_stats_not_computed_on_this_release_fail(root: Path) -> None:
    frames = frames_of(1, 9)
    write_episode(root, replace(frames, action=frames.action * np.float32(2.0)))
    finding = {f.check.name: f for f in run_checklist(root, g1_layout())}["v21.6.stats.release"]
    assert not finding.check.passed
    write_stats(root)
    assert checks(root)["v21.6.stats.release"].passed


def test_a_missing_stats_file_or_block_fails(root: Path) -> None:
    edit_json(root / "meta/stats_psi0.json", lambda s: s["states"].pop("max"))
    assert failed(root) == ["v21.6.stats.file"]
    (root / "meta/stats_psi0.json").unlink()
    assert failed(root) == ["v21.6.stats.file"]


def test_a_masked_constant_dim_is_no_stats_error(tmp_path: Path) -> None:
    # Plan 3/11 section 7: a masked action dim with std 0 gives no stats error.
    root = make_tray_dataset(tmp_path / "masked")
    for index, length in enumerate((6, 9, 4)):
        frames = frames_of(index, length)
        frames.action[:, 5] = 0.0
        write_episode(root, frames)
    write_stats(root)
    stats = json.loads((root / "meta/stats_psi0.json").read_text())["action"]
    assert stats["std"][5] == 0.0
    dims = list(g1_layout().dimensions)
    dims[5] = dims[5].model_copy(update={"masked": True})
    layout = ActionLayout(dimensions=dims)
    assert failed(root, layout) == []
    finding = {f.check.name: f for f in run_checklist(root, layout)}["v21.6.stats.constant"]
    assert "constant action dims [5, 31] (masked [5])" in finding.detail


def test_constant_dims_come_from_min_and_max_not_std(root: Path) -> None:
    # Dim 31 is 0.74 in every frame, yet SIMPLE's float32 stats give it a std above 0
    # (3.6e-4 on psi-data e78fb93): only min == max tells, as Psi0's normalizer does.
    stats = json.loads((root / "meta/stats_psi0.json").read_text())["action"]
    assert checklist.constant_dims(stats) == [31]
    block = {"min": [0.0, 1.0, 0.74], "max": [0.5, 1.0, 0.74 + 1e-6]}
    assert checklist.constant_dims(block) == [1, 2]


def test_an_unmasked_constant_dim_fails_once_undeclared_constants_are_errors(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert checks(root)["v21.6.stats.constant"].passed
    monkeypatch.setattr(checklist, "UNDECLARED_CONSTANT_IS_ERROR", True)
    assert checks(root)["v21.6.stats.constant"].value == 1


def test_stats_in_either_precision_count_as_computed_on_the_release(tmp_path: Path) -> None:
    # SIMPLE writes states stats in float64 and action stats in float32; over many frames
    # float32 accumulation moves a mean by more than the tolerance (7.7e-4 on tray S1).
    root = make_tray_dataset(tmp_path / "long", lengths=(30000,))
    states = pq.read_table(root / "data/chunk-000/episode_000000.parquet").column("states")
    values = np.asarray(states.to_pylist(), dtype=np.float32)
    in32, in64 = stats_block(values), stats_block(values.astype(np.float64))
    assert np.abs(np.subtract(in32["mean"], in64["mean"])).max() > checklist.STATS_TOLERANCE
    shifted = {**in64, "mean": [m + 1e-3 for m in in64["mean"]]}
    for block, passes in ((in32, True), (in64, True), (shifted, False)):
        stats = json.loads((root / "meta/stats_psi0.json").read_text())
        (root / "meta/stats_psi0.json").write_text(json.dumps({**stats, "states": block}))
        assert checks(root)["v21.6.stats.release"].passed is passes
