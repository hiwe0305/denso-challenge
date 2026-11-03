"""`fw data ingest | qa | release | report` end to end on a small dataset (DA-03 AC 6)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from flywheel.contracts.entities import LedgerEntry
from flywheel.contracts.v0 import ReleaseManifest
from flywheel.data.cli import app
from flywheel.data.ingest.lerobot import write_episode
from flywheel.store.paths import StorePaths
from qa_data import G1_YAML, QA_YAML, SPLITS, clean_frames, psi0_info, video_path
from typer.testing import CliRunner

CONFIG = ["--config", str(QA_YAML), "--layout", str(G1_YAML), "--split-plan", str(SPLITS)]
runner = CliRunner()


def psi_like(root: Path, mp4: Callable[..., None], lengths: list[int]) -> Path:
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps(psi0_info()))
    for index, length in enumerate(lengths):
        write_episode(root, clean_frames(index, length))
        mp4(video_path(root, index), length)
    return root


def run(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def ledger(store: Path) -> list[LedgerEntry]:
    files = sorted(StorePaths(store).runs_dir.glob("*/*/ledger.jsonl"))
    return [LedgerEntry.model_validate_json(line)
            for path in files for line in path.read_text().splitlines()]


def test_the_four_commands_on_a_psi_like_dataset(
    store: Path, mp4: Callable[..., None]
) -> None:
    dataset = psi_like(store / "psi", mp4, [20, 25, 1])
    output = run("ingest", str(dataset), "--source-detail", "psi_data", "--license", "unknown",
                 "--data-class", "public")
    work = Path(output.split("work: ")[1].split()[0])
    assert "3 episodes" in output
    assert "{'pass': 2, 'flag': 0, 'quarantine': 0, 'reject': 1}" in run("qa", str(work), *CONFIG)
    output = run("release", str(work), "--split-plan", str(SPLITS))
    source_id = json.loads((work / "ingest.json").read_text())["source_id"]
    release_dir = store / "releases" / f"psi_data_{source_id}"
    written = (release_dir / "release_manifest.json").read_text()
    manifest = ReleaseManifest.model_validate_json(written)
    assert manifest.release_id in output
    release = json.loads((release_dir / "release.json").read_text())
    assert [i["excluded"] for i in release["items"]].count(True) == 1  # the 1-frame episode
    output = run("report", str(work))
    page = (work / "report" / "index.html").read_text()
    assert "psi_data" in page and "min_frames" in output

    rows = ledger(store)
    assert len(rows) == 8  # four jobs, an estimate and a measurement each
    estimates = {r.id: r for r in rows if r.measure_kind == "estimated"}
    measured = [r for r in rows if r.measure_kind == "measured"]
    assert all(estimates[str(r.estimate_entry_id)].job_id == r.job_id for r in measured)
    assert {r.run_plan_id for r in rows} == {rows[0].run_plan_id}
    assert rows[0].run_plan_id.startswith("g0-DA-03-")
    assert {r.activity for r in rows} == {"pipeline", "qa"}


def test_a_refused_release_exits_2_and_still_records_its_cost(
    store: Path, mp4: Callable[..., None]
) -> None:
    dataset = psi_like(store / "copy", mp4, [20])
    (dataset / "meta" / "benchmark_copy.json").write_text('{"benchmark_copy_id": "bench-x"}')
    output = run("ingest", str(dataset), "--source-detail", "psi_data", "--license", "unknown",
                 "--data-class", "public", "--run-plan-id", "rp_test")
    work = Path(output.split("work: ")[1].split()[0])
    run("qa", str(work), *CONFIG, "--run-plan-id", "rp_test")
    result = runner.invoke(app, ["release", str(work), "--split-plan", str(SPLITS),
                                 "--run-plan-id", "rp_test"])
    assert result.exit_code == 2
    assert "benchmark copies ['bench-x']" in result.output
    notes = [r.note for r in ledger(store) if r.measure_kind == "measured"]
    assert any("data_release, failed: ReleaseRefused" in str(n) for n in notes)


def test_qa_refuses_a_source_changed_since_ingest(store: Path, mp4: Callable[..., None]) -> None:
    dataset = psi_like(store / "psi", mp4, [20])
    output = run("ingest", str(dataset), "--source-detail", "psi_data", "--license", "unknown",
                 "--data-class", "public")
    work = Path(output.split("work: ")[1].split()[0])
    write_episode(dataset, clean_frames(0, 19))
    result = runner.invoke(app, ["qa", str(work), *CONFIG])
    assert result.exit_code == 2 and "changed since ingest" in result.output


@pytest.mark.parametrize("missing", ["source.json"])
def test_commands_after_ingest_need_its_work_dir(tmp_path: Path, missing: str) -> None:
    result = runner.invoke(app, ["report", str(tmp_path)])
    assert result.exit_code == 2 and missing in result.output


def test_calibrate_prints_the_thresholds_block(store: Path, mp4: Callable[..., None]) -> None:
    dataset = psi_like(store / "psi", mp4, [20, 21])
    output = run("ingest", str(dataset), "--source-detail", "psi_data", "--license", "unknown",
                 "--data-class", "public")
    work = Path(output.split("work: ")[1].split()[0])
    printed = run("qa", str(work), *CONFIG, "--calibrate")
    assert "    arm: 0.01" in printed and not (work / "qa").exists()
