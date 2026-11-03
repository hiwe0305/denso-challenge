"""What one F-SYS check concludes about one episode (DA-13 AC 1).

These are lane-internal types, not contract records, the same split DA-08 made
between `Finding` and `TrainDiagnosis` and DA-36 made between `EpisodeScore`
and `Score`. `artifact.py` maps them onto the record the other lanes read.

Three things shape them.

**A check that could not run is not a check that passed.** Every check answers
with a measurement or with a reason it has none, so an episode whose RTC log
was never written cannot come back as an episode with no latency fault - the
silent pass FR21 forbids. `Skipped` of DA-08 carries the same idea for
F-TRAIN, and it is reused here rather than copied.

**The diagnosis is one label, the findings are all of them.** Spec section 6.4
orders the checks, and the label is the first fault in that order, because that
is the fault an engineer fixes first. Every other measurement still travels in
`findings`, so the engineer sees a sync offset that fired as well as the
tracking error that outranked it. Running every check costs nothing: they are
pure arithmetic over arrays already in memory.

**R6 is not a policy fault.** `infra_status` says the server, not the policy,
is what failed (AC 1; 03 section 4.3, rule 8). It is recorded and it becomes
the label only where nothing else fired, so an episode that crashed the
simulator never counts as a controller fault and never counts as a clean run
either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from flywheel.eval.diagnosis.train.finding import Skipped

# R3 before R1 and R2 before R4 before R5: the order of spec section 6.4. R6 is
# last because it is the one code that is not a statement about the policy.
SYSTEM_CODES = ("R3", "R1", "R2", "R4", "R5", "R6")


class SystemError(ValueError):
    """An episode the system check must not turn into a verdict."""


class Diagnosis(str, Enum):
    """The label one episode gets from the system check (spec section 6.4).

    The values are what goes into the record; the Vietnamese names of spec
    section 6.4 are a display concern and live in `cli.py`, so the artifact
    stays readable to a reader with no Vietnamese.
    """

    CLEAN = "clean"
    UNKNOWN = "unknown"
    CONTROLLER = "controller"
    RUNTIME = "runtime"
    SYNC = "sync"
    CALIBRATION = "calibration"
    INFRA = "infra"


# Which label each code carries when it is the first one to fire.
DIAGNOSIS_OF_CODE: dict[str, Diagnosis] = {
    "R1": Diagnosis.RUNTIME,
    "R2": Diagnosis.RUNTIME,
    "R3": Diagnosis.CONTROLLER,
    "R4": Diagnosis.SYNC,
    "R5": Diagnosis.CALIBRATION,
    "R6": Diagnosis.INFRA,
}


@dataclass(frozen=True)
class SystemFinding:
    """One system fault, with the measurement it was caught by.

    `part` names the half of the body a tracking error belongs to, since spec
    section 6.4 measures the upper and the lower body against their own
    thresholds and a finding that did not say which would send the engineer to
    the wrong half of the WBC configuration. It is None on every other code.

    `where` is the trace row, the chunk index or the camera uid the measurement
    came from - the evidence AC 3 asks a hypothesis to carry.
    """

    code: str
    value: float
    threshold: float
    part: str | None = None
    where: str | None = None

    def __post_init__(self) -> None:
        if self.code not in SYSTEM_CODES:
            raise SystemError(f"mã `{self.code}` không thuộc F-SYS {list(SYSTEM_CODES)}")


@dataclass(frozen=True)
class CheckResult:
    """What one check concluded: faults it caught, and codes it could not judge."""

    findings: list[SystemFinding] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


@dataclass(frozen=True)
class SystemVerdict:
    """The whole system check of one episode (AC 1).

    `diagnosis` is the label, `findings` and `skipped` are the evidence behind
    it, and `infra_status` is recorded whether or not R6 fired.

    `blocks_policy_analysis` is what a caller asks instead of reading the label
    and deciding for itself. An episode is not usable as evidence about the
    policy when the system is what failed, or when the check could not be made
    at all; spec section 6.4 fixes system faults first and re-runs the
    baseline, because the old measurement no longer holds.
    """

    episode_id: str
    diagnosis: Diagnosis
    findings: list[SystemFinding] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    infra_status: str | None = None

    @property
    def blocks_policy_analysis(self) -> bool:
        return self.diagnosis is not Diagnosis.CLEAN


def combine(episode_id: str, results: list[CheckResult], infra_status: str | None) -> SystemVerdict:
    """Fold every check of one episode into one verdict, in the order of spec 6.4.

    The label is the first code to fire in `SYSTEM_CODES` order. Where nothing
    fired but something went unjudged the label is UNKNOWN rather than CLEAN:
    "no fault found" and "no fault looked for" are different answers, and only
    one of them clears an episode (AC 1, first step of the ordered check).
    """
    findings = [finding for result in results for finding in result.findings]
    skipped = [skip for result in results for skip in result.skipped]
    fired = {finding.code for finding in findings}
    diagnosis = Diagnosis.CLEAN
    for code in SYSTEM_CODES:
        if code in fired:
            diagnosis = DIAGNOSIS_OF_CODE[code]
            break
    else:
        if skipped:
            diagnosis = Diagnosis.UNKNOWN
    return SystemVerdict(
        episode_id=episode_id,
        diagnosis=diagnosis,
        findings=_in_order(findings),
        skipped=skipped,
        infra_status=infra_status,
    )


def _in_order(findings: list[SystemFinding]) -> list[SystemFinding]:
    """Findings in the order of the ordered check, so the label is the first row."""
    return sorted(findings, key=lambda finding: SYSTEM_CODES.index(finding.code))
