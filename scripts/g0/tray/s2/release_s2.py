"""Release a gated S2 batch as a hashed Psi0 dataset (DA-35 task 12, AC 7).

Input is the Psi0 export of the batch (SIMPLE's `postprocess_psi0_sonic.py`, not
relabelled) and the gate run on a copy of it: the `fw data ingest` work
directory after `fw data qa` (the copy's `meta/episodes.jsonl` was relabelled
`s2 -> teleop_pico` for the ingest, so that one file differs).

Only an export DA-03 kept whole is released: every episode's decision must be
one `flywheel.data.release.build.INCLUDED` keeps (pass, flag), as decided on
5/11/2026 for S2. A batch with rejects is rerun on its kept jobs first
(`qa_pass_jobs.py`, `generate_s2.py --jobs-file`). It fails closed:

- the gated copy holds the same files as the export, and every file but
  `meta/episodes.jsonl` has the same sha256;
- one QA report per episode, one threshold version;
- every episode is a successful S2 variant (`source_kind` synthetic,
  `synthetic_tier` S2), and the episodes share one `visuals_revision` and one
  `generator_version`.

It then adds the batch's `summary.json`, `jobs.jsonl` and `qa_parents.json`, the
QA reports, and optionally the record of the kept-job list, under `meta/`,
writes `release_manifest.json` (`flywheel_simple.tray.release`, as the S1
releases) and renames the export to `<releases>/tray_s2_<release_hash[:12]>`.
`meta/release_info.json` records the checks' inputs.

    .venv/bin/python scripts/g0/tray/s2/release_s2.py --export <staging export> \\
        --qa-work <gate work dir> --batch fwdata/simple/tray/s2/<run> --releases fwdata/releases
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from flywheel_simple.tray.release import write_manifest

RELABELLED = "meta/episodes.jsonl"
BATCH_FILES = ("summary.json", "jobs.jsonl", "qa_parents.json")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def check(export: Path, qa_work: Path) -> dict[str, Any]:
    """Fail-closed checks of the export against its gate; what they found."""
    from flywheel.contracts.artifacts import QAReport  # workspace venv only
    from flywheel.data.release.build import INCLUDED

    listed: dict[str, str] = json.loads((qa_work / "source.json").read_text())["files"]
    here = sorted(p.relative_to(export).as_posix() for p in export.rglob("*") if p.is_file())
    if sorted(listed) != here:
        extra, missing = sorted(set(here) - set(listed)), sorted(set(listed) - set(here))
        raise ValueError(
            f"gate copy and export hold other files: extra {extra[:3]}, missing {missing[:3]}"
        )
    for rel in here:
        if rel != RELABELLED and sha256_of(export / rel) != listed[rel]:
            raise ValueError(f"{rel} differs between the export and the gated copy")

    episodes = jsonl_rows(export / RELABELLED)
    blocks = [json.loads(row["environment_config"])["flywheel"] for row in episodes]
    for n, block in enumerate(blocks):
        kind = (block.get("source_kind"), block.get("synthetic_tier"), block.get("s2_mode"))
        if kind != ("synthetic", "S2", "variant") or block.get("outcome") != "success":
            raise ValueError(f"episode {n} is not a successful S2 variant: {kind}")
    one = {}
    for field in ("visuals_revision", "generator_version"):
        values = sorted({str(b.get(field)) for b in blocks})
        if len(values) != 1:
            raise ValueError(f"episodes mix {field} {values}")
        one[field] = values[0]

    position_of = json.loads((qa_work / "episode_index.json").read_text())
    reports_file = qa_work / "qa" / "reports.jsonl"
    decisions: dict[int, str] = {}
    versions = set()
    for line in reports_file.read_text().splitlines():
        if not line:
            continue
        report = QAReport.model_validate_json(line)
        if (at := position_of[report.episode_id]) in decisions:
            raise ValueError(f"two DA-03 QA reports for {report.episode_id}")
        decisions[at] = report.decision
        versions.add(report.threshold_version)
    if sorted(decisions) != list(range(len(episodes))):
        raise ValueError(f"{len(decisions)} DA-03 QA reports for {len(episodes)} episodes")
    if len(versions) != 1:
        raise ValueError(f"DA-03 QA reports mix threshold versions {sorted(versions)}")
    counts = Counter(decisions.values())
    if dropped := {d: c for d, c in counts.items() if d not in INCLUDED}:
        raise ValueError(f"DA-03 left out {dropped}: rerun the kept jobs, then release")
    return {
        "episodes": len(episodes),
        "frames": sum(int(row["length"]) for row in episodes),
        "levels": dict(sorted(Counter(str(b["level"]) for b in blocks).items())),
        "parents": len({b["parent_episode"] for b in blocks}),
        "decisions": dict(sorted(counts.items())),
        "threshold_version": versions.pop(),
        "qa_reports_sha256": sha256_of(reports_file),
        **one,
    }


def release(export: Path, qa_work: Path, batch: Path, releases: Path,
            jobs_record: Path | None = None) -> dict[str, Any]:  # fmt: skip
    found = check(export, qa_work)
    meta = export / "meta"
    for name in BATCH_FILES:
        shutil.copyfile(batch / name, meta / f"batch_{name}")
    shutil.copyfile(qa_work / "qa" / "reports.jsonl", meta / "da03_qa_reports.jsonl")
    if jobs_record is not None:
        shutil.copyfile(jobs_record, meta / "batch_jobs_record.json")
    info = {"story": "DA-35", "batch": str(batch), "qa_work": str(qa_work), **found}
    (meta / "release_info.json").write_text(json.dumps(info, indent=1) + "\n")
    release_hash = write_manifest(export)
    final = releases / f"tray_s2_{release_hash[:12]}"
    if final.exists():
        raise ValueError(f"{final} exists")
    export.rename(final)
    return {"release": str(final), "release_hash": release_hash, **found}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--qa-work", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--releases", type=Path, required=True)
    parser.add_argument("--jobs-record", type=Path, help="qa_pass_jobs.py's record, if rerun")
    args = parser.parse_args(argv)
    try:
        out = release(args.export, args.qa_work, args.batch, args.releases, args.jobs_record)
    except (ValueError, KeyError, OSError) as error:
        print(f"refused: {error}")
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
