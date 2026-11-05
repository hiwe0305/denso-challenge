"""The gate copy's relabel touches source_detail only, marks what it changed, and refuses
anything but virtual_teleop->planner_wbc and s2->teleop_pico in a marked scratch root
(DA-35 task 12)."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

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


def gate_copy(root: Path, marked: bool = True) -> Path:
    """A scratch root holding one Psi0 export copy: episode 0 virtual_teleop, 1 s2."""
    root.mkdir(parents=True, exist_ok=True)
    if marked:
        (root / ".gate-scratch").touch()
    meta = root / "sources" / "copy" / "meta"
    meta.mkdir(parents=True)
    lines = [episode(0, "virtual_teleop"), episode(1, "s2")]
    (meta / "episodes.jsonl").write_text("".join(x + "\n" for x in lines))
    return meta.parent


def test_only_the_named_label_changes_and_each_change_is_marked(tmp_path: Path) -> None:
    copy = gate_copy(tmp_path / "gate")

    assert load().relabel(copy, "virtual_teleop", "planner_wbc", tmp_path / "gate") == (1, 2)

    rows = [json.loads(x) for x in (copy / "meta" / "episodes.jsonl").read_text().splitlines()]
    blocks = [json.loads(r["environment_config"])["flywheel"] for r in rows]
    assert blocks[0] == {
        "source_detail": "planner_wbc",
        "synthetic_tier": "S1",
        "seed": 100,
        "gate_relabel": "virtual_teleop->planner_wbc",
    }
    assert blocks[1] == {"source_detail": "s2", "synthetic_tier": "S1", "seed": 101}
    assert [r["episode_index"] for r in rows] == [0, 1]
    assert sorted(p.name for p in (copy / "meta").iterdir()) == ["episodes.jsonl"]


@pytest.mark.parametrize(
    ("root", "marked", "dataset", "fw_root", "why"),
    [
        ("gate", False, "gate", None, "no .gate-scratch marker"),
        ("gate", True, "store", None, "not inside the scratch root"),
        ("fwdata/gate", True, "fwdata/gate", None, "under a fwdata store"),
        ("store/gate", True, "store/gate", "store", "under FW_ROOT"),
    ],
)
def test_a_dataset_outside_a_marked_scratch_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: str, marked: bool, dataset: str,
    fw_root: str | None, why: str,
) -> None:  # fmt: skip
    gate_copy(tmp_path / root, marked)
    target = gate_copy(tmp_path / dataset, marked) if dataset != root else None
    copy = target or tmp_path / root / "sources" / "copy"
    if fw_root:
        monkeypatch.setenv("FW_ROOT", str(tmp_path / fw_root))
    else:
        monkeypatch.delenv("FW_ROOT", raising=False)
    before = (copy / "meta" / "episodes.jsonl").read_text()
    module = load()
    with pytest.raises(module.Refused, match=why):
        module.relabel(copy, "virtual_teleop", "planner_wbc", tmp_path / root)
    assert (copy / "meta" / "episodes.jsonl").read_text() == before


def test_the_cli_refuses_another_label_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FW_ROOT", raising=False)
    copy = gate_copy(tmp_path / "gate")
    before = (copy / "meta" / "episodes.jsonl").read_text()
    argv = ["--scratch-root", str(tmp_path / "gate"), str(copy), "s2", "planner_wbc"]
    assert load().main(argv) == 2
    assert (copy / "meta" / "episodes.jsonl").read_text() == before


def test_a_kill_before_the_rename_leaves_the_episodes_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FW_ROOT", raising=False)
    copy = gate_copy(tmp_path / "gate")
    before = (copy / "meta" / "episodes.jsonl").read_text()
    module = load()

    def killed(*_: object) -> None:
        raise OSError("killed before the rename")

    monkeypatch.setattr(module, "os", SimpleNamespace(replace=killed, getpid=os.getpid,
                                                     environ=os.environ))  # fmt: skip
    with pytest.raises(OSError, match="killed"):
        module.relabel(copy, "virtual_teleop", "planner_wbc", tmp_path / "gate")
    assert (copy / "meta" / "episodes.jsonl").read_text() == before


def test_the_s2_variants_relabel_to_teleop_pico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FW_ROOT", raising=False)
    copy = gate_copy(tmp_path / "gate")  # episode 0 virtual_teleop, 1 s2
    assert load().relabel(copy, "s2", "teleop_pico", tmp_path / "gate") == (1, 2)
    rows = [json.loads(x) for x in (copy / "meta" / "episodes.jsonl").read_text().splitlines()]
    blocks = [json.loads(r["environment_config"])["flywheel"] for r in rows]
    assert [b["source_detail"] for b in blocks] == ["virtual_teleop", "teleop_pico"]
    assert blocks[1]["gate_relabel"] == "s2->teleop_pico"
