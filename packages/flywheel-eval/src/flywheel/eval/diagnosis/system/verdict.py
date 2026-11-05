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

**R6 is not a policy fault, and it comes first.** `infra_status` says the
simulator or the server, not the policy, is what failed (AC 1; design section
10; 03 section 4.3, rule 8). When it did, the commands and measurements, the
latency and the buffer are its consequences, so R6 outranks every other code:
an episode that crashed the simulator is labelled `infra`, never `controller`,
and never counts as a clean run either. The other codes that fired still
travel in `findings` (decision Q1 of the PO, 3/11/2026).

**On a synchronous rollout R1 and R2 are recorded, not counted** (decision
(a) of the PO, 5/11/2026). SIMPLE waits for the server before it steps the
sim, so however slow the inference was, nothing moved while it ran: latency
cannot be what made a sim episode fail, the same reason R4 is 0 by
construction there. R1 and R2 are still measured, because the numbers say
what the robot would meet on hardware, but they go into `recorded` (and a
missing RTC log into `recorded_skipped`), which neither clears an episode nor
keeps it from the data attribution. Only an asynchronous rollout (DA-23)
counts them. A rollout whose mode nobody wrote down is not taken for a
synchronous one: R1 and R2 count, and their detail says the mode was unknown
(FR21).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal

from flywheel.eval.diagnosis.train.finding import Skipped

# R6 first: a failed simulator or server makes every other measurement a
# consequence of it (decision Q1, 3/11/2026; spec section 6.4 does not place
# R6 in its order). Then R3 before R1 and R2 before R4 before R5: the order of
# spec section 6.4.
SYSTEM_CODES = ("R6", "R3", "R1", "R2", "R4", "R5")

# Codes a synchronous rollout records without counting (decision (a), 5/11/2026).
RECORDED_ON_SYNC = ("R1", "R2")

Timing = Literal["sync", "async"]

_SYNC_NOTE = (
    "rollout đồng bộ: SIMPLE chờ server rồi mới bước sim, nên độ trễ không làm hỏng được "
    "episode trong sim; ghi nhận, không quy lỗi (quyết định (a) của PO, 5/11/2026)"
)
_UNKNOWN_NOTE = (
    "không rõ rollout đồng bộ hay bất đồng bộ (RolloutResult không ghi), "
    "nên tính như bất đồng bộ"
)


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

    `threshold` is None where the rule counts measurements rather than
    comparing against a number, the same way `DiagnosisFinding.threshold` of
    the contract is None for T1 on a loss that is not finite. A calibration
    reference that does not match is such a rule: there is no number to be
    over, so the count of cameras that disagree is the measurement and
    `detail` says what disagreed.
    """

    code: str
    value: float
    threshold: float | None
    part: str | None = None
    where: str | None = None
    detail: str | None = None

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
    it, and `infra_status` is recorded whether or not R6 fired. `recorded` and
    `recorded_skipped` are what a synchronous rollout measured on R1 and R2
    without counting it (module docstring); they never touch the label.
    `timing` is the rollout's mode as the inputs stated it, None where they
    did not.

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
    recorded: list[SystemFinding] = field(default_factory=list)
    recorded_skipped: list[Skipped] = field(default_factory=list)
    timing: Timing | None = None

    @property
    def blocks_policy_analysis(self) -> bool:
        return self.diagnosis is not Diagnosis.CLEAN


def combine(
    episode_id: str,
    results: list[CheckResult],
    infra_status: str | None,
    timing: Timing | None = None,
) -> SystemVerdict:
    """Fold every check of one episode into one verdict, in the order of spec 6.4.

    The label is the first code to fire in `SYSTEM_CODES` order. Where nothing
    fired but something went unjudged the label is UNKNOWN rather than CLEAN:
    "no fault found" and "no fault looked for" are different answers, and only
    one of them clears an episode (AC 1, first step of the ordered check).

    On a synchronous rollout R1 and R2 are set aside into `recorded` first, so
    they decide neither way; with `timing` None they count, and say why.
    """
    findings = [finding for result in results for finding in result.findings]
    skipped = [skip for result in results for skip in result.skipped]
    recorded: list[SystemFinding] = []
    recorded_skipped: list[Skipped] = []
    if timing == "sync":
        recorded = [
            replace(finding, detail=_noted(finding.detail, _SYNC_NOTE))
            for finding in findings
            if finding.code in RECORDED_ON_SYNC
        ]
        recorded_skipped = [
            Skipped(skip.code, _noted(skip.reason, _SYNC_NOTE))
            for skip in skipped
            if skip.code in RECORDED_ON_SYNC
        ]
        findings = [finding for finding in findings if finding.code not in RECORDED_ON_SYNC]
        skipped = [skip for skip in skipped if skip.code not in RECORDED_ON_SYNC]
    elif timing is None:
        findings = [
            replace(finding, detail=_noted(finding.detail, _UNKNOWN_NOTE))
            if finding.code in RECORDED_ON_SYNC
            else finding
            for finding in findings
        ]
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
        recorded=_in_order(recorded),
        recorded_skipped=recorded_skipped,
        timing=timing,
    )


def _noted(text: str | None, note: str) -> str:
    return note if not text else f"{text}; {note}"


def _in_order(findings: list[SystemFinding]) -> list[SystemFinding]:
    """Findings in the order of the ordered check, so the label is the first row."""
    return sorted(findings, key=lambda finding: SYSTEM_CODES.index(finding.code))
