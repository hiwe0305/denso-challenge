"""Contract shape tests for the public adapter protocols."""

from __future__ import annotations

import inspect

import pytest
from flywheel.contracts import (
    AdapterInfo,
    GenCapabilities,
    GeneratorAdapter,
    PolicyAdapter,
    SimCapabilities,
    SimulatorAdapter,
    TaskDefinition,
    TeleopSource,
    TrainerAdapter,
)
from pydantic import ValidationError

PROTOCOL_METHODS = {
    SimulatorAdapter: {
        "info",
        "capabilities",
        "control_spec",
        "materialize_conditions",
        "rollout",
        "replay",
        "snapshot",
    },
    PolicyAdapter: {"info", "describe", "serve"},
    TrainerAdapter: {"info", "export_dataset", "estimate", "train"},
    GeneratorAdapter: {"info", "capabilities", "plan", "estimate", "generate"},
    TeleopSource: {"info", "operator_kind", "request", "collect"},
    TaskDefinition: {
        "stages",
        "failure_kinds",
        "condition_schema",
        "required_signals",
        "evaluate",
    },
}


@pytest.mark.parametrize(("protocol", "methods"), PROTOCOL_METHODS.items())
def test_protocol_is_runtime_checkable_and_has_required_methods(
    protocol: type[object], methods: set[str]
) -> None:
    assert protocol.__dict__["_is_runtime_protocol"] is True
    assert methods <= {name for name, value in inspect.getmembers(protocol) if callable(value)}


def test_capability_models_expose_exact_v0_fields() -> None:
    assert set(SimCapabilities.model_fields) == {
        "restore_state",
        "visual_override",
        "fault_injection",
        "camera_params",
        "replay",
        "max_parallel",
        "levels",
    }
    assert set(GenCapabilities.model_fields) == {
        "sim_rollout",
        "variant",
        "recovery_from_state",
        "plan",
        "controller",
    }
    assert set(AdapterInfo.model_fields) == {
        "name",
        "version",
        "image_digest",
        "nondeterminism",
    }


def test_simulator_parallelism_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SimCapabilities(max_parallel=0)


def test_capability_records_are_immutable() -> None:
    capabilities = GenCapabilities(plan=True)

    with pytest.raises(ValidationError):
        capabilities.plan = False
