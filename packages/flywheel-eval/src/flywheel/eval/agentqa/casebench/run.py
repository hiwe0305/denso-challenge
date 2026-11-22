"""CLI: `python -m flywheel.eval.agentqa.casebench --answer F --run D [--floor-run D]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flywheel.eval.agentqa.casebench.answers import Refused, open_answer, refuse_path
from flywheel.eval.agentqa.casebench.report import CaseReport
from flywheel.eval.agentqa.casebench.rundir import check_leaks, load_run
from flywheel.eval.agentqa.casebench.score import score


def score_case(answer_path: Path, run_dir: Path, floor_dir: Path | None = None,
               sha256: str | None = None) -> CaseReport:
    """Verify the run(s), check for leaks, and only then open the answer."""
    refuse_path(answer_path)  # looks at the name only; nothing is opened
    run = load_run(run_dir)
    floor = load_run(floor_dir) if floor_dir is not None else None
    if floor is not None and floor.record.pack_id != run.record.pack_id:
        raise Refused(f"the runs are of different packs: {floor.record.pack_id!r} (floor) "
                      f"and {run.record.pack_id!r} (agent)")
    for each in (run, floor):
        if each is not None:
            check_leaks(each)
    answer, digest = open_answer(answer_path, sha256)  # the last step before matching
    return score(answer, digest, run, floor)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="casebench", description=__doc__)
    ap.add_argument("--answer", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True, help="the agent run when --floor-run")
    ap.add_argument("--floor-run", type=Path)
    ap.add_argument("--sha256")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        if args.out.exists():
            raise Refused(f"{args.out} exists: a report is written once")
        report = score_case(args.answer, args.run, args.floor_run, args.sha256)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as handle:
            handle.write(report.model_dump_json(indent=2) + "\n")
    except (Refused, FileExistsError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(report.summary())
    return 0
