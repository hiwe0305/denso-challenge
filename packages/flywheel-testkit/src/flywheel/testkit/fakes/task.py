"""Pure task definition for the planar pick-and-place world."""

from __future__ import annotations

from math import hypot

import pyarrow as pa  # type: ignore[import-untyped]
from flywheel.contracts import (
    ConditionSchema,
    FailureKindSpec,
    ScorerParams,
    SignalSpec,
    StageEvaluation,
    StageSpec,
)


class ToyPickPlace:
    """Three-stage task used to exercise scoring without a real simulator."""

    task_id = "toy-pick-place"
    version = "0.1.0"
    family = "pick_place"

    def stages(self) -> tuple[StageSpec, ...]:
        return (
            StageSpec(name="approach", failure_class="approach"),
            StageSpec(name="grasp", failure_class="grasp"),
            StageSpec(name="place", failure_class="place"),
        )

    def failure_kinds(self) -> tuple[FailureKindSpec, ...]:
        return (
            FailureKindSpec(kind="unreachable", failure_class="approach"),
            FailureKindSpec(kind="dropped", failure_class="grasp"),
            FailureKindSpec(kind="misplaced", failure_class="place"),
        )

    def condition_schema(self) -> ConditionSchema:
        return ConditionSchema(names=("part_x", "part_y", "target_x", "target_y"))

    def required_signals(self) -> tuple[SignalSpec, ...]:
        return tuple(
            SignalSpec(name=name, unit="normalized")
            for name in (
                "gripper_x",
                "gripper_y",
                "part_x",
                "part_y",
                "target_x",
                "target_y",
            )
        )

    def evaluate(self, signals: pa.Table, params: ScorerParams) -> StageEvaluation:
        required = {signal.name for signal in self.required_signals()}
        if not required <= set(signals.column_names) or signals.num_rows == 0:
            return StageEvaluation(stage_success=(None, None, None))

        threshold = params.thresholds.get("distance", 0.05)
        gripper_x = signals["gripper_x"].to_pylist()
        gripper_y = signals["gripper_y"].to_pylist()
        part_x = signals["part_x"].to_pylist()
        part_y = signals["part_y"].to_pylist()
        target_x = signals["target_x"].to_pylist()
        target_y = signals["target_y"].to_pylist()

        gripper_part = [
            hypot(float(gx) - float(px), float(gy) - float(py))
            for gx, gy, px, py in zip(gripper_x, gripper_y, part_x, part_y, strict=True)
        ]
        approach_ok = min(gripper_part) <= threshold
        first_contact = next(
            (i for i, distance in enumerate(gripper_part) if distance <= threshold), None
        )
        grasp_ok = first_contact is not None and max(gripper_part[first_contact:]) <= threshold
        place_distance = hypot(
            float(part_x[-1]) - float(target_x[-1]),
            float(part_y[-1]) - float(target_y[-1]),
        )
        place_ok = grasp_ok and place_distance <= threshold
        outcomes = (approach_ok, grasp_ok, place_ok)

        for index, passed in enumerate(outcomes):
            if not passed:
                failure = self.failure_kinds()[index]
                return StageEvaluation(
                    stage_success=outcomes,
                    first_failed_stage=index,
                    failure_kind=failure.kind,
                    failure_class=failure.failure_class,
                )
        return StageEvaluation(stage_success=outcomes)
