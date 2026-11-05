"""Episode selection, staging and action layout of the Psi0 export; no simulator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel_simple.tray.export import (
    action_layout,
    check_one_planner_version,
    export_psi0,
    kept_episodes,
    stage_shard,
    state_names,
)

LEFT_HAND = [f"left_hand_{f}_joint" for f in
             ("thumb_0", "thumb_1", "thumb_2", "index_0", "index_1", "middle_0", "middle_1")]
RIGHT_HAND = [n.replace("left", "right") for n in LEFT_HAND]
# Stand-in for SIMPLE g1_sonic WHOLE_BODY_JOINTS: legs 12, waist (yaw, roll, pitch), arms 7 + 7,
# hands.
NAMES_43 = (
    [f"leg_{i}" for i in range(12)]
    + ["waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"]
    + [f"left_arm_{i}" for i in range(7)]
    + [f"right_arm_{i}" for i in range(7)]
    + LEFT_HAND
    + RIGHT_HAND
)


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _shard(
    root: Path,
    gen: list[tuple[int, str]],
    replay: list[tuple[int, bool]] | None,
    name: str = "shard-00",
    planner: str = "p5",
) -> Path:
    """A shard whose log records episodes with these minimal-QA results and replay verdicts."""
    shard = root / name
    row = {"recorded": True, "planner_version": planner}
    _jsonl(shard / "gen_log.jsonl", [
        {**row, "seed": 100 + e, "episode_index": e, "qa": qa} for e, qa in gen
    ] + [{"seed": 99, "recorded": False, "episode_index": None, "qa": "not_recorded",
          "planner_version": "unrecorded"}])
    if replay is not None:
        _jsonl(shard / "replay" / "replay_qa.jsonl", [
            {"episode": e, "seed": 100 + e, "passed": ok} for e, ok in replay
        ])
    return shard


def test_one_planner_version_per_release(tmp_path: Path) -> None:
    a = _shard(tmp_path, [(0, "pass")], [(0, True)])
    b = _shard(tmp_path, [(0, "pass")], [(0, True)], name="shard-01")
    # the unrecorded attempts carry another version: they are not released
    assert check_one_planner_version([a, b]) == "p5"
    c = _shard(tmp_path, [(0, "pass")], [(0, True)], name="shard-02", planner="p4")
    with pytest.raises(ValueError, match=r"\['p4', 'p5'\]"):
        check_one_planner_version([a, b, c])


def test_export_refuses_a_batch_of_two_planner_versions_before_staging(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    _shard(batch, [(0, "pass")], [(0, True)], planner="p4")
    _shard(batch, [(0, "pass")], [(0, True)], name="shard-01")
    with pytest.raises(ValueError, match="mix planner versions"):
        export_psi0(batch, tmp_path / "out", simple=tmp_path / "simple")
    assert list(tmp_path.iterdir()) == [batch]  # no staging dir, no out


def test_kept_episodes_need_both_qa_steps(tmp_path: Path) -> None:
    shard = _shard(tmp_path, [(0, "pass"), (1, "nan"), (2, "pass"), (3, "pass")],
                   [(0, True), (1, True), (2, False), (3, True)])
    assert kept_episodes(shard) == [0, 3]


def test_kept_episodes_refuses_a_shard_without_replay_verdicts(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="replay QA"):
        kept_episodes(_shard(tmp_path, [(0, "pass")], None))
    with pytest.raises(ValueError, match=r"\[1\]"):
        kept_episodes(_shard(tmp_path, [(0, "pass"), (1, "pass")], [(0, True)]))


def test_stage_shard_renumbers_kept_episodes_as_links(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _jsonl(raw / "meta" / "episodes.jsonl", [
        {"episode_index": e, "length": 10 + e, "environment_config": "{}"} for e in range(4)
    ])
    for name in ("info.json", "tasks.jsonl"):
        (raw / "meta" / name).write_text("{}")
    for e in range(4):
        data = raw / "data" / "chunk-000" / f"episode_{e:06d}.parquet"
        video = raw / "videos/chunk-000/observation.images.ego_view" / f"episode_{e:06d}.mp4"
        for path in (data, video):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{path.suffix}{e}")

    rows = stage_shard(raw, [1, 3], tmp_path / "stage")

    stage = tmp_path / "stage"
    assert [(r["episode_index"], r["length"]) for r in rows] == [(0, 11), (1, 13)]
    staged = [json.loads(line) for line in (stage / "meta/episodes.jsonl").read_text().splitlines()]
    assert staged == rows
    assert (stage / "data/chunk-000/episode_000001.parquet").read_text() == ".parquet3"
    video = stage / "videos/chunk-000/observation.images.ego_view/episode_000000.mp4"
    assert video.is_symlink() and video.read_text() == ".mp41"


def test_action_layout_is_36_named_unpadded_dimensions() -> None:
    contracts = pytest.importorskip("flywheel.contracts.artifacts")
    layout = contracts.ActionLayout.model_validate(action_layout(NAMES_43))
    dims = layout.dimensions
    assert len(dims) == 36 and not any(d.masked for d in dims)
    names = [d.name for d in dims]
    # SIMPLE's order: left thumb, left middle, left index (Psi0's comment says index at 3:5).
    assert names[0:7] == LEFT_HAND[0:3] + LEFT_HAND[5:7] + LEFT_HAND[3:5]
    assert names[7:14] == RIGHT_HAND
    assert names[14:28] == NAMES_43[15:29]
    assert names[28:31] == ["waist_roll_joint", "waist_pitch_joint", "waist_yaw_joint"]
    assert names[31] == "base_height_command"
    assert [d.limit_high for d in dims[32:35]] == [0.5, 0.5, 1.0]
    assert {d.group for d in dims} == {
        "left_hand", "right_hand", "left_arm", "right_arm", "waist", "base_height", "navigate"
    }


def test_state_names_follow_the_action_order_without_commands() -> None:
    names = state_names(NAMES_43)
    assert len(names) == 32
    assert names[:31] == [d["name"] for d in action_layout(NAMES_43)["dimensions"][:31]]
    assert names[31] == "prev_base_height_command"
