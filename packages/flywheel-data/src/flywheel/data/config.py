"""Configuration of the data lane."""

from __future__ import annotations

import os
from pathlib import Path

# 03 section 8.1: $FW_ROOT, by default ./fwdata, holds sources, releases and runs.
DEFAULT_STORE = Path("fwdata")


def store_root() -> Path:
    """The store root: $FW_ROOT when set, else ./fwdata, as an absolute path."""
    return Path(os.environ.get("FW_ROOT") or DEFAULT_STORE).resolve()
