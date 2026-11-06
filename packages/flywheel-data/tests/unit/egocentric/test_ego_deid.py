"""DA-04 task 2: the de-identification gate and the D2 waiver (AC 2, NFR13)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import Episode, EpisodeMetadata
from flywheel.data.annotate.deid.gate import (
    WAIVED,
    DeidBlocked,
    annotate_allowed,
    deid_waiver,
    require_annotate,
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


def test_the_waiver_mirrors_da30_and_covers_only_public_egodex() -> None:
    assert WAIVED == frozenset({("egodex", "public")})
    assert deid_waiver("egodex", "public") is not None
    for detail, data_class in [("egodex", "internal"), ("egodex", "restricted"),
                               ("ego_video", "public"), ("ego_video", "internal")]:
        assert deid_waiver(detail, data_class) is None


def test_public_egodex_passes_raw_with_its_waiver() -> None:
    reason = deid_waiver("egodex", "public")
    raw = episode()
    assert annotate_allowed(raw, "egodex", "public", reason)
    require_annotate(raw, "egodex", "public", reason)


def test_every_other_raw_egocentric_episode_is_blocked() -> None:
    recorded = episode(data_class="internal", action_quality="pseudo")
    assert not annotate_allowed(recorded, "ego_video", "internal", None)
    with pytest.raises(DeidBlocked, match="NFR13"):
        require_annotate(recorded, "ego_video", "internal", None)
    # a waiver text is not enough without the pair, nor the pair without the text
    assert not annotate_allowed(recorded, "ego_video", "internal", "someone said so")
    assert not annotate_allowed(episode(), "egodex", "public", None)
    # the record must be the episode's own
    assert not annotate_allowed(episode(), "egodex", "internal", deid_waiver("egodex", "public"))


def test_blurred_egocentric_and_robot_episodes_pass() -> None:
    assert annotate_allowed(episode(deid_status="blurred", data_class="internal"),
                            "ego_video", "internal", None)
    robot = episode(source_kind="teleop", action_quality="measured")
    assert annotate_allowed(robot, "psi_data", "public", None)


def test_ingested_egodex_records_the_waiver_and_passes(store: Path, cfg: EgoConfig) -> None:
    record = register_egodex(store, cfg)
    work = store / "w"
    for e in api.ingest(record, work, cfg, store):
        assert e.deid_status == "raw" and api.gate_open(e, record)
    blocked = replace(record, data_class="internal")
    first = api.ingest(record, work, cfg, store)[0]
    with pytest.raises(DeidBlocked):
        api.require_gate(first, blocked)
