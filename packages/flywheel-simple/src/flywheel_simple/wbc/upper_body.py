"""Wrist targets through decoupled_wbc's TeleopRetargetingIK, and Dex3 hand closure.

This is the IK half of PicoDecoupledAgent with the PICO streamer taken out:
`body_data` gets two wrist poses (`left_wrist_yaw_link`, `right_wrist_yaw_link`)
in the frame of decoupled_wbc's G1 model, rooted at the pelvis (no floating
base; measured: its FK equals MuJoCo's wrist pose in the pelvis frame). Only the
arms are active: PICO's `upper_body` groups also move the waist, and for a 10 cm
one-arm reach the IK turned it 15 degrees, which the lower body answered by
turning the pelvis. The waist stays at the model's zero, so wrist poses are in
the pelvis frame with a straight waist, a fixed offset from the torso frame.
Hands bypass the hand IK: the caller overwrites the hand slots with `hand_q`.

Two wrist poses leave the arms redundant; the IK's posture task picks the pose.
Its default target (zero pose, shoulder roll +-0.2) puts the round trip 0.056
rad off the standing robot, so `reset` anchors the posture at the robot's
current joints and warm-starts the solver there.

`decoupled_wbc` is imported inside functions so this module imports in the
workspace, where it is absent.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

HAND_JOINTS = ("thumb_0", "thumb_1", "thumb_2", "index_0", "index_1", "middle_0", "middle_1")
# Flexion end of each Dex3 joint in natural order (thumb, index, middle), from
# g1_sonic's MJCF ranges. decoupled_wbc's robot model gives the right hand the
# left hand's limits, so it is not used. thumb_0 rotates the thumb rather than
# bending it; the power grasp of G1GripperInverseKinematicsSolver keeps it at 0.
_FLEXION_END = {
    "left": np.array([0.0, 1.047, 1.745, -1.571, -1.745, -1.571, -1.745]),
    "right": np.array([0.0, -1.047, -1.745, 1.571, 1.745, 1.571, 1.745]),
}
CLOSED_FRACTION = 0.8

Side = Literal["left", "right"]


def hand_q(side: Side, closure: float) -> NDArray[np.float64]:
    """Seven Dex3 joint targets (natural order): 0 open, 1 at 80 % of the flexion range."""
    return float(np.clip(closure, 0.0, 1.0)) * CLOSED_FRACTION * _FLEXION_END[side]


def _mod(name: str) -> Any:
    return importlib.import_module(name)


def _teleop_retargeting_ik() -> Any:
    # teleop_retargeting_ik imports its visualizer at module level, which needs
    # meshcat-shapes (decoupled_wbc[full], with IPython, tornado and pyngrok).
    # Visualisation stays off, so a placeholder module stands in when it is absent.
    name = "decoupled_wbc.control.visualization.humanoid_visualizer"
    if name not in sys.modules and importlib.util.find_spec("meshcat_shapes") is None:
        placeholder = types.ModuleType(name)
        placeholder.RobotVisualizer = None  # type: ignore[attr-defined]
        sys.modules[name] = placeholder
    return _mod("decoupled_wbc.control.teleop.teleop_retargeting_ik").TeleopRetargetingIK


def configuration(
    model: Any,
    sim_obs: dict[str, Any],
    body_key: str = "body_q",
    hand_key: str = "q",
    default_body: NDArray[np.float64] | None = None,
) -> Any:
    """Full decoupled_wbc configuration (43) from SIMPLE's proprio (hands in MJCF order)."""
    z7 = np.zeros(7)

    # MJCF hand joint order -> natural
    def natural(q: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.concatenate([q[:3], q[5:7], q[3:5]])

    return model.get_configuration_from_actuated_joints(
        body_actuated_joint_values=sim_obs.get(body_key, default_body),
        left_hand_actuated_joint_values=natural(sim_obs.get(f"left_hand_{hand_key}", z7)),
        right_hand_actuated_joint_values=natural(sim_obs.get(f"right_hand_{hand_key}", z7)),
    )


def _matrix(se3: Any) -> NDArray[np.float64]:
    pose = np.eye(4)
    pose[:3, :3] = se3.rotation
    pose[:3, 3] = se3.translation
    return pose


class UpperBodyIK:
    """Two wrist poses (4 x 4, pelvis frame) to the decoupled WBC's upper-body target."""

    def __init__(self, robot_model: Any) -> None:
        instantiate_g1_hand_ik_solver = _mod(
            "decoupled_wbc.control.teleop.solver.hand.instantiation.g1_hand_ik_instantiation"
        ).instantiate_g1_hand_ik_solver

        left_hand_ik, right_hand_ik = instantiate_g1_hand_ik_solver()
        self._ik = _teleop_retargeting_ik()(
            robot_model=robot_model,
            left_hand_ik_solver=left_hand_ik,
            right_hand_ik_solver=right_hand_ik,
            body_active_joint_groups=["arms"],
        )
        self._model = robot_model
        frames = robot_model.supplemental_info.hand_frame_names
        self.frames = (frames["left"], frames["right"])
        upper = list(robot_model.get_joint_group_indices("upper_body"))
        self.hand_slots = {
            side: [upper.index(i) for i in robot_model.get_hand_actuated_joint_indices(side=side)]
            for side in ("left", "right")
        }

    def reset(self, sim_obs: dict[str, Any]) -> None:
        """Warm-start the solver at the robot's joints and anchor its posture task there."""
        ik = self._ik
        ik.reset()
        q = ik.body.clip_configuration(
            ik.body.full_to_reduced_configuration(configuration(self._model, sim_obs))
        )
        solver = ik.body_ik_solver
        solver.configuration.q = q.copy()
        solver.configuration.update()
        solver.tasks["posture"].set_target(q)
        ik.in_warmup = False

    def current_wrists(
        self, sim_obs: dict[str, Any]
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Both wrist poses of the robot now, in the IK's frame (pelvis, straight waist)."""
        body = self._ik.body  # the IK's reduced model: waist at its fixed value
        body.cache_forward_kinematics(
            body.full_to_reduced_configuration(configuration(self._model, sim_obs))
        )
        left, right = (_matrix(body.frame_placement(f)) for f in self.frames)
        return left, right

    def solve(self, left: NDArray[np.float64], right: NDArray[np.float64]) -> NDArray[np.float64]:
        """Upper-body target (`upper_body` joint group order) reaching both wrist poses."""
        self._ik.set_goal(
            {
                "body_data": {self.frames[0]: left, self.frames[1]: right},
                "left_hand_data": None,
                "right_hand_data": None,
            }
        )
        upper: NDArray[np.float64] = np.array(self._ik.get_action(), dtype=float)
        return upper
