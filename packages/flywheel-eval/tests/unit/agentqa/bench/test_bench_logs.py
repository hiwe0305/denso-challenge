"""DA-31 AC 1 on a log copy: the code layer is this lane's F-TRAIN and F-SYS detectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.bench import BenchInputError, run_log_checks

REPO = Path(__file__).resolve().parents[6]
TRAIN = REPO / "configs/eval/diagnosis/train.yaml"
SYSTEM = REPO / "configs/eval/diagnosis/system.yaml"


def _train_job(job: Path, nan_at: int | None) -> None:
    job.mkdir(parents=True)
    rows = [
        TrainingMetric(
            run_plan_id="rp", job_id=job.name, checkpoint_id="ck", release_id="rel", attempt=0,
            step=step, epoch=0, split="train",
            loss="NaN" if step == nan_at else 1.0 / (step + 1),
            lr=1e-4, vlm_frozen=True, wall_time_s=float(step),
        )
        for step in range(0, 100, 10)
    ]
    (job / "metrics.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows))


def _rtc_job(job: Path, latency: float) -> None:
    job.mkdir(parents=True)
    rows = [
        RTCInferenceRecord(
            job_id=job.name, trace_id="t", chunk_index=i, observation_sent_s=i * 0.5,
            chunk_received_s=i * 0.5 + latency, delay_steps=2, buffer_level=0,
            boundary_jump=0.0,
        )
        for i in range(50)
    ]
    (job / "rtc.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows))


def test_each_job_is_checked_by_its_own_detector(tmp_path: Path) -> None:
    root = tmp_path / "bench-cccccccccccc"
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "benchmark_copy.json").write_text(
        json.dumps({"benchmark_copy_id": "bench-cccccccccccc"})
    )
    _train_job(root / "train" / "job-nan", nan_at=50)
    _train_job(root / "train" / "job-ok", nan_at=None)
    _rtc_job(root / "rtc" / "job-slow", latency=0.3)
    _rtc_job(root / "rtc" / "job-fast", latency=0.05)
    run = run_log_checks(root, TRAIN, SYSTEM)
    assert run.dataset_id == "bench-cccccccccccc"
    assert run.units == ("train/job-nan", "train/job-ok", "rtc/job-fast", "rtc/job-slow")
    found = {(d.target, d.code) for d in run.detections}
    assert ("train/job-nan", "T1") in found
    assert ("rtc/job-slow", "R1") in found
    assert not {t for t, _ in found} & {"rtc/job-fast"}


def test_a_dir_that_is_no_copy_is_refused(tmp_path: Path) -> None:
    _train_job(tmp_path / "train" / "job", nan_at=None)
    with pytest.raises(BenchInputError, match="not a benchmark copy"):
        run_log_checks(tmp_path, TRAIN, SYSTEM)
