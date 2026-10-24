"""Local test wiring for the separately packaged fake adapters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FAKES_SRC = Path(__file__).parents[3] / "flywheel-fakes" / "src"
sys.path.insert(0, str(FAKES_SRC))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e_fake: CPU-only end-to-end loop on fake adapters")
