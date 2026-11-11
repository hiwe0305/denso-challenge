from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.console.index import cited, story
from flywheel.console.paths import ConsolePaths

KEYS = {
    "runs", "train_log_tail", "vm_phases", "sources", "heat", "reasons", "qa_sample", "h1m",
    "ledger", "colab_balance", "colab_sessions", "ds", "eval",
}  # fmt: skip


def test_downsample_cap() -> None:
    pts = [(float(i), float(i * 2)) for i in range(100_000)]
    out = story.downsample(pts)
    assert len(out) <= 2000
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert story.downsample(pts[:10]) == pts[:10]


def _real(fw: ConsolePaths) -> ConsolePaths:
    # the packaged seed and docs come from the real repo checkout
    repo = Path(__file__).resolve().parents[4]
    return ConsolePaths(repo=repo, fw_root=fw.fw_root)


def test_story_keys(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    story.build(fw, out)
    data = json.loads((out / "story.json").read_text())
    assert KEYS <= set(data)
    assert data["runs"] == [] and data["colab_balance"] == [] and data["h1m"] == {}


def test_story_reads_runs_and_sources(fw: ConsolePaths, tmp_path: Path) -> None:
    run = fw.fw_root / "tray/pair60k/C_70/job1"
    run.mkdir(parents=True)
    rows = [
        {"split": "train", "step": i, "loss": 1.0, "loss_by_group": {"g": 2.0}} for i in range(5)
    ]
    (run / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    (run / "launch.json").write_text(json.dumps({"argv": ["a"]}))
    src = fw.fw_root / "pipeline/src_0123456789abcdef"
    (src / "report").mkdir(parents=True)
    (src / "qa").mkdir()
    (src / "source.json").write_text(json.dumps({"name": "x", "data_class": "public"}))
    (src / "report/egocentric.json").write_text(
        json.dumps({"episodes": 1, "decisions": {"pass": 1}, "checks": {"c": {"flag": 2}}})
    )
    (src / "qa/egocentric.jsonl").write_text(
        json.dumps({"episode_id": "e1", "reasons": ["bad:why"]}) + "\n"
    )
    out = tmp_path / "out"
    story.build(fw, out)
    d = json.loads((out / "story.json").read_text())
    assert d["runs"][0]["job"] == "job1" and d["runs"][0]["groups_last"] == {"g": 2.0}
    assert d["sources"][0]["id"] == "01234567" and d["heat"] == [["c", "01234567", 2]]
    assert d["reasons"] == [["bad", 1, ["e1"]]]


def test_story_eval_from_cited(fw: ConsolePaths, tmp_path: Path) -> None:
    paths = _real(fw)
    out = tmp_path / "out"
    story.build(paths, out)
    data = json.loads((out / "story.json").read_text())
    assert data["eval"] == json.loads(json.dumps(cited.eval_block(paths)))
    assert data["loop_chain"] == [240, 131, 262, 229, 177]


def test_story_ds_is_catalog(fw: ConsolePaths, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "catalog.json").write_text(json.dumps({"generated": "g", "rows": [{"id": "a"}]}))
    story.build(fw, out)
    assert json.loads((out / "story.json").read_text())["ds"]["rows"] == [{"id": "a"}]


@pytest.mark.parametrize("n", [0, 1, 2])
def test_downsample_tiny(n: int) -> None:
    pts = [(float(i), 0.0) for i in range(n)]
    assert story.downsample(pts, 2000) == pts
