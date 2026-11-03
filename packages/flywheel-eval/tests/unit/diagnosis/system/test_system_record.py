"""The record of one system check names every file the verdict was read from (AC 1, 2).

R1 and R2 read the RTC log, R5 the camera parameters and R6 `episode.json`,
not only the trace. A record that hashed the trace alone would let one trace
with two different RTC logs give two different verdicts that nothing in the
store tells apart.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from flywheel.eval.api import diagnose_episode_system


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


def _lines(items: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(item) + "\n" for item in items)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "system.yaml"
    shutil.copyfile(_repo_root() / "configs" / "eval" / "diagnosis" / "system.yaml", path)
    return path


@pytest.fixture
def episode(write_job, rollout_result, clean_rows, rtc_rows, camera_entry) -> Path:
    # the hook's layout: the RTC log is the job's, one directory up
    return write_job(clean_rows, rtc=rtc_rows, camera=camera_entry, result=rollout_result("ok"))


def test_the_record_hashes_every_file_the_verdict_read(episode: Path, config: Path) -> None:
    record = diagnose_episode_system(episode, config)

    assert record.trace_sha256 == _sha(episode / "trace.jsonl")
    assert record.rtc_sha256 == _sha(episode.parent / "rtc.jsonl")
    assert record.camera_sha256 == _sha(episode / "camera_params.json")
    assert record.infra_sha256 == _sha(episode / "episode.json")


def test_one_trace_with_two_rtc_logs_gives_two_distinguishable_records(
    episode: Path, config: Path, rtc_rows
) -> None:
    healthy = diagnose_episode_system(episode, config)
    slow = [{**row, "chunk_received_s": row["observation_sent_s"] + 0.4} for row in rtc_rows]
    (episode.parent / "rtc.jsonl").write_text(_lines(slow), encoding="utf-8")

    stalled = diagnose_episode_system(episode, config)

    assert healthy.trace_sha256 == stalled.trace_sha256
    assert healthy.diagnosis != stalled.diagnosis
    assert healthy.rtc_sha256 != stalled.rtc_sha256


def test_a_file_the_episode_lacks_is_hashed_as_none(episode: Path, config: Path) -> None:
    (episode.parent / "rtc.jsonl").unlink()
    for name in ("camera_params.json", "episode.json"):
        (episode / name).unlink()

    record = diagnose_episode_system(episode, config)

    assert (record.rtc_sha256, record.camera_sha256, record.infra_sha256) == (None, None, None)
