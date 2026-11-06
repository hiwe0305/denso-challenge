"""The record one system check leaves behind (DA-13 AC 1, 2).

03 section 4.3 keeps both of these in `meta` of `Cluster`, which `decide` of
the Vòng lane owns and writes. Nothing in `flywheel.contracts` carries them
yet: `DiagnosisFinding.code` is a `Literal` over T1-T8 and O1-O4, so an R-code
cannot go into a `TrainDiagnosis` even though the shape fits.

So the two records below are the lane's own, written field for field as the
contract change asks for them, the way DA-36 held `ScoreRecord` until `Score`
landed. The switch is registered as a task of the story. The records are
append-only JSONL in the store until `flywheel.store` offers a writer, which
is the same guarantee in the simplest form that holds it.

Four things the record has to keep, because they are the difference between a
diagnosis and an opinion:

* **What was not judged.** `skipped` travels with `findings`, so a record with
  both lists empty means every code ran and none fired - a claim somebody
  measured. Without it an episode nobody could check would read as clean
  (FR21).
* **The hash of the thresholds.** A finding is only reproducible against the
  numbers it was judged by (AC 2).
* **The hash of every input.** R1 and R2 read the RTC log, R5 the camera
  parameters and R6 the `infra_status` source, not only the trace, so each
  is hashed beside `trace_sha256` (None where the episode had no such file).
  Without them one trace with two RTC logs gives two verdicts nothing tells
  apart.
* **What was measured and not counted.** On a synchronous rollout R1 and R2
  are recorded without counting (`verdict.py`, decision (a) of 5/11/2026).
  They go into `recorded` and `recorded_skipped`, beside the rollout's
  `timing`, the three fields `SystemDiagnosis` gained in PR #146: the label
  stays what the counted codes say, and the latency still travels with it.

The stage attribution has its own record beside this one, in
`diagnosis/stage/artifact.py`, because it is answered per failure while this
is answered per episode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from flywheel.eval.diagnosis.system.reader import SystemInputs
from flywheel.eval.diagnosis.system.verdict import Skipped, SystemFinding, SystemVerdict
from pydantic import BaseModel, ConfigDict, Field

SYSTEM_RECORDS = Path("diagnosis") / "system.jsonl"


class SystemFindingRecord(BaseModel):
    """One F-SYS fault as it is stored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    value: float
    # None where the rule counts rather than compares, as `DiagnosisFinding` of
    # the contract already spells it.
    threshold: float | None = None
    part: str | None = None
    where: str | None = None
    detail: str | None = None


class SystemSkipRecord(BaseModel):
    """A code the episode could not be judged on, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    reason: str


class SystemDiagnosisRecord(BaseModel):
    """One system check of one episode (AC 1, 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    diagnosis: str
    config_sha256: str
    trace_sha256: str
    rtc_sha256: str | None = None
    camera_sha256: str | None = None
    infra_sha256: str | None = None
    infra_status: str | None = None
    findings: list[SystemFindingRecord] = Field(default_factory=list)
    skipped: list[SystemSkipRecord] = Field(default_factory=list)
    # The rollout's mode as the inputs stated it; None is unknown, never sync.
    timing: Literal["sync", "async"] | None = None
    # R1 and R2 of a synchronous rollout: measured, kept, never in the label.
    recorded: list[SystemFindingRecord] = Field(default_factory=list)
    recorded_skipped: list[SystemSkipRecord] = Field(default_factory=list)


def build_system_record(
    verdict: SystemVerdict, config_sha256: str, inputs: SystemInputs
) -> SystemDiagnosisRecord:
    """The record of one system check: every list, the mode, and the hash of every input."""
    return SystemDiagnosisRecord(
        episode_id=verdict.episode_id,
        diagnosis=verdict.diagnosis.value,
        config_sha256=config_sha256,
        trace_sha256=inputs.trace.trace_sha256,
        rtc_sha256=inputs.rtc_sha256,
        camera_sha256=inputs.camera_sha256,
        infra_sha256=inputs.infra_sha256,
        infra_status=verdict.infra_status,
        findings=_findings(verdict.findings),
        skipped=_skips(verdict.skipped),
        timing=verdict.timing,
        recorded=_findings(verdict.recorded),
        recorded_skipped=_skips(verdict.recorded_skipped),
    )


def _findings(findings: list[SystemFinding]) -> list[SystemFindingRecord]:
    return [
        SystemFindingRecord(
            code=finding.code,
            value=finding.value,
            threshold=finding.threshold,
            part=finding.part,
            where=finding.where,
            detail=finding.detail,
        )
        for finding in findings
    ]


def _skips(skipped: list[Skipped]) -> list[SystemSkipRecord]:
    return [SystemSkipRecord(code=skip.code, reason=skip.reason) for skip in skipped]


def write_system_record(record: SystemDiagnosisRecord, store_path: Path) -> Path:
    """Append a system diagnosis to the store; return the file it went into.

    Append-only: checking the same episode again adds a record beside the
    first, and `config_sha256` is what tells two runs under two threshold files
    apart instead of one silently replacing the other (03 section 4.4, rule 3).
    """
    return append_line(record.model_dump_json(), store_path / SYSTEM_RECORDS)


def append_line(line: str, path: Path) -> Path:
    """Append one JSONL record, creating the store directory if it is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return path
