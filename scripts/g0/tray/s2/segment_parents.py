"""Cut every parent demo of a batch into the S2 segments K, W, P (DA-35 task 8, AC 4).

Reads the parent list of `<parents>/summary.json` (generate_parents.py), cuts
each episode by its StepTracker flags and writes one line per parent to
`<parents>/s2_segments.jsonl`: parent id, shard, episode index, condition, style
seed and the cut (flywheel_simple.tray.s2.segments). Parents that cannot be cut
are listed with the reason. Prints segment lengths (p10 / p50 / p90, seconds).

Run in the SIMPLE venv (pandas reads the parquet):

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \\
        scripts/g0/tray/s2/segment_parents.py --parents fwdata/simple/tray/virtual/parents-1103b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from flywheel_simple.tray.s2.config import S2Config, segment_with
from flywheel_simple.tray.s2.parents import load_parent, parent_dataset
from flywheel_simple.tray.s2.segments import FPS, SegmentError

SEGMENTS_FILE = "s2_segments.jsonl"


def cut_batch(parents: Path, cfg: S2Config) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary = json.loads((parents / "summary.json").read_text())
    rows, refused = [], []
    for p in summary["parents"]:
        parent_id = f"{parents.name}/{p['shard']}/{p['episode_index']}"
        demo = load_parent(parent_dataset(parents, p["shard"]), p["episode_index"], parent_id)
        try:
            cut = segment_with(demo, cfg)
        except SegmentError as err:
            refused.append({"parent_id": parent_id, "reason": str(err)})
            continue
        rows.append(
            {
                "parent_id": parent_id,
                "shard": p["shard"],
                "episode_index": p["episode_index"],
                "level": demo.level,
                "seed": demo.seed,
                "style_seed": demo.meta.get("style_seed"),
                "operator_version": demo.meta.get("operator_version"),
                "segmentation": cut.as_dict(),
            }
        )
    return rows, refused


def lengths(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    spans: dict[str, list[float]] = {
        "K": [], "W": [], "P": [], "K_walk": [], "P_walk": [], "tray_anchor": []
    }  # fmt: skip
    for row in rows:
        s = row["segmentation"]
        spans["K"].append(s["k_end"] / FPS)
        spans["W"].append((s["w_end"] - s["k_end"]) / FPS)
        spans["P"].append((s["frames"] - s["w_end"]) / FPS)
        spans["K_walk"].append(s["walk_a_end"] / FPS)
        spans["P_walk"].append((s["place_start"] - s["w_end"]) / FPS)
        spans["tray_anchor"].append((s["grasp_end"] - s["reach_start"]) / FPS)
    return {
        k: [round(float(x), 2) for x in np.percentile(v, [10, 50, 90])] for k, v in spans.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--parents", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None, help="tray_s2.yaml")
    args = parser.parse_args(argv)
    rows, refused = cut_batch(args.parents, S2Config.load(args.config))
    with (args.parents / SEGMENTS_FILE).open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    report = {"cut": len(rows), "refused": refused, "seconds_p10_p50_p90": lengths(rows)}
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
