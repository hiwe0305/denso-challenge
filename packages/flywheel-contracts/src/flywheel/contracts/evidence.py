"""Evidence card: what an engineer decides one failure cluster on (DA-39).

Spec v10.5 section 4.5 lists what a card holds; sections 6.4-6.14 say where
each part comes from. The card is a view, not a catalog table: the evaluation
lane rebuilds it from `Cluster`, `Score`, the system diagnosis and the stage
attribution, and the engineer's part from a `Decision` (03 section 2.4, no
revision at L0). So it is a plain model here, not an entity of `entities.py`,
and it is never stored in the catalog.

Three rules shape it, because they are what makes a card evidence rather than
an opinion:

* **What was not judged reads as not judged (FR21).** Every check the card
  needs is present, with a value and the threshold it was judged by or with
  the reason it could not be run. Whether a check fired is recomputed here
  from its value and threshold, so a card cannot claim a pass its own numbers
  contradict, and an episode with a system check left unjudged cannot carry a
  data diagnosis.
* **The algorithm proposes, the engineer decides (spec section 6.14).** Stage
  hypotheses are proposals until the card has a decision; an override names
  what it overrides and why.
* **A cost says whether it was estimated or measured**, and points at the
  ledger rows it adds up, as `LedgerEntry` keeps the two apart.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from typing_extensions import Self

SHA256 = r"^[0-9a-f]{64}$"
LEDGER_ID = r"^led_[0-9A-HJKMNP-TV-Z]{26}$"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# F-SYS codes of design 27/10/2026 section 10.
SystemCode = Literal["R1", "R2", "R3", "R4", "R5", "R6"]

# Rows of the stage attribution table (spec section 6.4, design section 10), by
# the `row_id` of configs/eval/diagnosis/stage.yaml.
StageRow = Literal[
    "stage1_perception",
    "stage3_action_group",
    "runtime_distribution_shift",
    "stage3_forgetting",
    "out_of_domain",
]

# The 11 diagnoses of spec section 6.9 and `infra` of R6. English names as in
# `Diagnosis` of DA-13; the Vietnamese ones are a display concern:
# unknown CHƯA RÕ, controller LỖI CONTROLLER, runtime LỖI RUNTIME, sync LỖI ĐỒNG
# BỘ, calibration LỖI CALIBRATION, infeasible KHÔNG KHẢ THI, bad_start_state
# TRẠNG THÁI ĐẦU XẤU, perception NHẬN THỨC, out_of_domain NGOÀI MIỀN,
# coverage_gap THIẾU VÙNG PHỦ, weak_skill KỸ NĂNG YẾU.
Diagnosis = Literal[
    "unknown",
    "infra",
    "controller",
    "runtime",
    "sync",
    "calibration",
    "infeasible",
    "bad_start_state",
    "perception",
    "out_of_domain",
    "coverage_gap",
    "weak_skill",
]
SYSTEM_DIAGNOSES: frozenset[str] = frozenset(
    {"unknown", "infra", "controller", "runtime", "sync", "calibration"}
)
# The only three that spend the data budget (spec section 6.9).
DATA_DIAGNOSES: frozenset[str] = frozenset({"bad_start_state", "coverage_gap", "weak_skill"})

InterventionKind = Literal[
    "sim_s1",
    "sim_s2",
    "sim_s3",
    "sim_s4",
    "teleop_correction",
    "recovery_data",
    "repair_ticket",
    "report_only",
]
BUDGET_INTERVENTIONS: frozenset[str] = frozenset(
    {"sim_s1", "sim_s2", "sim_s3", "sim_s4", "teleop_correction", "recovery_data"}
)
# What each diagnosis may propose (spec sections 6.9 and 6.10).
INTERVENTIONS_OF_DIAGNOSIS: dict[str, frozenset[str]] = {
    **{diagnosis: frozenset({"repair_ticket"}) for diagnosis in SYSTEM_DIAGNOSES},
    "infeasible": frozenset({"repair_ticket"}),
    "perception": frozenset({"report_only"}),
    "out_of_domain": frozenset({"report_only"}),
    "bad_start_state": frozenset({"recovery_data"}),
    "coverage_gap": frozenset({"sim_s1", "sim_s2", "sim_s3", "sim_s4"}),
    "weak_skill": frozenset({"teleop_correction"}),
}

CheckName = Literal[
    "infra_status",
    "tracking_error",
    "latency_p99",
    "buffer_underruns",
    "sync_offset",
    "camera_reference",
    "camera_intrinsics_px",
    "camera_position_m",
    "camera_quaternion",
    "planner_feasible",
    "reset_success",
    "nominal_visuals",
    "in_train_domain",
    "coverage_distance",
]
# When a check fires, i.e. when the condition of its diagnosis holds:
# above / at_or_above compare a number with its threshold; differs compares a
# hash with the reference; not_in compares a status with the accepted ones;
# false / true is the flag value that fires.
Rule = Literal["above", "at_or_above", "differs", "not_in", "false", "true"]
CHECK_RULES: dict[str, Rule] = {
    "infra_status": "not_in",  # R6
    "tracking_error": "above",  # R3, one per part: upper_body, lower_body
    "latency_p99": "above",  # R1
    "buffer_underruns": "above",  # R2
    "sync_offset": "above",  # R4
    "camera_reference": "differs",  # R5, hash of the G0 reference
    "camera_intrinsics_px": "above",  # R5, tolerance per camera
    "camera_position_m": "above",  # R5
    "camera_quaternion": "above",  # R5
    "planner_feasible": "false",  # step 5: fires as KHÔNG KHẢ THI
    "reset_success": "at_or_above",  # step 6: s_k >= tau_k fires as TRẠNG THÁI ĐẦU XẤU
    "nominal_visuals": "true",  # step 7: success under level-0 visuals fires as NHẬN THỨC
    "in_train_domain": "false",  # step 8: fires as NGOÀI MIỀN
    "coverage_distance": "above",  # step 8: d > tau_cov fires as THIẾU VÙNG PHỦ
}
CHECK_CODES: dict[str, SystemCode] = {
    "infra_status": "R6",
    "tracking_error": "R3",
    "latency_p99": "R1",
    "buffer_underruns": "R2",
    "sync_offset": "R4",
    "camera_reference": "R5",
    "camera_intrinsics_px": "R5",
    "camera_position_m": "R5",
    "camera_quaternion": "R5",
}
# Every representative answers these, judged or not; the per-camera tolerances
# are extra detail of R5.
REQUIRED_CHECKS: frozenset[str] = frozenset(CHECK_RULES) - {
    "camera_intrinsics_px",
    "camera_position_m",
    "camera_quaternion",
}
SYSTEM_CHECKS: frozenset[str] = frozenset(CHECK_CODES)
# The check that has to have fired for a representative to carry the diagnosis.
FIRED_FOR_DIAGNOSIS: dict[str, frozenset[str]] = {
    "infra": frozenset({"infra_status"}),
    "controller": frozenset({"tracking_error"}),
    "runtime": frozenset({"latency_p99", "buffer_underruns"}),
    "sync": frozenset({"sync_offset"}),
    "calibration": frozenset(name for name, code in CHECK_CODES.items() if code == "R5"),
    "infeasible": frozenset({"planner_feasible"}),
    "bad_start_state": frozenset({"reset_success"}),
    "perception": frozenset({"nominal_visuals"}),
    "out_of_domain": frozenset({"in_train_domain"}),
    "coverage_gap": frozenset({"coverage_distance"}),
}

FailureClass = Literal["approach", "grasp", "carry", "place", "balance"]
Outcome = Literal["fired", "not_fired", "not_judged"]


def _fires(
    rule: Rule, value: float | bool | str, threshold: float | str | list[str] | None
) -> bool:
    if rule == "above":
        return float(value) > float(threshold)  # type: ignore[arg-type]
    if rule == "at_or_above":
        return float(value) >= float(threshold)  # type: ignore[arg-type]
    if rule == "differs":
        return value != threshold
    if rule == "not_in":
        return value not in threshold  # type: ignore[operator]
    return value is (rule == "true")


class CheckResult(Contract):
    """One check of one representative, with what it was judged by."""

    check: CheckName
    # Which half of the WBC (R3) or which camera (R5); None for a whole-episode check.
    part: str | None = Field(default=None, min_length=1)
    outcome: Outcome
    value: StrictBool | float | str | None = None
    # A number, the reference hash (camera_reference) or the accepted statuses
    # (infra_status); None for a flag, whose firing value is CHECK_RULES. A
    # not-judged check may keep the threshold it would have been judged by.
    threshold: float | str | list[str] | None = None
    # s_k comes with its counts (spec section 4.5): n_success of n_runs resets.
    n_success: int | None = Field(default=None, ge=0)
    n_runs: int | None = Field(default=None, ge=1)
    skipped_reason: str | None = Field(default=None, min_length=1)
    note: str | None = None

    @property
    def code(self) -> SystemCode | None:
        return CHECK_CODES.get(self.check)

    @model_validator(mode="after")
    def _judged_by_its_threshold(self) -> Self:
        if self.outcome == "not_judged":
            if self.value is not None or self.skipped_reason is None:
                raise ValueError(f"{self.check}: a check not judged has no value and a reason")
            return self
        if self.skipped_reason is not None:
            raise ValueError(f"{self.check}: a judged check has no skipped_reason")
        if self.value is None:
            raise ValueError(f"{self.check}: a judged check has a value")
        rule = CHECK_RULES[self.check]
        self._check_types(rule)
        if self.check == "reset_success":
            self._check_counts()
        fired = _fires(rule, self.value, self.threshold)
        if self.outcome != ("fired" if fired else "not_fired"):
            raise ValueError(
                f"{self.check}: value {self.value!r} against {self.threshold!r} "
                f"is {'fired' if fired else 'not_fired'}, not {self.outcome}"
            )
        return self

    def _check_types(self, rule: Rule) -> None:
        value, threshold = self.value, self.threshold
        if rule in ("above", "at_or_above"):
            ok = not isinstance(value, (bool, str)) and isinstance(threshold, float)
            expected = "a number and a numeric threshold"
        elif rule == "differs":
            ok = all(isinstance(x, str) and len(x) == 64 for x in (value, threshold))
            expected = "a sha256 and the reference sha256"
        elif rule == "not_in":
            ok = isinstance(value, str) and isinstance(threshold, list) and bool(threshold)
            expected = "a status and the accepted statuses"
        else:
            ok = isinstance(value, bool) and threshold is None
            expected = "a flag and no threshold"
        if not ok:
            raise ValueError(f"{self.check}: needs {expected}")
        if self.check != "reset_success" and (self.n_success, self.n_runs) != (None, None):
            raise ValueError(f"{self.check}: only reset_success has counts")

    def _check_counts(self) -> None:
        if self.n_success is None or self.n_runs is None or self.n_success > self.n_runs:
            raise ValueError("reset_success: needs n_success <= n_runs")
        if not math.isclose(float(self.value), self.n_success / self.n_runs):  # type: ignore[arg-type]
            raise ValueError("reset_success: value is n_success / n_runs")


class ProbeEvidence(Contract):
    """One probe measurement behind a stage hypothesis (`EvidenceRecord` of DA-13)."""

    probe: Literal["P1", "P2", "P3", "P4", "-"]
    where: str = Field(min_length=1)
    value: float
    # None where the row's own rule decides: T7 of DA-08, the in-domain check.
    threshold: float | None = None


class StageHypothesis(Contract):
    """A row of the stage table that applied, as a proposal (spec section 6.4)."""

    row_id: StageRow
    attribute_to: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    consumes_budget: bool
    # Only the engineer sets it, on the card (EvidenceCard checks there is a decision).
    confirmed: bool = False
    evidence: list[ProbeEvidence] = Field(default_factory=list)


class Unavailable(Contract):
    """A stage row nobody could judge, and why."""

    row_id: StageRow
    reason: str = Field(min_length=1)


class Representative(Contract):
    """One failure episode the expensive checks ran on (spec section 6.3)."""

    episode_id: str = Field(min_length=1)
    score_id: str = Field(pattern=r"^sc_[0-9a-f]{16}$")
    condition_seed: int | None = None
    trace_sha256: str = Field(pattern=SHA256)
    # Thresholds the checks were judged by, and the stage table.
    system_config_sha256: str = Field(pattern=SHA256)
    stage_table_sha256: str | None = Field(default=None, pattern=SHA256)
    checks: list[CheckResult]
    stage_hypotheses: list[StageHypothesis] = Field(default_factory=list)
    stage_unavailable: list[Unavailable] = Field(default_factory=list)
    diagnosis: Diagnosis

    @model_validator(mode="after")
    def _diagnosis_follows_the_checks(self) -> Self:
        keys = [(check.check, check.part) for check in self.checks]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{self.episode_id}: a check appears twice")
        missing = REQUIRED_CHECKS - {check.check for check in self.checks}
        if missing:
            raise ValueError(f"{self.episode_id}: checks missing, not judged: {sorted(missing)}")
        system = [check for check in self.checks if check.check in SYSTEM_CHECKS]
        if self.diagnosis == "unknown":
            if all(check.outcome != "not_judged" for check in system):
                raise ValueError(f"{self.episode_id}: unknown needs a system check not judged")
        elif self.diagnosis not in SYSTEM_DIAGNOSES and any(
            check.outcome != "not_fired" for check in system
        ):
            # System first, data after (spec section 6.9).
            raise ValueError(
                f"{self.episode_id}: {self.diagnosis} needs every system check judged, none fired"
            )
        fired = {check.check for check in self.checks if check.outcome == "fired"}
        needed = FIRED_FOR_DIAGNOSIS.get(self.diagnosis)
        if needed is not None and not fired & needed:
            raise ValueError(f"{self.episode_id}: {self.diagnosis} needs one of {sorted(needed)}")
        coverage = next(check for check in self.checks if check.check == "coverage_distance")
        if self.diagnosis == "weak_skill" and coverage.outcome != "not_fired":
            raise ValueError(f"{self.episode_id}: weak_skill needs coverage_distance d <= tau_cov")
        return self


class Cost(Contract):
    """Money and hours, estimated or measured, as the ledger rows add them up."""

    measure_kind: Literal["estimated", "measured"]
    usd_amount: float = Field(ge=0)
    human_hours: float = Field(default=0.0, ge=0)
    ledger_entry_ids: list[Annotated[str, Field(pattern=LEDGER_ID)]] = Field(min_length=1)


class ExpectedGain(Contract):
    """g_j of spec section 6.11, in points of dev success."""

    n_failures: int = Field(ge=1)  # m_j
    cap: int = Field(ge=1)  # L_t of section 6.10
    n_effective: int = Field(ge=1)  # n_eff_j = min(m_j, L_t)
    n_dev: int = Field(ge=1)  # N_dev
    fix_rate_alpha: float = Field(gt=0)  # Beta(alpha, beta) of f_t
    fix_rate_beta: float = Field(gt=0)
    expected_gain_pp: float = Field(ge=0)

    @model_validator(mode="after")
    def _formula(self) -> Self:
        if self.n_effective != min(self.n_failures, self.cap):
            raise ValueError("n_effective is min(n_failures, cap)")
        mean = self.fix_rate_alpha / (self.fix_rate_alpha + self.fix_rate_beta)
        expected = 100.0 * self.n_effective / self.n_dev * mean
        if not math.isclose(self.expected_gain_pp, expected, rel_tol=1e-6, abs_tol=1e-9):
            raise ValueError(f"expected_gain_pp is 100 * n_eff / n_dev * mean f_t = {expected}")
        return self


class InterventionProposal(Contract):
    """What the algorithm proposes for the cluster (spec sections 6.9-6.11)."""

    kind: InterventionKind
    description: str = Field(min_length=1)
    consumes_budget: bool
    # Amount after the per-cluster cap: rollouts, corrections or segments.
    quantity: int | None = Field(default=None, ge=1)
    unit: str | None = Field(default=None, min_length=1)
    gain: ExpectedGain | None = None
    cost: Cost | None = None
    intervention_id: str | None = Field(default=None, pattern=r"^iv_[0-9A-HJKMNP-TV-Z]{26}$")

    @model_validator(mode="after")
    def _budget(self) -> Self:
        if self.consumes_budget != (self.kind in BUDGET_INTERVENTIONS):
            raise ValueError(f"{self.kind}: consumes_budget is {self.kind in BUDGET_INTERVENTIONS}")
        if self.consumes_budget and None in (self.quantity, self.unit, self.gain, self.cost):
            raise ValueError("a data intervention has quantity, unit, gain and cost")
        if self.cost is not None and self.cost.measure_kind != "estimated":
            raise ValueError("a proposal's cost is estimated")
        return self


class EngineerDecision(Contract):
    """Accept or override, as the `Decision` it is regenerated from (spec section 6.14)."""

    verdict: Literal["accept", "override"]
    decision_id: str = Field(pattern=r"^dec_[0-9A-HJKMNP-TV-Z]{26}$")
    signed_by: str = Field(min_length=1)
    reason: str | None = None
    # What an override changes; both None on an accept.
    diagnosis: Diagnosis | None = None
    intervention: InterventionKind | None = None

    @model_validator(mode="after")
    def _override_has_a_reason(self) -> Self:
        if self.verdict == "accept":
            if self.diagnosis is not None or self.intervention is not None:
                raise ValueError("an accept changes neither diagnosis nor intervention")
            return self
        if self.reason is None or not self.reason.strip():
            raise ValueError("an override needs a reason (spec section 6.14)")
        if self.diagnosis is None and self.intervention is None:
            raise ValueError("an override names the diagnosis or intervention it changes")
        return self


class RetrainResult(Contract):
    """Fix rate measured against the parent on new conditions (spec section 6.13)."""

    parent_checkpoint_id: str = Field(min_length=1)
    candidate_checkpoint_id: str = Field(min_length=1)
    n_conditions: int = Field(ge=1)
    runs_per_condition: int = Field(ge=3)
    p_parent: float = Field(ge=0, le=1)
    p_candidate: float = Field(ge=0, le=1)
    fixed: int = Field(ge=0)
    fix_rate_event_id: str | None = Field(default=None, pattern=r"^fre_[0-9A-HJKMNP-TV-Z]{26}$")
    gate_decision_id: str | None = Field(default=None, pattern=r"^dec_[0-9A-HJKMNP-TV-Z]{26}$")
    cost: Cost

    @model_validator(mode="after")
    def _fixed(self) -> Self:
        if self.cost.measure_kind != "measured":
            raise ValueError("a retrain result's cost is measured")
        raw = self.n_conditions * (self.p_candidate - self.p_parent)
        clamped = min(max(raw, 0.0), float(self.n_conditions))
        if self.fixed > self.n_conditions or abs(self.fixed - clamped) > 0.5 + 1e-9:
            raise ValueError(f"fixed is round(n * (p_candidate - p_parent)) in [0, n] = {clamped}")
        return self


class EvidenceCard(Contract):
    """One card per failure cluster (spec section 4.5). Not a catalog table."""

    schema_version: str = "1.0.0"
    cluster_id: str = Field(pattern=r"^clu_[0-9a-f]{16}$")
    run_plan_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    embodiment_id: str = Field(min_length=1)
    level: int = Field(ge=0, le=2)
    first_failed_step: int = Field(ge=1)  # k
    failure_kind: str = Field(pattern=r"^L-[A-Z][A-Z-]*$")
    failure_class: FailureClass | None = None
    member_episode_ids: list[str] = Field(min_length=1)
    # Seed the representatives were drawn with; None when every member was checked.
    representative_seed: int | None = None
    representatives: list[Representative] = Field(min_length=1)
    # Majority of the representatives; None on a tie, which the engineer decides.
    diagnosis: Diagnosis | None
    proposal: InterventionProposal | None
    decision: EngineerDecision | None = None
    result: RetrainResult | None = None

    @model_validator(mode="after")
    def _card_is_consistent(self) -> Self:
        self._check_members()
        self._check_majority()
        self._check_proposal()
        self._check_engineer()
        return self

    def _check_members(self) -> None:
        members = set(self.member_episode_ids)
        if len(members) != len(self.member_episode_ids):
            raise ValueError("member_episode_ids are unique")
        checked = [rep.episode_id for rep in self.representatives]
        if len(set(checked)) != len(checked) or not set(checked) <= members:
            raise ValueError("representatives are distinct members of the cluster")
        if len(checked) < len(members) and self.representative_seed is None:
            raise ValueError("representatives drawn from the members record their seed")

    def _check_majority(self) -> None:
        votes: dict[str, int] = {}
        for rep in self.representatives:
            votes[rep.diagnosis] = votes.get(rep.diagnosis, 0) + 1
        top = max(votes.values())
        leaders = sorted(label for label, count in votes.items() if count == top)
        expected = leaders[0] if len(leaders) == 1 else None
        if self.diagnosis != expected:
            raise ValueError(f"diagnosis is the majority of the representatives: {expected}")

    def _check_proposal(self) -> None:
        if (self.diagnosis is None) != (self.proposal is None):
            raise ValueError("a proposal follows the diagnosis; a tie has neither")
        if self.diagnosis is None or self.proposal is None:
            return
        allowed = INTERVENTIONS_OF_DIAGNOSIS[self.diagnosis]
        if self.proposal.kind not in allowed:
            raise ValueError(f"{self.diagnosis} proposes one of {sorted(allowed)}")
        gain = self.proposal.gain
        if gain is not None and gain.n_failures != len(self.member_episode_ids):
            raise ValueError("gain.n_failures is the number of members")

    def _check_engineer(self) -> None:
        decision = self.decision
        if decision is None:
            if any(h.confirmed for rep in self.representatives for h in rep.stage_hypotheses):
                raise ValueError("a stage hypothesis is confirmed by the engineer's decision")
            if self.result is not None:
                raise ValueError("a retrain result follows the engineer's decision")
            return
        if self.diagnosis is None and decision.diagnosis is None:
            raise ValueError("a tie is decided by an override naming the diagnosis")
        if decision.diagnosis is not None and decision.diagnosis == self.diagnosis:
            raise ValueError("an override to the proposed diagnosis is an accept")
        proposal_kind = self.proposal.kind if self.proposal else None
        if decision.intervention is not None and decision.intervention == proposal_kind:
            raise ValueError("an override to the proposed intervention is an accept")
        final = decision.intervention or proposal_kind
        if self.result is not None and final not in BUDGET_INTERVENTIONS:
            raise ValueError("only a data intervention is retrained on")


__all__ = [
    "BUDGET_INTERVENTIONS",
    "CHECK_CODES",
    "CHECK_RULES",
    "DATA_DIAGNOSES",
    "INTERVENTIONS_OF_DIAGNOSIS",
    "REQUIRED_CHECKS",
    "CheckResult",
    "Cost",
    "EngineerDecision",
    "EvidenceCard",
    "ExpectedGain",
    "InterventionProposal",
    "ProbeEvidence",
    "Representative",
    "RetrainResult",
    "StageHypothesis",
    "Unavailable",
]
