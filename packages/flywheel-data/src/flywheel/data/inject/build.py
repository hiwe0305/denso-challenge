"""Build both benchmark copies of a LeRobot dataset and seal their answers (DA-27 tasks 9, 10).

    python -m flywheel.data.inject.build --source <lerobot root> --out <dir> \\
        [--layout configs/embodiments/g1.yaml] [--config configs/data/inject.yaml] [--store <root>]

Writes, under --out:

    copies/<copy id>/     the defect copy and the clean copy, ids from copy_ids(seed)
    answers/<copy id>/    defect_manifest.json and .sha256 of each copy, and the
                          writer's flywheel_lineage.jsonl of that copy (scorer only)
and writes the job's estimated and measured LedgerEntry rows to the store's run ledger
through `flywheel.data.ledger.job_ledger` (run plan `g0-DA-27-<yyyymmdd>` unless given),
then prints the handoff for DA-31: each copy's DatasetRef, manifest path and hash.
Neither the copy names nor the handoff say which copy is clean; only the manifests do.
"""

import argparse
import json
import shutil
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from flywheel.contracts.artifacts import ActionLayout, DefectManifest
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.ingest.lerobot import LINEAGE, read_info
from flywheel.data.inject.config import InjectConfig, load_inject_config
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.lerobot_copy import clean_copy, inject_copy
from flywheel.data.inject.manifest import MANIFEST_FILENAME, seal_manifest
from flywheel.data.ledger import Job, job_ledger

# Assumption, not a measurement: CPU seconds per frame per copy, for the estimate row.
ESTIMATED_SECONDS_PER_FRAME = 0.001


@dataclass(frozen=True)
class BuiltCopy:
    ref: DatasetRef
    manifest_path: Path
    manifest_sha256: str


@dataclass(frozen=True)
class BenchmarkBuild:
    defect: BuiltCopy
    clean: BuiltCopy
    ledger: Job  # its estimated and measured rows, as written to the store


def build_benchmark(
    src_root: Path,
    out_dir: Path,
    config: InjectConfig | None = None,
    layout: ActionLayout | None = None,
    *,
    store: Path | None = None,
    run_plan_id: str | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> BenchmarkBuild:
    """Write the defect copy and the clean copy of `src_root` under `out_dir`."""
    cfg = config or load_inject_config()
    defect_id, clean_id = copy_ids(cfg.seed)
    copies, answers = out_dir / "copies", out_dir / "answers"
    frames = int(read_info(src_root)["total_frames"])
    with job_ledger(
        "data_generation",
        "inject",
        2 * frames * ESTIMATED_SECONDS_PER_FRAME,
        note=f"Assumed {ESTIMATED_SECONDS_PER_FRAME} s per frame per copy, two copies",
        run_plan_id=run_plan_id,
        story="DA-27",
        store=store,
        clock=clock,
    ) as job:

        def seal(copy_id: str, manifest: DefectManifest) -> BuiltCopy:
            # The writer's renumbering record names source index values, from which the
            # source lengths and so the cut episodes follow: it goes to the scorer's side.
            lineage = copies / copy_id / "meta" / LINEAGE
            if lineage.is_file():
                (answers / copy_id).mkdir(parents=True, exist_ok=True)
                shutil.move(lineage, answers / copy_id / LINEAGE)
            path = answers / copy_id / MANIFEST_FILENAME
            digest = seal_manifest(manifest, path, copy_roots=[copies])
            return BuiltCopy(
                DatasetRef(dataset_id=copy_id, uri=str(copies / copy_id)), path, digest
            )

        defect = seal(defect_id, inject_copy(src_root, copies / defect_id, cfg, layout))
        clean = seal(clean_id, clean_copy(src_root, copies / clean_id, cfg))
    return BenchmarkBuild(defect, clean, job)


def ledger_handoff(job: Job) -> dict[str, object]:
    """Where the job's two ledger rows are, and the measured seconds."""
    assert job.measured is not None, "the job has not finished"
    return {
        "run_plan_id": job.run_plan_id,
        "job_id": job.job_id,
        "measured_seconds": job.measured.quantity,
    }


def load_layout(path: Path) -> ActionLayout:
    """The `action_layout` of an embodiment file such as configs/embodiments/g1.yaml."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ActionLayout.model_validate(raw["action_layout"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--store", type=Path, help="store root; default $FW_ROOT or ./fwdata")
    args = parser.parse_args(argv)
    result = build_benchmark(
        args.source,
        args.out,
        load_inject_config(args.config),
        load_layout(args.layout) if args.layout else None,
        store=args.store,
    )
    copies = sorted((result.defect, result.clean), key=lambda c: c.ref.dataset_id)
    handoff = {
        "copies": [
            {
                "dataset_id": c.ref.dataset_id,
                "uri": c.ref.uri,
                "manifest": str(c.manifest_path),
                "manifest_sha256": c.manifest_sha256,
            }
            for c in copies
        ],
        "ledger": ledger_handoff(result.ledger),
    }
    print(json.dumps(handoff, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
