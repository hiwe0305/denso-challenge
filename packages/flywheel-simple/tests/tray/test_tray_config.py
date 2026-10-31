"""TrayConfig round trip through its flat YAML file (pure)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from flywheel_simple.tray import TrayConfig


def test_written_config_loads_back_equal(tmp_path: Path) -> None:
    cfg = replace(TrayConfig.load(), corridor=8.0)
    assert TrayConfig.load(cfg.write(tmp_path / "tray.yaml")) == cfg
