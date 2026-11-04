"""The gate copy's relabel touches source_detail only and marks what it changed (DA-35 task 12)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "s2" / "gate_relabel.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gate_relabel", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def episode(index: int, detail: str) -> str:
    block = {"source_detail": detail, "synthetic_tier": "S1", "seed": 100 + index}
    config = {"uid": "tray", "flywheel": block}
    return json.dumps({"episode_index": index, "environment_config": json.dumps(config)})


def test_only_the_named_label_changes_and_each_change_is_marked(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir()
    lines = [episode(0, "virtual_teleop"), episode(1, "s2")]
    (meta / "episodes.jsonl").write_text("".join(x + "\n" for x in lines))

    assert load().relabel(tmp_path, "virtual_teleop", "planner_wbc") == (1, 2)

    rows = [json.loads(x) for x in (meta / "episodes.jsonl").read_text().splitlines()]
    blocks = [json.loads(r["environment_config"])["flywheel"] for r in rows]
    assert blocks[0] == {
        "source_detail": "planner_wbc",
        "synthetic_tier": "S1",
        "seed": 100,
        "gate_relabel": "virtual_teleop->planner_wbc",
    }
    assert blocks[1] == {"source_detail": "s2", "synthetic_tier": "S1", "seed": 101}
    assert [r["episode_index"] for r in rows] == [0, 1]
