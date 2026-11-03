"""Settings of the S2 generator, read from configs/sim/tray_s2.yaml (DA-35 tasks 8-12)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flywheel_simple.tray.config import find_config, load_flat_config

S2_CONFIG_RELPATH = Path("configs/sim/tray_s2.yaml")


@dataclass(frozen=True)
class S2Config:
    hold_s: float
    walk_min_s: float

    @staticmethod
    def default_path() -> Path:
        return find_config(S2_CONFIG_RELPATH)

    @classmethod
    def load(cls, path: Path | None = None) -> S2Config:
        return load_flat_config(cls, path or cls.default_path())
