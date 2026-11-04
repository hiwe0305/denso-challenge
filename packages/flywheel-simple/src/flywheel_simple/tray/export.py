"""Export QA-passed tray episodes to Psi0's LeRobot v2.1 layout (DA-33 Task 8, AC 4, 6).

The release holds the raw recorded episodes that passed both the generator's
minimal QA and the replay QA (D-24). They are staged per shard as a LeRobot
dataset of symlinks, renumbered from 0, and handed to SIMPLE's own
`scripts/postprocess_psi0_sonic.py` unchanged, so the output has the exact
layout of the authors' psi-data packages: `action` 36 (no padding), `states` 32,
video `observation.images.egocentric`, `meta/stats_psi0.json` over the release.
Psi0's transform pads states to 36 at training time (`pad_state_dim`).

Next to the script's output, the export writes `meta/action_layout.json` (the
ActionLayout contract: 36 named dimensions) and `meta/flywheel_export.json`
(state names, controller, the source of every exported episode).

The pure parts (selection, staging, layout) import in the workspace; `export_psi0`
runs the script in the SIMPLE venv.
"""

from __future__ import annotations

import importlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flywheel_simple.tray.generate import LOG_NAME, read_log

VIDEO_KEY = "observation.images.ego_view"
POSTPROCESS = "scripts/postprocess_psi0_sonic.py"
REPLAY_QA = "replay/replay_qa.jsonl"

# Copied from SIMPLE scripts/postprocess_psi0_sonic.py (6d10628, MIT): ranges of
# g1_sonic WHOLE_BODY_JOINTS in output order. The script first reorders the raw
# `action` and `observation.state` columns by joint name into that order (the
# recorder's columns follow decoupled_wbc's joint order, not this one). The left
# hand goes thumb, middle, index, as SIMPLE's psi0_decoupled_wbc baseline unpacks
# it; Psi0's ACTION_SLICES_36D comment labels 3:5 "index", but the data holds
# middle there. The sim contract test checks these against the script and the data.
STATE_SLICES = [("left_hand", 29, 32), ("left_hand", 34, 36), ("left_hand", 32, 34),
                ("right_hand", 36, 43), ("left_arm", 15, 22), ("right_arm", 22, 29)]
ACTION_SLICES = STATE_SLICES + [("waist", 13, 15), ("waist", 12, 13)]
WAIST_RPY = ("waist_roll_joint", "waist_pitch_joint", "waist_yaw_joint")
# action[31:36] = teleop.base_height_command, then teleop.navigate_command.
COMMAND_DIMS: list[tuple[str, str, float | None]] = [
    ("base_height_command", "base_height", None),
    ("navigate.vx", "navigate", 0.5),
    ("navigate.vy", "navigate", 0.5),
    # The WBC reads this as the turning flag (g1_gear_wbc_policy); PICO and the
    # planner send vyaw in rad/s, as psi-data holds.
    ("navigate.vyaw", "navigate", 1.0),
    ("navigate.target_yaw", "navigate", math.pi),
]
CONTROLLER = {
    "name": "decoupled_wbc",
    "lower_body": "Balance.onnx / Walk.onnx (G1DecoupledWholeBodyPolicy)",
    "upper_body": "TeleopRetargetingIK targets sent to the WBC (D-24)",
    "eval_cli": "eval-decoupled-wbc",
}


@dataclass(frozen=True)
class ExportedEpisode:
    episode_index: int
    shard: str
    raw_episode: int
    seed: int


def kept_episodes(shard: Path) -> list[int]:
    """Recorded episodes of a shard that passed minimal QA and replay QA, ascending."""
    gen_ok = {
        int(r["episode_index"])
        for r in read_log(shard / LOG_NAME)
        if r["recorded"] and r["qa"] == "pass"
    }
    if not gen_ok:
        return []
    replay = shard / REPLAY_QA
    if not replay.exists():
        raise FileNotFoundError(f"{replay} missing: run replay QA on {shard.name} first")
    verdicts = {int(v["episode"]): bool(v["passed"]) for v in read_log(replay)}
    unjudged = gen_ok - verdicts.keys()
    if unjudged:
        raise ValueError(f"{shard.name}: episodes {sorted(unjudged)} have no replay verdict")
    return sorted(e for e in gen_ok if verdicts[e])


def check_one_planner_version(shards: Sequence[Path]) -> str:
    """The one planner_version of the recorded episodes; a mixed batch is refused (D-28)."""
    versions = {
        str(r["planner_version"])
        for shard in shards
        for r in read_log(shard / LOG_NAME)
        if r["recorded"]
    }
    if len(versions) > 1:
        raise ValueError(f"recorded episodes mix planner versions {sorted(versions)}")
    return versions.pop() if versions else ""


def _episode_file(root: Path, index: int, kind: str) -> Path:
    chunk = f"chunk-{index // 1000:03d}"
    if kind == "data":
        return root / "data" / chunk / f"episode_{index:06d}.parquet"
    return root / "videos" / chunk / VIDEO_KEY / f"episode_{index:06d}.mp4"


def stage_shard(raw: Path, keep: Sequence[int], stage: Path) -> list[dict[str, Any]]:
    """A LeRobot dataset at stage holding raw's episodes `keep`, renumbered 0..k-1 as symlinks.

    Returns the staged episodes.jsonl rows in order.
    """
    entries = {int(e["episode_index"]): e for e in read_log(raw / "meta" / "episodes.jsonl")}
    (stage / "meta").mkdir(parents=True)
    rows = []
    for new, old in enumerate(keep):
        for kind in ("data", "video"):
            link = _episode_file(stage, new, kind)
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(_episode_file(raw, old, kind).resolve())
        rows.append({**entries[old], "episode_index": new})
    (stage / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    for name in ("info.json", "tasks.jsonl"):
        shutil.copyfile(raw / "meta" / name, stage / "meta" / name)
    return rows


def action_layout(whole_body_joints: Sequence[str]) -> dict[str, Any]:
    """ActionLayout (flywheel.contracts) of the 36-D action, from g1_sonic WHOLE_BODY_JOINTS."""
    dims: list[dict[str, Any]] = [
        {"name": whole_body_joints[i], "group": group, "masked": False}
        for group, start, end in ACTION_SLICES
        for i in range(start, end)
    ]
    for name, group, limit in COMMAND_DIMS:
        dim: dict[str, Any] = {"name": name, "group": group, "masked": False}
        if limit is not None:
            dim |= {"limit_low": -limit, "limit_high": limit}
        dims.append(dim)
    return {"dimensions": dims}


def state_names(whole_body_joints: Sequence[str]) -> list[str]:
    """Names of the 32-D `states` column, from g1_sonic WHOLE_BODY_JOINTS."""
    names = [whole_body_joints[i] for _, start, end in STATE_SLICES for i in range(start, end)]
    return names + list(WAIST_RPY) + ["prev_base_height_command"]


def simple_root() -> Path:
    """SIMPLE checkout of the running venv (fwdata/simple/SIMPLE next to fwdata/simple/.venv)."""
    return Path(sys.prefix).parent / "SIMPLE"


def export_psi0(
    batch: Path,
    out: Path,
    max_episodes: int | None = None,
    simple: Path | None = None,
    python: str = sys.executable,
) -> list[ExportedEpisode]:
    """Export the kept episodes of every shard of `batch` into a new directory `out`."""
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty")
    simple = simple or simple_root()
    shards = [s for s in sorted(batch.glob("shard-*")) if (s / LOG_NAME).exists()]
    check_one_planner_version(shards)
    exported: list[ExportedEpisode] = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=f".{out.name}.stage-") as tmp:
        for shard in shards:
            room = None if max_episodes is None else max_episodes - len(exported)
            if room == 0:
                break
            keep = kept_episodes(shard)[:room]
            if not keep:
                continue
            rows = stage_shard(shard / "raw", keep, Path(tmp) / shard.name)
            for raw_episode, row in zip(keep, rows):
                seed = json.loads(row["environment_config"])["flywheel"]["seed"]
                exported.append(ExportedEpisode(len(exported), shard.name, raw_episode, seed))
        if not exported:
            raise ValueError(f"no episode of {batch} passed both QA steps")
        cmd = [python, str(simple / POSTPROCESS), "--sim-root", f"{tmp}/shard-*"]
        cmd += ["--out-dir", str(out), "--skip", "0", "--total_episodes", str(len(exported))]
        log = out.parent / f"{out.name}.postprocess.log"
        with log.open("w") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
    _write_meta(out, batch, exported)
    return exported


def _write_meta(out: Path, batch: Path, exported: list[ExportedEpisode]) -> None:
    joints = importlib.import_module("simple.robots.g1_sonic").WHOLE_BODY_JOINTS
    layout = action_layout(joints)
    (out / "meta" / "action_layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    meta = {
        "action_dim": len(layout["dimensions"]),
        "state": {
            "dim": 32,
            "names": state_names(joints),
            "pad_to": 36,  # Psi0 transform pad_state_dim; action is not padded
        },
        "controller": CONTROLLER,
        "postprocess": f"SIMPLE {POSTPROCESS} --skip 0 --downsample 1",
        "source_batch": str(batch.resolve()),
        "episodes": [asdict(e) for e in exported],
    }
    (out / "meta" / "flywheel_export.json").write_text(json.dumps(meta, indent=2) + "\n")
