"""The jobs of an S2 batch whose episodes DA-03's QA kept (DA-35 task 12).

Joins the gate of an S2 batch, i.e. the `fw data ingest` work directory (after
`fw data qa`) and the Psi0 export it ingested (its `meta/` is enough), with the
batch's `jobs.jsonl`. Writes, in the batch's job order, the jobs whose episode's
decision is one DA-03's release keeps (`flywheel.data.release.build.INCLUDED`:
pass, flag), for `generate_s2.py --jobs-file`. A job is a pure function of
(parent_id, level, seed, gen_seed), so running the list again on a newer tree
replays the same variants: with the target zone drawn (DA-33 task 13), say.

It fails closed: the work directory must be the QA of that export, every export
episode needs exactly one report, the reports share one threshold version, and
every episode must be a successful variant matching exactly one job of the batch.
A JSON record (counts by decision, threshold version, sha256 of the reports, the
export meta and the batch's job list) goes beside the output as `<out>.record.json`.

    .venv/bin/python scripts/g0/tray/s2/qa_pass_jobs.py --qa-work <work> \\
        --qa-export <export> --batch fwdata/simple/tray/s2/prod-1105 --out pass-jobs.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

JOB_KEYS = ("parent_id", "level", "seed", "gen_seed")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def kept_jobs(
    qa_work: Path, export: Path, batch: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The batch's jobs whose episodes DA-03 kept, in job order, and a record of the join."""
    from flywheel.contracts.artifacts import QAReport  # workspace venv only
    from flywheel.data.release.build import INCLUDED
    from pydantic import ValidationError

    meta = export / "meta" / "episodes.jsonl"
    listed = json.loads((qa_work / "source.json").read_text())["files"]
    if listed.get("meta/episodes.jsonl") != sha256_of(meta):
        raise ValueError(f"{qa_work} is the QA of another export than {export}")
    position_of = json.loads((qa_work / "episode_index.json").read_text())
    reports_file = qa_work / "qa" / "reports.jsonl"
    decision_at: dict[int, str] = {}
    versions = set()
    for n, line in enumerate(reports_file.read_text().splitlines(), 1):
        if not line:
            continue
        try:
            report = QAReport.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(f"{reports_file} line {n} is not a QAReport: {error}") from error
        if (at := position_of[report.episode_id]) in decision_at:
            raise ValueError(f"{reports_file} has two DA-03 QA reports for {report.episode_id}")
        decision_at[at] = report.decision
        versions.add(report.threshold_version)
    if len(versions) != 1:
        raise ValueError(f"{reports_file} mixes threshold versions {sorted(versions)}")

    jobs = jsonl_rows(batch / "jobs.jsonl")
    order = {tuple(j[k] for k in JOB_KEYS): n for n, j in enumerate(jobs)}
    if len(order) != len(jobs):
        raise ValueError(f"{batch}/jobs.jsonl lists a job twice")
    kept_at: list[int] = []
    seen: set[int] = set()
    episodes = jsonl_rows(meta)
    for n, row in enumerate(episodes):
        block = json.loads(row["environment_config"])["flywheel"]
        if block.get("s2_mode") != "variant" or block.get("outcome") != "success":
            raise ValueError(f"export episode {n} is not a successful S2 variant")
        key = (block["parent_episode"], block["level"], block["seed"], block["gen_seed"])
        if key not in order:
            raise ValueError(f"export episode {n} {key} is no job of {batch}")
        if order[key] in seen:
            raise ValueError(f"two export episodes for job {key}")
        seen.add(order[key])
        if n not in decision_at:
            raise ValueError(f"no DA-03 QA report in {reports_file} for export episode {n}")
        if decision_at[n] in INCLUDED:
            kept_at.append(order[key])
    if len(decision_at) != len(episodes):
        raise ValueError(f"{len(decision_at)} reports for {len(episodes)} export episodes")
    kept = [{k: jobs[n][k] for k in JOB_KEYS} for n in sorted(kept_at)]
    record = {
        "qa_work": str(qa_work),
        "export": str(export),
        "batch": str(batch),
        "export_meta_sha256": sha256_of(meta),
        "reports_sha256": sha256_of(reports_file),
        "batch_jobs_sha256": sha256_of(batch / "jobs.jsonl"),
        "threshold_version": versions.pop(),
        "episodes": len(episodes),
        "decisions": dict(sorted(Counter(decision_at.values()).items())),
        "kept": len(kept),
    }
    return kept, record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--qa-work", type=Path, required=True)
    parser.add_argument("--qa-export", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        kept, record = kept_jobs(args.qa_work, args.qa_export, args.batch)
    except (ValueError, KeyError, OSError) as error:
        print(f"refused: {error}")
        return 1
    args.out.write_text("".join(json.dumps(j) + "\n" for j in kept))
    record["out_sha256"] = sha256_of(args.out)
    record_path = args.out.with_name(f"{args.out.name}.record.json")
    record_path.write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
