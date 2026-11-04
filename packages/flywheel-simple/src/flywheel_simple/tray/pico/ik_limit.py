"""A joint speed limit and a waist lock for decoupled_wbc's body IK (DA-35 task 10, 12).

The limit follows DA-33's D-28, the lock DA-33's D-12. Imports pink only when called,
so it loads in the workspace for the CPU tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


def limit_joint_step(solver: Any, max_joint_step: float) -> None:
    """Velocity limit of a BodyIKSolver's QP such that one control step moves a joint <= this.

    pink's default limit is the URDF's (22-37 rad/s, several radians per control step).
    Near the palm-up hold the arm then reconfigures in null space while the wrist poses
    stay on target, and the recorded `action` jumps (docs/g0/tray/wrist-jump.md; DA-33
    bounds its own UpperBodyIK the same way). The solver runs `num_step_per_frame` QP
    steps of `dt` per control step and moves `velocity * dt * amplify_factor` each; the
    URDF limit stays where it is lower. pink adds its default limit only to a model that
    has none, so this one survives the solver's `initialize` at every reset.
    """
    from pink.limits import VelocityLimit  # type: ignore[import-not-found]  # SIMPLE venv

    model = solver.configuration.model
    per_step = solver.num_step_per_frame * solver.dt * solver.amplify_factor
    speed = np.minimum(np.asarray(model.velocityLimit, float), max_joint_step / per_step)
    model.velocity_limit = VelocityLimit(model, velocity_limit=speed)


ARMS_ONLY = ["arms"]  # body_active_joint_groups of DA-33's UpperBodyIK (D-12)


def arms_only(ik_class: Any) -> Callable[..., Any]:
    """`ik_class` (TeleopRetargetingIK) built on the arms alone: the waist stays at zero.

    SIMPLE builds the PICO IK on the `upper_body` groups, waist included, and the
    pipeline sends the IK's waist to the lower body as `target_waist`, which the
    recorder writes into `action`. Under the virtual operator the robot did not
    follow that waist: DA-17's kinematic check rejected every parent on it
    (virtual-teleop.md, PO 4/11/2026). With the arms alone, the reduced model keeps
    the waist at its fixed zero, as DA-33's UpperBodyIK does.
    """

    def build(*args: Any, **kwargs: Any) -> Any:
        return ik_class(*args, **{**kwargs, "body_active_joint_groups": list(ARMS_ONLY)})

    return build
