"""Record planner episodes in SIMPLE's teleop LeRobot format (DA-33 Task 5, AC 4).

The frame, features and environment_config follow SIMPLE's
`simple.cli.teleop_decoupled_wbc` (`_init_exporter`, `_build_frame`,
`_save_episode_env_config`; SIMPLE is MIT), so synthetic and teleop episodes have
the same fields. That module is not imported: it pulls the PICO streamer. The
action fields come from `StandWalkController.last_record`, which holds what
SIMPLE's teleop agent records.

SIMPLE logs object poses from `mj_objects`, empty for the tray scene (one
articulated MJCF), so the tray pose, part positions and scorer steps are added as
TRAY_FEATURES instead of `observation.object_poses`. The names are those of
DA-35's `tray/pico/recording.py`, so S1 and S2 episodes share one schema; import
them from there once DA-35 is merged.

`decoupled_wbc` and `simple` are imported inside functions so the meta helpers
import in the workspace.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from flywheel_simple.tray.planner import PLANNER_VERSION, PlannerConfig
from flywheel_simple.tray.predicates import STEP_NAMES, StepReport
from flywheel_simple.tray.randomize import split_of

FPS = 50
STORY = "DA-33"

_POSE_NAMES = ["pos_x", "pos_y", "pos_z", "quat_w", "quat_x", "quat_y", "quat_z"]
TRAY_FEATURES: dict[str, dict[str, Any]] = {
    "observation.tray_pose": {
        "dtype": "float64",
        "shape": (7,),
        "names": [f"tray.{n}" for n in _POSE_NAMES],
    },
    "observation.part_pos": {
        "dtype": "float64",
        "shape": (18,),
        "names": [f"part_{i}.{axis}" for i in range(6) for axis in "xyz"],
    },
    "observation.tray_steps": {
        "dtype": "float64",
        "shape": (len(STEP_NAMES),),
        "names": list(STEP_NAMES),
    },
}


def _mod(name: str) -> Any:
    return importlib.import_module(name)


@dataclass(frozen=True)
class FlywheelMeta:
    """`environment_config["flywheel"]` of a synthetic S1 episode; train seeds only."""

    seed: int
    level: int
    planner_version: str
    visuals_revision: str
    purpose: str = "coverage"  # "failure_targeted" for a Failure -> Data round (Task 10)
    cluster_id: str | None = None  # failure cluster a targeted episode was generated for
    source_kind: str = "synthetic"
    source_detail: str = "planner_wbc"
    synthetic_tier: str = "S1"
    action_quality: str = "planned"
    embodiment_id: str = "g1_sonic_dwbc@1"
    renderer: str = "mujoco"
    data_class: str = "public"
    story: str = STORY
    split: str = field(init=False)

    def __post_init__(self) -> None:
        split = split_of(self.seed)
        if split != "train":
            raise ValueError(f"seed {self.seed} is in {split}; generate from train seeds only")
        object.__setattr__(self, "split", split)


def planner_version(cfg: PlannerConfig) -> str:
    """PLANNER_VERSION plus a hash of every config value, so tuned configs stay apart."""
    values = json.dumps(asdict(cfg), sort_keys=True).encode()
    return f"{PLANNER_VERSION}+cfg.{hashlib.sha256(values).hexdigest()[:8]}"


def visuals_revision(manifest: Path | None) -> str:
    """SimReady revision the scene was rendered with, or "none" for plain boxes."""
    if manifest is None or not manifest.is_file():
        return "none"
    return str(json.loads(manifest.read_text())["revision"])


def tray_frame(
    privileged: Mapping[str, NDArray[np.float64]], report: StepReport | None
) -> dict[str, NDArray[np.float64]]:
    """Tray pose, part positions and reached steps for one frame, as TRAY_FEATURES declares."""
    steps = report.steps if report is not None else (False,) * len(STEP_NAMES)
    return {
        "observation.tray_pose": np.concatenate(
            [privileged["tray_pos"], privileged["tray_quat"]]
        ).astype(np.float64),
        "observation.part_pos": np.asarray(privileged["part_pos"], np.float64).reshape(-1),
        "observation.tray_steps": np.asarray(steps, np.float64),
    }


def build_frame(
    robot_model: Any,
    observation: Mapping[str, Any],
    info: Mapping[str, Any],
    record: Mapping[str, NDArray[np.float64]],
) -> dict[str, Any]:
    """One frame: the observation an action was computed from, and that action.

    Keys as SIMPLE's `teleop_decoupled_wbc._build_frame`; `record` is
    `StandWalkController.last_record` of the same step. Unlike that recorder, the
    upper body of `action` (arms, hands, waist), `teleop.navigate_command` and
    `teleop.base_height_command` are the commands this step sent to the WBC, not its
    synced output (D-24): the output lags the command by a step, and its navigate
    mixes the previous step's velocity with this step's turn flag, so replaying the
    output drifted from the recording as soon as the robot walked. replay- and
    eval-decoupled-wbc feed these fields back as commands. The lower body of
    `action` stays the WBC's output.
    """
    proprio = info["proprio"]
    action_q = robot_model.get_configuration_from_actuated_joints(
        body_actuated_joint_values=record["target_q"],
        left_hand_actuated_joint_values=record["left_hand_q"],
        right_hand_actuated_joint_values=record["right_hand_q"],
    )
    action_q[list(robot_model.get_joint_group_indices("upper_body"))] = record["goal_upper_body"]
    frame = {
        "observation.images.ego_view": observation["head_stereo_left"],
        "observation.state": np.asarray(observation["joint_qpos"], dtype=np.float64),
        "observation.eef_state": np.asarray(record["action_eef"], dtype=np.float64),
        "action": np.asarray(action_q, dtype=np.float64),
        "action.eef": np.asarray(record["action_eef"], dtype=np.float64),
        "observation.img_state_delta": np.array([0.0], dtype=np.float32),
        "teleop.navigate_command": np.asarray(record["goal_navigate_cmd"], dtype=np.float64),
        "teleop.base_height_command": np.asarray(
            record["goal_base_height_command"], dtype=np.float64
        ),
        "observation.base_pose": np.asarray(proprio["floating_base_pose"], dtype=np.float64),
        "observation.base_vel": np.asarray(proprio["floating_base_vel"], dtype=np.float64),
    }
    frame.update(tray_frame(info["privileged"], info.get("tray_report")))
    return frame


class EpisodeRecorder:
    """LeRobot v2.1 dataset of planner episodes; the exporter opens on the first frame.

    `add` every step from `run_episode(on_frame=...)`, then `save` a kept episode
    with the task's state_dict (it must carry the flywheel block) or `discard` it.
    """

    def __init__(
        self, save_dir: Path, robot_model: Any, joint_names: Sequence[str], task_prompt: str
    ) -> None:
        self.save_dir = Path(save_dir)
        self.robot_model = robot_model
        self.joint_names = list(joint_names)
        self.task_prompt = task_prompt
        self.exporter: Any = None
        self.frames = 0

    @classmethod
    def for_env(cls, env: Any, agent: Any, save_dir: Path) -> EpisodeRecorder:
        task = env.unwrapped.task
        return cls(save_dir, agent.ctrl.model, task.robot.joint_names, task.instruction)

    def _open(self, ego_shape: Sequence[int]) -> Any:
        utils = _mod("decoupled_wbc.data.utils")
        recording = _mod("simple.cli._decoupled_wbc_recording")
        features = utils.get_dataset_features(self.robot_model)
        recording.set_ego_view_feature_shape(features, ego_shape)
        recording.validate_existing_ego_view_feature_shape(self.save_dir, ego_shape)
        features["observation.state"]["names"] = self.joint_names
        features.update({k: dict(v) for k, v in TRAY_FEATURES.items()})
        return _mod("decoupled_wbc.data.exporter").Gr00tDataExporter.create(
            save_root=self.save_dir,
            fps=FPS,
            features=features,
            modality_config=utils.get_modality_config(self.robot_model),
            task=self.task_prompt,
        )

    def add(
        self,
        observation: Mapping[str, Any],
        info: Mapping[str, Any],
        record: Mapping[str, NDArray[np.float64]],
    ) -> None:
        if self.exporter is None:
            self.exporter = self._open(observation["head_stereo_left"].shape)
        self.exporter.add_frame(build_frame(self.robot_model, observation, info, record))
        self.frames += 1

    def save(self, environment_config: Mapping[str, Any]) -> int:
        """Write the episode and its environment_config; returns the episode index."""
        if not environment_config.get("flywheel"):
            raise ValueError("environment_config has no flywheel block; set_flywheel_meta first")
        if self.exporter is None or self.frames == 0:
            raise ValueError("no frames recorded")
        index = int(self.exporter.episode_buffer["episode_index"])
        self.exporter.save_episode()
        self._write_environment_config(index, environment_config)
        self.frames = 0
        return index

    def discard(self) -> None:
        """Drop the frames of the current episode; the next saved episode takes its index."""
        if self.exporter is not None:
            self.exporter.skip_and_start_new_episode()
        self.frames = 0

    def close(self) -> None:
        if self.exporter is not None:
            self.exporter.stop_video_writers()

    def _write_environment_config(self, index: int, config: Mapping[str, Any]) -> None:
        encoder = _mod("simple.utils").NumpyArrayEncoder
        meta_file = self.save_dir / "meta" / "episodes.jsonl"
        lines = [json.loads(line) for line in meta_file.read_text().splitlines() if line]
        lines[index]["environment_config"] = json.dumps(dict(config), cls=encoder)
        meta_file.write_text("".join(json.dumps(entry) + "\n" for entry in lines))
