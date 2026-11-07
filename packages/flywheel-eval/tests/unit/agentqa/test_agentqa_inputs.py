"""DA-20 AC 2: the agent reads the artifacts it is given, never vault/ or a sealed key."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentqa_build import qa_work, rtc_job, train_job
from flywheel.eval.agentqa.inputs import InputRefused, collect, load_file


def test_known_files_are_loaded_by_kind_and_the_rest_skipped(tmp_path: Path) -> None:
    qa_work(tmp_path / "work", 3)
    train_job(tmp_path / "logs" / "train" / "job-a")
    rtc_job(tmp_path / "logs" / "rtc" / "job-b")
    (tmp_path / "logs" / "notes.txt").write_text("free text")
    found = collect([tmp_path])
    kinds = sorted(x.kind for x in found.loaded)
    assert kinds == ["episode_index", "episodes", "metrics", "qa_reports", "rtc_log"]
    assert any(s.endswith("notes.txt") for s in found.skipped)
    assert all(len(x.sha256) == 64 for x in found.loaded)


@pytest.mark.parametrize("part", ["vault", "answers"])
def test_a_forbidden_path_is_refused(tmp_path: Path, part: str) -> None:
    path = train_job(tmp_path / part / "train" / "job-a")
    with pytest.raises(InputRefused, match=part):
        load_file(path)
    with pytest.raises(InputRefused):
        collect([tmp_path / part])


def test_a_forbidden_dir_inside_a_given_root_is_skipped_unread(tmp_path: Path) -> None:
    train_job(tmp_path / "copy" / "train" / "job-a")
    key = tmp_path / "copy" / "answers" / "x" / "metrics.jsonl"
    key.parent.mkdir(parents=True)
    key.write_text("not even json")
    found = collect([tmp_path / "copy"])
    assert [x.kind for x in found.loaded] == ["metrics"]
    assert any("forbidden" in s for s in found.skipped)


def test_a_file_that_is_not_its_contract_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "train" / "job-a" / "metrics.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"step": 1}) + "\n")
    with pytest.raises(InputRefused, match="metrics"):
        load_file(path)


def test_a_link_into_a_forbidden_dir_is_refused(tmp_path: Path) -> None:
    secret = train_job(tmp_path / "vault" / "train" / "job-a")
    given = tmp_path / "given"
    (given / "train" / "job-file").mkdir(parents=True)
    (given / "train" / "job-file" / "metrics.jsonl").symlink_to(secret)
    (given / "train" / "job-dir").symlink_to(secret.parent, target_is_directory=True)
    with pytest.raises(InputRefused, match="vault"):
        load_file(given / "train" / "job-file" / "metrics.jsonl")
    with pytest.raises(InputRefused, match="vault"):
        collect([given / "train" / "job-dir"])
    found = collect([given])
    assert found.loaded == []
    assert any("forbidden" in s for s in found.skipped)
