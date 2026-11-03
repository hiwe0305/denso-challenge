"""Export a generated, replay-QA'd tray batch to Psi0's LeRobot v2.1 layout (DA-33 Task 8).

Keeps the episodes that passed minimal QA (gen_log.jsonl) and replay QA
(shard-NN/replay/replay_qa.jsonl), runs SIMPLE's postprocess_psi0_sonic.py on
them and adds meta/action_layout.json and meta/flywheel_export.json.

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        scripts/g0/tray/export_psi0.py --batch fwdata/simple/tray/gen/<run> \
        --out fwdata/simple/tray/export/<run>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flywheel_simple.tray.export import export_psi0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", type=Path, required=True, help="batch directory of generate.py")
    ap.add_argument("--out", type=Path, required=True, help="new, empty export directory")
    ap.add_argument("--max-episodes", type=int)
    args = ap.parse_args()
    exported = export_psi0(args.batch, args.out, args.max_episodes)
    print(json.dumps({"out": str(args.out), "episodes": len(exported)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
