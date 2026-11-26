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

Two smaller sets for the image pipeline check of rule 0 (docs/he/tray.md section 14):

* `--train-set C --first 20`: the first 20 episodes of the plan's demo set C in the
  hash order the sets were cut from (`demo_sets.rank`), at the release's level, with
  split train: the scenes C was trained on (T1);
* `--only 1:1000100:1000120`: the plan's eval conditions of level 1, seeds
  [1000100, 1000120), row for row as in the full set (T2).

DA-47, the fixed-jig scene and plans without an eval section:

* `--scene jig2` records `scene: jig2` in each row's `environment_config.flywheel`
  (zone1, the default, records nothing, so the rows and sha256 of earlier sets hold);
  `eval_batch --scene` refuses a set of another scene. The template must be a jig
  release (its `visuals_revision` ends with `+jig2`). The jig task rebuilds its scene
  from (level, seed) and its own `configs/sim/tray_jig.yaml`; the recorded `tray.jig`
  block is not read, so it is dropped with the rest of `tray`;
* `--levels LEVEL:START:STOP ...` names the eval conditions: required for a `mix_train`
  plan (`TrayMixPlan`, no eval section; its id is the frozen one of its lock file),
  refused for a `TrayRunPlan` (its `eval.by_level` is the one source). Seeds must be in
  the simulator's dev range (`randomize.SEED_RANGES`), the split the rows record;
* `--exclude-seeds-of <release> ...` refuses conditions whose seed is an episode seed of
  one of those releases (the train data of the plan):

    python -m flywheel_psi0.tray.eval_set configs/runplans/tray/he-tray-jig-m.yaml \
        --scene jig2 --levels 1:1000300:1000330 2:1000300:1000330 \
        --release <level 1 jig release> --exclude-seeds-of <each release of the cut> \
        --out <dir>
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

import yaml

from flywheel_psi0.tray.demo_sets import DemoSets, ReleaseEpisode, rank, read_release
from flywheel_psi0.tray.mixplan import TrayMixPlan
from flywheel_psi0.tray.runplan import REPO, TrayRunPlan, file_sha256, lock_path, run_plan_id

DATA = "data/chunk-000/episode_{:06d}.parquet"
SCENES = ("zone1", "jig2")  # as eval_batch.SCENES
DEFAULT_SCENE = "zone1"
# scene -> env id, as eval_batch.SCENES (eval_batch imports this module, so it is mirrored;
# a test keeps the two equal). A plan's task.env_id tells which scene its set must be.
SCENE_ENVS = {
    "zone1": "simple/G1WholebodyTrayTransferTeleop-v0",
    "jig2": "simple/G1WholebodyTrayTransferJigTeleop-v0",
}
JIG_REVISION = "jig2"  # flywheel_simple.tray.jig.JIG_REVISION, the suffix of visuals_revision
DEV_SEEDS = range(1_000_000, 1_001_000)  # flywheel_simple.tray.randomize.SEED_RANGES["dev"]


def conditions_sha256(rows: list[dict[str, Any]]) -> str:
    """sha256 of the rows as compact JSON, keys in insertion order."""
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def environment_config(
    template: dict[str, Any],
    level: int,
    seed: int,
    plan_id: str,
    split: str = "dev",
    purpose: str = "eval",
    scene: str = DEFAULT_SCENE,
) -> dict[str, Any]:
    """The release episode's config with the tray sample of (level, seed) and no recorded report."""
    config = copy.deepcopy(template)
    config.setdefault("metadata", {}).update(dr_level=level, split=split)
    config["tray"] = {"sample": {"level": level, "seed": seed}}
    config["flywheel"] = {
        "seed": seed,
        "level": level,
        "purpose": purpose,
        "split": split,
        "run_plan_id": plan_id,
    }
    if scene != DEFAULT_SCENE:
        config["flywheel"]["scene"] = scene
    return config


Levels = list[tuple[int, int, int]]  # (level, start, stop) of --levels


def condition_rows(
    plan: TrayRunPlan, template: dict[str, Any], scene: str = DEFAULT_SCENE
) -> list[dict[str, Any]]:
    """One row per eval episode, levels in the plan's order, seeds ascending."""
    if plan.eval.by_level is None:
        raise ValueError("eval_set needs a version 2 plan (eval.by_level)")
    plan_id = run_plan_id(plan)
    return [
        {
            "level": c.level,
            "seed": seed,
            "unit": c.unit,
            "environment_config": environment_config(template, c.level, seed, plan_id, scene=scene),
        }
        for c in plan.eval.by_level
        for seed in range(c.seeds.start, c.seeds.stop)
    ]


def level_rows(
    levels: Levels, plan_id: str, template: dict[str, Any], scene: str = DEFAULT_SCENE
) -> list[dict[str, Any]]:
    """Rows of explicit (level, start, stop) conditions, in the given order.

    Level 0 has one scene, so its seeds are replicates (as `LevelConditions` requires).
    """
    seen = [lv for lv, _, _ in levels]
    if len(set(seen)) != len(seen):
        raise ValueError(f"--levels repeats a level: {seen}")
    for level, start, stop in levels:
        if level not in (0, 1, 2) or not start < stop:
            raise ValueError(f"--levels {level}:{start}:{stop}: level 0-2 and start < stop")
        if start < DEV_SEEDS.start or stop > DEV_SEEDS.stop:
            raise ValueError(
                f"--levels {level}:{start}:{stop} is outside the dev seeds "
                f"[{DEV_SEEDS.start}, {DEV_SEEDS.stop}): the env refuses other ranges"
            )
    return [
        {
            "level": level,
            "seed": seed,
            "unit": "replicate" if level == 0 else "condition",
            "environment_config": environment_config(template, level, seed, plan_id, scene=scene),
        }
        for level, start, stop in levels
        for seed in range(start, stop)
    ]


def frozen_plan_id(plan: TrayMixPlan, plan_path: Path) -> str:
    """The run_plan_id of a mix plan's lock file; refuses a plan not frozen or changed since."""
    lock = lock_path(plan_path)
    if not lock.is_file():
        raise ValueError(f"{plan_path} is not frozen: no {lock.name}")
    frozen = str(json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"])
    if frozen != run_plan_id(plan):
        raise ValueError(f"{plan_path} changed since it was frozen as {frozen}")
    return frozen


def check_scene(raw: dict[str, Any], scene: str) -> None:
    """Refuses a scene other than the one the plan's task.env_id names; unknown env ids pass."""
    env_id = (raw.get("task") or {}).get("env_id")
    expected = next((name for name, env in SCENE_ENVS.items() if env == env_id), None)
    if expected is not None and expected != scene:
        raise ValueError(f"plan env {env_id} is scene {expected}; got --scene {scene}")


def check_template(template: dict[str, Any], scene: str) -> None:
    """A jig2 set needs a jig release as its template (visuals_revision ends with +jig2)."""
    if scene != "jig2":
        return
    revision = str((template.get("flywheel") or {}).get("visuals_revision", ""))
    if not revision.endswith("+" + JIG_REVISION):
        raise ValueError(f"scene jig2 needs a jig release; template visuals_revision {revision!r}")


def check_seeds(rows: list[dict[str, Any]], releases: Sequence[Path]) -> None:
    """Refuses rows whose seed is an episode seed of one of `releases`, listing the overlap."""
    seeds = {int(r["seed"]) for r in rows}
    problems = []
    for release in releases:
        _, episodes = read_release(release)
        overlap = sorted(seeds & {e.seed for e in episodes})
        if overlap:
            problems.append(f"{release}: {len(overlap)} seeds, {overlap[:10]}")
    if problems:
        raise ValueError("eval seeds are train seeds: " + "; ".join(problems))


def only(rows: list[dict[str, Any]], level: int, start: int, stop: int) -> list[dict[str, Any]]:
    """The rows of `level` with seed in [start, stop); all of them must be in the set."""
    picked = [r for r in rows if r["level"] == level and start <= r["seed"] < stop]
    if len(picked) != stop - start:
        raise ValueError(f"the plan has {len(picked)} conditions in {level}:{start}:{stop}")
    return picked


def train_rows(
    plan: TrayRunPlan,
    repo: Path,
    template: dict[str, Any],
    set_name: str,
    first: int,
    scene: str = DEFAULT_SCENE,
) -> list[dict[str, Any]]:
    """The first `first` episodes of a demo set in its hash order, as train conditions."""
    path = repo / plan.demo_sets.file
    if plan.demo_sets.file_sha256 is not None and file_sha256(path) != plan.demo_sets.file_sha256:
        raise ValueError(f"{plan.demo_sets.file} is not the demo-set file the plan pins")
    sets = DemoSets.model_validate_json(path.read_text(encoding="utf-8"))
    demo = sets.sets[set_name]
    if not 0 < first <= demo.n:
        raise ValueError(f"set {set_name} has {demo.n} episodes, asked for {first}")
    episodes = [
        ReleaseEpisode(episode_index=i, seed=s)
        for i, s in zip(demo.episode_indices, demo.seeds, strict=True)
    ]
    level = int(template["tray"]["sample"]["level"])
    plan_id = run_plan_id(plan)
    return [
        {
            "level": level,
            "seed": seed,
            "unit": "train_condition",
            "environment_config": environment_config(
                template,
                level,
                seed,
                plan_id,
                split="train",
                purpose="pipeline_check",
                scene=scene,
            ),
        }
        for seed in rank(sets.release_hash, episodes, sets.salt)[:first]
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


def build(
    plan_path: Path,
    release: Path,
    out: Path | None,
    train_set: tuple[str, int] | None = None,
    subset: tuple[int, int, int] | None = None,
    repo: Path = REPO,
    scene: str = DEFAULT_SCENE,
    levels: Levels | None = None,
    exclude: Sequence[Path] = (),
) -> str:
    """The conditions' sha256; with `out`, also the datasets and conditions.jsonl."""
    if scene not in SCENES:
        raise ValueError(f"scene {scene!r} is not one of {SCENES}")
    info, template, tasks, stats = read_template(release)
    check_template(template, scene)
    raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    check_scene(raw, scene)
    if raw.get("purpose") == "mix_train":
        mix = TrayMixPlan.load(plan_path)
        if levels is None or train_set is not None:
            raise ValueError("a mix_train plan has no eval section: give --levels")
        rows = level_rows(levels, frozen_plan_id(mix, plan_path), template, scene)
    else:
        plan = TrayRunPlan.load(plan_path)
        if levels is not None:
            raise ValueError("this plan's conditions are its eval.by_level: drop --levels")
        if train_set is not None:
            rows = train_rows(plan, repo, template, *train_set, scene=scene)
        else:
            rows = condition_rows(plan, template, scene)
    if subset is not None and train_set is None:
        rows = only(rows, *subset)
    check_seeds(rows, exclude)
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
    kind = parser.add_mutually_exclusive_group()
    kind.add_argument("--train-set", help="demo set of the plan, e.g. C (with --first)")
    kind.add_argument("--only", help="LEVEL:START:STOP of the plan's eval conditions")
    parser.add_argument("--first", type=int, help="episodes of --train-set, in hash order")
    parser.add_argument("--scene", choices=SCENES, default=DEFAULT_SCENE, help="DA-47")
    parser.add_argument(
        "--levels", nargs="+", help="LEVEL:START:STOP eval conditions (mix_train plans)"
    )
    parser.add_argument(
        "--exclude-seeds-of",
        type=Path,
        nargs="+",
        action="extend",
        default=[],
        help="release dirs whose episode seeds the conditions must avoid",
    )
    args = parser.parse_args(argv)
    if (args.train_set is None) != (args.first is None):
        parser.error("--train-set and --first go together")
    train_set = None if args.train_set is None else (args.train_set, args.first)
    subset = None
    if args.only is not None:
        level, start, stop = (int(x) for x in args.only.split(":"))
        subset = (level, start, stop)
    levels = None
    if args.levels is not None:
        levels = [(lv, a, b) for lv, a, b in (map(int, x.split(":")) for x in args.levels)]
    digest = build(
        args.plan,
        args.release,
        args.out,
        train_set,
        subset,
        scene=args.scene,
        levels=levels,
        exclude=args.exclude_seeds_of,
    )
    print(digest)
    if args.check is not None and digest != args.check:
        print(f"conditions moved: {digest} != {args.check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
