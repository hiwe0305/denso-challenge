"""The loader under the conditions a 5-minute cron meets (review #72 points 4, 6, 7, 8, 10).

* two lots or two experiments claiming the same key (point 4);
* a JSONL line the core is still writing, or one that is broken (point 6);
* a crash while the sink is being written (point 7);
* `verify` right after a clean import (point 8);
* a training run's worth of telemetry in one import (point 10).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from web.fwsync.cli import app
from web.fwsync.runner import loaded_counts, run_import, run_verify
from web.fwsync.sink import JsonlSink
from web.tests.test_fwsync import DATASET, EPISODE, QA_REPORT, _rows, _write_jsonl

MOCK = Path(__file__).resolve().parents[2] / "mock" / "demo-17-11"


# ---------------------------------------------------------------- point 4


def test_two_lots_on_one_source_refuse_the_episode(tmp_path: Path) -> None:
    # A benchmark copy cut from a real lot keeps the lot's source id. The
    # episode used to land silently in whichever lot was read last.
    source = tmp_path / "src"
    copy = {**DATASET, "dataset_code": "bench_copy", "has_seeded_faults": True}
    _write_jsonl(source / "datasets.jsonl", [DATASET, copy])
    _write_jsonl(source / "episodes.jsonl", [EPISODE])

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "partial"
    [error] = [e for e in result.errors if e["table"] == "episodes"]
    assert "source_id" in error["message"] and "nhiều dòng" in error["message"]
    assert _rows(tmp_path / "sink", "episodes") == []


def test_the_same_lot_written_twice_is_not_ambiguous(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _write_jsonl(source / "datasets.jsonl", [DATASET, DATASET])
    _write_jsonl(source / "episodes.jsonl", [EPISODE])

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "ok", result.errors
    assert _rows(tmp_path / "sink", "episodes")[0]["dataset_code"] == "ds_psi_teleop"


def test_two_experiments_on_one_run_plan_refuse_the_metric(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _write_jsonl(source / "experiments.jsonl", [
        {"experiment_code": "exp_a", "run_plan_ref": "rp_1"},
        {"experiment_code": "exp_b", "run_plan_ref": "rp_1"},
    ])
    # The experiment is resolved before the metric is validated, so a bare
    # row is enough to reach the ambiguity.
    _write_jsonl(source / "training_metrics.jsonl", [
        {"run_plan_id": "rp_1", "checkpoint_id": None, "step": 1, "split": "train"},
    ])

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    [error] = [e for e in result.errors if e["table"] == "training_metrics"]
    assert "run_plan_id" in error["message"] and "nhiều dòng" in error["message"]


# ---------------------------------------------------------------- point 6


def _write_raw(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def test_a_last_line_still_being_written_is_skipped_not_fatal(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _write_jsonl(source / "datasets.jsonl", [DATASET])
    _write_raw(source / "episodes.jsonl", json.dumps(EPISODE) + '\n{"episode_id": "ep_trunc')

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "ok", result.errors
    assert any("đang ghi dở" in line for line in result.ignored)
    assert len(_rows(tmp_path / "sink", "episodes")) == 1


def test_a_broken_line_is_one_rejected_row(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _write_jsonl(source / "datasets.jsonl", [DATASET])
    _write_raw(source / "episodes.jsonl", "{not json\n" + json.dumps(EPISODE) + "\n")
    _write_jsonl(source / "qa_reports.jsonl", [QA_REPORT])

    sink = JsonlSink(directory=tmp_path / "sink")
    result = run_import(source, sink)

    assert result.status == "partial"
    [error] = result.errors
    assert error["ref"] == "episodes.jsonl:1" and error["code"] == "SourceError"
    assert sink.counts()["episodes"]["rejected"] == 1
    assert len(_rows(tmp_path / "sink", "episodes")) == 1
    assert len(_rows(tmp_path / "sink", "episode_qa_reports")) == 1


def test_a_broken_json_file_does_not_stop_the_others(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _write_jsonl(source / "datasets.jsonl", [DATASET])
    _write_jsonl(source / "episodes.jsonl", [EPISODE])
    _write_raw(source / "recommendation.json", "{")

    result = run_import(source, JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "partial"
    assert [e["ref"] for e in result.errors] == ["recommendation.json"]
    assert len(_rows(tmp_path / "sink", "episodes")) == 1


# ---------------------------------------------------------------- point 7


def test_a_crash_while_committing_leaves_the_old_file_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = JsonlSink(directory=tmp_path / "sink")
    first.write("cost_ledger_entries", {"entry_ref": "led_1", "usd_amount": 1.0})
    first.commit()
    before = (tmp_path / "sink" / "cost_ledger_entries.jsonl").read_bytes()

    second = JsonlSink(directory=tmp_path / "sink")
    second.write("cost_ledger_entries", {"entry_ref": "led_2", "usd_amount": 2.0})

    def crash(*_: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="disk full"):
        second.commit()

    assert (tmp_path / "sink" / "cost_ledger_entries.jsonl").read_bytes() == before


def test_a_commit_leaves_no_temporary_file(tmp_path: Path) -> None:
    sink = JsonlSink(directory=tmp_path / "sink")
    sink.write("episodes", {"episode_ref": "ep_1"})
    sink.commit()

    assert sorted(path.name for path in (tmp_path / "sink").iterdir()) == ["episodes.jsonl"]


# ---------------------------------------------------------------- point 8


def test_verify_is_quiet_right_after_a_clean_import_of_the_mock(tmp_path: Path) -> None:
    # Hiếu's probe: five tables used to differ because verify counted source
    # records by source table, not the rows the import writes.
    sink = tmp_path / "sink"
    assert run_import(MOCK, JsonlSink(directory=sink), origin="mock").status == "ok"

    result = run_verify(MOCK, loaded_counts(sink))

    assert result.status == "ok", result.errors


def test_verify_still_reports_a_missing_row(tmp_path: Path) -> None:
    sink = tmp_path / "sink"
    run_import(MOCK, JsonlSink(directory=sink), origin="mock")
    counts = loaded_counts(sink)
    counts["defect_scores"] -= 1

    result = run_verify(MOCK, counts)

    assert [e["table"] for e in result.errors] == ["defect_scores"]


def test_verify_takes_the_sink_directory_on_the_command_line(tmp_path: Path) -> None:
    sink = tmp_path / "sink"
    run_import(MOCK, JsonlSink(directory=sink), origin="mock")

    outcome = CliRunner().invoke(app, ["verify", "--from", str(MOCK), "--loaded", str(sink)])

    assert outcome.exit_code == 0, outcome.output


# ---------------------------------------------------------------- point 10


def test_a_training_run_of_telemetry_loads_in_linear_time(tmp_path: Path) -> None:
    # 8,000 rows took 15.8 s with a linear scan per row; a Ψ₀ run is ~80k.
    sink = JsonlSink(directory=tmp_path / "sink")
    started = time.perf_counter()
    for step in range(40_000):
        for split in ("train", "val"):
            sink.write("training_metrics",
                       {"experiment_code": "exp", "attempt": 1, "step": step, "split": split})
    sink.write("training_metrics",
               {"experiment_code": "exp", "attempt": 1, "step": 7, "split": "val", "loss": 1.0})
    elapsed = time.perf_counter() - started

    assert elapsed < 10, f"80k rows took {elapsed:.1f}s"
    assert len(sink.rows["training_metrics"]) == 80_000
    assert sink.counts()["training_metrics"]["updated"] == 1


def test_the_index_is_rebuilt_from_disk(tmp_path: Path) -> None:
    first = JsonlSink(directory=tmp_path / "sink")
    first.write("episodes", {"episode_ref": "ep_1", "split": "train"})
    first.commit()

    second = JsonlSink(directory=tmp_path / "sink")
    assert second.write("episodes", {"episode_ref": "ep_1", "split": "dev"}) == "updated"
    second.commit()
    assert _rows(tmp_path / "sink", "episodes") == [{"episode_ref": "ep_1", "split": "dev"}]
