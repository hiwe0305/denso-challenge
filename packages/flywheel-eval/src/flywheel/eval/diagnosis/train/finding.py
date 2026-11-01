"""What one F-TRAIN or F-OFF detector returns (DA-08 AC 1, 4).

A detector answers with two lists, never with one. `findings` is what it caught;
`skipped` is what it could not judge and why. An empty `findings` list cannot
carry "I had nothing to judge this on", so a detector that returned findings
alone would turn a missing signal into a clean checkpoint - the silent pass
FR21 forbids. T7 without the parent probe, T8 without `vlm_frozen` and T6 on a
dimension whose target std is zero all take the `skipped` path.

These are lane-internal types, not contract records. Task 6 maps them onto the
`TrainDiagnosis` record of `flywheel.contracts`, both lists of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    """One fault a detector caught, with the measurement it caught it by."""

    code: str
    start_step: int
    group: str | None
    dim: int | None
    value: float
    threshold: float
    stop_job: bool = False  # T1 only; the train adapter is what actually stops a job


@dataclass(frozen=True)
class Skipped:
    """A code the detector could not judge, and the reason in the reader's words."""

    code: str  # a code, or one branch of it: "T7", "T8a"
    reason: str


@dataclass(frozen=True)
class DetectorResult:
    """What one detector, or a whole run of them, concluded."""

    findings: list[Finding] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
