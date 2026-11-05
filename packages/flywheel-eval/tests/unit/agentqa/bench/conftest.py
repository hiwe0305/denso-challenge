"""Builders for the bench tests: a sealed answer key, a QA work dir, an AgentReport.

Everything is built in the test with a known answer, on CPU, from the contracts
and the testkit's Episode fixture; nothing here imports the data lane.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path

import pytest
from flywheel.contracts.agentqa import (
    AgentFact,
    AgentFinding,
    AgentInput,
    AgentModel,
    AgentReport,
)
from flywheel.contracts.artifacts import Defect, DefectManifest, Episode, QACheck, QAReport
from flywheel.eval.agentqa.bench.answers import manifest_sha256

T0 = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
INJECTED = "bench-aaaaaaaaaaaa"
CLEAN = "bench-bbbbbbbbbbbb"

Seal = Callable[[Path, str, Sequence[Defect]], Path]
QAWork = Callable[[Path, str, int, Mapping[int, Sequence[str]]], Path]
Report = Callable[..., AgentReport]


def defect(target: str, code: str, kind: str, **params: str | int) -> Defect:
    return Defect(target_ref=target, code=code, parameters={"kind": kind, **params})


def ep_id(copy_id: str, index: int) -> str:
    return f"ep_{copy_id[-4:]}{index:012d}"


@pytest.fixture
def seal() -> Seal:
    def build(root: Path, dataset_id: str, defects: Sequence[Defect]) -> Path:
        manifest = DefectManifest(dataset_id=dataset_id, seed=42, defects=list(defects))
        folder = root / dataset_id
        folder.mkdir(parents=True)
        (folder / "defect_manifest.json").write_text(manifest.model_dump_json(indent=2))
        (folder / "defect_manifest.sha256").write_text(manifest_sha256(manifest))
        return folder

    return build


@pytest.fixture
def qa_work() -> QAWork:
    """A `fw data qa` work dir of `n` episodes; `reasons` maps an index to its reasons."""

    text = (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text()
    base = Episode.model_validate_json(text)

    def build(root: Path, copy_id: str, n: int, reasons: Mapping[int, Sequence[str]]) -> Path:
        work = root / f"work-{copy_id}"
        (work / "qa").mkdir(parents=True)
        episodes, index, reports = [], {}, []
        for i in range(n):
            eid = ep_id(copy_id, i)
            meta = base.meta.model_copy(update={"benchmark_copy_id": copy_id})
            episodes.append(base.model_copy(update={"episode_id": eid, "meta": meta}))
            index[eid] = i
            why = list(reasons.get(i, []))
            check = QACheck(name="x", value=1.0 if why else 0.0, threshold=0.5, passed=not why)
            reports.append(
                QAReport(
                    report_id=f"qa_{i}",
                    episode_id=eid,
                    threshold_version="v1",
                    decision="reject" if why else "pass",
                    reasons=why,
                    checks=[check],
                )
            )
        (work / "episodes.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in episodes))
        (work / "episode_index.json").write_text(json.dumps(index))
        (work / "qa" / "reports.jsonl").write_text(
            "".join(r.model_dump_json() + "\n" for r in reports)
        )
        return work

    return build


@pytest.fixture
def report() -> Report:
    """An AgentReport whose findings are (target, code[, rank]) tuples."""

    def build(
        report_id: str,
        findings: Sequence[tuple[str, str] | tuple[str, str, int]],
        *,
        subject: str = "copies/bench-x",
        inputs: Sequence[str] = ("copies/bench-x/meta/info.json",),
        minutes: float = 5.0,
    ) -> AgentReport:
        fact = AgentFact(fact_id="F1", name="n", value=1, source_ref=inputs[0])
        items = [
            AgentFinding(
                finding_id=f"{report_id}-f{i}",
                code=item[1],
                rank=item[2] if len(item) == 3 else i + 1,  # type: ignore[misc]
                target_ref=item[0],
                evidence=["F1"],
                insight="value {F1}",
                suggestion="look at it",
            )
            for i, item in enumerate(findings)
        ]
        return AgentReport(
            report_id=report_id,
            subject_ref=subject,
            stage="dataset",
            created_at=T0 + timedelta(minutes=minutes),
            model=AgentModel(name="fake", revision="r0", temperature=0.0, prompt_sha256="0" * 64),
            inputs=[AgentInput(ref=ref, kind="data", sha256="1" * 64) for ref in inputs],
            facts=[fact],
            findings=items,
            status="ok",
        )

    return build
