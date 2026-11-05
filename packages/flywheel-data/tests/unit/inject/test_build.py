"""Both benchmark copies, the sealed answers and the job's ledger rows (tasks 9 and 10)."""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from flywheel.contracts.entities import LedgerEntry
from flywheel.data.ingest.lerobot import iter_episodes
from flywheel.data.inject.api import copy_marker
from flywheel.data.inject.build import build_benchmark, main
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.manifest import ManifestLock, load_manifest
from flywheel.store.ledger_append import read_job_ledger
from flywheel.store.paths import StorePaths
from lerobot_data import make_dataset, tree_hashes


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    base = tmp_path_factory.mktemp("bench")
    src = base / "psi"
    make_dataset(src, count=40, length=8)
    before = tree_hashes(src)
    result = build_benchmark(src, base / "inject", store=base / "store")
    assert tree_hashes(src) == before
    return src, base / "inject", result


def test_two_copies_with_neutral_ids_and_markers(built) -> None:  # type: ignore[no-untyped-def]
    _, out, result = built
    defect_id, clean_id = copy_ids(42)
    assert (result.defect.ref.dataset_id, result.clean.ref.dataset_id) == (defect_id, clean_id)
    assert sorted(p.name for p in (out / "copies").iterdir()) == sorted([defect_id, clean_id])
    for copy in (result.defect, result.clean):
        assert copy_marker(Path(copy.ref.uri)) == copy.ref.dataset_id


def test_clean_copy_is_the_source_data_of_the_same_size(built) -> None:  # type: ignore[no-untyped-def]
    src, _, result = built
    source = list(iter_episodes(src))
    clean = list(iter_episodes(Path(result.clean.ref.uri)))
    assert len(clean) == len(source) == len(list(iter_episodes(Path(result.defect.ref.uri))))
    for a, b in zip(source, clean, strict=True):
        assert a.task == b.task
        for name in ("timestamp", "frame_index", "states", "action"):
            assert np.array_equal(getattr(a, name), getattr(b, name))


def test_answers_are_sealed_outside_both_copies(built) -> None:  # type: ignore[no-untyped-def]
    _, out, result = built
    for copy, defects in ((result.defect, 33), (result.clean, 0)):
        path = copy.manifest_path
        assert path.is_relative_to(out / "answers") and path.name == "defect_manifest.json"
        assert ManifestLock(path).verify_integrity()
        manifest = load_manifest(path)
        assert manifest.dataset_id == copy.ref.dataset_id and len(manifest.defects) == defects
    for copy_root in (out / "copies").iterdir():
        assert not list(copy_root.rglob("defect_manifest*"))


def test_job_writes_an_estimate_and_a_measurement_to_the_store(built) -> None:  # type: ignore[no-untyped-def]
    # Both rows go through flywheel.data.ledger.job_ledger into the store's run ledger.
    _, out, result = built
    job = result.ledger
    store = out.parent / "store"
    rows = [
        LedgerEntry.model_validate(row)
        for row in read_job_ledger(job.run_plan_id, job.job_id, StorePaths(store))
    ]
    assert rows == [job.estimate, job.measured]
    estimate, measured = rows
    assert (estimate.measure_kind, measured.measure_kind) == ("estimated", "measured")
    assert measured.estimate_entry_id == estimate.id
    assert re.fullmatch(r"g0-DA-27-\d{8}", job.run_plan_id) and job.job_id.startswith("job_inject_")
    assert estimate.activity == "data_generation" and measured.quantity >= 0
    assert not (out / "ledger.jsonl").exists()


def test_cli_prints_the_handoff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "psi"
    make_dataset(src, count=40, length=6)
    store = tmp_path / "store"
    args = ["--source", str(src), "--out", str(tmp_path / "inject"), "--store", str(store)]
    assert main(args) == 0
    handoff = json.loads(capsys.readouterr().out)
    assert {c["dataset_id"] for c in handoff["copies"]} == set(copy_ids(42))
    assert all(len(c["manifest_sha256"]) == 64 for c in handoff["copies"])
    assert read_job_ledger(
        handoff["ledger"]["run_plan_id"], handoff["ledger"]["job_id"], StorePaths(store)
    )
