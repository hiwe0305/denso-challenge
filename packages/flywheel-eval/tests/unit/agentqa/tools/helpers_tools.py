"""Small synthetic records for the trace, training and lineage tool tests.

A plain module (not a conftest): mypy refuses two `conftest` modules in one run.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from flywheel.contracts.artifacts import DatasetReport, Episode
from flywheel.contracts.entities import Condition, LedgerEntry, Score
from flywheel.contracts.outcome import RolloutOutcome, ScorerVerdict
from flywheel.contracts.trace import LOWER_BODY, UPPER_BODY, FloatOrNonFinite, TraceStep
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.tools.base import (
    JobMetrics,
    RunOutcomes,
    RunScores,
    RunTrace,
    TraceFile,
)

SHA = "0" * 64


def rollout(run: str, name: str, cycles: int = 10, *, upper_gap: float = 0.0,
            lower_gap: float = 0.0, speed: float = 0.0, cmd_speed: float | None = None,
            nan_at: int | None = None) -> list[TraceStep]:
    """`cycles` control cycles of episode `<run>/<name>`.

    The command of upper channel 0 leads the measurement by `upper_gap` rad, the command
    of `waist_pitch` by `lower_gap` rad; the base moves at `speed` m/s along x, and the
    command says `cmd_speed` (the same by default). `nan_at` sets one measured upper
    channel to "NaN" on that cycle.
    """
    steps = []
    for k in range(cycles):
        cmd_up: list[FloatOrNonFinite] = [0.0] * len(UPPER_BODY)
        meas_up: list[FloatOrNonFinite] = [0.0] * len(UPPER_BODY)
        cmd_up[0] = upper_gap
        if k == nan_at:
            meas_up[1] = "NaN"
        cmd_lo: list[FloatOrNonFinite] = [0.0] * len(LOWER_BODY)
        meas_lo: list[FloatOrNonFinite] = [0.0] * len(LOWER_BODY)
        cmd_lo[LOWER_BODY.index("waist_pitch")] = lower_gap
        cmd_lo[LOWER_BODY.index("vx")] = speed if cmd_speed is None else cmd_speed
        meas_lo[LOWER_BODY.index("vx")] = speed
        steps.append(TraceStep(
            trace_id=f"tr-{run}-{name}", episode_id=f"{run}/{name}", run_plan_id="rp-1",
            step=k, t_state=0.1 * k, t_image=None, cmd_upper=cmd_up, meas_upper=meas_up,
            cmd_lower=cmd_lo, meas_lower=meas_lo))
    return steps


def score(run: str, name: str, success: bool | None) -> Score:
    return Score(episode_id=f"{run}/{name}", task_id="tray", config_sha256=SHA,
                 trace_sha256=SHA, success=success)


def run_of(run: str, outcomes: dict[str, bool | None]) -> RunScores:
    return RunScores(run, f"{run}/scores.jsonl",
                     tuple(score(run, n, ok) for n, ok in outcomes.items()))


FILE_SHA = "f" * 64  # matches no score: such a file is split by episode_id


def trace_of(run: str, steps: Sequence[TraceStep]) -> RunTrace:
    return RunTrace(run, (TraceFile(f"{run}/trace.jsonl", FILE_SHA, tuple(steps)),))


def trace_file(ref: str, sha: str, steps: Sequence[TraceStep]) -> TraceFile:
    return TraceFile(ref, sha, tuple(steps))


def scored(run: str, name: str, success: bool | None, sha: str) -> Score:
    """A score whose rollout file has sha256 `sha`."""
    return score(run, name, success).model_copy(update={"trace_sha256": sha})


def metric(job: str, step: int, loss: float | Literal["NaN"], *, split: str = "train",
           checkpoint: str = "ckpt-1", release: str = "rel-1", groups: dict[str, float] | None
           = None, vlm: float | None = None, action: float | None = None) -> TrainingMetric:
    return TrainingMetric(
        run_plan_id="rp-1", job_id=job, checkpoint_id=checkpoint, release_id=release,
        attempt=0, step=step, epoch=0, split=split,  # type: ignore[arg-type]
        loss=loss, lr=1e-4, vlm_frozen=True, loss_by_group=groups or {},
        grad_norm_vlm=vlm, grad_norm_action=action, wall_time_s=float(step))


def job_of(job: str, rows: Sequence[TrainingMetric]) -> JobMetrics:
    return JobMetrics(job, f"{job}/metrics.jsonl", tuple(rows))


def episode(episode_id: str, checkpoint: str | None) -> Episode:
    return Episode(
        episode_id=episode_id, kind="eval_rollout", operator_kind="machine", is_root=False,
        condition_id="c1", checkpoint_id=checkpoint, run_plan_id="rp-1", bundle_uri="b/x",
        license="example", data_class="public", split="eval", source_kind="synthetic",
        action_quality="none", deid_status="verified", embodiment_id="g1",
        meta={})  # type: ignore[arg-type]


def report(dataset_id: str) -> DatasetReport:
    return DatasetReport(dataset_id=dataset_id, episode_count=1)


def condition(level: int, seed: int, values: dict[str, object]) -> Condition:
    """A condition whose components are read by name from `values` (`vector` stays empty)."""
    return Condition(condition_seed=seed, level=level, values=values, layout_hash="h")


def ledger_row(kind: str, activity: str, resource: str, unit: str, quantity: float,
               usd: float, estimate: str | None = None, job: str = "job-1") -> LedgerEntry:
    return LedgerEntry.model_validate({
        "activity": activity, "resource_type": resource, "quantity": quantity, "unit": unit,
        "usd_amount": usd, "measure_kind": kind, "estimate_entry_id": estimate,
        "run_plan_id": "g0-DA-43-20261121", "job_id": job})


def labelled(run: str, name: str, success: bool, label: str | None = None, level: int = 1,
             first_failed: int | None = None) -> Score:
    """A score with a failure label and a level; `first_failed` defaults to `place` (5)."""
    return Score(episode_id=f"{run}/{name}", task_id="tray", config_sha256=SHA,
                 trace_sha256=SHA, success=success, failure_kind=label, level=level,
                 first_failed_step=None if success else (5 if first_failed is None
                                                         else first_failed))


def outcome(run: str, name: str, success: bool, label: str | None = None, level: int = 1, *,
            final: dict[str, object] | None = None, failure_t: float | None = None,
            task_id: str = "tray") -> RolloutOutcome:
    """The K1 outcome of episode `<run>/<name>`; a failure gets `failure_t` 1 s by default."""
    t = (1.0 if failure_t is None else failure_t) if label is not None else None
    verdict = ScorerVerdict(scorer_version="2", step_names=["approach_a", "place"],
                            step_latched=[True, success], success=success,
                            failure_label=label, failure_t=t)
    return RolloutOutcome(episode_id=f"{run}/{name}", run_plan_id="rp-1", task_id=task_id,
                          run=run, seed=1, level=level, sim_time_s=10.0, control_steps=500,
                          verdict=verdict, final=final or {})  # type: ignore[arg-type]


def outcomes_of(run: str, rows: Sequence[RolloutOutcome]) -> RunOutcomes:
    return RunOutcomes(run, f"{run}/outcomes.jsonl", tuple(rows))
