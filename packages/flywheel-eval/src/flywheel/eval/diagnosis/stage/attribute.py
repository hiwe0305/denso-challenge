"""Which stage of Ψ₀ a failure is blamed on, and the probe behind the claim.

Spec section 6.4, step 4b, and design section 10 hold one table since
30/10/2026. It runs after the system check and the data check have cleared a
failure, and before the feasibility check of step 5.

Three rules shape this module.

**A hypothesis is a proposal, never an intervention.** AC 4 is explicit: the
engineer confirms it on the evidence card. So nothing here decides anything -
a `StageHypothesis` carries the row it came from, the probe values behind it
and the suggested intervention as the text of the table, and `confirmed` is
False on everything this module produces. The Stage 1 row goes further and
consumes no budget at all, because spec section 7.3 fixes visual augmentation
for every branch and leaves no data intervention to ask for.

**A hypothesis with no probe behind it is not stated.** An episode whose P1
never ran cannot be blamed on perception and cannot be cleared of it either,
so the rows that need P1 come back as `unavailable` naming the probe, the same
way DA-08 skips a code whose input is missing. Guessing either way is the
silent pass FR21 forbids.

**Out of domain is not a stage.** The last row of the table says so, and when
it applies it is the only row stated: blaming a stage for a condition outside
the train domain is what that row exists to prevent (spec section 6.8). The
rest of the evidence still travels in the record, so the engineer sees it.

The evidence rules are code and the table is config. `stage.yaml` can reword a
row, change what it blames or change what it suggests without a code change -
which is what the decision of 28/10/2026 asked for - but it cannot invent a
rule, and the loader refuses a row whose `evidence` nothing implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from flywheel.contracts.artifacts import ProbeP1, ProbeP3
from flywheel.eval.config import StageRow, StageTable, StageThresholds
from flywheel.eval.diagnosis.system.reader import StageInputs

# Every evidence rule this module implements, in the order of the table. The
# loader checks `stage.yaml` against this, so a row nobody implements cannot
# sit in the table never firing.
EVIDENCE_RULES = (
    "p1_wrong_on_failure_frames",
    "p3_high_on_related_group",
    "p3_low_but_closed_loop_failed",
    "t7_after_finetune",
    "out_of_domain",
)

OUT_OF_DOMAIN = "out_of_domain"

# What a rule says when the probe it needs is not there. A reason, not an empty
# answer: a row nobody could judge must not read as a row that did not apply.
NO_P1 = "không có kết quả probe P1 của checkpoint"
NO_P3 = "không có kết quả probe P3 của checkpoint"
NO_P4 = "không có kết quả probe P4 của checkpoint sau fine-tune"
NO_GROUPS = "không biết nhóm action nào liên quan tới bước hỏng"
NO_T7 = "chưa có kết luận T7 của DA-08 cho checkpoint này"


@dataclass(frozen=True)
class Evidence:
    """One measurement behind a hypothesis (AC 3): which probe, where, what value."""

    probe: str
    where: str
    value: float
    threshold: float | None = None


# A rule answers with the evidence that makes it apply, a reason it could not
# be judged, or None where it simply does not apply.
Verdict = list[Evidence] | str | None


@dataclass(frozen=True)
class StageHypothesis:
    """One row of the table that applied, with its evidence and its proposal.

    `confirmed` is False on everything this module produces and nothing here
    ever sets it: it is the engineer's mark on the evidence card (AC 4).
    """

    row_id: str
    attribute_to: str
    intervention: str
    consumes_budget: bool
    evidence: list[Evidence] = field(default_factory=list)
    confirmed: bool = False


@dataclass(frozen=True)
class Unavailable:
    """A row that could not be decided, and the probe it was waiting for."""

    row_id: str
    reason: str


@dataclass(frozen=True)
class StageAttribution:
    """What the table concluded about one failure: proposals and what was unjudged."""

    hypotheses: list[StageHypothesis] = field(default_factory=list)
    unavailable: list[Unavailable] = field(default_factory=list)


def attribute_stage(inputs: StageInputs, table: StageTable) -> StageAttribution:
    """Apply the table to one failure (AC 3, 4).

    The input is one failure rather than one episode, because the table asks
    about the step that broke and the action groups behind it. A cluster is
    attributed by its representative; clustering itself is the Vòng lane's
    (`decide`, 07 section 2.0).
    """
    if inputs.out_of_domain:
        row = table.row(OUT_OF_DOMAIN)
        if row is None:
            return StageAttribution()
        return StageAttribution(hypotheses=[_hypothesis(row, [_out_of_domain_evidence(inputs)])])
    hypotheses: list[StageHypothesis] = []
    unavailable: list[Unavailable] = []
    for evidence in EVIDENCE_RULES:
        row = table.row(evidence)
        if row is None or evidence == OUT_OF_DOMAIN:
            continue
        verdict = _apply(evidence, inputs, table.thresholds)
        if isinstance(verdict, str):
            unavailable.append(Unavailable(row.row_id, verdict))
        elif verdict is not None:
            hypotheses.append(_hypothesis(row, verdict))
    return StageAttribution(hypotheses=hypotheses, unavailable=unavailable)


def _apply(evidence: str, inputs: StageInputs, cfg: StageThresholds) -> Verdict:
    """One evidence rule: the measurements that make it apply, a reason it cannot
    be judged, or None where the rule simply does not apply."""
    if evidence == "p1_wrong_on_failure_frames":
        return _p1_wrong(inputs, cfg)
    if evidence == "p3_high_on_related_group":
        return _p3_high(inputs, cfg)
    if evidence == "p3_low_but_closed_loop_failed":
        return _p3_low(inputs, cfg)
    if evidence == "t7_after_finetune":
        return _forgetting(inputs)
    return None


def _p1_wrong(inputs: StageInputs, cfg: StageThresholds) -> Verdict:
    """Row 1: P1 answered under the accuracy the table asks for.

    The table asks for P1 wrong "on the frames of this very failure", but
    `ProbeP1` is a score over a whole probe set (`dataset_sha256`) and knows
    nothing of which frames a failure saw. The evidence says so - it names the
    probe set, not frames - and a P1 scored per failure is a contract change
    for P1 (issue #70), not something this rule can claim.
    """
    if inputs.p1 is None:
        return NO_P1
    return _wrong_answers(inputs, cfg) or None


def _p3_high(inputs: StageInputs, cfg: StageThresholds) -> Verdict:
    """Row 2: P1 was right and P3 of a group behind the failed step is high."""
    if inputs.p1 is None:
        return NO_P1
    if _wrong_answers(inputs, cfg):
        return None  # perception was wrong, so row 1 applies and this one does not
    if inputs.p3 is None:
        return NO_P3
    if not inputs.action_groups:
        # Without the groups behind step k there is no "related group" to look
        # at, and looking at every group would blame whichever one happens to
        # be worst.
        return NO_GROUPS
    if not _related_errors(inputs, inputs.p3):
        return _no_related_group(inputs)
    return _high_groups(inputs, inputs.p3, cfg) or None


def _p3_low(inputs: StageInputs, cfg: StageThresholds) -> Verdict:
    """Row 3: P1 right, P3 low, and the closed loop broke anyway - a run-time shift."""
    if inputs.p1 is None:
        return NO_P1
    if _wrong_answers(inputs, cfg):
        return None  # perception was wrong, so row 1 applies and this one does not
    if inputs.p3 is None:
        return NO_P3
    if not inputs.closed_loop_failed:
        return None
    if not inputs.action_groups:
        return NO_GROUPS
    errors = _related_errors(inputs, inputs.p3)
    if not errors:
        return _no_related_group(inputs)
    worst = max(errors.values())
    if worst >= cfg.p3_low_error:
        if _high_groups(inputs, inputs.p3, cfg):
            return None  # P3 is high, so row 2 applies and this one does not
        # Neither low enough for this row nor high enough for row 2: said, so
        # the record does not come back empty as though every row was judged.
        return (
            f"P3 của nhóm liên quan nằm giữa hai ngưỡng: lớn nhất {worst:g}, không dưới "
            f"p3_low_error {cfg.p3_low_error:g} và không nhóm nào trên ngưỡng cao của nó; "
            f"không dòng P3 nào áp dụng"
        )
    return [
        Evidence(
            probe="P3",
            where=_step_label(inputs),
            value=worst,
            threshold=cfg.p3_low_error,
        )
    ]


def _forgetting(inputs: StageInputs) -> Verdict:
    """Row 4: a failure new after fine-tuning, with T7 of DA-08 on the checkpoint.

    T7 is passed in rather than recomputed. DA-08 owns the forgetting rule, and
    two stories computing it apart would eventually disagree about whether a
    checkpoint forgot. None means the caller has not run DA-08, which is not
    the same as T7 not firing, so it is unavailable rather than inapplicable.

    The other half of the row, "a failure new after fine-tuning", needs the
    failures of the parent checkpoint and is not checked here yet.
    """
    if inputs.p4 is None:
        return NO_P4
    if inputs.t7 is None:
        return NO_T7
    if not inputs.t7:
        return None
    return [
        Evidence(
            probe="P4",
            where=f"so với checkpoint cha `{inputs.p4.parent_checkpoint_id}`",
            value=_p4_score(inputs.p4.p1),
            threshold=None,
        )
    ]


def _related_errors(inputs: StageInputs, p3: ProbeP3) -> dict[str, float]:
    """The P3 error of every group behind the failed step that P3 measured."""
    measured = p3.error_by_group
    return {group: measured[group] for group in inputs.action_groups if group in measured}


def _high_groups(inputs: StageInputs, p3: ProbeP3, cfg: StageThresholds) -> list[Evidence]:
    """The related groups whose P3 error is over their threshold (row 2)."""
    high = []
    for group, error in _related_errors(inputs, p3).items():
        limit = cfg.p3_high_error_by_group.get(group, cfg.p3_high_error)
        if error > limit:
            high.append(
                Evidence(probe="P3", where=f"nhóm action `{group}`", value=error, threshold=limit)
            )
    return high


def _no_related_group(inputs: StageInputs) -> str:
    # Rows 2 and 3 lack the same data here, so they give the same answer.
    groups = ", ".join(f"`{group}`" for group in inputs.action_groups)
    return f"P3 không đo nhóm action nào của bước hỏng ({groups})"


def _wrong_answers(inputs: StageInputs, cfg: StageThresholds) -> list[Evidence]:
    """The P1 question types answered under the accuracy the table asks for.

    Rows 2 and 3 both start from "P1 đúng", so they ask this and stand down
    where it is non-empty: perception was wrong, row 1 applies, and blaming
    stage 3 as well would be two answers to one question.
    """
    if inputs.p1 is None:
        return []
    return [
        Evidence(
            probe="P1",
            where=_where(inputs.p1, kind),
            value=accuracy,
            threshold=cfg.p1_min_accuracy,
        )
        for kind, accuracy in sorted(inputs.p1.accuracy_by_question_type.items())
        if accuracy < cfg.p1_min_accuracy
    ]


def _out_of_domain_evidence(inputs: StageInputs) -> Evidence:
    return Evidence(probe="-", where=_step_label(inputs), value=1.0, threshold=None)


def _hypothesis(row: StageRow, evidence: list[Evidence]) -> StageHypothesis:
    return StageHypothesis(
        row_id=row.row_id,
        attribute_to=row.attribute_to,
        intervention=row.intervention,
        consumes_budget=row.consumes_budget,
        evidence=evidence,
    )


def _where(p1: ProbeP1, question_kind: str) -> str:
    return f"câu hỏi `{question_kind}`, tập probe P1 `{p1.dataset_sha256}`"


def _step_label(inputs: StageInputs) -> str:
    return "không rõ bước" if inputs.failed_step is None else f"bước {inputs.failed_step}"


def _p4_score(p1: ProbeP1) -> float:
    """The P1 score inside P4, averaged over question types, for the evidence line."""
    values = list(p1.accuracy_by_question_type.values())
    return sum(values) / len(values) if values else float("nan")


def related_groups(p3: ProbeP3) -> tuple[str, ...]:
    """Every action group a P3 result carries, for a caller with no step mapping.

    This is a fallback, not the rule: `StageInputs.action_groups` is meant to
    name the groups behind the failed step, which the task definition knows and
    this module does not.
    """
    return tuple(sorted(p3.error_by_group))
