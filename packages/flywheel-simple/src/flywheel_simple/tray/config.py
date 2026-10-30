"""Tray task configuration, loaded from configs/sim/tray.yaml.

The file is a flat YAML subset (`key: number` lines and comments) so it loads
without PyYAML, which the workspace does not ship.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_RELPATH = Path("configs/sim/tray.yaml")
_LINE = re.compile(r"^([a-z_][a-z0-9_]*):\s*(-?[0-9]+(?:\.[0-9]+)?(?:[eE]-?[0-9]+)?)\s*$")


@dataclass(frozen=True)
class TrayConfig:
    table_length: float
    table_depth: float
    table_height: float
    corridor: float
    tray_length: float
    tray_width: float
    tray_height: float
    tray_mass: float
    part_count: int
    part_mass: float
    friction: float
    tray_edge_offset: float
    robot_spawn_x: float
    target_pos_tol: float
    target_yaw_tol_deg: float
    t_stable: float
    h_lift: float
    tilt_max_deg: float
    r_reach: float
    episode_limit_s: float

    @property
    def tray_footprint(self) -> tuple[float, float]:
        """Tray extent (x, y) in its own frame: width across, long side along y."""
        return (self.tray_width, self.tray_length)

    @staticmethod
    def default_path() -> Path:
        for parent in Path(__file__).resolve().parents:
            if (parent / CONFIG_RELPATH).is_file():
                return parent / CONFIG_RELPATH
        raise FileNotFoundError(f"{CONFIG_RELPATH} not found above {__file__}")

    @classmethod
    def load(cls, path: Path | None = None) -> TrayConfig:
        path = path or cls.default_path()
        values = _read_flat_yaml(path.read_text())
        fields = {f.name: f for f in dataclasses.fields(cls)}
        unknown = sorted(set(values) - set(fields))
        missing = sorted(set(fields) - set(values))
        if unknown or missing:
            raise ValueError(f"{path}: unknown keys {unknown}, missing keys {missing}")
        kwargs: dict[str, float | int] = {}
        for name, value in values.items():
            if fields[name].type in (int, "int"):
                if value != int(value):
                    raise ValueError(f"{path}: {name} must be an integer, got {value}")
                kwargs[name] = int(value)
            else:
                kwargs[name] = value
        return cls(**kwargs)  # type: ignore[arg-type]


def _read_flat_yaml(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue
        match = _LINE.match(line)
        if match is None:
            raise ValueError(f"line {number}: expected `key: number`, got {raw!r}")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"line {number}: duplicate key {key}")
        values[key] = float(value)
    return values
