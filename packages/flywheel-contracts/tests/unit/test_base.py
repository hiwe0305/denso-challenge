"""Tests for BaseRecord, canonical JSON serialization, and ID generation."""

import re
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from flywheel.contracts.base import (
    BaseRecord,
    CROCKFORD_BASE32,
    canonical_json,
    content_id,
    event_id,
    is_valid_content_id,
    is_valid_event_id,
    new_ulid,
)


def test_base_record_default_columns() -> None:
    """AC 3: site_id, task_id, embodiment_id, schema_version and meta take defaults."""
    record = BaseRecord()
    assert record.site_id == "local"
    assert record.task_id == "default"
    assert record.embodiment_id == "default"
    assert record.schema_version == "1.0.0"
    assert record.meta == {}


def test_base_record_custom_columns() -> None:
    """Verify that columns can be overridden."""
    record = BaseRecord(
        site_id="factory_tokyo",
        task_id="g1_locomotion_pick_between_tables",
        embodiment_id="g1_sonic_dwbc@1",
        schema_version="2.0.0",
        meta={"source": "unit_test"},
    )
    assert record.site_id == "factory_tokyo"
    assert record.task_id == "g1_locomotion_pick_between_tables"
    assert record.embodiment_id == "g1_sonic_dwbc@1"
    assert record.schema_version == "2.0.0"
    assert record.meta == {"source": "unit_test"}


def test_ulid_generation_format() -> None:
    """AC 4: ULID has 26 Crockford Base32 characters and matches regex."""
    ulid = new_ulid()
    assert len(ulid) == 26
    assert re.match(r"^[0-9A-HJKMNP-TV-Z]{26}$", ulid)
    assert all(c in CROCKFORD_BASE32 for c in ulid)


def test_ulid_deterministic() -> None:
    """Test deterministic ULID generation with fixed timestamp and random bytes."""
    ts = 1700000000000
    rnd = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
    ulid1 = new_ulid(timestamp_ms=ts, random_bytes=rnd)
    ulid2 = new_ulid(timestamp_ms=ts, random_bytes=rnd)
    assert ulid1 == ulid2
    assert len(ulid1) == 26


def test_event_id_format() -> None:
    eid = event_id("ep")
    assert eid.startswith("ep_")
    assert is_valid_event_id(eid, "ep")
    assert not is_valid_event_id(eid, "qa")


def test_content_id_deterministic() -> None:
    """AC 4: Same content produces same ID, changing a field produces different ID."""
    data1 = {"name": "test", "count": 42, "tags": ["a", "b"]}
    data2 = {"tags": ["a", "b"], "name": "test", "count": 42}
    data3 = {"name": "test", "count": 43, "tags": ["a", "b"]}

    cid1 = content_id("rel", data1)
    cid2 = content_id("rel", data2)
    cid3 = content_id("rel", data3)

    assert cid1 == cid2
    assert cid1 != cid3
    assert is_valid_content_id(cid1, "rel")
    assert re.match(r"^rel_[0-9a-f]{16}$", cid1)


def test_content_id_ignores_existing_id() -> None:
    """Content ID calculation is pure content-based even if 'id' field is present."""
    data = {"name": "sample", "num": 1}
    data_with_id = {"id": "rel_1234567890abcdef", "name": "sample", "num": 1}
    assert content_id("rel", data) == content_id("rel", data_with_id)


# Property-based testing with hypothesis
json_primitives = st.none() | st.booleans() | st.integers(min_value=-10000, max_value=10000) | st.text(max_size=30)


@given(st.dictionaries(st.text(min_size=1, max_size=10), json_primitives, max_size=10))
def test_hypothesis_canonical_json_permutation_invariant(d: dict[str, Any]) -> None:
    """Hypothesis property: Permuting dictionary keys never changes canonical JSON or content ID."""
    keys = list(d.keys())
    reversed_dict = {k: d[k] for k in reversed(keys)}

    json1 = canonical_json(d)
    json2 = canonical_json(reversed_dict)
    assert json1 == json2

    cid1 = content_id("tst", d)
    cid2 = content_id("tst", reversed_dict)
    assert cid1 == cid2
