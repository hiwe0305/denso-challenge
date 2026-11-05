"""Episode meta and per-frame tray fields of the recorder; no simulator (DA-33 Task 5)."""

from __future__ import annotations

from dataclasses import asdict, replace

import numpy as np
import pytest
from flywheel_simple.tray.planner import PlannerConfig
from flywheel_simple.tray.predicates import STEP_NAMES
from flywheel_simple.tray.recorder import (
    TRAY_FEATURES,
    FlywheelMeta,
    planner_version,
    tray_frame,
    visuals_revision,
)


def test_meta_marks_synthetic_s1_planned_public_train() -> None:
    meta = asdict(FlywheelMeta(seed=7, level=1, planner_version="p", visuals_revision="none"))
    assert meta["source_kind"] == "synthetic" and meta["source_detail"] == "planner_wbc"
    assert meta["synthetic_tier"] == "S1" and meta["action_quality"] == "planned"
    assert meta["data_class"] == "public" and meta["split"] == "train"
    assert meta["embodiment_id"] == "g1_sonic_dwbc@1" and meta["renderer"] == "mujoco"
    assert (meta["seed"], meta["level"]) == (7, 1)


@pytest.mark.parametrize("seed", [1_000_000, 2_000_000])
def test_meta_refuses_dev_and_holdout_seeds(seed: int) -> None:
    with pytest.raises(ValueError, match="train"):
        FlywheelMeta(seed=seed, level=1, planner_version="p", visuals_revision="none")


def test_planner_version_follows_the_config_values() -> None:
    cfg = PlannerConfig.load()
    assert planner_version(cfg) == planner_version(PlannerConfig.load())
    assert planner_version(cfg) != planner_version(replace(cfg, lift_height=cfg.lift_height + 0.01))


def test_visuals_revision_reads_the_manifest_or_says_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert visuals_revision(None) == "none"
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"revision": "abc123", "assets": []}')
    assert visuals_revision(manifest) == "abc123"


def test_tray_frame_matches_the_declared_features() -> None:
    privileged = {
        "tray_pos": np.array([1.0, 0.0, 0.8]),
        "tray_quat": np.array([1.0, 0.0, 0.0, 0.0]),
        "part_pos": np.zeros((6, 3)),
    }
    frame = tray_frame(privileged, None)
    assert set(frame) == set(TRAY_FEATURES)
    for key, spec in TRAY_FEATURES.items():
        assert frame[key].shape == tuple(spec["shape"]) and frame[key].dtype == np.float64
        assert len(spec["names"]) == spec["shape"][0]
    assert not frame["observation.tray_steps"].any()
    assert len(STEP_NAMES) == TRAY_FEATURES["observation.tray_steps"]["shape"][0]


def _meta_dir(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """A recorder over a dataset whose episodes.jsonl holds two episodes; no simulator."""
    import json
    import types

    from flywheel_simple.tray import recorder as rec

    encoder = types.SimpleNamespace(NumpyArrayEncoder=json.JSONEncoder)
    monkeypatch.setattr(rec, "_mod", lambda name: encoder)
    meta = tmp_path / "ds" / "meta"
    meta.mkdir(parents=True)
    old = "".join(json.dumps({"episode_index": i, "length": 10}) + "\n" for i in range(2))
    (meta / "episodes.jsonl").write_text(old)
    recorder = rec.EpisodeRecorder(
        tmp_path / "ds", robot_model=None, joint_names=[], task_prompt="x"
    )
    return recorder, meta / "episodes.jsonl", old


def test_environment_config_lands_on_its_episode(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import json

    recorder, meta_file, _ = _meta_dir(tmp_path, monkeypatch)
    recorder._write_environment_config(1, {"flywheel": {"seed": 7}})
    rows = [json.loads(line) for line in meta_file.read_text().splitlines()]
    assert "environment_config" not in rows[0]
    assert json.loads(rows[1]["environment_config"]) == {"flywheel": {"seed": 7}}
    assert sorted(p.name for p in meta_file.parent.iterdir()) == ["episodes.jsonl"]  # no temp left


def test_a_crash_mid_write_leaves_episodes_jsonl_whole(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path

    recorder, meta_file, old = _meta_dir(tmp_path, monkeypatch)
    real_write = Path.write_text

    def dies_halfway(self: Path, text: str, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        real_write(self, text[: len(text) // 2], *args, **kwargs)  # the part a kill leaves
        raise OSError("killed mid-write")

    monkeypatch.setattr(Path, "write_text", dies_halfway)
    with pytest.raises(OSError, match="mid-write"):
        recorder._write_environment_config(0, {"flywheel": {"seed": 7}})
    monkeypatch.undo()
    assert meta_file.read_text() == old
