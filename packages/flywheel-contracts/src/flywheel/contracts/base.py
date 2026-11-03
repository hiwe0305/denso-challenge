"""Base record class, canonical JSON serialization, and ID generation."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import secrets
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Crockford's Base32 character set (32 characters, excluding I, L, O, U)
CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

CONTENT_ID_PATTERN = r"^[a-z0-9]+_[0-9a-f]{16}$"
EVENT_ID_PATTERN = r"^[a-z0-9]+_[0-9A-HJKMNP-TV-Z]{26}$"

CONTENT_ID_REGEX = re.compile(CONTENT_ID_PATTERN)
EVENT_ID_REGEX = re.compile(EVENT_ID_PATTERN)


def new_ulid(
    timestamp_ms: int | None = None,
    random_bytes: bytes | None = None,
) -> str:
    """Generate a standard 26-character Crockford Base32 ULID.

    48-bit timestamp (10 Base32 characters) + 80-bit randomness (16 Base32 characters).
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    if timestamp_ms < 0 or timestamp_ms > 0xFFFFFFFFFFFF:
        raise ValueError("Timestamp out of range for 48-bit integer")

    if random_bytes is None:
        random_bytes = secrets.token_bytes(10)
    elif len(random_bytes) != 10:
        raise ValueError("random_bytes must be exactly 10 bytes (80 bits)")

    # Encode 48-bit timestamp into 10 characters
    time_chars = ["0"] * 10
    val = timestamp_ms
    for i in range(9, -1, -1):
        time_chars[i] = CROCKFORD_BASE32[val & 0x1F]
        val >>= 5

    # Encode 80-bit randomness (10 bytes) into 16 characters
    rand_int = int.from_bytes(random_bytes, byteorder="big")
    rand_chars = ["0"] * 16
    for i in range(15, -1, -1):
        rand_chars[i] = CROCKFORD_BASE32[rand_int & 0x1F]
        rand_int >>= 5

    return "".join(time_chars) + "".join(rand_chars)


def canonical_repr(data: Any) -> Any:
    """Recursively convert data into canonical python types for JSON serialization."""
    if isinstance(data, BaseModel):
        return canonical_repr(data.model_dump(mode="json"))
    if isinstance(data, dict):
        sorted_items = sorted(data.items(), key=lambda item: str(item[0]))
        return {str(k): canonical_repr(v) for k, v in sorted_items}
    if isinstance(data, (list, tuple)):
        return [canonical_repr(v) for v in data]
    if isinstance(data, datetime.datetime):
        # Format ISO with Z or standard offset
        if data.tzinfo is None:
            return data.isoformat() + "Z"
        return data.isoformat()
    if isinstance(data, datetime.date):
        return data.isoformat()
    if isinstance(data, float):
        # Normalize -0.0 to 0.0
        if data == 0.0:
            return 0.0
        return data
    return data


def canonical_json(data: Any) -> str:
    """Serialize data into deterministic canonical JSON (sorted keys, no spaces, UTF-8)."""
    canon = canonical_repr(data)
    return json.dumps(
        canon,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_id(prefix: str, content: Any) -> str:
    """Generate a content-addressed ID: <prefix>_<16 hex chars of sha256 of canonical JSON>."""
    if isinstance(content, BaseModel):
        payload = content.model_dump(mode="json")
    elif isinstance(content, dict):
        payload = dict(content)
    else:
        payload = content

    # If payload is a dict, remove 'id' if present to avoid circular dependency
    if isinstance(payload, dict) and "id" in payload:
        payload = {k: v for k, v in payload.items() if k != "id"}

    canon = canonical_json(payload)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def event_id(prefix: str, ulid_str: str | None = None) -> str:
    """Generate an event ID: <prefix>_<ULID>."""
    return f"{prefix}_{ulid_str or new_ulid()}"


def is_valid_content_id(id_str: str, prefix: str | None = None) -> bool:
    """Check if string matches content ID format, optionally checking prefix."""
    if not CONTENT_ID_REGEX.match(id_str):
        return False
    if prefix is not None:
        return id_str.startswith(f"{prefix}_")
    return True


def is_valid_event_id(id_str: str, prefix: str | None = None) -> bool:
    """Check if string matches event ID format, optionally checking prefix."""
    if not EVENT_ID_REGEX.match(id_str):
        return False
    if prefix is not None:
        return id_str.startswith(f"{prefix}_")
    return True


class BaseRecord(BaseModel):
    """Base record for all L0-lite catalog entities.

    Enforces immutability, extra='forbid', canonical defaults for
    site_id, task_id, embodiment_id, schema_version and meta.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        populate_by_name=True,
    )

    site_id: str = "local"
    task_id: str = "default"
    embodiment_id: str = "default"
    schema_version: str = "1.0.0"
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_canonical_json(self) -> str:
        """Return canonical JSON representation of this record."""
        return canonical_json(self)
