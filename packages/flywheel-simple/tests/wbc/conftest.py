"""Tray envs standing on decoupled WBC, for the locomotion and upper-body tests.

Simulator imports stay inside the fixtures so the pure tests in this directory
collect in the workspace.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

# Corridor of the open-floor variant: table A's edge 3.55 m ahead of the spawn,
# room for 4 s at 0.5 m/s. In the default 1.8 m corridor G1's fingers hit table
# A's edge 6 cm after the start (docs/g0/tray/locomotion.md).
OPEN_CORRIDOR = 8.0


class SceneEnvs:
    """At most one live tray env (make_env: one per process), rebuilt when the scene changes."""

    def __init__(self, open_config: Path) -> None:
        self._configs = {"default": None, "open": str(open_config)}
        self._scene: str | None = None
        self._env: Any = None

    def get(self, scene: str) -> Any:
        from flywheel_simple.tray.simple_task import make_env

        if scene != self._scene:
            self.close()
            self._env = make_env(seed=0, tray_config=self._configs[scene])
            self._scene = scene
        return self._env

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
        self._env, self._scene = None, None


def _standing(env: Any) -> Any:
    from flywheel_simple.wbc import StandWalkController, release_band
    from flywheel_simple.wbc.drive import Driver

    env.reset(seed=0)
    ctrl = StandWalkController(env.unwrapped.task.robot)
    ctrl.reset()
    release_band(env, ctrl)
    return Driver(env, ctrl)


@pytest.fixture(scope="module")
def scene_envs(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SceneEnvs]:
    from flywheel_simple.tray import TrayConfig

    path = tmp_path_factory.mktemp("tray") / "tray_open.yaml"
    envs = SceneEnvs(replace(TrayConfig.load(), corridor=OPEN_CORRIDOR).write(path))
    yield envs
    envs.close()


@pytest.fixture
def tray_env_standing(scene_envs: SceneEnvs) -> Any:
    """Driver on the tray env at seed 0, level 0, after the elastic band is released."""
    return _standing(scene_envs.get("default"))


@pytest.fixture
def open_floor_standing(scene_envs: SceneEnvs) -> Any:
    """As tray_env_standing, with the tables OPEN_CORRIDOR apart."""
    return _standing(scene_envs.get("open"))
