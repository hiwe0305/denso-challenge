"""DA-04 task 2: the de-identification gate and the D2 waiver (AC 2, NFR13)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from ego_data import FRAMES, write_mp4
from flywheel.contracts.artifacts import Episode, EpisodeMetadata
from flywheel.data.annotate.deid import gate
from flywheel.data.annotate.deid.gate import (
    WAIVED,
    WAIVER_REASON,
    DeidBlocked,
    annotate_allowed,
    deid_copy,
    deid_waiver,
    require_annotate,
    uncovered_videos,
    unpinned_videos,
)
from flywheel.data.ingest.egocentric import api
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.source import register_egodex


def episode(**change: object) -> Episode:
    base = {
        "episode_id": "ep_1", "kind": "teleop_demo", "operator_kind": "human",
        "is_root": True, "condition_id": "c", "run_plan_id": "rp", "bundle_uri": "b",
        "license": "l", "data_class": "public", "split": "train",
        "source_kind": "egocentric", "action_quality": "retargeted", "deid_status": "raw",
        "embodiment_id": "human_hands@egodex", "meta": EpisodeMetadata(),
    }
    return Episode.model_validate({**base, **change})


REAL_PIN = gate.egodex_pin  # before the fixture below replaces it
VIDEO = {"part1/basic_pick_place/0.mp4": "a" * 64, "part1/basic_pick_place/0.hdf5": "b" * 64}


@pytest.fixture(autouse=True)
def pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "egodex_pin",
                        lambda: ("test-pin@0", {"basic_pick_place/0.mp4": "a" * 64}))


def test_the_waiver_mirrors_da30_and_covers_only_public_egodex() -> None:
    assert WAIVED == frozenset({("egodex", "public")})
    assert deid_waiver("egodex", "public", VIDEO) == (WAIVER_REASON, "test-pin@0")
    for detail, data_class in [("egodex", "internal"), ("egodex", "restricted"),
                               ("ego_video", "public"), ("ego_video", "internal")]:
        assert deid_waiver(detail, data_class, VIDEO) == (None, None)


def test_public_egodex_passes_raw_with_its_waiver() -> None:
    reason, _ = deid_waiver("egodex", "public", VIDEO)
    raw = episode()
    assert annotate_allowed(raw, "egodex", "public", reason, VIDEO)
    require_annotate(raw, "egodex", "public", reason, VIDEO)


def test_the_labels_are_not_enough_without_pinned_videos() -> None:
    """Review of PR 152: a root pointed at the team's videos carries egodex/public too."""
    own = {"part1/basic_pick_place/0.mp4": "c" * 64, "part1/basic_pick_place/0.hdf5": "b" * 64}
    assert deid_waiver("egodex", "public", own) == (None, None)
    assert unpinned_videos(own) == ["part1/basic_pick_place/0.mp4"]
    # a record that claims the waiver anyway is still stopped, with the reason
    with pytest.raises(DeidBlocked, match="not in the pinned EgoDex sample"):
        require_annotate(episode(), "egodex", "public", WAIVER_REASON, own)
    # one unpinned video stops the whole source; no video at all waives nothing
    mixed = {**VIDEO, "part1/basic_pick_place/1.mp4": "d" * 64}
    assert not annotate_allowed(episode(), "egodex", "public", WAIVER_REASON, mixed)
    assert unpinned_videos({"part1/x/0.hdf5": "b" * 64}) == ["part1/x/0.hdf5"]
    assert not annotate_allowed(episode(), "egodex", "public", WAIVER_REASON, {})


def test_every_other_raw_egocentric_episode_is_blocked() -> None:
    recorded = episode(data_class="internal", action_quality="pseudo")
    assert not annotate_allowed(recorded, "ego_video", "internal", None, VIDEO)
    with pytest.raises(DeidBlocked, match="NFR13"):
        require_annotate(recorded, "ego_video", "internal", None, VIDEO)
    # a waiver text is not enough without the pair, nor the pair without the text
    assert not annotate_allowed(recorded, "ego_video", "internal", "someone said so", VIDEO)
    assert not annotate_allowed(episode(), "egodex", "public", None, VIDEO)
    # the record must be the episode's own
    assert not annotate_allowed(episode(), "egodex", "internal", WAIVER_REASON, VIDEO)


TEAM = {"two_table/0.mp4": "e" * 64, "two_table/1.mp4": "f" * 64, "device.json": "9" * 64}
COPIES = {"two_table/0.deid.mp4": "1" * 64, "two_table/1.deid.mp4": "2" * 64}


def team(status: str = "blurred") -> Episode:
    return episode(deid_status=status, data_class="internal", action_quality="pseudo")


def test_robot_episodes_pass_and_raw_team_video_is_refused() -> None:
    robot = episode(source_kind="teleop", action_quality="measured")
    assert annotate_allowed(robot, "psi_data", "public", None, {})
    # raw team video: copies on disk do not help until the episodes are blurred
    assert not annotate_allowed(team("raw"), "ego_video", "internal", None, TEAM, COPIES, COPIES)
    with pytest.raises(DeidBlocked, match="not waived"):
        require_annotate(team("raw"), "ego_video", "internal", None, TEAM, COPIES, COPIES)


def test_a_blurred_source_passes_when_every_copy_has_its_recorded_sha256() -> None:
    assert annotate_allowed(team(), "ego_video", "internal", None, TEAM, COPIES, COPIES)
    require_annotate(team("verified"), "ego_video", "internal", None, TEAM, COPIES, COPIES)
    assert uncovered_videos(TEAM, COPIES, COPIES) == []
    assert deid_copy("two_table/0.mp4") == "two_table/0.deid.mp4"
    with pytest.raises(ValueError):
        deid_copy("two_table/0.deid.mp4")


def test_the_status_alone_is_not_enough() -> None:
    """episodes.jsonl is a text file: `blurred` without copies is refused (was allowed)."""
    assert not annotate_allowed(team(), "ego_video", "internal", None, TEAM)
    assert not annotate_allowed(team(), "ego_video", "internal", None, {})
    one = {"two_table/0.deid.mp4": "1" * 64}
    assert uncovered_videos(TEAM, one, one) == ["two_table/1.mp4"]
    assert not annotate_allowed(team(), "ego_video", "internal", None, TEAM, one, one)
    # the record must be the episode's own
    assert not annotate_allowed(team(), "ego_video", "public", None, TEAM, COPIES, COPIES)


@pytest.mark.parametrize("on_disk", [
    {**COPIES, "two_table/1.deid.mp4": "3" * 64},  # the copy changed after deid
    {**COPIES, "two_table/1.deid.mp4": None},  # the copy is gone
])
def test_a_copy_whose_sha256_differs_is_refused(on_disk: dict[str, str | None]) -> None:
    assert not annotate_allowed(team(), "ego_video", "internal", None, TEAM, COPIES, on_disk)
    with pytest.raises(DeidBlocked, match="no de-identified copy with the sha256.*1.mp4"):
        require_annotate(team(), "ego_video", "internal", None, TEAM, COPIES, on_disk)


def test_the_pin_holds_the_videos_of_da30s_sample() -> None:
    name, files = REAL_PIN()
    assert name.startswith("egodex-test-da30-part1@") and len(name.split("@")[1]) == 12
    assert len(files) == 218 and all(k.endswith(".mp4") and k.count("/") == 1 for k in files)
    assert all(len(d) == 64 for d in files.values())


def test_ingested_egodex_records_the_waiver_and_passes(store: Path, cfg: EgoConfig) -> None:
    record = register_egodex(store, cfg)
    assert record.deid_waiver == WAIVER_REASON and record.deid_waiver_manifest
    work = store / "w"
    for e in api.ingest(record, work, cfg, store):
        assert e.deid_status == "raw" and api.gate_open(e, record)
    blocked = replace(record, data_class="internal")
    first = api.ingest(record, work, cfg, store)[0]
    with pytest.raises(DeidBlocked):
        api.require_gate(first, blocked)


def test_a_video_not_in_the_pin_is_not_waived(store: Path, cfg: EgoConfig) -> None:
    """The team's own mp4 beside an EgoDex HDF5, under the configured EgoDex root."""
    write_mp4(store / "egodex" / "part1" / "stack_cups" / "0.mp4", frames=FRAMES - 1)
    record = register_egodex(store, cfg)
    assert record.deid_waiver is None and record.deid_waiver_manifest is None
    work = store / "w"
    episodes = api.ingest(record, work, cfg, store)
    assert not any(api.gate_open(e, record) for e in episodes)
