"""Fixtures of the egocentric tests: a store with a small EgoDex-like sample."""

from __future__ import annotations

from pathlib import Path

import pytest
from ego_data import config_for, make_egodex
from flywheel.data.ingest.egocentric.config import EgoConfig, load_config


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "store"
    make_egodex(root)
    monkeypatch.setenv("FW_ROOT", str(root))
    return root


@pytest.fixture
def config_path(tmp_path: Path, store: Path) -> Path:
    return config_for(tmp_path)


@pytest.fixture
def cfg(config_path: Path) -> EgoConfig:
    return load_config(config_path)
