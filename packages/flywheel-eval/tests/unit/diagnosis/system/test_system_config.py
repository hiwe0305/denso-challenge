"""`system.yaml`: every threshold named, hashed, and no default in code (DA-13 AC 2).

The file in `configs/` is read as it ships, because a threshold file that does
not parse is a story that cannot run, and a key the code stopped reading is a
number its author wrote and nobody uses.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.eval.config import ConfigError, SystemThresholds, load_system_thresholds

SYSTEM_CONFIG = Path("configs") / "eval" / "diagnosis" / "system.yaml"


def _repo_root() -> Path:
    for folder in (Path.cwd(), *Path.cwd().parents):
        if (folder / ".git").exists():
            return folder
    raise AssertionError("test phải chạy trong repo")


@pytest.fixture
def shipped() -> dict[str, Any]:
    return yaml.safe_load((_repo_root() / SYSTEM_CONFIG).read_text(encoding="utf-8"))


def test_the_shipped_config_parses_and_carries_its_hash() -> None:
    thresholds, digest = load_system_thresholds(_repo_root() / SYSTEM_CONFIG)

    assert len(digest) == 64
    assert thresholds.r3.tau_track_upper > 0
    assert thresholds.r1.percentile == 99.0
    assert thresholds.r6.ok_statuses == ("ok",)


def test_the_hash_is_of_the_bytes_that_were_parsed(tmp_path: Path, shipped) -> None:
    # The hash in a record must name the file that run actually read, so two
    # files that differ by one number cannot share a hash (AC 2).
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    first.write_text(yaml.safe_dump(shipped), encoding="utf-8")
    moved = {**shipped, "r3": {**shipped["r3"], "tau_track_upper": 0.11}}
    second.write_text(yaml.safe_dump(moved), encoding="utf-8")

    assert load_system_thresholds(first)[1] != load_system_thresholds(second)[1]


def test_the_camera_reference_ships_pinned_for_the_two_table_task(shipped) -> None:
    # Pinned at G0 on 3/11/2026 for SIMPLE b75c678 (DA-38). Both head cameras
    # render 640x360 at a 110 degree fov, so fx = 320 / tan(55 degrees).
    r5 = SystemThresholds.from_mapping(shipped).r5
    assert r5.reference_sha256 == "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"
    assert sorted(r5.cameras) == ["head_stereo_left", "head_stereo_right"]
    for camera in r5.cameras.values():
        assert (camera.width, camera.height, camera.mount) == (640, 360, "eye_in_head")
        assert camera.fx == pytest.approx(320 / math.tan(math.radians(55)))


def test_a_missing_threshold_raises_rather_than_defaulting(shipped) -> None:
    r3 = {key: value for key, value in shipped["r3"].items() if key != "percentile"}
    without = {**shipped, "r3": r3}

    with pytest.raises(ConfigError, match="missing threshold `r3.percentile`"):
        SystemThresholds.from_mapping(without)


def test_a_missing_section_raises(shipped) -> None:
    without = {key: value for key, value in shipped.items() if key != "r4"}

    with pytest.raises(ConfigError, match="missing section `r4`"):
        SystemThresholds.from_mapping(without)


def test_a_key_nobody_reads_raises(shipped) -> None:
    # A number nobody reads is not the number in use.
    extra = {**shipped, "r4": {**shipped["r4"], "tau_sync_ms": 20}}

    with pytest.raises(ConfigError, match="unknown key"):
        SystemThresholds.from_mapping(extra)


def test_a_percentile_outside_the_range_raises(shipped) -> None:
    broken = {**shipped, "r1": {**shipped["r1"], "percentile": 120.0}}

    with pytest.raises(ConfigError, match="percentile in \\[0, 100\\]"):
        SystemThresholds.from_mapping(broken)


def test_a_gap_allowance_outside_the_range_raises(shipped) -> None:
    broken = {**shipped, "signals": {**shipped["signals"], "max_gap_fraction": 2.0}}

    with pytest.raises(ConfigError, match="fraction in \\[0, 1\\]"):
        SystemThresholds.from_mapping(broken)


def test_a_reference_hash_that_is_not_a_hash_raises(shipped) -> None:
    broken = {**shipped, "r5": {**shipped["r5"], "reference_sha256": "deadbeef"}}

    with pytest.raises(ConfigError, match="64 hex characters or null"):
        SystemThresholds.from_mapping(broken)


def test_a_reference_hash_left_out_entirely_raises(shipped) -> None:
    # Writing `null` means "not pinned yet"; leaving the key out is an author
    # who forgot, and the two must not read the same.
    without = {
        **shipped,
        "r5": {key: value for key, value in shipped["r5"].items() if key != "reference_sha256"},
    }

    with pytest.raises(ConfigError, match="missing threshold `r5.reference_sha256`"):
        SystemThresholds.from_mapping(without)


def test_a_camera_reference_is_read_with_its_pose(shipped) -> None:
    pinned = {
        **shipped,
        "r5": {
            **shipped["r5"],
            "reference_sha256": "b" * 64,
            "cameras": {
                "head": {
                    "mount": "head_link",
                    "width": 640,
                    "height": 480,
                    "fx": 400.0,
                    "fy": 400.0,
                    "cx": 320.0,
                    "cy": 240.0,
                    "pose": [0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0],
                }
            },
        },
    }

    thresholds = SystemThresholds.from_mapping(pinned)

    assert thresholds.r5.cameras["head"].mount == "head_link"
    assert thresholds.r5.cameras["head"].pose == (0.0, 0.0, 1.5, 1.0, 0.0, 0.0, 0.0)


def test_a_camera_pose_of_the_wrong_length_raises(shipped) -> None:
    broken = {
        **shipped,
        "r5": {
            **shipped["r5"],
            "reference_sha256": "b" * 64,
            "cameras": {
                "head": {
                    "mount": "head_link",
                    "width": 640,
                    "height": 480,
                    "fx": 400.0,
                    "fy": 400.0,
                    "cx": 320.0,
                    "cy": 240.0,
                    "pose": [0.0, 0.0, 1.5],
                }
            },
        },
    }

    with pytest.raises(ConfigError, match="7 numbers"):
        SystemThresholds.from_mapping(broken)


def test_a_file_that_is_not_there_is_a_config_error(tmp_path: Path) -> None:
    # The command that asked for it says what it could not do, rather than
    # handing the engineer a traceback (review of #58, point 5).
    with pytest.raises(ConfigError, match="không đọc được"):
        load_system_thresholds(tmp_path / "missing.yaml")
