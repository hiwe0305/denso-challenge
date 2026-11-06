"""The eval conditions of the frozen tray plan as LeRobot datasets, on CPU (DA-34 task 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from flywheel_psi0.tray.eval_set import DATA, build, conditions_sha256, main
from flywheel_psi0.tray.runplan import TrayRunPlan, run_plan_id

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "configs/runplans/tray/he-tray-v2.yaml"
TEMPLATE_CONFIG = {
    "uid": "g1_wholebody_tray_transfer_teleop",
    "metadata": {"dr_level": 1, "split": "train", "max_episode_steps": 4500},
    "robot_cfg": {"uid": "g1_sonic"},
    "tray": {"sample": {"level": 1, "seed": 1210, "table_gap": 1.8}, "report": {"success": True}},
    "flywheel": {"seed": 1210, "purpose": "coverage"},
}


@pytest.fixture
def release(tmp_path: Path) -> Path:
    """A two-frame, one-episode release in the export's layout, with a video feature."""
    root = tmp_path / "release"
    (root / "meta").mkdir(parents=True)
    (root / "data/chunk-000").mkdir(parents=True)
    features = {
        "observation.images.egocentric": {"dtype": "video", "shape": [4, 4, 3]},
        "states": {"dtype": "float32", "shape": [-1]},
        "timestamp": {"dtype": "float32", "shape": [1]},
        "episode_index": {"dtype": "int64", "shape": [1]},
    }
    info = {
        "codebase_version": "v2.1",
        "fps": 50,
        "total_episodes": 1,
        "features": features,
        "video_path": "videos/x.mp4",
        "data_path": DATA.replace("{:06d}", "{episode_index:06d}"),
    }
    (root / "meta/info.json").write_text(json.dumps(info))
    (root / "meta/tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": "carry"}) + "\n")
    episode = {"episode_index": 0, "length": 2, "environment_config": json.dumps(TEMPLATE_CONFIG)}
    (root / "meta/episodes.jsonl").write_text(json.dumps(episode) + "\n")
    stats = {"states": {"min": [0.0]}, "observation.images.egocentric": {"min": [0.0]}}
    (root / "meta/episodes_stats.jsonl").write_text(
        json.dumps({"episode_index": 0, "stats": stats}) + "\n"
    )
    table = pa.Table.from_pylist(
        [
            {
                "states": [0.5, 0.25],
                "timestamp": 0.0,
                "frame_index": 0,
                "episode_index": 0,
                "index": 0,
                "next.done": False,
            },
            {
                "states": [0.75, 0.0],
                "timestamp": 0.02,
                "frame_index": 1,
                "episode_index": 0,
                "index": 1,
                "next.done": True,
            },
        ]
    )
    pq.write_table(table, root / DATA.format(0))
    return root


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_one_episode_per_eval_condition_in_plan_order(release: Path, tmp_path: Path) -> None:
    plan = TrayRunPlan.load(PLAN)
    build(PLAN, release, tmp_path / "set")
    rows = lines(tmp_path / "set/conditions.jsonl")
    assert [(r["level"], r["seed"]) for r in rows] == plan.eval_conditions()
    assert len(rows) == 270
    assert [r["unit"] for r in rows[:30]] == ["replicate"] * 30
    for level, n in ((0, 30), (1, 120), (2, 120)):
        episodes = lines(tmp_path / f"set/dr-level-{level}/meta/episodes.jsonl")
        assert [e["episode_index"] for e in episodes] == list(range(n))
        mine = [r for r in rows if r["level"] == level]
        assert [json.loads(e["environment_config"]) for e in episodes] == [
            r["environment_config"] for r in mine
        ]


def test_the_env_sees_only_the_conditions_seed_and_level(release: Path, tmp_path: Path) -> None:
    build(PLAN, release, tmp_path / "set")
    row = lines(tmp_path / "set/conditions.jsonl")[40]
    config = row["environment_config"]
    assert config["tray"] == {
        "sample": {"level": row["level"], "seed": row["seed"]}
    }  # no recorded report
    assert config["metadata"] == {
        "dr_level": row["level"],
        "split": "dev",
        "max_episode_steps": 4500,
    }
    assert config["flywheel"]["run_plan_id"] == run_plan_id(TrayRunPlan.load(PLAN))
    assert config["robot_cfg"] == TEMPLATE_CONFIG["robot_cfg"]


def test_each_level_is_a_valid_one_frame_dataset_without_video(
    release: Path, tmp_path: Path
) -> None:
    build(PLAN, release, tmp_path / "set")
    level = tmp_path / "set/dr-level-2"
    info = json.loads((level / "meta/info.json").read_text())
    assert "observation.images.egocentric" not in info["features"] and "video_path" not in info
    assert (info["total_episodes"], info["total_frames"], info["total_videos"]) == (120, 120, 0)
    frame = pq.read_table(level / DATA.format(7)).to_pylist()
    assert frame == [
        {
            "states": [0.5, 0.25],
            "timestamp": 0.0,
            "frame_index": 0,
            "episode_index": 7,
            "index": 7,
            "next.done": True,
        }
    ]
    stats = lines(level / "meta/episodes_stats.jsonl")
    assert len(stats) == 120 and stats[7] == {
        "episode_index": 7,
        "stats": {"states": {"min": [0.0]}},
    }


def test_check_recomputes_the_digest_and_refuses_a_moved_set(release: Path, tmp_path: Path) -> None:
    digest = build(PLAN, release, tmp_path / "set")
    assert (tmp_path / "set/conditions.sha256").read_text().strip() == digest
    assert digest == conditions_sha256(lines(tmp_path / "set/conditions.jsonl"))
    assert build(PLAN, release, None) == digest
    assert main([str(PLAN), "--release", str(release), "--check", digest]) == 0
    assert main([str(PLAN), "--release", str(release), "--check", "0" * 64]) == 1


def test_an_existing_set_is_never_overwritten(release: Path, tmp_path: Path) -> None:
    build(PLAN, release, tmp_path / "set")
    with pytest.raises(FileExistsError):
        build(PLAN, release, tmp_path / "set")
