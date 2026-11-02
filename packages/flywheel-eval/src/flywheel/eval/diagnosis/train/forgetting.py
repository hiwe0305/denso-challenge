"""T7 - the fine-tune lost something its parent checkpoint had (design 10).

A fine-tune that improves the task and loses the language grounding is still a
regression, and nothing in `metrics.jsonl` shows it: the loss of the new data
falls the whole way. T7 is the only code of this story that compares two
checkpoints, so it needs the P4 probe of the child and of its parent, and it
reads which parent to look for from the child's own record, never from a guess.

Two things keep the comparison meaningful.

**Direction.** P1 reports accuracy, where higher is better; P3 reports error
and a hand-event offset, where higher is worse. The plan writes the rule as
`(parent - child) / parent`, which is the drop of a score; on an error the same
fault shows up as `(child - parent) / parent`. Both are the same question -
*how much of the parent's standing did the child lose* - so the sign is decided
per metric here, and `relative_drop` of `series.py` computes either.

**The same probe set.** A score is only comparable against a score measured on
the same probe data, so the `dataset_sha256` of both probes has to match. That
is the guarantee the plan asked Long for, already in the contract.

What this cannot do is judge the first fine-tune off the published checkpoint:
P4 runs after a fine-tune, so the published parent has none (design 8.3). That
case is a skip naming the parent, not a clean verdict - the demo runs exactly
it, and a silent pass there would be the worst place to have one (FR21).
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
from flywheel.contracts.artifacts import ProbeP4
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.series import relative_drop

# A probe is measured on a checkpoint, not at a step of the train job, so an
# offline finding has no step to point at. `DiagnosisFinding.start_step` is
# required and non-negative, so it is 0 and means "not a step of this log".
NO_STEP = 0


def detect_t7(child: ProbeP4, parent: ProbeP4 | None, cfg: TrainThresholds) -> DetectorResult:
    """Which probe metrics of `child` fell behind the `parent` checkpoint it came from."""
    if parent is None:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T7",
                    f"không có kết quả P4 của checkpoint cha `{child.parent_checkpoint_id}`; "
                    "lần fine-tune đầu từ checkpoint công bố chưa có P4 của cha (design 8.3)",
                )
            ]
        )
    if parent.checkpoint_id != child.parent_checkpoint_id:
        return DetectorResult(
            skipped=[
                Skipped(
                    "T7",
                    f"P4 đưa vào là của checkpoint `{parent.checkpoint_id}`, "
                    f"không phải cha `{child.parent_checkpoint_id}` của bản đang chẩn",
                )
            ]
        )
    if mismatch := _probe_set_mismatch(child, parent):
        return DetectorResult(skipped=[Skipped("T7", mismatch)])

    findings: list[Finding] = []
    skipped: list[Skipped] = []
    for name, child_value, parent_value, higher_is_better in _paired_metrics(child, parent):
        if child_value is None or parent_value is None:
            missing = "con" if child_value is None else "cha"
            skipped.append(
                Skipped("T7", f"chỉ số `{name}` chỉ có ở một bên, thiếu ở bên {missing}")
            )
            continue
        regression = _regression(parent_value, child_value, higher_is_better)
        if regression is None:
            continue  # the child is no worse than its parent on this metric
        if not np.isfinite(regression):
            skipped.append(
                Skipped(
                    "T7",
                    f"chỉ số `{name}` kém đi nhưng giá trị của cha là {parent_value:g}, "
                    "không có thang để tính mức giảm tương đối",
                )
            )
            continue
        if regression > cfg.t7.max_relative_drop:
            findings.append(
                Finding(
                    code="T7",
                    start_step=NO_STEP,
                    group=name,
                    dim=None,
                    value=regression,
                    threshold=cfg.t7.max_relative_drop,
                )
            )
    return DetectorResult(findings=findings, skipped=skipped)


def _probe_set_mismatch(child: ProbeP4, parent: ProbeP4) -> str | None:
    """Why the two P4 results are not measured on comparable probe data, if so."""
    for probe, child_hash, parent_hash in (
        ("P1", child.p1.dataset_sha256, parent.p1.dataset_sha256),
        ("P3", child.p3.dataset_sha256, parent.p3.dataset_sha256),
    ):
        if child_hash != parent_hash:
            return (
                f"{probe} của hai checkpoint chạy trên bộ probe khác nhau "
                f"(dataset_sha256 {child_hash[:12]}… so với {parent_hash[:12]}…), "
                "điểm của hai bên không so được với nhau"
            )
    return None


def _paired_metrics(
    child: ProbeP4, parent: ProbeP4
) -> Iterator[tuple[str, float | None, float | None, bool]]:
    """Every metric either probe carries, as `(name, child, parent, higher_is_better)`.

    A metric one side does not have comes out with None on that side: the
    caller names it as a skip, because a checkpoint cannot be cleared on a
    metric nobody measured on both ends.
    """
    yield from _paired_mapping(
        "p1",
        child.p1.accuracy_by_question_type,
        parent.p1.accuracy_by_question_type,
        higher_is_better=True,
    )
    yield from _paired_mapping(
        "p3.error_by_group",
        child.p3.error_by_group,
        parent.p3.error_by_group,
        higher_is_better=False,
    )
    # The offset is a distance from the demonstrated step; which side of it the
    # event landed on says nothing about how much was forgotten.
    yield (
        "p3.hand_event_offset_steps",
        abs(child.p3.hand_event_offset_steps),
        abs(parent.p3.hand_event_offset_steps),
        False,
    )


def _paired_mapping(
    prefix: str,
    child: dict[str, float],
    parent: dict[str, float],
    *,
    higher_is_better: bool,
) -> Iterator[tuple[str, float | None, float | None, bool]]:
    for key in sorted(set(child) | set(parent)):
        yield f"{prefix}.{key}", child.get(key), parent.get(key), higher_is_better


def _regression(parent: float, child: float, higher_is_better: bool) -> float | None:
    """Share of the parent's standing the child lost; None when it lost none.

    nan when the child is worse but the parent value carries no scale to be
    relative to, which the caller reports as a skip rather than as a number it
    made up.
    """
    worse = child < parent if higher_is_better else child > parent
    if not worse:
        return None
    if higher_is_better:
        return relative_drop(parent, child)
    return -relative_drop(parent, child)
