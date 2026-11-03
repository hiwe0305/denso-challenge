"""Build both benchmark copies of a LeRobot dataset and seal their answers (DA-27 tasks 9, 10).

    python -m flywheel.data.inject.build --source <lerobot root> --out <dir> \\
        [--layout configs/embodiments/g1.yaml] [--config configs/data/inject.yaml]

Writes, under --out:

    copies/<copy id>/     the defect copy and the clean copy, ids from copy_ids(seed)
    answers/<copy id>/    defect_manifest.json and .sha256 of each copy, and the
                          writer's flywheel_lineage.jsonl of that copy (scorer only)
    ledger.jsonl          the job's estimated and measured LedgerEntry rows

and prints the handoff for DA-31: each copy's DatasetRef, manifest path and hash.
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
from flywheel.contracts.base import canonical_json
from flywheel.contracts.entities import LedgerEntry
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.ingest.lerobot import LINEAGE, read_info
from flywheel.data.inject.config import InjectConfig, load_inject_config
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.lerobot_copy import clean_copy, inject_copy
from flywheel.data.inject.manifest import MANIFEST_FILENAME, seal_manifest

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
    ledger: tuple[LedgerEntry, LedgerEntry]  # estimated, then measured


def build_benchmark(
    src_root: Path,
    out_dir: Path,
    config: InjectConfig | None = None,
    layout: ActionLayout | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> BenchmarkBuild:
    """Write the defect copy and the clean copy of `src_root` under `out_dir`."""
    cfg = config or load_inject_config()
    defect_id, clean_id = copy_ids(cfg.seed)
    copies, answers = out_dir / "copies", out_dir / "answers"
    frames = int(read_info(src_root)["total_frames"])
    start = clock()

    def seal(copy_id: str, manifest: DefectManifest) -> BuiltCopy:
        # The writer's renumbering record names source index values, from which the
        # source lengths and so the cut episodes follow: it goes to the scorer's side.
        lineage = copies / copy_id / "meta" / LINEAGE
        if lineage.is_file():
            (answers / copy_id).mkdir(parents=True, exist_ok=True)
            shutil.move(lineage, answers / copy_id / LINEAGE)
        path = answers / copy_id / MANIFEST_FILENAME
        digest = seal_manifest(manifest, path, copy_roots=[copies])
        return BuiltCopy(DatasetRef(dataset_id=copy_id, uri=str(copies / copy_id)), path, digest)

    defect = seal(defect_id, inject_copy(src_root, copies / defect_id, cfg, layout))
    clean = seal(clean_id, clean_copy(src_root, copies / clean_id, cfg))
    rows = ledger_rows(
        f"rp_inject_{defect_id}",
        f"job_inject_{defect_id}",
        estimate_s=2 * frames * ESTIMATED_SECONDS_PER_FRAME,
        measured_s=round(clock() - start, 3),
        note=f"Assumed {ESTIMATED_SECONDS_PER_FRAME} s per frame per copy, two copies",
    )
    append_ledger(out_dir, rows)
    return BenchmarkBuild(defect, clean, rows)


def ledger_rows(
    run_plan_id: str, job_id: str, estimate_s: float, measured_s: float, note: str
) -> tuple[LedgerEntry, LedgerEntry]:
    """The job's estimated and measured CPU-time rows; the measured one points at the estimate."""
    estimate = LedgerEntry(
        activity="data_generation",
        resource_type="cpu_seconds",
        quantity=estimate_s,
        unit="s",
        usd_amount=0.0,
        measure_kind="estimated",
        run_plan_id=run_plan_id,
        job_id=job_id,
        note=note,
    )
    measured = LedgerEntry(
        activity="data_generation",
        resource_type="cpu_seconds",
        quantity=measured_s,
        unit="s",
        usd_amount=0.0,
        measure_kind="measured",
        estimate_entry_id=estimate.id,
        run_plan_id=run_plan_id,
        job_id=job_id,
        note="Wall time of the job on one CPU process",
    )
    return estimate, measured


def append_ledger(out_dir: Path, rows: tuple[LedgerEntry, LedgerEntry]) -> None:
    with (out_dir / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write("".join(canonical_json(row) + "\n" for row in rows))


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
    args = parser.parse_args(argv)
    result = build_benchmark(
        args.source,
        args.out,
        load_inject_config(args.config),
        load_layout(args.layout) if args.layout else None,
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
        "ledger": str(args.out / "ledger.jsonl"),
        "measured_seconds": result.ledger[1].quantity,
    }
    print(json.dumps(handoff, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
