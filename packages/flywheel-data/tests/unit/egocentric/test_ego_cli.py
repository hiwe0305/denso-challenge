"""`fw egocentric` end to end on a small EgoDex-like sample (DA-04 AC 1-7).

Every command writes its estimated and measured ledger rows; a second run over the
same files gives the same segments; the team's recordings stop at the gate with
exit 2.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ego_data import make_videos
from flywheel.contracts.artifacts import DatasetReport, QAReport
from flywheel.contracts.entities import LedgerEntry
from flywheel.data.egocentric_cli import app
from flywheel.data.ingest.egocentric.episodes import SEGMENTS, bundle_dir, read_episodes
from flywheel.store.paths import StorePaths
from typer.testing import CliRunner

runner = CliRunner()


def run(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def ledger(store: Path) -> list[LedgerEntry]:
    files = sorted(StorePaths(store).runs_dir.glob("*/*/ledger.jsonl"))
    return [LedgerEntry.model_validate_json(line)
            for path in files for line in path.read_text().splitlines()]


def segment_hash(work: Path) -> str:
    digest = hashlib.sha256()
    for episode in sorted(read_episodes(work), key=lambda e: e.episode_id):
        digest.update((bundle_dir(work, episode.episode_id) / SEGMENTS).read_bytes())
    return digest.hexdigest()


def test_ingest_pose_annotate_qa_report_review(store: Path, config_path: Path) -> None:
    config = ["--config", str(config_path)]
    output = run("ingest", "egodex", *config)
    assert "4 episodes" in output and "waived (D2; videos match test-pin@" in output
    work = Path(output.split("work: ")[1].split()[0])
    assert "E-B pose of 4 episodes" in run("pose", str(work))
    output = run("annotate", str(work), *config)
    assert "4 episodes, 8 segments" in output
    output = run("qa", str(work), *config)
    assert "4 QAReports: {'pass': 4, 'flag': 0, 'reject': 0}" in output
    reports = [QAReport.model_validate_json(line)
               for line in (work / "qa" / "egocentric.jsonl").read_text().splitlines()]
    assert {r.decision for r in reports} == {"pass"}
    run("report", str(work), *config)
    contract = DatasetReport.model_validate_json(
        (work / "report" / "dataset_report.json").read_text())
    assert contract.episode_count == 4
    summary = json.loads((work / "report" / "egocentric.json").read_text())
    assert summary["segments"] == 8 and summary["label_sources"] == {"rule": 8}
    assert summary["source"]["deid_waiver"] and summary["decisions"]["pass"] == 4
    assert "<h2>Egocentric</h2>" in (work / "report" / "index.html").read_text()
    assert "segments to review" in run("review", str(work), "--sample", *config)
    assert (work / "review" / "sheet.jsonl").is_file()

    rows = ledger(store)
    assert len(rows) == 2 * 6
    assert {r.measure_kind for r in rows} == {"estimated", "measured"}
    estimates = {r.id for r in rows if r.measure_kind == "estimated"}
    assert {r.estimate_entry_id for r in rows if r.measure_kind == "measured"} == estimates


def test_a_rerun_gives_the_same_segments(store: Path, config_path: Path) -> None:
    config = ["--config", str(config_path)]
    work = Path(run("ingest", "egodex", *config).split("work: ")[1].split()[0])
    run("pose", str(work))
    run("annotate", str(work), *config)
    first = segment_hash(work)
    run("annotate", str(work), *config)
    assert segment_hash(work) == first


def test_a_changed_source_file_is_refused(store: Path, config_path: Path) -> None:
    config = ["--config", str(config_path)]
    work = Path(run("ingest", "egodex", *config).split("work: ")[1].split()[0])
    run("pose", str(work))
    hdf5 = sorted((store / "egodex" / "part1").glob("*/0.hdf5"))[0]
    hdf5.write_bytes(hdf5.read_bytes() + b"\0")
    result = runner.invoke(app, ["annotate", str(work), *config])
    assert result.exit_code == 2 and "changed" in result.output


def test_recordings_stop_at_the_gate_with_exit_2(
    tmp_path: Path, store: Path, config_path: Path
) -> None:
    config = ["--config", str(config_path)]
    root = make_videos(tmp_path / "rec")
    output = run("ingest", "video", "--root", str(root), *config)
    assert "not waived: blocked before E-A and annotate" in output
    work = Path(output.split("work: ")[1].split()[0])
    result = runner.invoke(app, ["annotate", str(work), *config])
    assert result.exit_code == 2 and "ego_video" in result.output
    assert len(ledger(store)) == 4  # the refused job still wrote its measured row


def test_a_wrong_source_name_is_refused(store: Path, config_path: Path) -> None:
    result = runner.invoke(app, ["ingest", "kinect", "--config", str(config_path)])
    assert result.exit_code == 2 and "egodex or video" in result.output
