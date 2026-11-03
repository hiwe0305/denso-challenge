"""R1, R2, R4, R5 and R6: the rest of the ordered system check (DA-13 AC 1).

Each check is its own function over its own input, so a file one check needs
never costs another check its verdict - the rule DA-08 settled on for the
twelve F-TRAIN codes.

* **R1 latency** (spec section 6.4, step 3): the p99 of the inference cycle
  over tau_lat, measured from the RTC log. Latency is the interval between the
  observation going out and the chunk coming back, which is what
  `RTCInferenceRecord` records.
* **R2 buffer** (design section 10): chunks whose inference took more control
  steps than the buffer had left when the request went out
  (`delay_steps > buffer_level`, the two fields `RTCClient` of DA-19 writes).
  Counted rather than averaged: a stall is a moment, and an average over a
  long episode hides it.
* **R4 sync** (step 4): the largest |t_image - t_state| over the episode,
  against tau_sync. Spec asks for the largest offset, not a percentile of it,
  because one badly paired frame is enough to make the policy act on a stale
  image.
* **R5 calibration** (step 5): the camera parameters against the reference
  pinned at G0, in two steps (decision Q3, 3/11/2026).
  `CameraParams.reference_sha256` is the hash of the G0-pinned reference the
  episode ran against, which the SimpleSim hook copies from the RunPlan - not
  a hash of the camera values the episode happens to have. R5 first compares
  that hash with `system.yaml`: an episode run against another reference is
  reported even where its numbers are close, because the comparison with the
  rest of the run is what the hash protects. It then compares the values
  with the pinned ones within tolerance, whatever the hash said, so a camera
  that drifted is caught on its numbers and the tolerances are never dead
  code behind the hash.
* **R6 infrastructure** (design section 10): `infra_status` that is not one of
  the healthy values. It is recorded, it never counts as a policy fault
  (AC 1; 03 section 4.3, rule 8), and it outranks every other code in the
  label (`verdict.py`).

What is absent is said, not assumed. An episode with no RTC log loses R1 and
R2 by name, and one with no camera parameters loses R5, which is what keeps
`combine` from clearing it.
"""

from __future__ import annotations

import numpy as np
from flywheel.contracts.artifacts import RTCInferenceRecord
from flywheel.eval.config import (
    CameraReference,
    R1Thresholds,
    R2Thresholds,
    R4Thresholds,
    R5Thresholds,
    R6Thresholds,
)
from flywheel.eval.diagnosis.system.reader import (
    CAMERA_NAME,
    RTC_NAME,
    CameraView,
    TraceLog,
    percentile,
)
from flywheel.eval.diagnosis.system.verdict import CheckResult, SystemFinding
from flywheel.eval.diagnosis.train.finding import Skipped


def check_r1(records: tuple[RTCInferenceRecord, ...], cfg: R1Thresholds) -> CheckResult:
    """Inference cycle latency against tau_lat (spec section 6.4, step 3)."""
    if not records:
        return CheckResult(skipped=[Skipped("R1", _no_rtc_log())])
    latency = np.array(
        [record.chunk_received_s - record.observation_sent_s for record in records],
        dtype=np.float64,
    )
    statistic = percentile(latency, cfg.percentile)
    if not np.isfinite(statistic) or statistic <= cfg.tau_lat_s:
        return CheckResult()
    worst = records[int(np.nanargmax(latency))]
    return CheckResult(
        findings=[
            SystemFinding(
                code="R1",
                value=statistic,
                threshold=cfg.tau_lat_s,
                where=f"chunk {worst.chunk_index}",
                detail=f"phân vị {cfg.percentile:g} của độ trễ chu kỳ suy luận, đơn vị giây",
            )
        ]
    )


def check_r2(records: tuple[RTCInferenceRecord, ...], cfg: R2Thresholds) -> CheckResult:
    """Chunks whose inference outlasted the actions left in the buffer (design section 10).

    `buffer_level` is the level when the request went out, not when the chunk
    came back, so a low level is healthy as long as it covers `delay_steps`.
    """
    if not records:
        return CheckResult(skipped=[Skipped("R2", _no_rtc_log())])
    underruns = [record for record in records if record.delay_steps > record.buffer_level]
    if len(underruns) <= cfg.max_underruns:
        return CheckResult()
    return CheckResult(
        findings=[
            SystemFinding(
                code="R2",
                value=float(len(underruns)),
                threshold=float(cfg.max_underruns),
                where=f"chunk {underruns[0].chunk_index}",
                detail=(
                    f"{len(underruns)} chunk có delay_steps lớn hơn buffer_level lúc gửi "
                    f"request, thiếu nhiều nhất "
                    f"{max(record.delay_steps - record.buffer_level for record in underruns)}"
                    f" action (chunk {underruns[0].chunk_index}: "
                    f"buffer {underruns[0].buffer_level}, trễ {underruns[0].delay_steps})"
                ),
            )
        ]
    )


def check_r4(trace: TraceLog, cfg: R4Thresholds) -> CheckResult:
    """The largest offset between the image clock and the state clock (step 4).

    **On a SIMPLE rollout this is 0 by construction.** SIMPLE steps the
    simulator synchronously and renders the frame at the sim time of the
    state, so the SimpleSim hook (DA-38) writes `t_image = t_state` on every
    cycle that carries a frame. R4 never fires on a sim rollout and that is
    correct, but a clean R4 there says nothing about sensor sync: it only
    measures something on teleop data and on the injected
    `timestamp_sync_offset` fault. Part 6 of the demo must not present "R4
    clean" on sim as sync having been checked.
    """
    offset = trace.sync_offset()
    statistic = percentile(offset, 100.0)  # the largest offset, as spec 6.4 asks
    if not np.isfinite(statistic):
        # No cycle paired a frame with a state; `signals.py` normally says so
        # first, and a direct caller must not read it as clocks that agreed.
        return CheckResult(
            skipped=[Skipped("R4", "không có chu kỳ nào có cả `t_image` và `t_state` hữu hạn")]
        )
    if statistic <= cfg.tau_sync_s:
        return CheckResult()
    return CheckResult(
        findings=[
            SystemFinding(
                code="R4",
                value=statistic,
                threshold=cfg.tau_sync_s,
                where=f"dòng trace {int(np.nanargmax(offset))}",
                detail="lệch lớn nhất giữa t_image và t_state, đơn vị giây",
            )
        ]
    )


def check_r5(cameras: tuple[CameraView, ...], cfg: R5Thresholds) -> CheckResult:
    """The camera parameters of the episode against the reference pinned at G0 (step 5).

    The hash first, then the values within tolerance, both for every camera
    the reference knows (decision Q3, 3/11/2026; module docstring).
    """
    if cfg.reference_sha256 is None:
        # Nothing to compare against. Comparing the declared numbers instead
        # would be judging an episode against a reference nobody has fixed,
        # and passing it would be the silent pass FR21 forbids (AC 2).
        return CheckResult(
            skipped=[Skipped("R5", "bản tham chiếu camera chưa ghim ở G0 (`system.yaml`, r5)")]
        )
    if not cameras:
        return CheckResult(
            skipped=[Skipped("R5", f"episode không có tham số camera (`{CAMERA_NAME}`)")]
        )
    findings: list[SystemFinding] = []
    skipped: list[Skipped] = []
    for camera in cameras:
        reference = cfg.cameras.get(camera.uid)
        if reference is None:
            # A camera nobody calibrated cannot be compared, and guessing that
            # it is fine is the silent pass FR21 forbids.
            skipped.append(
                Skipped(
                    "R5",
                    f"camera `{camera.uid}` không có trong bản tham chiếu của `system.yaml`",
                )
            )
            continue
        if camera.reference_sha256 != cfg.reference_sha256:
            findings.append(
                SystemFinding(
                    code="R5",
                    value=1.0,
                    threshold=None,
                    where=camera.uid,
                    detail=(
                        f"chạy theo bản tham chiếu `{camera.reference_sha256[:12]}…`, "
                        f"cấu hình ghim `{cfg.reference_sha256[:12]}…`"
                    ),
                )
            )
        findings.extend(_drifted(camera, reference, cfg))
    return CheckResult(findings=findings, skipped=skipped)


def check_r6(infra_status: str | None, cfg: R6Thresholds) -> CheckResult:
    """`infra_status` of the episode: the server, not the policy (AC 1)."""
    if infra_status is None:
        return CheckResult(skipped=[Skipped("R6", "episode không ghi `infra_status`")])
    if infra_status in cfg.ok_statuses:
        return CheckResult()
    return CheckResult(
        findings=[
            SystemFinding(
                code="R6",
                value=1.0,
                threshold=None,
                detail=f"`infra_status` là `{infra_status}`, không phải lỗi policy",
            )
        ]
    )


def _drifted(
    camera: CameraView, reference: CameraReference, cfg: R5Thresholds
) -> list[SystemFinding]:
    """Parameters of one camera that moved further than their tolerance allows.

    The render resolution and the mount body are compared exactly: they are
    integers and a name, so a difference is a different camera rather than
    drift, and a tolerance on them would mean nothing.
    """
    findings: list[SystemFinding] = []
    for name, got, want in (
        ("width", float(camera.width), float(reference.width)),
        ("height", float(camera.height), float(reference.height)),
    ):
        if got != want:
            findings.append(_drift(camera.uid, name, abs(got - want), 0.0))
    if camera.mount != reference.mount:
        findings.append(
            SystemFinding(
                code="R5",
                value=1.0,
                threshold=None,
                where=camera.uid,
                detail=f"gắn trên `{camera.mount}`, bản tham chiếu là `{reference.mount}`",
            )
        )
    for name in ("fx", "fy", "cx", "cy"):
        deviation = abs(getattr(camera, name) - getattr(reference, name))
        if deviation > cfg.tolerance_intrinsics_px:
            findings.append(_drift(camera.uid, name, deviation, cfg.tolerance_intrinsics_px))
    position = max(abs(got - want) for got, want in zip(camera.pose[:3], reference.pose[:3]))
    if position > cfg.tolerance_position_m:
        findings.append(_drift(camera.uid, "vị trí camera", position, cfg.tolerance_position_m))
    # q and -q are one rotation, so the deviation is the nearer of the two signs.
    orientation = min(
        max(abs(got - sign * want) for got, want in zip(camera.pose[3:], reference.pose[3:]))
        for sign in (1.0, -1.0)
    )
    if orientation > cfg.tolerance_quaternion:
        findings.append(_drift(camera.uid, "hướng camera", orientation, cfg.tolerance_quaternion))
    return findings


def _drift(uid: str, name: str, deviation: float, tolerance: float) -> SystemFinding:
    return SystemFinding(
        code="R5",
        value=deviation,
        threshold=tolerance,
        where=uid,
        detail=f"`{name}` lệch khỏi bản tham chiếu",
    )


def _no_rtc_log() -> str:
    return (
        f"episode không có bản ghi RTC nào (`{RTC_NAME}` thiếu, hoặc không có chunk của "
        f"`trace_id` này), không đo được độ trễ và buffer"
    )
