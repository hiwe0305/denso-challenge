"""Eval conditions of a tray RunPlan as LeRobot datasets for `eval-decoupled-wbc` (DA-34 task 3).

SIMPLE's `eval-decoupled-wbc --data-format lerobot --data-dir D` opens D with
`LeRobotDataset` and resets the env from each episode's `environment_config`. The tray
env rebuilds the whole scene from `tray.sample.seed` and `tray.sample.level` of that
config (`flywheel_simple.tray.simple_task`), so a condition needs no recorded frames:
each eval episode here is one frame copied from the release's first episode, with that
episode's `environment_config` as the template and its tray sample replaced by
(level, seed) of the plan's `eval.by_level`.

Writes `<out>/dr-level-<k>/` for each level, in the plan's order, and
`<out>/conditions.jsonl`, one row (level, seed, unit, environment_config) per eval
episode. `conditions.sha256` is the sha256 of those rows as compact JSON, so a rerun
with `--check` shows the conditions did not move. The video feature is left out: the
eval reads no frames from the condition (the tray loader of `flywheel_simple.tray.run`
decodes frames only when one is read, and only policy `vlt` reads them), and
`LeRobotDataset` refuses a dataset whose listed video files are missing.

    python -m flywheel_psi0.tray.eval_set configs/runplans/tray/he-tray-v2.yaml \
        --release <release dir> --out fwdata/tray/eval-sets/rp_a04c14e79dfd
    python -m flywheel_psi0.tray.eval_set ... --check <sha256>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel_psi0.tray.runplan import TrayRunPlan, run_plan_id

DATA = "data/chunk-000/episode_{:06d}.parquet"


def conditions_sha256(rows: list[dict[str, Any]]) -> str:
    """sha256 of the rows as compact JSON, keys in insertion order."""
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def environment_config(
    template: dict[str, Any], level: int, seed: int, plan_id: str
) -> dict[str, Any]:
    """The release episode's config with the tray sample of (level, seed) and no recorded report."""
    config = copy.deepcopy(template)
    config.setdefault("metadata", {}).update(dr_level=level, split="dev")
    config["tray"] = {"sample": {"level": level, "seed": seed}}
    config["flywheel"] = {
        "seed": seed,
        "level": level,
        "purpose": "eval",
        "split": "dev",
        "run_plan_id": plan_id,
    }
    return config


def condition_rows(plan: TrayRunPlan, template: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per eval episode, levels in the plan's order, seeds ascending."""
    if plan.eval.by_level is None:
        raise ValueError("eval_set needs a version 2 plan (eval.by_level)")
    plan_id = run_plan_id(plan)
    return [
        {
            "level": c.level,
            "seed": seed,
            "unit": c.unit,
            "environment_config": environment_config(template, c.level, seed, plan_id),
        }
        for c in plan.eval.by_level
        for seed in range(c.seeds.start, c.seeds.stop)
    ]


def read_template(release: Path) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    """(info.json, environment_config, tasks.jsonl text, stats) of the release's first episode."""
    info = json.loads((release / "meta/info.json").read_text())
    first = json.loads((release / "meta/episodes.jsonl").read_text().splitlines()[0])
    stats = json.loads((release / "meta/episodes_stats.jsonl").read_text().splitlines()[0])
    return (
        info,
        json.loads(first["environment_config"]),
        (release / "meta/tasks.jsonl").read_text(),
        stats,
    )


def write_level(
    out: Path,
    release: Path,
    info: dict[str, Any],
    tasks: str,
    stats: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    """One LeRobot v2.1 dataset of len(rows) one-frame episodes, without the video feature."""
    import pyarrow as pa  # type: ignore[import-untyped]  # in the SIMPLE and Psi0 venvs
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    videos = [k for k, v in info["features"].items() if v.get("dtype") == "video"]
    n = len(rows)
    meta = {
        **info,
        "features": {k: v for k, v in info["features"].items() if k not in videos},
        "total_episodes": n,
        "total_frames": n,
        "total_videos": 0,
        "total_chunks": 1,
        "splits": {"dev": f"0:{n}"},
    }
    meta.pop("video_path", None)
    first = pq.read_table(release / DATA.format(0)).slice(0, 1).to_pylist()[0]
    (out / "meta").mkdir(parents=True)
    (out / "data/chunk-000").mkdir(parents=True)
    (out / "meta/info.json").write_text(json.dumps(meta, indent=4))
    (out / "meta/tasks.jsonl").write_text(tasks)
    task = json.loads(tasks.splitlines()[0])["task"]
    episode_stats = {k: v for k, v in stats["stats"].items() if k not in videos}
    with (
        (out / "meta/episodes.jsonl").open("w") as ep,
        (out / "meta/episodes_stats.jsonl").open("w") as st,
    ):
        for i, row in enumerate(rows):
            frame = {
                **first,
                "episode_index": i,
                "index": i,
                "frame_index": 0,
                "timestamp": 0.0,
                "next.done": True,
            }
            table = pa.Table.from_pylist([frame], schema=pq.read_schema(release / DATA.format(0)))
            pq.write_table(table, out / DATA.format(i))
            line = {
                "episode_index": i,
                "tasks": [task],
                "length": 1,
                "environment_config": json.dumps(row["environment_config"]),
            }
            ep.write(json.dumps(line) + "\n")
            st.write(json.dumps({"episode_index": i, "stats": episode_stats}) + "\n")


def build(plan_path: Path, release: Path, out: Path | None) -> str:
    """The conditions' sha256; with `out`, also the datasets and conditions.jsonl."""
    plan = TrayRunPlan.load(plan_path)
    info, template, tasks, stats = read_template(release)
    rows = condition_rows(plan, template)
    digest = conditions_sha256(rows)
    if out is None:
        return digest
    out.mkdir(parents=True)  # refuses to overwrite an earlier set
    for level in dict.fromkeys(r["level"] for r in rows):
        write_level(
            out / f"dr-level-{level}",
            release,
            info,
            tasks,
            stats,
            [r for r in rows if r["level"] == level],
        )
    with (out / "conditions.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    (out / "conditions.sha256").write_text(digest + "\n")
    return digest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--release", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--check", help="conditions sha256 of an earlier build")
    args = parser.parse_args(argv)
    digest = build(args.plan, args.release, args.out)
    print(digest)
    if args.check is not None and digest != args.check:
        print(f"conditions moved: {digest} != {args.check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
