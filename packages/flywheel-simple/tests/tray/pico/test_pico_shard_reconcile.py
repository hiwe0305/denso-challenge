"""A shard's saved episodes must match its attempts log before it is resumed (DA-35 task 12)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from flywheel_simple.tray.pico import session
from flywheel_simple.tray.pico.recording import atomic_write_text, shard_mismatches

ENV_ID = "simple/G1WholebodyTrayTransferTeleop-v0"


def shard(
    tmp_path: Path,
    saved: list[int],
    logged: list[int | None],
    no_block: tuple[int, ...] = (),
) -> Path:
    """A shard as a session leaves it: one dataset, and one log line per attempt."""
    meta = tmp_path / "shard-00" / ENV_ID / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text("{}")
    rows = []
    for i in saved:
        row: dict[str, object] = {"episode_index": i, "length": 10}
        if i not in no_block:
            row["environment_config"] = json.dumps({"uid": "tray", "flywheel": {"seed": i}})
        rows.append(json.dumps(row) + "\n")
    if saved:
        (meta / "episodes.jsonl").write_text("".join(rows))
    attempts = [json.dumps({"seed": k, "episode_index": i}) + "\n" for k, i in enumerate(logged)]
    (tmp_path / "shard-00" / "attempts.jsonl").write_text("".join(attempts))
    return tmp_path / "shard-00"


def test_a_shard_whose_episodes_are_its_logged_attempts_agrees(tmp_path: Path) -> None:
    # Attempts that saved nothing (failures) log no episode_index.
    assert shard_mismatches(shard(tmp_path, [0, 1, 2], [0, None, 1, None, 2])) == []


def test_a_crash_after_the_save_but_before_the_log_is_found(tmp_path: Path) -> None:
    # Episode 2 was saved and given its block; the worker died before logging it.
    problems = shard_mismatches(shard(tmp_path, [0, 1, 2], [0, 1]))
    assert problems == ["episodes [2] saved but no attempt logs them"]


def test_a_crash_before_the_flywheel_block_is_found(tmp_path: Path) -> None:
    problems = shard_mismatches(shard(tmp_path, [0, 1], [0], no_block=(1,)))
    assert problems == [
        "episodes [1] saved but no attempt logs them",
        "episodes [1] have no flywheel block",
    ]


def test_logged_episodes_must_be_in_the_dataset_once(tmp_path: Path) -> None:
    problems = shard_mismatches(shard(tmp_path, [0], [0, 0, 1]))
    assert problems == [
        "episode 0 logged by 2 attempts",
        "episodes [1] logged but not in the dataset",
    ]


def test_a_dataset_set_aside_as_empty_is_not_counted(tmp_path: Path) -> None:
    root = shard(tmp_path, [0], [0])
    empty = root / "simple" / "G1WholebodyTrayTransferTeleop-v0.empty-1104T1740" / "meta"
    empty.mkdir(parents=True)
    (empty / "info.json").write_text("{}")
    assert shard_mismatches(root) == []


def test_atomic_write_replaces_the_file_and_leaves_no_temporary(tmp_path: Path) -> None:
    path = tmp_path / "episodes.jsonl"
    path.write_text("old\n")
    atomic_write_text(path, "new\n")
    assert path.read_text() == "new\n"
    assert [p.name for p in tmp_path.iterdir()] == ["episodes.jsonl"]


def test_a_session_refuses_to_resume_a_shard_that_does_not_reconcile(tmp_path: Path) -> None:
    root = shard(tmp_path, [0, 1], [0])
    env = SimpleNamespace(unwrapped=SimpleNamespace(task=SimpleNamespace(robot=None),
                                                    spec=SimpleNamespace(id=ENV_ID)))  # fmt: skip
    with pytest.raises(session.ShardMismatch, match=r"episodes \[1\] saved but no attempt"):
        session.run_session(
            env, agent=None, queue=None,  # type: ignore[arg-type]  # refused before use
            save_dir=root, operator="op-virtual", session="s", source_detail="s2",
        )  # fmt: skip
    assert not (root / "sessions.jsonl").exists()
