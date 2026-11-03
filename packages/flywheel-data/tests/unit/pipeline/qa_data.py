"""Episodes, labels and config paths shared by the QA, release and report tests (DA-03 PR 2)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from flywheel.contracts.artifacts import Episode
from flywheel.data.ingest.lerobot import EpisodeFrames
from flywheel.data.ingest.sources import EpisodeLineage

FPS = 50
CAMERA = "observation.images.egocentric"
TASK = "pick up the cracker box from table1, locomotion to table2, and place on table2."


REPO = Path(__file__).resolve().parents[5]
QA_YAML = REPO / "configs" / "data" / "qa.yaml"
G1_YAML = REPO / "configs" / "embodiments" / "g1.yaml"
SPLITS = REPO / "configs" / "splits" / "default.yaml"
EPISODE_EXAMPLE = (
    REPO / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/Episode.json"
)
# The labels to_episode gives each source (sources.PROFILES).
SOURCE_LABELS: dict[str, dict[str, object]] = {
    "psi_data": {"kind": "teleop_demo", "operator_kind": "human", "is_root": True,
                 "source_kind": "teleop", "action_quality": "measured", "tier": None},
    "planner_wbc": {"kind": "sim_rollout", "operator_kind": "machine", "is_root": False,
                    "source_kind": "synthetic", "action_quality": "planned", "tier": "S1"},
    "teleop_pico": {"kind": "variant", "operator_kind": "machine", "is_root": False,
                    "source_kind": "synthetic", "action_quality": "planned", "tier": "S2"},
}


def clean_frames(index: int = 0, length: int = 20, task: str = TASK) -> EpisodeFrames:
    """An episode every QA check passes: zero action (inside every G1 limit) and small steps."""
    action = np.zeros((length, 36), dtype=np.float32)
    action[:, 14] = np.linspace(0.0, 0.01 * (length - 1), length, dtype=np.float32)
    return EpisodeFrames(
        episode_index=index,
        task=task,
        timestamp=np.arange(length, dtype=np.float64) / FPS,
        frame_index=np.arange(length, dtype=np.int64),
        states=np.zeros((length, 32), dtype=np.float32),
        action=action,
        video_frames={CAMERA: length},
    )


def episode_of(
    source_detail: str = "psi_data", episode_id: str = "ep_1", **update: object
) -> Episode:
    """The testkit Episode, relabelled as to_episode labels `source_detail`."""
    labels = dict(SOURCE_LABELS[source_detail])
    tier = labels.pop("tier")
    base = Episode.model_validate_json(EPISODE_EXAMPLE.read_text())
    meta = base.meta.model_copy(update={"source_detail": source_detail, "synthetic_tier": tier})
    fields = {"episode_id": episode_id, "source_id": "src_1", "meta": meta, **labels}
    if source_detail == "teleop_pico":
        fields["parent_id"] = "ep_parent"
    fields.update(update)
    return Episode.model_validate({**base.model_dump(), **fields, "meta": fields["meta"]})


def lineage_of(seed: int | None = 7, version: str | None = "p-1") -> EpisodeLineage:
    return EpisodeLineage(seed=seed, level=0, split="train", generator_version=version)
