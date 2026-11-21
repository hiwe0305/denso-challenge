"""Contract tests for RolloutOutcome (DA-43 K1)."""

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.outcome import RolloutOutcome, ScorerVerdict
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
SCHEMAS = ROOT / "packages/flywheel-contracts/schemas"


def _raw(name: str = "RolloutOutcome-failed") -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("name", ["RolloutOutcome", "RolloutOutcome-failed"])
def test_fixtures_validate_and_round_trip(name: str) -> None:
    value = RolloutOutcome.model_validate_json((FIXTURES / f"{name}.json").read_text("utf-8"))
    assert RolloutOutcome.model_validate_json(value.model_dump_json()) == value


def test_failed_fixture_carries_the_da42_fields() -> None:
    value = RolloutOutcome.model_validate(_raw())
    assert value.repeat == 1
    assert value.verdict.failure_label == "L-TRAY-TILT"
    assert value.verdict.at_failure is not None
    assert value.verdict.at_failure["hand_contact_left"] is True
    assert [v.scorer_version for v in value.other_verdicts] == ["1"]
    assert "palm_handle_bar_min_both_m" in value.extrema


def test_schema_matches_committed_file() -> None:
    committed = json.loads((SCHEMAS / "RolloutOutcome.json").read_text(encoding="utf-8"))
    assert committed == RolloutOutcome.model_json_schema()


def test_invalid_fixture_fails_on_the_failure_label() -> None:
    with pytest.raises(ValidationError, match="successful rollout has no failure label"):
        RolloutOutcome.model_validate(_raw("invalid-RolloutOutcome"))


def test_repeat_defaults_to_zero_and_is_not_negative() -> None:
    raw = _raw("RolloutOutcome")
    del raw["repeat"]
    assert RolloutOutcome.model_validate(raw).repeat == 0
    raw["repeat"] = -1
    with pytest.raises(ValidationError):
        RolloutOutcome.model_validate(raw)


def _verdict(**over: Any) -> dict[str, Any]:
    return {**_raw()["verdict"], **over}


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"step_latched": [True]}, "one entry per step name"),
        ({"step_latch_t": [1.0]}, "one entry per step name"),
        ({"step_latch_t": [2.5, 3.5, 5.0, 6.0, None, None, None]}, "exactly when the step latched"),
        ({"step_names": ["a", "a", "b", "c", "d", "e", "f"]}, "unique"),
        ({"step_names": ["Approach"] + ["b", "c", "d", "e", "f", "g"]}, "pattern"),
        ({"failure_t": None}, "failure_t is set exactly when failure_label is"),
        ({"failure_label": None, "failure_t": None}, "at_failure needs a failure label"),
        ({"at_failure": {"tilt": 25.0}}, "numeric measure ends in"),
        ({"at_failure": {"tray_quat": [1.0, 0.0]}}, "four numbers"),
    ],
)
def test_verdict_rules(over: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ScorerVerdict.model_validate(_verdict(**over))


def test_unfinished_rollout_has_neither_success_nor_label() -> None:
    v = ScorerVerdict.model_validate(
        _verdict(failure_label=None, failure_t=None, at_failure=None, success=False)
    )
    assert v.failure_label is None and not v.success


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"other_verdicts": [_raw()["verdict"]]}, "scorer versions must be unique"),
        ({"sim_time_s": 7.0}, "failure_t is after the episode ended"),
        ({"final": {"Tray": True}}, "pattern"),
        ({"final": {"tray_to_target": 0.6}}, "numeric measure ends in"),
        ({"extrema": {"min_dist": [0.1]}}, "numeric measure ends in"),
        ({"final": {"inside_frac": 1.5}}, "fraction"),
        ({"videos": ["/abs/video.mp4"]}, "relative paths"),
        ({"videos": ["../video.mp4"]}, "relative paths"),
        ({"videos": ["C:/video.mp4"]}, "relative paths"),
        ({"videos": ["data/vault/video.mp4"]}, "relative paths"),
        ({"videos": ["a.mp4", "a.mp4"]}, "unique"),
        ({"meta": {}}, "Extra inputs"),
    ],
)
def test_outcome_rules(over: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        RolloutOutcome.model_validate({**_raw(), **over})


def test_measure_values_keep_their_type() -> None:
    value = RolloutOutcome.model_validate(_raw())
    assert value.final["tray_on_target_table"] is False
    assert value.final["tray_to_target_m"] == 0.6
    assert value.verdict.at_failure is not None
    assert value.verdict.at_failure["tray_on_table"] == "none"
