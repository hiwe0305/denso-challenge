import json
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import ActionLayout, Episode
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/Episode.json"
)


@given(
    st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12),
        min_size=1,
        max_size=20,
        unique=True,
    )
)
def test_layout_round_trip_and_duplicate_names(names: list[str]) -> None:
    dimensions = [{"name": name, "group": "arm", "masked": False} for name in names]
    layout = ActionLayout.model_validate({"dimensions": dimensions})
    assert ActionLayout.model_validate_json(layout.model_dump_json()) == layout
    with pytest.raises(ValidationError):
        ActionLayout.model_validate({"dimensions": [*dimensions, dimensions[0]]})


@given(
    st.sampled_from(
        [
            "teleop_demo",
            "teleop_correction",
            "recovery",
            "sim_rollout",
            "variant",
            "eval_rollout",
            "diag_rollout",
        ]
    ),
    st.sampled_from(["human", "machine"]),
)
def test_root_episode_requires_human_demonstration(kind: str, operator: str) -> None:
    episode = json.loads(FIXTURE.read_text(encoding="utf-8"))
    episode.update(is_root=True, kind=kind, operator_kind=operator)
    if operator == "human" and kind in {"teleop_demo", "teleop_correction", "recovery"}:
        value = Episode.model_validate(episode)
        assert Episode.model_validate_json(value.model_dump_json()) == value
    else:
        with pytest.raises(ValidationError):
            Episode.model_validate(episode)
