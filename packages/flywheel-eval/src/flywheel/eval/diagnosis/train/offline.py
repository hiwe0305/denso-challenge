"""O1-O4 - the action faults a P3 probe shows without running the robot (design 10).

F-OFF is what can be said about a checkpoint from replaying it against held-out
demonstrations: which action group it is worst at (O1), whether the error grows
along the action chunk (O2), whether the hand opens and closes at the wrong
moment (O3), and whether it commands joints past their limits (O4). None of
these needs a simulator, so they are the cheapest evidence the loop has, and
they run before any rollout is paid for.

The limits of O4 come from the `ActionLayout` of the embodiment, never from a
number in this module (AC 2): G1 has five padding dimensions that drive nothing
(S1-07), and a probe naming one of them is a layout mismatch to report, not an
action fault. `LayoutView` of the reader is the one place those are read.

`ProbeP3` is already a handful of plain numbers on no axis, so these detectors
read the record directly instead of going through a series view - there is
nothing to put on an axis. The rest of the reader rule still holds: no detector
here opens a file, and no threshold is written in this module.
"""

from __future__ import annotations

import numpy as np
from flywheel.contracts.artifacts import ProbeP3
from flywheel.eval.config import TrainThresholds
from flywheel.eval.diagnosis.train.finding import DetectorResult, Finding, Skipped
from flywheel.eval.diagnosis.train.forgetting import NO_STEP
from flywheel.eval.diagnosis.train.reader import LayoutView
from flywheel.eval.diagnosis.train.series import linear_slope


def detect_offline(probe: ProbeP3, cfg: TrainThresholds, layout: LayoutView) -> DetectorResult:
    """Every F-OFF code on one probe result, each judged on its own signal.

    The codes are independent: a probe that cannot be judged on one of them is
    still judged on the others, so one missing field never costs three verdicts.
    """
    results = (
        detect_o1(probe, cfg),
        detect_o2(probe, cfg),
        detect_o3(probe, cfg),
        detect_o4(probe, cfg, layout),
    )
    return DetectorResult(
        findings=[finding for result in results for finding in result.findings],
        skipped=[skip for result in results for skip in result.skipped],
    )


def detect_o1(probe: ProbeP3, cfg: TrainThresholds) -> DetectorResult:
    """O1 - an action group whose offline error is past its budget.

    A group with a budget in `train.yaml` is judged against it. A group without
    one is judged against the median group of the same probe, which asks the
    only question answerable before the budgets are calibrated on real P3
    results: is this group much worse than the rest of the body? A run where
    every group is equally bad has no worst group, and that is a bad checkpoint
    rather than a bad group - the detector stays silent and T2 or O2 is where
    it shows.
    """
    errors = probe.error_by_group
    if not errors:
        return DetectorResult(skipped=[Skipped("O1", "P3 không ghi error_by_group")])
    median = float(np.median(np.asarray(sorted(errors.values()), dtype=np.float64)))
    findings = []
    for name, error in sorted(errors.items()):
        budget = cfg.o1.max_error_by_group.get(name, median * cfg.o1.max_error_ratio)
        if error > budget:
            findings.append(
                Finding(
                    code="O1",
                    start_step=NO_STEP,
                    group=name,
                    dim=None,
                    value=error,
                    threshold=budget,
                )
            )
    return DetectorResult(findings=findings)


def detect_o2(probe: ProbeP3, cfg: TrainThresholds) -> DetectorResult:
    """O2 - error growing with the position inside the action chunk.

    Two rules under one code, because neither alone covers the shape of the
    fault. A slope fitted over the whole chunk catches error that drifts up
    across it, but a long chunk that is flat until the last few positions
    averages that slope away; the ratio of the last position to the first
    catches that. Either rule is one O2 finding, never two.
    """
    error = np.asarray(probe.error_by_chunk_pos, dtype=np.float64)
    finite = np.isfinite(error)
    if int(finite.sum()) < 2:
        return DetectorResult(
            skipped=[
                Skipped(
                    "O2",
                    "P3 ghi dưới 2 vị trí chunk hữu hạn trong error_by_chunk_pos, "
                    "một vị trí không thành xu hướng",
                )
            ]
        )
    position = np.arange(error.size, dtype=np.float64)
    slope = linear_slope(position, error)
    if np.isfinite(slope) and slope > cfg.o2.max_slope:
        return DetectorResult(findings=[_o2_finding(slope, cfg.o2.max_slope)])
    kept = np.flatnonzero(finite)
    first, last = float(error[kept[0]]), float(error[kept[-1]])
    if first > 0.0 and last / first > cfg.o2.max_ratio:
        return DetectorResult(findings=[_o2_finding(last / first, cfg.o2.max_ratio)])
    return DetectorResult()


def detect_o3(probe: ProbeP3, cfg: TrainThresholds) -> DetectorResult:
    """O3 - the hand event landing off the step the demonstration opens the hand at.

    Early and late are the same fault: a grasp that closes before the object is
    reached and one that closes after it has been pushed away both fail, so the
    distance is what is compared.
    """
    offset = abs(probe.hand_event_offset_steps)
    if not np.isfinite(offset):
        return DetectorResult(
            skipped=[Skipped("O3", "P3 ghi hand_event_offset_steps không hữu hạn")]
        )
    if offset <= cfg.o3.max_offset_steps:
        return DetectorResult()
    return DetectorResult(
        findings=[
            Finding(
                code="O3",
                start_step=NO_STEP,
                group=None,
                dim=None,
                value=offset,
                threshold=float(cfg.o3.max_offset_steps),
            )
        ]
    )


def detect_o4(probe: ProbeP3, cfg: TrainThresholds, layout: LayoutView) -> DetectorResult:
    """O4 - commanded actions outside the joint limits of the embodiment (AC 2).

    Branch (a) is membership: `max_fraction` is 0.0 by decision - one frame
    past a joint limit is already a fault - so a dimension appearing in
    `out_of_limit_dims` is one, and the probe listing it is the measurement.
    `value` is 1.0 and reads as "at least one frame", since P3 reports which
    dimensions left their limits and not how many frames did.

    Branch (b) is that missing count. A `max_fraction` above zero cannot be
    checked against anything P3 carries, so it skips under `O4b` rather than
    pass every checkpoint whose fraction nobody measured.

    Each listed dimension is checked against the layout, which is where AC 2
    lands: a masked dimension drives nothing and cannot leave a limit, a
    dimension the layout does not have means the probe ran under another
    layout, and a dimension the layout sets no limit for had nothing to leave.
    All three are skips naming the dimension.
    """
    if cfg.o4.max_fraction > 0.0:
        return DetectorResult(
            skipped=[
                Skipped(
                    "O4b",
                    f"o4.max_fraction = {cfg.o4.max_fraction:g} cần tỉ lệ khung vượt giới hạn, "
                    "P3 chỉ ghi out_of_limit_dims",
                )
            ]
        )
    low, high = layout.limits()
    findings: list[Finding] = []
    skipped: list[Skipped] = []
    for dim in sorted(set(probe.out_of_limit_dims)):
        if dim >= layout.n_dims:
            skipped.append(
                Skipped(
                    "O4",
                    f"P3 báo chiều {dim} vượt giới hạn nhưng action_layout "
                    f"chỉ có {layout.n_dims} chiều",
                )
            )
            continue
        if not bool(layout.unmasked[dim]):
            skipped.append(
                Skipped(
                    "O4",
                    f"chiều {dim} (`{layout.name(dim)}`) là chiều masked của action_layout, "
                    "không điều khiển gì nên không có giới hạn để vượt",
                )
            )
            continue
        if not (np.isfinite(low[dim]) or np.isfinite(high[dim])):
            skipped.append(
                Skipped(
                    "O4",
                    f"action_layout không đặt giới hạn nào cho chiều {dim} "
                    f"(`{layout.name(dim)}`), không có ngưỡng để so",
                )
            )
            continue
        findings.append(
            Finding(
                code="O4",
                start_step=NO_STEP,
                group=layout.layout.dimensions[dim].group,
                dim=dim,
                value=1.0,
                threshold=cfg.o4.max_fraction,
            )
        )
    return DetectorResult(findings=findings, skipped=skipped)


def _o2_finding(value: float, threshold: float) -> Finding:
    return Finding(
        code="O2",
        start_step=NO_STEP,
        group=None,
        dim=None,
        value=value,
        threshold=threshold,
    )
