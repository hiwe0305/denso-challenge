"""Cut the place segment of a tray release into a derived release (DA-46 task 3, AC 3).

Keeps each episode from ARRIVE_B (else LOWER) minus --lead-s seconds to its end, with
phase times from the batch's gen_log.jsonl, and writes the release
<releases>/tray_s1place_<release_hash[:12]> (flywheel_simple.tray.cut). With
--demo-sets and --set, only that set's seeds are kept; the file must be of the parent
release.

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/cut_place.py --release fwdata/releases/tray_s1_<hash12> \
        --batch fwdata/simple/tray/gen/<run> --releases fwdata/releases
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from flywheel_simple.tray.cut import CUT_META, cut_release
from flywheel_simple.tray.release import MANIFEST


def selected_seeds(path: Path, name: str, release_hash: str) -> tuple[list[int], dict[str, Any]]:
    """Seeds of set `name` in a demo_sets file of the parent release, and their record."""
    raw = path.read_bytes()
    sets = json.loads(raw)
    if sets.get("release_hash") != release_hash:
        raise SystemExit(f"{path} is for release {sets.get('release_hash')}, not {release_hash}")
    if name not in sets.get("sets", {}):
        raise SystemExit(f"{path} has no set {name!r}")
    seeds = [int(s) for s in sets["sets"][name]["seeds"]]
    record = {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "set": name,
        "n": len(seeds),
    }
    return seeds, record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--release", type=Path, required=True, help="parent tray_s1_<hash12> dir")
    ap.add_argument("--batch", type=Path, required=True, help="the batch the parent came from")
    ap.add_argument("--releases", type=Path, required=True)
    ap.add_argument("--lead-s", type=float, default=1.0)
    ap.add_argument("--demo-sets", type=Path, help="demo_sets JSON of the parent release")
    ap.add_argument("--set", dest="set_name", help="set of --demo-sets to keep")
    args = ap.parse_args()
    if (args.demo_sets is None) != (args.set_name is None):
        ap.error("--demo-sets and --set go together")

    seeds = selection = None
    if args.demo_sets is not None:
        parent_hash = json.loads((args.release / MANIFEST).read_text())["release_hash"]
        seeds, selection = selected_seeds(args.demo_sets, args.set_name, parent_hash)
    final = cut_release(
        args.release, args.batch, args.releases, args.lead_s, seeds=seeds, selection=selection
    )
    marker = json.loads((final / "meta" / CUT_META).read_text())
    release_hash = json.loads((final / MANIFEST).read_text())["release_hash"]
    print(json.dumps({
        "release": str(final),
        "release_hash": release_hash,
        "episodes": len(marker["episodes"]),
        "frames_cut": marker["frames"]["cut"],
        "frames_parent": marker["frames"]["parent"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
