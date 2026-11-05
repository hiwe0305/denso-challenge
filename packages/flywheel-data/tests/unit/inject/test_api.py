"""Release gate exported to DA-03 (plan Q5): has_injected_defect on contract episodes."""

from importlib.resources import files
from pathlib import Path

from flywheel.contracts.artifacts import Episode
from flywheel.data.inject.api import has_injected_defect, mark_copy_episode


def _episode() -> Episode:
    text = (files("flywheel.testkit") / "fixtures/artifacts/Episode.json").read_text()
    return Episode.model_validate_json(text)


def test_plain_episode_has_no_injected_defect() -> None:
    assert has_injected_defect(_episode()) is False


def test_any_benchmark_copy_episode_is_caught() -> None:
    ep = _episode()
    marked = ep.model_copy(
        update={"meta": ep.meta.model_copy(update={"benchmark_copy_id": "bench-000000000001"})}
    )
    assert has_injected_defect(marked) is True


def test_ingest_of_a_copy_stamps_every_episode(tmp_path: Path) -> None:
    copy_root = tmp_path / "bench-000000000001"
    (copy_root / "meta").mkdir(parents=True)
    (copy_root / "meta" / "benchmark_copy.json").write_text(
        '{"benchmark_copy_id": "bench-000000000001"}'
    )
    ep = _episode()
    marked = mark_copy_episode(ep, copy_root)
    assert marked.meta.benchmark_copy_id == "bench-000000000001"
    assert has_injected_defect(marked) is True
    # A dataset that is not a copy leaves the episode as it is
    assert mark_copy_episode(ep, tmp_path) is ep
