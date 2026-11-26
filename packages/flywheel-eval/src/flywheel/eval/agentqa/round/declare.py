"""Write the `round.yaml` of a directory of job folders (DA-43 task 5.3).

    python -m flywheel.eval.agentqa.round.declare --root <dir> --task tray \\
        --declared-by hieu --data-class public

For a log copy as DA-27 writes it (`flywheel.data.inject.log_defects`):

    <root>/train/<job>/metrics.jsonl, action_layout.json, probe_p3.json,
                       probe_p4.json, probe_p4_parent.json
    <root>/rtc/<job>/rtc.jsonl

and for the work dir `fw data qa` leaves on a dataset copy (`flywheel.data.cli`):

    <root>/qa/reports.jsonl, episodes.jsonl, episode_index.json,
           report/dataset_report.json, replay*.jsonl

Each file DA-08 or DA-13 reads becomes one entry with its kind and `subject.job`; each
file of the work dir one entry with its kind and no subject (one dataset per root, and
no step reads a subject of these kinds). Any other file (`meta/`, `source.json`,
`qa/summary.json`, a figure) is left out. The engineer still owns the
declaration: the class is given, never guessed, and the file is written once.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml
from flywheel.eval.agentqa.round.pack import PackRefused
from flywheel.eval.agentqa.round.records import DataClass

DECLARATION_FILE = "round.yaml"
# part -> file name -> pack kind
JOB_FILES: dict[str, dict[str, str]] = {
    "train": {"metrics.jsonl": "metrics", "action_layout.json": "action_layout",
              "probe_p3.json": "probe_p3", "probe_p4.json": "probe_p4",
              "probe_p4_parent.json": "probe_p4_parent"},
    "rtc": {"rtc.jsonl": "rtc_log"},
}
# path under the root -> pack kind, for a `fw data qa` work dir
DATA_FILES: dict[str, str] = {
    "qa/reports.jsonl": "qa_reports", "episodes.jsonl": "episodes",
    "episode_index.json": "episode_index", "report/dataset_report.json": "dataset_report",
}
# `replay*.jsonl` at the root are ReplayReport lines (version 3's `inputs.kind_of`), but
# DA-17's replay run (`flywheel.data.replay_check`) leaves outcome rows under this name.
REPLAY_OUTCOMES = "replay_outcomes.jsonl"


def declare_jobs(root: Path, task_id: str, declared_by: str,
                 data_class: DataClass) -> dict[str, Any]:
    """The declaration of every known file under `root/train/*/`, `root/rtc/*/` and of a
    `fw data qa` work dir at `root`."""
    entries: list[dict[str, Any]] = []
    for part, kinds in JOB_FILES.items():
        base = root / part
        jobs = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
        for job in jobs:
            for name, kind in kinds.items():
                if (job / name).is_file():
                    entries.append({"path": f"{part}/{job.name}/{name}", "kind": kind,
                                    "subject": {"job": job.name}})
    for name, kind in DATA_FILES.items():
        if (root / name).is_file():
            entries.append({"path": name, "kind": kind, "subject": {}})
    for path in sorted(root.glob("replay*.jsonl")):
        if path.is_file() and path.name != REPLAY_OUTCOMES:
            entries.append({"path": path.name, "kind": "replay_reports", "subject": {}})
    if not entries:
        raise PackRefused(f"{root}: no train/<job>/, rtc/<job>/ or `fw data qa` work dir "
                          "file to declare")
    return {"task_id": task_id, "declared_by": declared_by, "data_class": data_class,
            "entries": entries}


def write_declaration(root: Path, task_id: str, declared_by: str,
                      data_class: DataClass) -> Path:
    path = root / DECLARATION_FILE
    if path.exists():
        raise PackRefused(f"{path} exists: a declaration is written once")
    declared = declare_jobs(root, task_id, declared_by, data_class)
    path.write_text(yaml.safe_dump(declared, sort_keys=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--declared-by", required=True)
    parser.add_argument("--data-class", required=True,
                        choices=("public", "internal", "restricted"))
    args = parser.parse_args(argv)
    try:
        path = write_declaration(args.root, args.task, args.declared_by, args.data_class)
    except (PackRefused, OSError) as error:
        print(f"error: {error}")
        return 2
    print(f"{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
