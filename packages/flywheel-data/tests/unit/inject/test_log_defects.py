"""Train log defects T1-T8 and RTC log defects R1-R2 (story task 2, AC 2), lane-local.

The logs are written in the contract schemas the real ones use (`TrainingMetric`,
`RTCInferenceRecord`, `ProbeP4`). Here each injected job is compared with the clean job
its id gives: the defect must change exactly its one signal, by the configured amount.
That the evaluation lane's detectors then raise exactly that code is checked across the
lanes, in tests/e2e/test_log_defects_detected.py.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.artifacts import ProbeP4, RTCInferenceRecord
from flywheel.contracts.training import TrainingMetric
from flywheel.data.inject.build import load_layout
from flywheel.data.inject.codes import LOG_DEFECT_CODES
from flywheel.data.inject.config import LogDefectConfig
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.log_defects import (
    G1_LAYOUT,
    build_log_benchmark,
    clean_rtc_log,
    clean_train_job,
    main,
)
from flywheel.data.inject.manifest import ManifestLock, load_manifest

REPO = Path(__file__).resolve().parents[5]
WORDS = (b"inject", b"defect", b"duplicate", b"bench")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Any:
    out = tmp_path_factory.mktemp("logs") / "logs"
    return out, build_log_benchmark(out)


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


CFG = LogDefectConfig()


def _train_diff(job: Path) -> tuple[list[tuple[int, str, str]], bool, ProbeP4, ProbeP4]:
    """(step, split, field) of every metric that differs from the clean job of this id."""
    written = [
        TrainingMetric.model_validate_json(x)
        for x in (job / "metrics.jsonl").read_text().splitlines()
    ]
    clean, clean_child, clean_parent = clean_train_job(job.name, load_layout(G1_LAYOUT), CFG)
    assert [(r.step, r.split) for r in written] == [(r.step, r.split) for r in clean]
    changed = [
        (w.step, w.split, name)
        for w, c in zip(written, clean, strict=True)
        for name in TrainingMetric.model_fields
        if json.dumps(getattr(w, name)) != json.dumps(getattr(c, name))
    ]
    child = ProbeP4.model_validate_json((job / "probe_p4.json").read_text())
    parent = ProbeP4.model_validate_json((job / "probe_p4_parent.json").read_text())
    return changed, child != clean_child or parent != clean_parent, child, parent


def test_each_defect_changes_exactly_its_signal_by_the_configured_amount(built: Any) -> None:
    _, result = built
    root = Path(result.defect.ref.uri)
    kinds = {d.target_ref: d for d in load_manifest(result.defect.manifest_path).defects}
    for job in sorted((root / "train").iterdir()):
        changed, probes, child, parent = _train_diff(job)
        fields = {name for _, _, name in changed}
        defect = kinds.get(f"train/{job.name}")
        kind = str(defect.parameters["kind"]) if defect else ""
        expected = {
            "": set(),
            "T7_forgetting": set(),
            "T1_divergence": {"loss"},
            "T2_not_learning": {"loss", "loss_by_group"},
            "T3_overfitting": {"loss"},
            "T4_group_imbalance": {"loss_by_group"},
            "T5_dead_dimension": {"pred_var_by_dim"},
            "T6_mode_collapse": {"pred_std"},
            "T8_gradient_anomaly": {"grad_norm_vlm"},
        }[kind]
        assert fields == expected, (job.name, kind, fields)
        assert probes == (kind == "T7_forgetting"), (job.name, kind)
        metrics = [
            TrainingMetric.model_validate_json(x)
            for x in (job / "metrics.jsonl").read_text().splitlines()
        ]
        if kind == "T1_divergence":
            assert [
                m.loss
                for m in metrics
                if m.step == defect.parameters["step"] and m.split == "train"
            ] == ["NaN"]
            assert len(changed) == 1
        if kind == "T3_overfitting":
            assert {split for _, split, _ in changed} == {"val"} and len(
                changed
            ) == CFG.t3_val_rises
        if kind == "T6_mode_collapse":
            late = [m for m in metrics if m.split == "train" and m.step > CFG.steps // 2]
            assert all(
                p == pytest.approx(CFG.t6_std_ratio * t)
                for m in late
                for p, t in zip(m.pred_std, m.target_std)
            )
        if kind == "T7_forgetting":
            q = str(defect.parameters["question"])
            assert child.p1.accuracy_by_question_type[q] == pytest.approx(
                parent.p1.accuracy_by_question_type[q] * (1 - CFG.t7_p1_drop)
            )
        if kind == "T8_gradient_anomaly":
            assert len(changed) == 1
            assert [
                m.grad_norm_vlm
                for m in metrics
                if m.step == defect.parameters["step"] and m.split == "train"
            ] == [CFG.t8_frozen_grad]
    for job in sorted((root / "rtc").iterdir()):
        written = [
            RTCInferenceRecord.model_validate_json(x)
            for x in (job / "rtc.jsonl").read_text().splitlines()
        ]
        clean = clean_rtc_log(job.name, CFG)
        off = [w for w, c in zip(written, clean, strict=True) if w != c]
        defect = kinds.get(f"rtc/{job.name}")
        kind = str(defect.parameters["kind"]) if defect else ""
        latency = [w.chunk_received_s - w.observation_sent_s for w in off]
        if kind == "R1_high_latency":
            assert len(off) == round(CFG.r1_fraction * CFG.rtc_chunks)
            assert latency == pytest.approx([CFG.r1_latency_s] * len(off)) and {
                w.delay_steps for w in off
            } == {8}
        elif kind == "R2_buffer_depleted":
            assert len(off) == 1 and latency == pytest.approx([CFG.r2_latency_s])
            assert off[0].delay_steps == 12
        else:
            assert off == [], job.name


def test_the_clean_copy_is_the_clean_jobs(built: Any) -> None:
    _, result = built
    root = Path(result.clean.ref.uri)
    for job in sorted((root / "train").iterdir()):
        changed, probes, _, _ = _train_diff(job)
        assert changed == [] and not probes, job.name
    for job in sorted((root / "rtc").iterdir()):
        written = [
            RTCInferenceRecord.model_validate_json(x)
            for x in (job / "rtc.jsonl").read_text().splitlines()
        ]
        assert written == clean_rtc_log(job.name, CFG), job.name


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
