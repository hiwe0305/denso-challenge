"""Release a generated, replay-QA'd tray batch as a hashed Psi0 dataset (DA-33 Task 9).

Exports the kept episodes (scripts/g0/tray/export_psi0.py), copies the batch's
summary.json and replay_summary.json into meta/, writes release_manifest.json
and renames the directory to <releases>/tray_s1_<release_hash[:12]>.

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/release.py --batch fwdata/simple/tray/gen/<run> --releases fwdata/releases
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from flywheel_simple.tray.export import export_psi0
from flywheel_simple.tray.release import write_manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", type=Path, required=True)
    ap.add_argument("--releases", type=Path, required=True)
    args = ap.parse_args()

    staging = args.releases / f".staging-{args.batch.name}"
    exported = export_psi0(args.batch, staging)
    for name in ("summary.json", "replay_summary.json"):
        shutil.copyfile(args.batch / name, staging / "meta" / f"batch_{name}")
    release_hash = write_manifest(staging)
    final = args.releases / f"tray_s1_{release_hash[:12]}"
    staging.rename(final)
    print(json.dumps({"release": str(final), "release_hash": release_hash,
                      "episodes": len(exported)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
