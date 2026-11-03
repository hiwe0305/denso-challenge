"""Release gate exported to DA-03 (plan Q5): has_injected_defect on contract episodes."""

from importlib.resources import files

from flywheel.contracts.artifacts import Episode, InjectedDefect
from flywheel.data.inject.api import has_injected_defect


def _episode() -> Episode:
    text = (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text()
    return Episode.model_validate_json(text)


def test_plain_episode_has_no_injected_defect() -> None:
    assert has_injected_defect(_episode()) is False


def test_marked_episode_has_an_injected_defect() -> None:
    ep = _episode()
    marked = ep.model_copy(
        update={
            "meta": ep.meta.model_copy(
                update={"injected_defect": InjectedDefect(code="D1", parameters={})}
            )
        }
    )
    assert has_injected_defect(marked) is True
