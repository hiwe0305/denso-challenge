"""Relabel `flywheel.source_detail` in a gate copy so DA-03's ingest accepts it (DA-35 task 12).

DA-03's ingest knows psi_data, planner_wbc and teleop_pico. DA-35's parents record
virtual_teleop: synthetic, planned, tier S1, which is planner_wbc's profile in every
other label, and qa.yaml runs the same source checks for planner_wbc and teleop_pico.
For the gate only, a copy of the Psi0 export in a scratch store is relabelled and
ingested as planner_wbc; each relabelled episode records `gate_relabel`. The
recordings and any release are never relabelled: the missing profile is DA-03's
(notes for the PO, 4/11/2026). The S2 variants record `s2`, which fits
teleop_pico (synthetic, planned, S2, parent_episode required) in every other
label, so their gate copy is relabelled `s2` -> `teleop_pico` the same way.

The script refuses anything but those two relabels, inside a scratch root that holds
a `.gate-scratch` marker and lies outside every `fwdata` directory and outside an
unmarked $FW_ROOT:

    mkdir -p $G && touch $G/.gate-scratch
    python3 scripts/g0/tray/s2/gate_relabel.py --scratch-root $G $G/sources/<copy> \\
        virtual_teleop planner_wbc
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

MARKER = ".gate-scratch"
ALLOWED = {("virtual_teleop", "planner_wbc"), ("s2", "teleop_pico")}


class Refused(ValueError):
    """The relabel would touch something other than a gate copy."""


def check_scratch(dataset: Path, scratch_root: Path) -> None:
    """Raise Refused unless `dataset` is a gate copy inside a marked scratch root."""
    root, path = scratch_root.resolve(), dataset.resolve()
    if not (root / MARKER).is_file():
        raise Refused(f"{root} has no {MARKER} marker: not a scratch root")
    if not path.is_relative_to(root) or path == root:
        raise Refused(f"{path} is not inside the scratch root {root}")
    if "fwdata" in path.parts:
        raise Refused(f"{path} is under a fwdata store")
    store = os.environ.get("FW_ROOT")
    if store and path.is_relative_to(Path(store).resolve()) and Path(store).resolve() != root:
        raise Refused(f"{path} is under FW_ROOT={store}, which is not the scratch root")


def relabel(dataset: Path, old: str, new: str, scratch_root: Path) -> tuple[int, int]:
    """Rewrite meta/episodes.jsonl through a temporary file; returns (relabelled, episodes)."""
    if (old, new) not in ALLOWED:
        raise Refused(f"only {sorted(ALLOWED)} may be relabelled, not {old}->{new}")
    check_scratch(dataset, scratch_root)
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
    tmp = meta.with_name(f".{meta.name}.tmp-{os.getpid()}")
    tmp.write_text("".join(r + "\n" for r in rows))
    os.replace(tmp, meta)
    return changed, len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scratch-root", type=Path, required=True,
                        help=f"the gate's scratch store; must hold a {MARKER} marker")  # fmt: skip
    parser.add_argument("dataset", type=Path, help="a copy of the Psi0 export, never a release")
    parser.add_argument("old")
    parser.add_argument("new")
    args = parser.parse_args(argv)
    try:
        changed, total = relabel(args.dataset, args.old, args.new, args.scratch_root)
    except Refused as e:
        print(f"refused: {e}")
        return 2
    print(f"relabelled {changed}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
