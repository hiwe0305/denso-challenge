"""Relabel `flywheel.source_detail` in a gate copy so DA-03's ingest accepts it (DA-35 task 12).

DA-03's ingest knows psi_data, planner_wbc and teleop_pico. DA-35's parents record
virtual_teleop: synthetic, planned, tier S1, which is planner_wbc's profile in every
other label, and qa.yaml runs the same source checks for planner_wbc and teleop_pico.
For the gate only, a copy of the Psi0 export in a scratch store is relabelled and
ingested as planner_wbc; each relabelled episode records `gate_relabel`. The
recordings and any release are never relabelled: the missing profile is DA-03's
(notes for the PO, 4/11/2026).

    python3 scripts/g0/tray/s2/gate_relabel.py <psi0 dataset copy> virtual_teleop planner_wbc
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def relabel(dataset: Path, old: str, new: str) -> tuple[int, int]:
    """Rewrite meta/episodes.jsonl in place; returns (relabelled, episodes)."""
    meta = dataset / "meta" / "episodes.jsonl"
    rows, changed = [], 0
    for line in meta.read_text().splitlines():
        row = json.loads(line)
        config = json.loads(row["environment_config"])
        block = config["flywheel"]
        if block["source_detail"] == old:
            block["source_detail"] = new
            block["gate_relabel"] = f"{old}->{new}"
            changed += 1
        row["environment_config"] = json.dumps(config)
        rows.append(json.dumps(row))
    meta.write_text("".join(r + "\n" for r in rows))
    return changed, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", type=Path, help="a copy of the Psi0 export, never a release")
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args()
    changed, total = relabel(args.dataset, args.old, args.new)
    print(f"relabelled {changed}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
