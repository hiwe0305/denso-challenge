"""make_env builds its own task each time (SIMPLE caches one Task per uid per process).

Runs in the SIMPLE venv:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
        fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray -m sim -v
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytestmark = pytest.mark.sim


def test_each_make_env_applies_its_own_tray_config(tmp_path: Path) -> None:
    from flywheel_simple.tray import TrayConfig
    from flywheel_simple.tray.simple_task import make_env

    wide = replace(TrayConfig.load(), corridor=8.0).write(tmp_path / "tray_wide.yaml")
    env = make_env(seed=0, tray_config=str(wide))
    wide_x = float(env.unwrapped.mjData.body("table_a").xpos[0])
    env.close()
    env = make_env(seed=0)
    default_x = float(env.unwrapped.mjData.body("table_a").xpos[0])
    env.close()
    # table A's centre: corridor / 2 + table_depth / 2
    assert wide_x == pytest.approx(4.4) and default_x == pytest.approx(1.3)
