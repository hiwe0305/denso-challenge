"""`python -m flywheel.data.replay_check replay` runs the adapter as one job (DA-17 task 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from flywheel.data.replay_check.cli import app
from typer.testing import CliRunner

FAKE_ADAPTER = """
import json, sys
from pathlib import Path
work = Path(sys.argv[sys.argv.index("--work") + 1])
work.mkdir(parents=True, exist_ok=True)
(work / "replay_outcomes.jsonl").write_text("")
(work / "replay_run.json").write_text(json.dumps({{"replayed": 2}}))
sys.exit({code})
"""


@pytest.fixture(autouse=True)
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FW_ROOT", str(tmp_path / "store"))
    return tmp_path / "store"


def fake_python(tmp_path: Path, code: int = 0) -> str:
    """A python whose `-m flywheel_simple.replay.outcomes` is a fake that exits `code`."""
    pkg = tmp_path / "fake" / "flywheel_simple" / "replay"
    pkg.mkdir(parents=True)
    (pkg.parent / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "outcomes.py").write_text(FAKE_ADAPTER.format(code=code))
    script = tmp_path / "python"
    script.write_text(f"#!/bin/sh\nPYTHONPATH={tmp_path / 'fake'} exec {sys.executable} \"$@\"\n")
    script.chmod(0o755)
    return str(script)


def dataset(root: Path) -> Path:
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps({"codebase_version": "v2.1"}))
    rows = [{"episode_index": i, "length": 100} for i in range(2)]
    (root / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return root


def ledger_rows(store: Path) -> list[dict[str, object]]:
    paths = list(store.glob("sites/*/runs/g0-DA-17-*/job_replay_*/ledger.jsonl"))
    assert len(paths) == 1
    return [json.loads(line) for line in paths[0].read_text().splitlines()]


def test_replay_writes_an_estimate_and_a_measurement(tmp_path: Path, store: Path) -> None:
    args = ["replay", str(dataset(tmp_path / "d")), "--work", str(tmp_path / "w"),
            "--python", fake_python(tmp_path), "--workers", "2"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    estimate, measured = ledger_rows(store)
    assert estimate["measure_kind"] == "estimated" and estimate["quantity"] == 200 * 0.05 / 2
    assert measured["estimate_entry_id"] == estimate["id"]
    assert '"replayed": 2' in str(measured["note"])


def test_failed_adapter_is_refused_and_still_measured(tmp_path: Path, store: Path) -> None:
    args = ["replay", str(dataset(tmp_path / "d")), "--work", str(tmp_path / "w"),
            "--python", fake_python(tmp_path, code=3)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2 and "exit 3" in result.output
    assert [r["measure_kind"] for r in ledger_rows(store)] == ["estimated", "measured"]
