"""Check HAND_LEAD and NAV_LEAD against an exact-replay batch (DA-35 task 9).

For every saved episode of an exact replay run (generate_s2.py --replay) loads
the replay and its parent and re-derives, per channel, how many steps the
recording lags what the operator sent (flywheel_simple.tray.s2.leads). Prints the
lag distribution per channel and writes it to `<run>/lead_check.json`; exits 1 if
any channel's lags are not all equal to the lead the replay uses.

Run in the SIMPLE venv (pandas reads the parquet), after the replay batch:

    PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \\
        scripts/g0/tray/s2/check_leads.py --run fwdata/simple/tray/s2/replay-1103 \\
        --parents fwdata/simple/tray/virtual/parents-1103b
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from flywheel_simple.tray.s2.leads import CHANNELS, derive_lags
from flywheel_simple.tray.s2.parents import load_parent, parent_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--parents", type=Path, required=True)
    args = parser.parse_args(argv)
    lags: dict[str, Counter[str]] = {name: Counter() for name in CHANNELS}
    episodes = 0
    for shard in sorted(args.run.glob("shard-*")):
        for line in (shard / "attempts.jsonl").read_text().splitlines():
            attempt = json.loads(line)
            if attempt["episode_index"] is None:
                continue
            pid = attempt["parent_episode"]
            _, p_shard, p_index = pid.split("/")
            parent = load_parent(parent_dataset(args.parents, p_shard), int(p_index), pid)
            replay = load_parent(parent_dataset(args.run, shard.name), attempt["episode_index"], "r")
            for name, lag in derive_lags(replay, parent).items():
                lags[name][str(lag)] += 1
            episodes += 1
    expected = {name: lead for name, (_, _, lead) in CHANNELS.items()}
    report = {
        "episodes": episodes,
        "leads": expected,
        "lags": {name: dict(counts) for name, counts in lags.items()},
    }
    (args.run / "lead_check.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    ok = all(set(counts) == {str(expected[name])} for name, counts in lags.items())
    return 0 if ok and episodes else 1


if __name__ == "__main__":
    sys.exit(main())
