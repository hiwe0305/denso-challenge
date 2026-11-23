"""Write a tray eval batch as `RolloutOutcome` records, so the lanes can read it (DA-43 K1).

The tray eval writes one outcome row per rollout in the adapter's own shape
(`outcomes.jsonl` of `eval_batch`); no lane may read that (03 section 7.3). This command
turns each row into the contract `RolloutOutcome` (`flywheel.contracts.outcome`).

Rollouts and `episode_id` are those of `export_scores`: per condition, the earliest
finished attempt (`eval_results.collect`), `episode_id` `<run>/l<level>-s<seed>`, so an
outcome joins its `Score` by `episode_id`. Per rollout:

    run_plan_id        the eval set's, `environment_config.flywheel.run_plan_id` of the
                       condition's row in `conditions.jsonl`
    sim_time_s         the row's `sim_time_s`
    control_steps      the row's `steps` (the env's step count)
    verdict            the sim's scorer: the seven step names of `eval_results.STEP_NAMES`,
                       `step_latched` from `scorer_steps`, success, failure label, and
                       `scorer_version` as `export_scores` stamps it. Same limit as there:
                       the stamp names the scorer at EXPORT time; the eval batch records no
                       version of the predicates it scored with. The row has no failure time,
                       no latch times and no state at failure: `failure_t`, `step_latch_t`
                       and `at_failure` are left absent, never filled in
    final              the state at the end of the episode, `FINAL_MEASURES`:
        tray_pos_m           final tray position (x, y, z), world frame, m
        tray_quat            final tray orientation (w, x, y, z): the row's `tray_quat` is
                             MuJoCo's `xquat` of the tray body, scalar first, the contract's
                             order (checked against `place_error.yaw_of` in the tests)
        tray_yaw_rad         yaw of `tray_quat`, `place_error.yaw_of`, rad in [-pi, pi]
        target_xy_m          the target zone's centre (x, y) on table B, rebuilt from
                             (level, seed) with `sample_episode`, m (the zone has no z)
        target_yaw_rad       the target zone's yaw from the same sample, rad
        place_distance_m     |tray_xy - target_xy|, `place_error.pose_error`, m
        place_yaw_error_deg  yaw error under the tray's half-turn symmetry,
                             `place_error.pose_error`, deg in [0, 90]
    extrema, videos    empty: the batch records no extrema, and no video path per rollout

A missing rollout, or a row without `sim_time_s`, `steps`, `scorer_steps`, `tray_pos` or
`tray_quat`, stops the export (exit 1) and lists it; nothing is written. So does a row
the contract refuses: the contract (`ScorerVerdict`) sets `failure_t` exactly when
`failure_label` is, and the eval batch has no failure time, so a labelled failure cannot
be written until the contract lets `failure_t` be absent; the error names the rollouts.

    python -m flywheel_psi0.tray.export_outcomes --set <eval set> --out <eval_batch dir> \
        --run C_70 --outcomes <file> [--max-chunks 6] [--chunk 10]

`flywheel_simple` is imported when the command runs, as `place_error` does.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.outcome import RolloutOutcome, ScorerVerdict
from pydantic import ValidationError

from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for
from flywheel_psi0.tray.eval_results import STEP_NAMES, Rollout, collect
from flywheel_psi0.tray.export_scores import SCORER_VERSION, TASK_ID, episode_id
from flywheel_psi0.tray.place_error import pose_error, yaw_of

Target = tuple[float, float, float]  # x, y, yaw of the target zone
FINAL_MEASURES = (
    "tray_pos_m",
    "tray_quat",
    "tray_yaw_rad",
    "target_xy_m",
    "target_yaw_rad",
    "place_distance_m",
    "place_yaw_error_deg",
)
REQUIRED = ("success", "sim_time_s", "steps", "scorer_steps", "tray_pos", "tray_quat")


def final_measures(row: dict[str, Any], target: Target) -> dict[str, Any]:
    """The `final` measures of one outcome row, against the target (x, y, yaw)."""
    pos = [float(v) for v in row["tray_pos"]]
    quat = [float(v) for v in row["tray_quat"]]
    distance, yaw_error = pose_error(pos, quat, target)
    return {
        "tray_pos_m": pos,
        "tray_quat": quat,
        "tray_yaw_rad": yaw_of(quat),
        "target_xy_m": [float(target[0]), float(target[1])],
        "target_yaw_rad": float(target[2]),
        "place_distance_m": distance,
        "place_yaw_error_deg": yaw_error,
    }


def outcome_of(rollout: Rollout, run: str, run_plan_id: str, target: Target) -> RolloutOutcome:
    row = rollout.row
    success = bool(row["success"])
    verdict = ScorerVerdict(
        scorer_version=SCORER_VERSION,
        step_names=list(STEP_NAMES),
        step_latched=[bool(v) for v in row["scorer_steps"]],
        success=success,
        failure_label=None if success else row.get("failure"),
    )
    return RolloutOutcome(
        episode_id=episode_id(run, rollout),
        run_plan_id=run_plan_id,
        task_id=TASK_ID,
        run=run,
        seed=rollout.seed,
        level=rollout.level,
        repeat=0,
        sim_time_s=float(row["sim_time_s"]),
        control_steps=int(row["steps"]),
        verdict=verdict,
        final=final_measures(row, target),
    )


def run_plan_ids(rows: Sequence[dict[str, Any]]) -> dict[tuple[int, int], str]:
    """(level, seed) -> the eval set's run_plan_id, from each condition's environment_config."""
    out = {}
    for row in rows:
        config = row.get("environment_config") or {}
        plan_id = (config.get("flywheel") or {}).get("run_plan_id")
        if plan_id:
            out[(int(row["level"]), int(row["seed"]))] = str(plan_id)
    return out


def default_target_of() -> Callable[[int, int], Target]:
    from flywheel_simple.tray.config import TrayConfig
    from flywheel_simple.tray.randomize import sample_episode

    cfg = TrayConfig.load()

    def target_of(level: int, seed: int) -> Target:
        t = sample_episode(cfg, level, seed).target_pose
        return float(t.x), float(t.y), float(t.yaw)

    return target_of


def export(
    eval_set: Path,
    out: Path,
    run: str,
    chunk: int = 10,
    max_chunks: int | None = None,
    target_of: Callable[[int, int], Target] | None = None,
) -> list[RolloutOutcome]:
    rows: list[dict[str, Any]] = [
        json.loads(line) for line in (eval_set / "conditions.jsonl").read_text().splitlines()
    ]
    chunks = chunk_plan(rows, chunk, phases_for(rows))
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    chosen, _, missing = collect(out, chunks)
    if missing:
        raise ValueError(f"rollouts missing for (level, seed) {missing}")
    plan_ids = run_plan_ids(rows)
    incomplete = [
        (r.level, r.seed, [k for k in REQUIRED if r.row.get(k) is None])
        for r in chosen
        if any(r.row.get(k) is None for k in REQUIRED) or (r.level, r.seed) not in plan_ids
    ]
    if incomplete:
        raise ValueError(f"rollouts without a field, or a run_plan_id in the set: {incomplete}")
    target_of = target_of or default_target_of()
    outcomes, refused = [], []
    for r in chosen:
        try:
            target = target_of(r.level, r.seed)
            outcomes.append(outcome_of(r, run, plan_ids[(r.level, r.seed)], target))
        except ValidationError as exc:
            first = exc.errors()[0]
            refused.append((r.level, r.seed, r.row.get("failure"), first["msg"]))
    if refused:
        raise ValueError(f"{len(refused)} rollouts the contract refuses: {refused}")
    return outcomes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--out", type=Path, required=True, help="eval_batch directory")
    parser.add_argument("--run", required=True, help="run name, e.g. C_70")
    parser.add_argument("--outcomes", type=Path, required=True, help="outcomes.jsonl to write")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--max-chunks", type=int, help="first N chunks only (6: stage 1)")
    args = parser.parse_args(argv)
    if "/" in args.run:
        parser.error("--run may not hold '/': it is the first part of every episode_id")
    if args.outcomes.exists():
        parser.error(f"{args.outcomes} exists; write to a new file")
    try:
        outcomes = export(args.set, args.out, args.run, args.chunk, args.max_chunks)
    except ValueError as exc:
        print(f"export_outcomes: {exc}", file=sys.stderr)
        return 1
    args.outcomes.parent.mkdir(parents=True, exist_ok=True)
    args.outcomes.write_text("".join(o.model_dump_json(exclude_none=True) + "\n" for o in outcomes))
    print(json.dumps({"outcomes": len(outcomes), "file": str(args.outcomes)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
