"""The evaluation lane's detectors catch exactly the log defects DA-27 injects.

A seam between two lanes (03 section 7.3): the data lane writes the injected train and
RTC logs (`flywheel.data.inject.log_defects`), the evaluation lane's F-TRAIN and F-SYS
detectors read them. Every injected job must raise its own code and no other; a clean
job, and every job of the clean copy, none (DA-27 story: "cấy một lần, phép kiểm tương
ứng bắt được").
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from flywheel.data.inject.config import InjectConfig, LogDefectConfig
from flywheel.data.inject.log_defects import build_log_benchmark
from flywheel.data.inject.manifest import load_manifest
from flywheel.eval.api import diagnose_train

# No api function yet takes an RTC log alone: diagnose_episode_system needs a whole
# trace. Missing in flywheel.eval.api: check_rtc_log(rtc_path, config_path).
from flywheel.eval.config import load_system_thresholds  # missing api: check_rtc_log
from flywheel.eval.diagnosis.system.reader import read_rtc_log  # missing api: check_rtc_log
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2  # missing api: check_rtc_log

REPO = Path(__file__).resolve().parents[2]
TRAIN_CONFIG = REPO / "configs/eval/diagnosis/train.yaml"
SYSTEM = load_system_thresholds(REPO / "configs/eval/diagnosis/system.yaml")[0]
TRAIN_CODES = {f"T{i}" for i in range(1, 9)}


def _codes(job: Path) -> set[str]:
    if (job / "rtc.jsonl").is_file():
        records = read_rtc_log(job / "rtc.jsonl")
        found = check_r1(records, SYSTEM.r1).findings + check_r2(records, SYSTEM.r2).findings
        return {f.code for f in found}
    return {f.code for f in diagnose_train(job, TRAIN_CONFIG).findings} & TRAIN_CODES


def _jobs(root: Path) -> list[Path]:
    return sorted((root / "train").iterdir()) + sorted((root / "rtc").iterdir())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    base = tmp_path_factory.mktemp("logs")
    return build_log_benchmark(base / "logs", store=base / "store")


def test_each_injected_job_raises_exactly_its_code(built) -> None:  # type: ignore[no-untyped-def]
    root = Path(built.defect.ref.uri)
    expected = {d.target_ref: d.code for d in load_manifest(built.defect.manifest_path).defects}
    assert len(expected) == 30
    for job in _jobs(root):
        ref = job.relative_to(root).as_posix()
        assert _codes(job) == ({expected[ref]} if ref in expected else set()), ref


def test_the_clean_copy_raises_nothing(built) -> None:  # type: ignore[no-untyped-def]
    for job in _jobs(Path(built.clean.ref.uri)):
        assert _codes(job) == set(), job.name


def test_a_defect_short_of_its_threshold_goes_unseen(tmp_path: Path) -> None:
    # The check bites: pred_std at half of target_std is above t6.min_std_ratio 0.30.
    weak = dataclasses.replace(InjectConfig(), logs=LogDefectConfig(t6_std_ratio=0.5))
    result = build_log_benchmark(tmp_path / "logs", weak, store=tmp_path / "store")
    root = Path(result.defect.ref.uri)
    t6 = [d for d in load_manifest(result.defect.manifest_path).defects if d.code == "T6"]
    assert len(t6) == 3
    assert all("T6" not in _codes(root / d.target_ref) for d in t6)
