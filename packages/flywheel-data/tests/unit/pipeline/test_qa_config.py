"""configs/data/qa.yaml: every key required, the version names the bytes read (DA-03 AC 3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from flywheel.data.config import ConfigError, QAConfig, load_layout, load_qa_config
from qa_data import G1_YAML, QA_YAML, SPLITS


def test_the_shipped_config_loads_with_g1_and_the_shared_split_plan(qa_config: QAConfig) -> None:
    assert qa_config.train_seeds == (0, 1_000_000)
    assert set(qa_config.action_jump) == set(qa_config.groups)
    assert len(qa_config.limits) == 36 and qa_config.limits[17] == (-1.0472, 2.0944)
    assert set(qa_config.source_checks) == {"psi_data", "planner_wbc", "teleop_pico"}
    assert all(rule.code.startswith("D") for rule in qa_config.checks.values())


Edit = Callable[[dict[str, object]], None]


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d.pop("min_frames"), "missing \\['min_frames'\\]"),
        (lambda d: d["checks"].pop("joint_limits"), "missing \\['joint_limits'\\]"),
        (lambda d: d.update(extra=1), "unknown \\['extra'\\]"),
        (lambda d: d["checks"]["lineage"].update(code="D9"), "is not one of"),
        (lambda d: d["checks"]["lineage"].update(on_fail="drop"), "on_fail 'drop'"),
        (lambda d: d["action_jump"]["thresholds"].pop("arm"), "missing \\['arm'\\]"),
        (lambda d: d["checks"]["replay_dynamic"].pop("when_missing"), "missing"),
    ],
)
def test_the_config_has_no_implicit_defaults(tmp_path: Path, edit: Edit, message: str) -> None:
    data = yaml.safe_load(QA_YAML.read_text())
    edit(data)
    path = tmp_path / "qa.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigError, match=message):
        load_qa_config(path, load_layout(G1_YAML), SPLITS)


def test_the_threshold_version_names_the_bytes_read(tmp_path: Path, qa_config: QAConfig) -> None:
    path = tmp_path / "qa.yaml"
    path.write_text(QA_YAML.read_text() + "\n# edited\n")
    edited = load_qa_config(path, load_layout(G1_YAML), SPLITS)
    assert edited.threshold_version != qa_config.threshold_version
    assert edited.threshold_version.split("@")[0] == qa_config.version == "qa-1"
