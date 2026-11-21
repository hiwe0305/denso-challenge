"""Write a tray eval batch as `Score` records, so the lanes can read it (DA-43 task 1.2).

The tray eval writes one outcome row per rollout in the adapter's own shape
(`outcomes.jsonl` of `eval_batch`); no lane may read that (03 section 7.3). Until the
outcome becomes a contract artifact (DA-43 design 7.2, K1, with DA-42), this command
carries the part `Score` already holds: success, level, failure label, and the state of
the seven scorer steps. That is enough for the per-step pass table, failure clusters
and the step-latch check of Agent QA/QC.

Rollouts are the ones `eval_results` reads: per condition, the earliest finished
attempt. For each:

    episode_id         `<run>/l<level>-s<seed>`: the run, the condition's level and seed
    step_status        from `scorer_steps`. The tray scorer latches steps in order, so a
                       step after the first one not latched was never judged: the first
                       not latched is `fail`, later ones `not_attempted`. A later step
                       marked latched stays `pass` (it never happens on the scorer as
                       written, and hiding it would hide a scorer fault). No flags at all:
                       every step `unknown`, reason `no_verdict`
    first_failed_step  index (from 0) of the first step not latched, also on a success:
                       a success whose steps never latched is what the step-latch check
                       looks for (docs/he/tray.md 20.11, H1)
    config_sha256      sha256 of the file holding the thresholds the predicates scored
                       with (`--scorer-config`, `configs/sim/tray.yaml` by default)
    trace_sha256       sha256 of the rollout's DA-38 `steps.jsonl`; a rollout without one
                       is refused, since a Score must name what it scored

Limit of the stamp: `config_sha256` and `scorer_version` describe the files at EXPORT
time, not at eval time. The eval batch records no stamp of either: `runs.jsonl` holds
chunk, seeds, start time, wall time and exit code; each outcome row holds the scorer's
step flags but no config hash or code version; `rollout_result.json` (DA-38) names only
the trace writer (`adapter_info`). So a batch evaluated before `configs/sim/tray.yaml`
or the SIMPLE tray predicates changed, and exported after, carries the new stamp. Export
a batch with the config and code it was evaluated with. To lift the limit, the eval
side would have to record, per attempt (in `runs.jsonl`) or per outcome row, the sha256
of the tray config the env loaded and a version of the predicates (the git SHA of
`flywheel_simple.tray.predicates`, or its file sha256); this command would then copy
those values instead of hashing the files it finds now.

    python -m flywheel_psi0.tray.export_scores --set <eval set> --out <eval_batch dir> \
        --run C_70 --scores <file> [--max-chunks 6] [--chunk 10]

A missing rollout stops the export (exit 1) and lists it; nothing is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.entities import Score

from flywheel_psi0.tray.eval_batch import chunk_plan, phases_for
from flywheel_psi0.tray.eval_results import STEP_NAMES, Rollout, collect, trace_of

REPO = Path(__file__).resolve().parents[5]
DEFAULT_SCORER_CONFIG = REPO / "configs/sim/tray.yaml"
TASK_ID = "tray"  # task_id of configs/eval/scorer/tray.yaml
SCORER_VERSION = "simple-tray-predicates"  # the sim's predicates, not the lane's scorer


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def step_status(flags: Sequence[bool] | None) -> tuple[list[str], list[str | None] | None]:
    """(step_status, unknown_reason) of the outcome's `scorer_steps`."""
    if flags is None:
        return ["unknown"] * len(STEP_NAMES), ["no_verdict"] * len(STEP_NAMES)
    if len(flags) != len(STEP_NAMES):
        raise ValueError(f"scorer_steps has {len(flags)} flags, the tray has {len(STEP_NAMES)}")
    status: list[str] = []
    failed = False
    for latched in flags:
        if latched:
            status.append("pass")
        elif not failed:
            status.append("fail")
            failed = True
        else:
            status.append("not_attempted")
    return status, None


def episode_id(run: str, rollout: Rollout) -> str:
    return f"{run}/l{rollout.level}-s{rollout.seed}"


def score_of(rollout: Rollout, run: str, config_sha256: str, trace_sha256: str) -> Score:
    row = rollout.row
    flags = row.get("scorer_steps")
    status, reasons = step_status(flags)
    first = next((k for k, s in enumerate(status) if s == "fail"), None)
    return Score(
        episode_id=episode_id(run, rollout),
        task_id=TASK_ID,
        config_sha256=config_sha256,
        trace_sha256=trace_sha256,
        scorer_version=SCORER_VERSION,
        success=bool(row["success"]),
        step_status=status,  # type: ignore[arg-type]
        unknown_reason=reasons,  # type: ignore[arg-type]
        first_failed_step=first,
        failure_kind=None if row["success"] else row.get("failure"),
        level=rollout.level,
    )


def export(
    eval_set: Path,
    out: Path,
    run: str,
    chunk: int = 10,
    max_chunks: int | None = None,
    scorer_config: Path = DEFAULT_SCORER_CONFIG,
) -> list[Score]:
    rows: list[dict[str, Any]] = [
        json.loads(line) for line in (eval_set / "conditions.jsonl").read_text().splitlines()
    ]
    chunks = chunk_plan(rows, chunk, phases_for(rows))
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    chosen, _, missing = collect(out, chunks)
    if missing:
        raise ValueError(f"rollouts missing for (level, seed) {missing}")
    config_sha = sha256_of(scorer_config)
    scores, no_trace = [], []
    for rollout in chosen:
        steps = trace_of(out, rollout)
        if steps is None:
            no_trace.append((rollout.level, rollout.seed))
            continue
        scores.append(score_of(rollout, run, config_sha, sha256_of(steps)))
    if no_trace:
        raise ValueError(f"rollouts without a trace for (level, seed) {no_trace}")
    return scores


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", type=Path, required=True, help="eval set of eval_set.py")
    parser.add_argument("--out", type=Path, required=True, help="eval_batch directory")
    parser.add_argument("--run", required=True, help="run name, e.g. C_70")
    parser.add_argument("--scores", type=Path, required=True, help="scores.jsonl to write")
    parser.add_argument("--chunk", type=int, default=10)
    parser.add_argument("--max-chunks", type=int, help="first N chunks only (6: stage 1)")
    parser.add_argument("--scorer-config", type=Path, default=DEFAULT_SCORER_CONFIG)
    args = parser.parse_args(argv)
    if "/" in args.run:
        parser.error("--run may not hold '/': it is the first part of every episode_id")
    if args.scores.exists():
        parser.error(f"{args.scores} exists; write to a new file")
    try:
        scores = export(args.set, args.out, args.run, args.chunk, args.max_chunks,
                        args.scorer_config)
    except ValueError as exc:
        print(f"export_scores: {exc}", file=sys.stderr)
        return 1
    args.scores.parent.mkdir(parents=True, exist_ok=True)
    args.scores.write_text("".join(s.model_dump_json() + "\n" for s in scores))
    print(json.dumps({"scores": len(scores), "file": str(args.scores)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
