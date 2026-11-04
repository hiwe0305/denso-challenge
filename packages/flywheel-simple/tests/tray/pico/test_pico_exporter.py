"""The PICO session's exporter writes its videos through JoinedVideoWriter, on CPU."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from flywheel_simple.tray import recorder
from flywheel_simple.tray.pico import session


class FakeBase:
    """Gr00tDataExporter's classmethod `create` and its video writer hook."""

    created: dict[str, Any] = {}

    @classmethod
    def create(cls, **kwargs: Any) -> FakeBase:
        FakeBase.created = kwargs
        return cls()

    def create_video_writer(self) -> str:
        return "decoupled_wbc VideoWriter"


def fake_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    utils = SimpleNamespace(
        get_dataset_features=lambda model: {"observation.state": {"names": []}},
        get_modality_config=lambda model: {"modality": True},
    )
    rec = SimpleNamespace(
        set_ego_view_feature_shape=lambda features, shape: None,
        validate_existing_ego_view_feature_shape=lambda root, shape: None,
    )
    exporter = types.ModuleType("decoupled_wbc.data.exporter")
    exporter.Gr00tDataExporter = FakeBase  # type: ignore[attr-defined]
    mods = {"decoupled_wbc.data.utils": utils, "simple.cli._decoupled_wbc_recording": rec}
    monkeypatch.setattr(session, "_mod", lambda name: mods[name])
    monkeypatch.setitem(sys.modules, "decoupled_wbc.data.exporter", exporter)
    recorder._exporter_class.cache_clear()


def test_init_exporter_uses_the_joined_video_writer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_modules(monkeypatch)
    task = SimpleNamespace(robot=SimpleNamespace(joint_names=["j0"]), instruction="carry")
    env = SimpleNamespace(unwrapped=SimpleNamespace(task=task))
    agent = SimpleNamespace(_dwbc_robot_model=object())
    try:
        exporter = session.init_exporter(tmp_path, env, agent, (480, 640, 3))
    finally:
        recorder._exporter_class.cache_clear()
    assert isinstance(exporter, FakeBase)
    assert type(exporter).create_video_writer is recorder._create_video_writer
    assert FakeBase.created["save_root"] == str(tmp_path)
    assert FakeBase.created["features"]["observation.state"]["names"] == ["j0"]
    assert "observation.tray_pose" in FakeBase.created["features"]
