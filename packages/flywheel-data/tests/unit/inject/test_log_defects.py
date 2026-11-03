"""Train log defects T1-T8 and RTC log defects R1-R2 (story task 2, AC 2).

The logs are written in the contract schemas the real ones use (`TrainingMetric`,
`RTCInferenceRecord`, `ProbeP4`) and in the job layout the evaluation lane reads, so the
evaluation lane's own detectors judge them here: an injected job must raise exactly its
code, a clean job none (story: "cấy một lần, phép kiểm tương ứng bắt được").
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.artifacts import ProbeP4, RTCInferenceRecord
from flywheel.contracts.training import TrainingMetric
from flywheel.data.inject.codes import LOG_DEFECT_CODES
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.log_defects import build_log_benchmark, main
from flywheel.data.inject.manifest import ManifestLock, load_manifest
from flywheel.eval.config import load_system_thresholds, load_train_thresholds
from flywheel.eval.diagnosis.system.reader import read_rtc_log
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2
from flywheel.eval.diagnosis.train.artifact import diagnose_all, load_job

REPO = Path(__file__).resolve().parents[5]
TRAIN = load_train_thresholds(REPO / "configs/eval/diagnosis/train.yaml")[0]
SYSTEM = load_system_thresholds(REPO / "configs/eval/diagnosis/system.yaml")[0]
TRAIN_CODES = {f"T{i}" for i in range(1, 9)}
WORDS = (b"inject", b"defect", b"duplicate", b"bench")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Any:
    out = tmp_path_factory.mktemp("logs") / "logs"
    return out, build_log_benchmark(out)


def _codes(job: Path) -> set[str]:
    if (job / "rtc.jsonl").is_file():
        records = read_rtc_log(job / "rtc.jsonl")
        found = check_r1(records, SYSTEM.r1).findings + check_r2(records, SYSTEM.r2).findings
        return {f.code for f in found}
    return {f.code for f in diagnose_all(load_job(job), TRAIN).findings} & TRAIN_CODES


def _jobs(root: Path) -> list[Path]:
    return sorted(p for p in (root / "train").iterdir()) + sorted((root / "rtc").iterdir())


def test_logs_are_in_the_contract_schemas(built: Any) -> None:
    _, result = built
    for copy in (result.defect, result.clean):
        root = Path(copy.ref.uri)
        for job in sorted((root / "train").iterdir()):
            for line in (job / "metrics.jsonl").read_text().splitlines():
                TrainingMetric.model_validate_json(line)
            for name in ("probe_p4.json", "probe_p4_parent.json"):
                ProbeP4.model_validate_json((job / name).read_text())
        for job in sorted((root / "rtc").iterdir()):
            for line in (job / "rtc.jsonl").read_text().splitlines():
                RTCInferenceRecord.model_validate_json(line)


def test_three_jobs_per_kind_and_the_design_codes(built: Any) -> None:
    _, result = built
    manifest = load_manifest(result.defect.manifest_path)
    assert Counter(d.parameters["kind"] for d in manifest.defects) == {
        kind: 3 for kind in LOG_DEFECT_CODES
    }
    assert all(d.code == LOG_DEFECT_CODES[str(d.parameters["kind"])] for d in manifest.defects)
    assert len({d.target_ref for d in manifest.defects}) == 30
    assert load_manifest(result.clean.manifest_path).defects == []


def test_the_evaluation_detectors_find_exactly_the_injected_code(built: Any) -> None:
    _, result = built
    root = Path(result.defect.ref.uri)
    expected = {d.target_ref: d.code for d in load_manifest(result.defect.manifest_path).defects}
    for job in _jobs(root):
        ref = job.relative_to(root).as_posix()
        assert _codes(job) == ({expected[ref]} if ref in expected else set()), ref


def test_the_clean_copy_raises_nothing(built: Any) -> None:
    _, result = built
    root = Path(result.clean.ref.uri)
    for job in _jobs(root):
        assert _codes(job) == set(), job.name


def test_both_copies_look_alike_and_keep_the_answer_outside(built: Any) -> None:
    out, result = built
    roots = [Path(result.defect.ref.uri), Path(result.clean.ref.uri)]

    def shape(root: Path) -> list[tuple[str, int, list[str]]]:
        return [
            (job.parent.name, len(job.name), sorted(p.name for p in job.iterdir()))
            for job in _jobs(root)
        ]

    assert shape(roots[0]) == shape(roots[1])
    assert {r.name for r in roots}.isdisjoint(copy_ids(42))  # not the data copies' ids
    for copy in (result.defect, result.clean):
        assert copy.manifest_path.is_relative_to(out / "answers")
        assert ManifestLock(copy.manifest_path).verify_integrity()
    stamps = set()
    for root in roots:
        marker = json.loads((root / "meta/benchmark_copy.json").read_text())
        assert marker["benchmark_copy_id"] == root.name
        for path in root.rglob("*"):
            if path.is_file():
                stamps.add(path.stat().st_mtime)
                if path.name != "benchmark_copy.json":
                    assert not [w for w in WORDS if w in path.read_bytes().lower()], path
    assert len(stamps) == 1


def test_cli_prints_the_handoff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--out", str(tmp_path / "logs")]) == 0
    handoff = json.loads(capsys.readouterr().out)
    assert len(handoff["copies"]) == 2
    assert all(len(c["manifest_sha256"]) == 64 for c in handoff["copies"])
