"""LeRobot v2.1 reader and writer (DA-03 task 1, AC 1; plan 3/11 section 7)."""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from flywheel.data.ingest.lerobot import (
    EpisodeFrames,
    LeRobotFormatError,
    iter_episodes,
    mp4_frame_count,
    read_info,
    write_episode,
)

CAMERA = "observation.images.egocentric"
Factory = Callable[[Path, list[int]], list[EpisodeFrames]]


def parquet(root: Path, index: int) -> Path:
    return root / "data" / "chunk-000" / f"episode_{index:06d}.parquet"


def assert_same(a: EpisodeFrames, b: EpisodeFrames) -> None:
    assert a.episode_index == b.episode_index
    assert a.task == b.task
    assert a.video_frames == b.video_frames
    for name in ("timestamp", "frame_index", "states", "action"):
        x, y = getattr(a, name), getattr(b, name)
        assert x.dtype == y.dtype, name
        assert x.shape == y.shape, name
        np.testing.assert_array_equal(x, y, err_msg=name)


def test_read_info_returns_info_json(dataset: tuple[Path, list[EpisodeFrames]]) -> None:
    root, _ = dataset
    info = read_info(root)
    assert info["codebase_version"] == "v2.1"
    assert info["fps"] == 50
    assert info["total_episodes"] == 3
    assert info["total_frames"] == 15
    assert info["total_tasks"] == 1


def test_read_info_names_the_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="info.json"):
        read_info(tmp_path)


def test_read_info_rejects_another_codebase_version(tmp_path: Path) -> None:
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "info.json").write_text(json.dumps({"codebase_version": "v3.0"}))
    with pytest.raises(LeRobotFormatError, match="v3.0"):
        read_info(tmp_path)


def test_three_episodes_read_with_psi0_shapes(dataset: tuple[Path, list[EpisodeFrames]]) -> None:
    root, _ = dataset
    episodes = list(iter_episodes(root))
    assert [e.episode_index for e in episodes] == [0, 1, 2]
    for frames, length in zip(episodes, [5, 7, 3]):
        assert frames.timestamp.shape == (length,) and frames.timestamp.dtype == np.float64
        assert frames.frame_index.shape == (length,) and frames.frame_index.dtype == np.int64
        assert frames.states.shape == (length, 32) and frames.states.dtype == np.float32
        assert frames.action.shape == (length, 36) and frames.action.dtype == np.float32
        assert frames.video_frames == {CAMERA: length}
        assert frames.task.startswith("pick up the cracker box")


def test_write_then_read_is_equal_value_by_value(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, written = dataset
    for a, b in zip(written, iter_episodes(root), strict=True):
        assert_same(a, b)


def test_rewriting_an_episode_round_trips_and_keeps_the_others(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, written = dataset
    first = next(iter_episodes(root))
    # A frame drop as DA-27 injects it: two rows go, the video keeps its frames.
    keep = np.array([0, 1, 4])
    dropped = replace(
        first,
        timestamp=first.timestamp[keep],
        frame_index=first.frame_index[keep],
        states=first.states[keep],
        action=first.action[keep],
    )
    write_episode(root, dropped)
    again = list(iter_episodes(root))
    assert_same(again[0], dropped)
    assert again[0].video_frames == {CAMERA: 5}
    assert_same(again[1], written[1])
    assert_same(again[2], written[2])
    info = read_info(root)
    assert info["total_episodes"] == 3
    assert info["total_frames"] == 3 + 7 + 3


def test_global_index_follows_episode_order(dataset: tuple[Path, list[EpisodeFrames]]) -> None:
    root, _ = dataset
    index = pq.read_table(parquet(root, 2)).column("index").to_pylist()
    assert index == [12, 13, 14]


def test_a_new_task_is_appended_to_tasks_jsonl(tmp_path: Path, dataset_factory: Factory) -> None:
    root = tmp_path / "ds"
    frames = dataset_factory(root, [2])[0]
    write_episode(root, replace(frames, episode_index=1, task="wave at table2"))
    tasks = [json.loads(line) for line in (root / "meta" / "tasks.jsonl").read_text().splitlines()]
    assert [t["task"] for t in tasks] == [frames.task, "wave at table2"]
    assert [e.task for e in iter_episodes(root)] == [frames.task, "wave at table2"]


def test_zero_and_one_frame_episodes_read_without_error(
    tmp_path: Path, dataset_factory: Factory
) -> None:
    root = tmp_path / "short"
    written = dataset_factory(root, [0, 1])
    episodes = list(iter_episodes(root))
    assert episodes[0].states.shape == (0, 32)
    assert episodes[0].action.shape == (0, 36)
    assert episodes[0].timestamp.shape == (0,)
    assert episodes[1].action.shape == (1, 36)
    for a, b in zip(written, episodes, strict=True):
        assert_same(a, b)


def test_missing_video_file_reads_as_zero_frames(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    video(root, 1).unlink()
    counts = [e.video_frames for e in iter_episodes(root)]
    assert counts == [{CAMERA: 5}, {CAMERA: 0}, {CAMERA: 3}]


def video(root: Path, index: int) -> Path:
    return root / "videos" / "chunk-000" / "egocentric" / f"episode_{index:06d}.mp4"


def test_video_count_comes_from_the_mp4_not_the_meta(
    dataset: tuple[Path, list[EpisodeFrames]], mp4: Callable[..., None]
) -> None:
    # Review #69 point 6: a count copied from `length` could never disagree with the rows.
    root, _ = dataset
    mp4(video(root, 0), 9)
    assert next(iter_episodes(root)).video_frames == {CAMERA: 9}


def test_mp4_frame_count_reads_large_boxes_and_stz2(tmp_path: Path) -> None:
    hdlr = struct.pack(">I4s", 33, b"hdlr") + bytes(8) + b"vide" + bytes(12) + b"\0"
    stz2 = struct.pack(">I4s", 20, b"stz2") + bytes(4) + struct.pack(">II", 8, 4)
    stbl = struct.pack(">I4s", 8 + len(stz2), b"stbl") + stz2
    minf = struct.pack(">I4s", 8 + len(stbl), b"minf") + stbl
    mdia_payload = hdlr + minf
    # size 1: the real size follows as a 64-bit largesize
    mdia = struct.pack(">I4sQ", 1, b"mdia", 16 + len(mdia_payload)) + mdia_payload
    trak = struct.pack(">I4s", 8 + len(mdia), b"trak") + mdia
    moov = struct.pack(">I4s", 8 + len(trak), b"moov") + trak
    path = tmp_path / "large.mp4"
    path.write_bytes(moov)
    assert mp4_frame_count(path) == 4


@pytest.mark.parametrize(
    "content, reason",
    [
        (b"\x00not a real mp4", "broken mp4 box"),
        (b"", "no moov box"),
        (b"\x00\x00\x00\x10moov\x00\x00\x00\x08mvex", "fragmented"),
        (b"\x00\x00\x00\x08moov", "no video track"),
        (b"\x00\x00\x00\x40moov", "broken mp4 box"),
    ],
)
def test_an_mp4_the_reader_cannot_walk_is_named(
    tmp_path: Path, content: bytes, reason: str
) -> None:
    path = tmp_path / "bad.mp4"
    path.write_bytes(content)
    with pytest.raises(LeRobotFormatError, match=reason) as err:
        mp4_frame_count(path)
    assert str(path) in str(err.value)


def test_write_episode_keeps_meta_it_does_not_own(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    # Review #69 point 7: no new keys in episodes.jsonl, tasks.jsonl rows unchanged.
    root, _ = dataset
    tasks = root / "meta" / "tasks.jsonl"
    rows = [json.loads(line) for line in tasks.read_text().splitlines()]
    rows[0] |= {"category": "", "description": "as the authors wrote it"}
    tasks.write_text("".join(json.dumps(r) + "\n" for r in rows))
    write_episode(root, next(iter_episodes(root)))
    assert [json.loads(line) for line in tasks.read_text().splitlines()] == rows
    episodes = (root / "meta" / "episodes.jsonl").read_text().splitlines()
    assert all("video_frames" not in json.loads(line) for line in episodes)


def _rewrite(path: Path, edit: Callable[[pa.Table], pa.Table]) -> None:
    pq.write_table(edit(pq.read_table(path)), path)


def test_missing_action_column_names_file_and_column(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    path = parquet(root, 1)
    _rewrite(path, lambda t: t.drop_columns(["action"]))
    with pytest.raises(LeRobotFormatError) as err:
        list(iter_episodes(root))
    assert str(path) in str(err.value) and "'action'" in str(err.value)


def test_missing_states_column_names_file_and_column(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    path = parquet(root, 0)
    _rewrite(path, lambda t: t.drop_columns(["states"]))
    with pytest.raises(LeRobotFormatError) as err:
        list(iter_episodes(root))
    assert str(path) in str(err.value) and "'states'" in str(err.value)


@pytest.mark.parametrize("column, width", [("action", 35), ("states", 36)])
def test_wrong_width_names_file_and_column(
    dataset: tuple[Path, list[EpisodeFrames]], column: str, width: int
) -> None:
    root, _ = dataset
    path = parquet(root, 2)

    def widen(table: pa.Table) -> pa.Table:
        values = np.zeros((table.num_rows, width), dtype=np.float32).tolist()
        position = table.schema.get_field_index(column)
        return table.set_column(position, column, pa.array(values, pa.list_(pa.float32())))

    _rewrite(path, widen)
    with pytest.raises(LeRobotFormatError) as err:
        list(iter_episodes(root))
    message = str(err.value)
    assert str(path) in message and f"'{column}'" in message and str(width) in message


def test_ragged_action_rows_are_a_width_error(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    path = parquet(root, 0)

    def ragged(table: pa.Table) -> pa.Table:
        rows = [[0.0] * 36 for _ in range(table.num_rows)]
        rows[2] = [0.0] * 30
        position = table.schema.get_field_index("action")
        return table.set_column(position, "action", pa.array(rows, pa.list_(pa.float32())))

    _rewrite(path, ragged)
    with pytest.raises(LeRobotFormatError, match="'action'"):
        list(iter_episodes(root))


def test_parquet_listed_in_meta_but_absent_is_named(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    parquet(root, 1).unlink()
    with pytest.raises(FileNotFoundError, match="episode_000001.parquet"):
        list(iter_episodes(root))


def test_write_episode_refuses_wrong_widths(dataset: tuple[Path, list[EpisodeFrames]]) -> None:
    root, written = dataset
    bad = replace(written[0], action=written[0].action[:, :35])
    with pytest.raises(LeRobotFormatError, match="'action'"):
        write_episode(root, bad)


def test_write_episode_carries_unowned_columns_by_frame_index(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    path = parquet(root, 0)
    hands = [[float(i)] * 14 for i in range(5)]
    _rewrite(path, lambda t: t.append_column("observation.hand_joints", pa.array(hands)))
    first = next(iter_episodes(root))
    keep = np.array([1, 3])
    write_episode(
        root,
        replace(
            first,
            timestamp=first.timestamp[keep],
            frame_index=first.frame_index[keep],
            states=first.states[keep],
            action=first.action[keep],
        ),
    )
    carried = pq.read_table(path).column("observation.hand_joints").to_pylist()
    assert carried == [hands[1], hands[3]]


def test_rewriting_an_unchanged_psi0_parquet_gives_the_same_table(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    # Psi0's postprocess stores float64 lists and timestamp, observation.* first,
    # whatever info.json declares (measured on psi-data e78fb93 and tray S1).
    root, _ = dataset
    path = parquet(root, 1)
    table = pq.read_table(path)
    psi0 = pa.table(
        {
            "observation.prev_height": pa.array([[0.74]] * table.num_rows, pa.list_(pa.float64())),
            **{n: table.column(n) for n in table.column_names},
        }
    )
    psi0 = psi0.cast(
        pa.schema(
            [
                pa.field(f.name, pa.list_(pa.float64()))
                if f.name in ("states", "action")
                else pa.field(f.name, pa.float64())
                if f.name == "timestamp"
                else f
                for f in psi0.schema
            ]
        )
    )
    pq.write_table(psi0, path)
    frames = list(iter_episodes(root))[1]
    write_episode(root, frames)
    assert pq.read_table(path).equals(psi0)


def test_the_lane_api_exposes_the_reader() -> None:
    from flywheel.data import api

    assert api.iter_episodes is iter_episodes
    assert api.write_episode is write_episode
    assert api.read_info is read_info
    assert api.EpisodeFrames is EpisodeFrames


@pytest.mark.parametrize("column", ["action", "states"])
def test_float64_values_that_float32_rounds_are_refused(
    dataset: tuple[Path, list[EpisodeFrames]], column: str
) -> None:
    # Review #69 point 2: 0.1 read as float32 is 0.10000000149; never round silently.
    root, _ = dataset
    path = parquet(root, 0)
    width = 36 if column == "action" else 32

    def precise(table: pa.Table) -> pa.Table:
        values = np.full((table.num_rows, width), 0.1).tolist()
        position = table.schema.get_field_index(column)
        return table.set_column(position, column, pa.array(values, pa.list_(pa.float64())))

    _rewrite(path, precise)
    with pytest.raises(LeRobotFormatError) as err:
        list(iter_episodes(root))
    message = str(err.value)
    assert str(path) in message and f"'{column}'" in message
    assert f"{5 * width} of {5 * width} values change" in message and "float32" in message


def test_float64_values_exact_in_float32_read_unchanged(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    # psi-data and tray S1 store float32-exact values as float64 (rtx3060, 3/11).
    root, written = dataset
    path = parquet(root, 0)
    table = pq.read_table(path)
    position = table.schema.get_field_index("action")
    wide = table.column("action").cast(pa.list_(pa.float64()))
    pq.write_table(table.set_column(position, "action", wide), path)
    np.testing.assert_array_equal(next(iter_episodes(root)).action, written[0].action)


def test_nan_survives_the_cast_and_is_left_to_qa(
    dataset: tuple[Path, list[EpisodeFrames]],
) -> None:
    root, _ = dataset
    path = parquet(root, 0)

    def with_nan(table: pa.Table) -> pa.Table:
        values = np.zeros((table.num_rows, 36))
        values[1, 3] = np.nan
        position = table.schema.get_field_index("action")
        nan = pa.array(values.tolist(), pa.list_(pa.float64()))
        return table.set_column(position, "action", nan)

    _rewrite(path, with_nan)
    assert np.isnan(next(iter_episodes(root)).action[1, 3])


def test_fractional_frame_index_is_refused(dataset: tuple[Path, list[EpisodeFrames]]) -> None:
    root, _ = dataset
    path = parquet(root, 2)

    def fractional(table: pa.Table) -> pa.Table:
        position = table.schema.get_field_index("frame_index")
        return table.set_column(position, "frame_index", pa.array([0.0, 1.5, 2.0]))

    _rewrite(path, fractional)
    with pytest.raises(LeRobotFormatError, match="'frame_index'.*1 of 3 values change"):
        list(iter_episodes(root))
