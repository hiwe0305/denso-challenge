"""`Psi0Trainer` for stage 1: same job directory and resume rules, stage 1 launcher.

Everything but the launcher module is DA-19's `Psi0Trainer`: the recipe renders the
argv, the TrainSpec picks dataset, parent and seed, and `metrics.jsonl`, `launch.json`
and `result.json` land in `runs/<job_id>/`.
"""

from __future__ import annotations

from flywheel.contracts.artifacts import ActionDimension, ActionLayout

from flywheel_psi0.trainer import Psi0Trainer

# Psi0's EgoDex delta action, 48-D (`convert_to_delta_actions` at the pin): per hand
# the wrist translation, its roll-pitch-yaw change, three zeros, then five fingertips.
_HAND = [("wrist_xyz", "wrist"), ("wrist_rpy", "wrist"), ("pad", "pad")]
_HAND += [(f"{tip}_tip", "fingertips") for tip in ("thumb", "index", "middle", "ring", "little")]


def egodex_layout() -> ActionLayout:
    return ActionLayout(
        dimensions=[
            ActionDimension(
                name=f"{side}_{part}_{axis}",
                group=f"{side}_{group}",
                masked=group == "pad",
                constant=group == "pad",
            )
            for side in ("left", "right")
            for part, group in _HAND
            for axis in "xyz"
        ]
    )


class Stage1Trainer(Psi0Trainer):
    """Train Psi0 stage 1 under `flywheel_psi0.stage1.launch`."""

    def command(self) -> list[str]:
        return [*super().command()[:-1], "flywheel_psi0.stage1.launch"]
