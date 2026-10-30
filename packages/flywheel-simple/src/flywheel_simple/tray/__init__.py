"""G1 tray-transfer task (DA-32). Pure logic here; SIMPLE and MuJoCo glue in submodules."""

from flywheel_simple.tray.config import TrayConfig
from flywheel_simple.tray.geometry import Pose2D, SceneGeometry, scene_geometry

__all__ = ["Pose2D", "SceneGeometry", "TrayConfig", "scene_geometry"]
