"""Write a tray eval batch as `RolloutOutcome` records, so the lanes can read it (DA-43 K1).

The tray eval writes one outcome row per rollout in the adapter's own shape
(`outcomes.jsonl` of `eval_batch`); no lane may read that (03 section 7.3). This command
turns each row into the contract `RolloutOutcome` (`flywheel.contracts.outcome`).

Rollouts and `episode_id` are those of `export_scores`: per condition and repeat, the
earliest finished attempt (`eval_results.collect`); `--repeats N` (as given to
`eval_batch`) reads the `.r<k>` directories, one outcome per rollout. `episode_id` is
`<run>/l<level>-s<seed>` for repeat 0 and `<run>/l<level>-s<seed>-r<k>` for repeat
k >= 1, so an outcome joins its `Score` by `episode_id`. Per rollout:

    run_plan_id        the eval set's, `environment_config.flywheel.run_plan_id` of the
                       condition's row in `conditions.jsonl`
    task_id            `export_scores.TASK_ID` ("tray"), on both scenes: the lanes key
                       their task view by it (configs/eval/agentqa/tasks/tray.yaml) and the
                       jig scene keeps the task's steps and labels
    repeat             the rollout's repeat
    sim_time_s         the row's `sim_time_s`
    control_steps      the row's `steps` (the env's step count)
    verdict            the sim's scorer: the seven step names of `eval_results.STEP_NAMES`,
                       `step_latched` from `scorer_steps`, success, failure label, and
                       `scorer_version` as `export_scores` stamps it
                       (`simple-tray-predicates@<n>` for a row of scorer version n, the bare
                       name for rows before DA-42). Rows of DA-42 also give `failure_t`,
                       `step_latch_t` and `at_failure`:
        tilt_deg             tray tilt from upright in the failure's cycle, deg
        tray_pos_m           tray position (x, y, z), world frame, m
        tray_quat            tray orientation (w, x, y, z)
        tray_on_table        "A", "B" or "none"
        hand_contact_left    left hand on its handle (bool)
        hand_contact_right   right hand on its handle (bool)
                       A label without a failure time (rows before DA-42) is written with
                       its label only: no `failure_t`, no `at_failure` (#211)
    other_verdicts     the row's `scorer_v1` (version 1 run beside the row's own on the same
                       states, DA-42) as `simple-tray-predicates@1`, same fields
    final              the state at the end of the episode, `FINAL_MEASURES`:
        tray_pos_m           final tray position (x, y, z), world frame, m
        tray_quat            final tray orientation (w, x, y, z): the row's `tray_quat` is
                             MuJoCo's `xquat` of the tray body, scalar first, the contract's
                             order (checked against `place_error.yaw_of` in the tests)
        tray_yaw_rad         yaw of `tray_quat`, `place_error.yaw_of`, rad in [-pi, pi]
        target_xy_m          the target zone's centre (x, y) on table B, rebuilt from
                             (level, seed) by the row's scene (`place_error.target_for`:
                             the jig target for `task_uid` JIG_TASK_UID, else
                             `sample_episode`), m (the zone has no z)
        target_yaw_rad       the target zone's yaw from the same sample, rad
        place_distance_m     |tray_xy - target_xy|, `place_error.pose_error`, m
        place_yaw_error_deg  yaw error under the tray's half-turn symmetry,
                             `place_error.pose_error`, deg in [0, 90]
    extrema            DA-42 rows: smallest palm distance over the episode, `EXTREMA`
                       (`palm_handle_*_min_m` to the handle centre, `palm_bar_*_min_m` to
                       the handle bar; `both` the smaller of the cycle's larger of two);
                       null values are left out
    videos             empty: the batch records no video path per rollout

A missing rollout, or a row without `sim_time_s`, `steps`, `scorer_steps`, `tray_pos` or
`tray_quat`, stops the export (exit 1) and lists it; nothing is written. So does a batch
whose rows mix scorer versions or scenes, and a row the contract refuses (a latch time
on a step not latched, a failure time after the episode, a failure time on a success):
the error names the rollouts; no row is altered to fit.

    python -m flywheel_psi0.tray.export_outcomes --set <eval set> --out <eval_batch dir> \
        --run C_70 --outcomes <file> [--max-chunks 6] [--chunk 10] [--repeats 3]

`flywheel_simple` is imported when the command runs, as `place_error` does.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.outcome import MeasureValue, RolloutOutcome, ScorerVerdict
from pydantic import ValidationError

from flywheel_psi0.tray.eval_results import (
    STEP_NAMES,
    Rollout,
    collect,
    repeats_note,
    scorer_version,
)
from flywheel_psi0.tray.export_scores import TASK_ID, batch_chunks, episode_id, scorer_stamp
from flywheel_psi0.tray.place_error import (
    Target,
    TargetOf,
    pose_error,
    scene_of,
    target_for,
    yaw_of,
)

FINAL_MEASURES = (
    "tray_pos_m",
    "tray_quat",
    "tray_yaw_rad",
    "target_xy_m",
    "target_yaw_rad",
    "place_distance_m",
    "place_yaw_error_deg",
)
# extrema name -> (row key, side) of the DA-42 palm minima
EXTREMA = {
    f"palm_{name}_{side}_min_m": (key, side)
    for name, key in (("handle", "palm_handle_min_m"), ("bar", "palm_handle_bar_min_m"))
    for side in ("left", "right", "both")
}
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


def at_failure_measures(snapshot: dict[str, Any]) -> dict[str, MeasureValue]:
    """`at_failure` of the tracker's snapshot (`StepTracker._snapshot`), contract names."""
    contacts = snapshot["hand_contacts"]
    return {
        "tilt_deg": float(snapshot["tilt_deg"]),
        "tray_pos_m": [float(v) for v in snapshot["tray_pos"]],
        "tray_quat": [float(v) for v in snapshot["tray_quat"]],
        "tray_on_table": str(snapshot["tray_on_table"]),
        "hand_contact_left": contacts["left"],
        "hand_contact_right": contacts["right"],
    }


def verdict_of(
    stamp: str, steps: list[Any], success: Any, failure: Any, signals: dict[str, Any]
) -> ScorerVerdict:
    """One scorer's verdict; `signals` holds `failure_t`, `step_latch_t`, `at_failure` or not.

    `at_failure` goes with `failure_t`: a snapshot without a failure time is refused.
    """
    ok = bool(success)
    failure_t, snapshot = signals.get("failure_t"), signals.get("at_failure")
    if snapshot is not None and failure_t is None:
        raise ValueError(f"{stamp}: at_failure without failure_t")
    latch = signals.get("step_latch_t")
    return ScorerVerdict(
        scorer_version=stamp,
        step_names=list(STEP_NAMES),
        step_latched=[bool(v) for v in steps],
        step_latch_t=None if latch is None else [None if t is None else float(t) for t in latch],
        success=ok,
        failure_label=None if ok else failure,
        failure_t=None if failure_t is None else float(failure_t),
        at_failure=None if snapshot is None else at_failure_measures(snapshot),
    )


def extrema_of(row: dict[str, Any]) -> dict[str, MeasureValue]:
    out: dict[str, MeasureValue] = {}
    for name, (key, side) in EXTREMA.items():
        value = (row.get(key) or {}).get(side)
        if value is not None:
            out[name] = float(value)
    return out


def outcome_of(
    rollout: Rollout, run: str, run_plan_id: str, target: Target, stamp: str | None = None
) -> RolloutOutcome:
    row = rollout.row
    own = scorer_stamp(row.get("scorer_version")) if stamp is None else stamp
    verdict = verdict_of(own, row["scorer_steps"], row["success"], row.get("failure"), row)
    others = []
    if isinstance(v1 := row.get("scorer_v1"), dict):
        version = scorer_stamp(v1["scorer_version"])
        others.append(verdict_of(version, v1["steps"], v1["success"], v1.get("failure"), v1))
    return RolloutOutcome(
        episode_id=episode_id(run, rollout),
        run_plan_id=run_plan_id,
        task_id=TASK_ID,
        run=run,
        seed=rollout.seed,
        level=rollout.level,
        repeat=rollout.repeat,
        sim_time_s=float(row["sim_time_s"]),
        control_steps=int(row["steps"]),
        verdict=verdict,
        other_verdicts=others,
        final=final_measures(row, target),
        extrema=extrema_of(row),
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


def default_target_of() -> TargetOf:
    """The zone1 target (rows without `task_uid`), `place_error.target_for(None)`."""
    return target_for(None)


def export(
    eval_set: Path,
    out: Path,
    run: str,
    chunk: int = 10,
    max_chunks: int | None = None,
    target_of: TargetOf | None = None,
    repeats: int = 1,
) -> list[RolloutOutcome]:
    """`target_of` overrides the target of the batch's scene (tests)."""
    rows, _, chunks = batch_chunks(eval_set, chunk, max_chunks, repeats)
    chosen, _, missing = collect(out, chunks)
    if missing:
        raise ValueError(f"rollouts missing: {missing}")
    plan_ids = run_plan_ids(rows)
    incomplete = [
        (episode_id(run, r), [k for k in REQUIRED if r.row.get(k) is None])
        for r in chosen
        if any(r.row.get(k) is None for k in REQUIRED) or (r.level, r.seed) not in plan_ids
    ]
    if incomplete:
        raise ValueError(f"rollouts without a field, or a run_plan_id in the set: {incomplete}")
    stamp = scorer_stamp(scorer_version(chosen))  # refuses a batch of two scorer versions
    scene = scene_of(chosen)  # refuses a batch of two scenes
    target_of = target_of or target_for(scene)
    outcomes, refused = [], []
    for r in chosen:
        try:
            target = target_of(r.level, r.seed)
            outcomes.append(outcome_of(r, run, plan_ids[(r.level, r.seed)], target, stamp))
        except ValidationError as exc:
            first = exc.errors()[0]
            refused.append((episode_id(run, r), r.row.get("failure"), first["msg"]))
        except (KeyError, TypeError, ValueError) as exc:
            refused.append((episode_id(run, r), r.row.get("failure"), repr(exc)))
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
    parser.add_argument("--repeats", type=int, default=1, help="rollouts per condition, as run")
    args = parser.parse_args(argv)
    if "/" in args.run:
        parser.error("--run may not hold '/': it is the first part of every episode_id")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.outcomes.exists():
        parser.error(f"{args.outcomes} exists; write to a new file")
    try:
        outcomes = export(
            args.set, args.out, args.run, args.chunk, args.max_chunks, repeats=args.repeats
        )
    except ValueError as exc:
        print(f"export_outcomes: {exc}", file=sys.stderr)
        return 1
    _, chunks, _ = batch_chunks(args.set, args.chunk, args.max_chunks, args.repeats)
    if (note := repeats_note(args.out, chunks, args.repeats)) is not None:
        print(f"export_outcomes: {note}", file=sys.stderr)
    args.outcomes.parent.mkdir(parents=True, exist_ok=True)
    args.outcomes.write_text("".join(o.model_dump_json(exclude_none=True) + "\n" for o in outcomes))
    print(json.dumps({"outcomes": len(outcomes), "file": str(args.outcomes)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
