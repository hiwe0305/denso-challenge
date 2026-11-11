from __future__ import annotations

import json
from pathlib import Path

from conftest import make_lerobot
from flywheel.console.index import robot
from flywheel.console.paths import ConsolePaths

V5_KEYS = ["i", "n", "s", "lv", "seed", "part", "cut", "ok", "dist", "r", "gap", "light", "out"]


def _build(
    fw: ConsolePaths, tmp_path: Path, rows: list[dict[str, object]]
) -> tuple[Path, dict[str, int]]:
    out = tmp_path / "out"
    return out, robot.build(fw, out, rows)


def test_robot_episodes_shape(fw: ConsolePaths, lerobot: Path, tmp_path: Path) -> None:
    out, counts = _build(fw, tmp_path, [{"id": "S70", "lerobot": "cut/S70"}])
    assert counts == {"S70": 3}
    eps = json.loads((out / "ds/S70/episodes.json").read_text())
    assert len(eps) == 3
    assert list(eps[0]) == V5_KEYS
    assert eps[0]["s"] == 0.2 and eps[0]["dist"] == 2.0 and len(eps[0]["r"]) == 7
    env = json.loads((out / "ds/S70/env.json").read_text())
    assert set(env) == {"0", "1", "2"} and env["0"]["instruction"] == "Carry the tray."
    for name in ("quality", "method"):
        assert (out / f"ds/S70/{name}.json").is_file()
    q = json.loads((out / "ds/S70/quality.json").read_text())
    assert q["success_rate_ok"] == 1.0 and q["hists"]


def test_robot_posters_written(fw: ConsolePaths, lerobot: Path, tmp_path: Path) -> None:
    out, _ = _build(fw, tmp_path, [{"id": "S70", "lerobot": "cut/S70"}])
    for i in range(3):
        assert (out / f"ds/S70/posters/{i}.jpg").read_bytes()[:2] == b"\xff\xd8"


def test_rows_without_lerobot_or_dir_are_skipped(fw: ConsolePaths, tmp_path: Path) -> None:
    rows: list[dict[str, object]] = [{"id": "x"}, {"id": "y", "lerobot": "missing"}]
    out, counts = _build(fw, tmp_path, rows)
    assert counts == {} and not (out / "ds").exists()


def test_all_reuses_s70_poster_when_same_cut(fw: ConsolePaths, tmp_path: Path) -> None:
    make_lerobot(fw.fw_root / "cut/S70", n=2, base=0)
    all_root = make_lerobot(fw.fw_root / "cut/ALL", n=2, base=0)
    # S70 episodes carry cut indices through flywheel_subset.json
    part_eps = [
        {"episode_index": 0, "cut_episode_index": 1},
        {"episode_index": 1, "cut_episode_index": 5},
    ]
    sub = {"parts": [{"release_id": "r_41899efb4b27", "episodes": part_eps}]}
    (fw.fw_root / "cut/S70/meta/flywheel_subset.json").write_text(json.dumps(sub))
    out, counts = _build(
        fw, tmp_path,
        [{"id": "S70", "lerobot": "cut/S70"}, {"id": "ALL", "lerobot": "cut/ALL"}],
    )  # fmt: skip
    assert counts == {"S70": 2, "ALL": 2}
    # ALL episode 1 matches S70 cut 1 (same mp4 size): poster is a copy of S70/0.jpg
    assert (out / "ds/ALL/posters/1.jpg").read_bytes() == (
        out / "ds/S70/posters/0.jpg"
    ).read_bytes()
    assert all_root.is_dir()


def test_rows_none_reads_seed_catalog(fw: ConsolePaths, tmp_path: Path) -> None:
    # the shipped seed rows point at fwdata dirs that do not exist under this empty fw_root
    assert robot.load_rows(fw) is not None
    assert robot.build(fw, tmp_path / "out") == {}
