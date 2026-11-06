"""Shared DA-13 system diagnosis and stage attribution records (issue #70)."""

from typing import Literal

from flywheel.contracts.training import Contract, DiagnosisSkip
from pydantic import Field, model_validator

SHA256 = r"^[0-9a-f]{64}$"
SystemCode = Literal["R1", "R2", "R3", "R4", "R5", "R6"]
SystemLabel = Literal["clean", "unknown", "controller", "runtime", "sync", "calibration", "infra"]
# Timing checks a sync rollout records without counting (PO decision (a), 5/11/2026).
RECORDED_CODES = frozenset({"R1", "R2"})


class SystemFinding(Contract):
    """One measured F-SYS fault; part identifies the body half for R3."""

    code: SystemCode
    value: float
    threshold: float | None = None
    part: Literal["upper", "lower"] | None = None
    where: str | None = None
    detail: str | None = None


class SystemDiagnosis(Contract):
    """One episode's system verdict, with unjudged checks and input hashes."""

    episode_id: str = Field(min_length=1)
    diagnosis: SystemLabel
    config_sha256: str = Field(pattern=SHA256)
    trace_sha256: str = Field(pattern=SHA256)
    rtc_sha256: str | None = Field(default=None, pattern=SHA256)
    camera_sha256: str | None = Field(default=None, pattern=SHA256)
    infra_sha256: str | None = Field(default=None, pattern=SHA256)
    infra_status: str | None = None
    findings: list[SystemFinding]
    skipped: list[DiagnosisSkip]
    # Rollout timing the check used; None = unknown, judged as async (FR21).
    timing: Literal["sync", "async"] | None = None
    # R1/R2 on a sync rollout: measured and kept, never counted in the label
    # (PO decision (a), 5/11/2026).
    recorded: list[SystemFinding] = Field(default_factory=list)
    recorded_skipped: list[DiagnosisSkip] = Field(default_factory=list)

    @model_validator(mode="after")
    def clean_requires_completed_checks(self) -> "SystemDiagnosis":
        if self.diagnosis == "clean" and (self.findings or self.skipped):
            raise ValueError("clean requires no findings and no skipped checks")
        return self

    @model_validator(mode="after")
    def recorded_only_for_sync_timing_checks(self) -> "SystemDiagnosis":
        codes = [item.code for item in self.recorded] + [
            item.code for item in self.recorded_skipped
        ]
        if codes and self.timing != "sync":
            raise ValueError("recorded checks require timing == 'sync'")
        if any(code not in RECORDED_CODES for code in codes):
            raise ValueError(f"only {sorted(RECORDED_CODES)} may be recorded")
        counted = [item.code for item in self.findings] + [item.code for item in self.skipped]
        if self.timing == "sync" and RECORDED_CODES.intersection(counted):
            raise ValueError("a sync rollout records R1/R2, it does not count them")
        return self


class ProbeMeasurement(Contract):
    """A probe measurement supporting an attribution hypothesis."""

    probe: str = Field(min_length=1)
    where: str = Field(min_length=1)
    value: float
    threshold: float | None = None


class StageHypothesis(Contract):
    """A proposed attribution; confirmation belongs to the engineer."""

    row_id: str = Field(min_length=1)
    attribute_to: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    consumes_budget: bool
    confirmed: bool = False
    evidence: list[ProbeMeasurement] = Field(default_factory=list)


class StageAttribution(Contract):
    """Stage hypotheses and unavailable table rows for one failure."""

    episode_id: str = Field(min_length=1)
    table_sha256: str = Field(pattern=SHA256)
    failed_step: int | None = Field(default=None, ge=0)
    hypotheses: list[StageHypothesis]
    unavailable: list[DiagnosisSkip]
