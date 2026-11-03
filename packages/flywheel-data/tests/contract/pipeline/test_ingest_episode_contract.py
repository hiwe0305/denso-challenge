"""The Episode that ingest writes is the contract's Episode (DA-03 AC 2; 03 section 7.3).

Other lanes read these records as JSON, never as lane objects, so the check is
on the serialized form: it parses back to the same Episode, it has exactly the
fields of the testkit example, and the three robot sources keep the labels the
design gives them (design 27/10 section 6.1).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts.artifacts import Episode
from flywheel.data.api import EpisodeFrames, register_source, to_episode, write_episode

ROOT = Path(__file__).resolve().parents[5]
EXAMPLE = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/Episode.json"
INFO = {
    "codebase_version": "v2.1",
    "fps": 50,
    "chunks_size": 1000,
    "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
    "video_path": "videos/chunk-{episode_chunk:03d}/egocentric/episode_{episode_index:06d}.mp4",
    "features": {"observation.images.egocentric": {"dtype": "video", "shape": [360, 640, 3]}},
}
# The flywheel block each recorder writes (DA-33 FlywheelMeta, DA-35 flywheel_meta).
BLOCKS: dict[str, dict[str, object]] = {
    "psi_data": {},
    "planner_wbc": {"seed": 7, "level": 0, "split": "train", "planner_version": "p-1",
                    "source_kind": "synthetic", "synthetic_tier": "S1"},
    "teleop_pico": {"seed": 8, "level": 1, "split": "train", "generator_version": "s2-1",
                    "source_kind": "synthetic", "synthetic_tier": "S2",
                    "parent_episode": "ep_parent"},
}
LABELS = {
    "psi_data": ("teleop", "measured", None),
    "planner_wbc": ("synthetic", "planned", "S1"),
    "teleop_pico": ("synthetic", "planned", "S2"),
}


def set_block(root: Path, block: dict[str, object]) -> None:
    meta = root / "meta" / "episodes.jsonl"
    row = json.loads(meta.read_text())
    row["environment_config"] = json.dumps({"uid": "task", "flywheel": block})
    meta.write_text(json.dumps(row) + "\n")


@pytest.fixture
def frames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, EpisodeFrames]:
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "info.json").write_text(json.dumps(INFO))
    one = EpisodeFrames(
        episode_index=0,
        task="pick up the cracker box from table1, locomotion to table2, and place on table2.",
        timestamp=np.arange(4) / 50,
        frame_index=np.arange(4, dtype=np.int64),
        states=np.zeros((4, 32), dtype=np.float32),
        action=np.zeros((4, 36), dtype=np.float32),
        video_frames={"observation.images.egocentric": 4},
    )
    write_episode(tmp_path, one)
    return tmp_path, one


@pytest.mark.parametrize("detail", sorted(LABELS))
def test_ingested_episode_round_trips_as_the_contract(
    frames: tuple[Path, EpisodeFrames], detail: str
) -> None:
    root, one = frames
    set_block(root, BLOCKS[detail])
    episode = to_episode(one, register_source(root, detail, "unknown", "public"), "train")
    payload = json.loads(episode.model_dump_json())
    assert Episode.model_validate(payload) == episode
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert payload.keys() == example.keys()
    assert payload["meta"].keys() == example["meta"].keys()
    kind, quality, tier = LABELS[detail]
    assert (payload["source_kind"], payload["action_quality"]) == (kind, quality)
    assert payload["meta"]["synthetic_tier"] == tier
    assert payload["meta"]["source_detail"] == detail
    assert payload["data_class"] == "public"
    assert payload["meta"]["benchmark_copy_id"] is None
    assert payload["parent_id"] == BLOCKS[detail].get("parent_episode")
    assert payload["bundle_uri"] == "data/chunk-000/episode_000000.parquet"
    assert ("unknown" in payload["condition_id"]) == ("seed" not in BLOCKS[detail])
