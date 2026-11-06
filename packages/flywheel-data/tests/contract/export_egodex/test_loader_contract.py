"""DA-18 AC 2: Psi0's stage 1 loader at `cda3fdf` reads the export back as a saved batch.

`golden_batch.json` is the batch Psi0's own `EgoDexDataset` and `bounds_q99` field
transform drew from the export of `GOLDEN_SPECS` (`psi0_loader_probe.py`, run in the
authors' Psi0 image; see `docs/g0/ledger/DA-18.csv`). In CI the fake loader, a
torch-free copy of the same logic, must draw that batch value by value from a fresh
export. With `PSI0_ROOT` set, Psi0's loader itself must draw it again; `PSI0_PYTHON`
names the interpreter of Psi0's environment (default `$PSI0_ROOT/.venv-psi/bin/python`).
With `EGODEX_PROBE` also set (a directory of EgoDex `<task>/<i>.hdf5|mp4`), the fake
and the real loader must agree on an export of those real episodes.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from egodex_workdir import Spec, build, from_egodex
from fake_loader import get_item, normalize_bounds_q99, scan
from flywheel.data.export.egodex import STATS_FILE, export_stage1
from loader_batch import compare, draw, record

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden_batch.json"
GOLDEN_SPECS = [
    Spec("ep_a", 40, [(0, 20), (20, 40)]),
    Spec("ep_b", 12, [(0, 12)], task="open_close_box"),
    Spec("ep_c", 9, [(2, 9)], split="test"),
    Spec("ep_d", 4, [(0, 2), (2, 4)], task="open_close_box"),  # T = 2: index is always 0
]
PSI0_ROOT = os.environ.get("PSI0_ROOT")


def golden_export(root: Path) -> Path:
    work = build(root / "work", GOLDEN_SPECS, seed=18)
    export_stage1(work, root / "out", store=root / "store")
    return root / "out"


def fake_batch(out: Path) -> dict:  # type: ignore[type-arg]
    files = {str(f["hdf5"].relative_to(out)): f for f in scan(out) + scan(out, val=True)}

    def get(path: str) -> dict:  # type: ignore[type-arg]
        item = get_item(files[path])
        return record(item, normalize_bounds_q99(item["actions"], out / STATS_FILE))

    return draw(list(files), get)


def psi0_batch(out: Path, tmp: Path) -> dict:  # type: ignore[type-arg]
    assert PSI0_ROOT is not None
    python = os.environ.get("PSI0_PYTHON", f"{PSI0_ROOT}/.venv-psi/bin/python")
    target = tmp / "psi0_batch.json"
    run = subprocess.run(
        [python, str(HERE / "psi0_loader_probe.py"), str(out), str(out / STATS_FILE), str(target)],
        cwd=PSI0_ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    assert not list(out.rglob("filelist_cache.pkl"))
    return json.loads(target.read_text())  # type: ignore[no-any-return]


def test_the_saved_batch_covers_every_case() -> None:
    golden = json.loads(GOLDEN.read_text())
    assert sorted(golden) == [
        "part1/open_close_box/0.hdf5",
        "part1/open_close_box/1.hdf5",
        "part1/open_close_box/2.hdf5",
        "part1/pick_place_cup/0.hdf5",
        "part1/pick_place_cup/1.hdf5",
        "test/pick_place_cup/0.hdf5",
    ]
    assert {len(s["actions"]) for s in golden.values()} == {1}
    assert {len(s["actions"][0]) for s in golden.values()} == {48}
    assert any(s["action_indices"][0] == s["action_indices"][1] for s in golden.values())


def test_the_fake_loader_draws_the_saved_batch(tmp_path: Path) -> None:
    golden = json.loads(GOLDEN.read_text())
    assert compare(golden, fake_batch(golden_export(tmp_path))) == []


@pytest.mark.skipif(PSI0_ROOT is None, reason="PSI0_ROOT not set: Psi0's own loader not run")
def test_psi0s_loader_draws_the_saved_batch(tmp_path: Path) -> None:
    golden = json.loads(GOLDEN.read_text())
    assert compare(golden, psi0_batch(golden_export(tmp_path), tmp_path)) == []


@pytest.mark.skipif(
    PSI0_ROOT is None or not os.environ.get("EGODEX_PROBE"),
    reason="PSI0_ROOT and EGODEX_PROBE not both set: no real EgoDex check",
)
def test_psi0s_loader_and_the_fake_agree_on_real_egodex(tmp_path: Path) -> None:
    probe = Path(os.environ["EGODEX_PROBE"])
    work = from_egodex(tmp_path / "work", sorted(probe.glob("*/*.hdf5")))
    export_stage1(work, tmp_path / "out", store=tmp_path / "store")
    real = psi0_batch(tmp_path / "out", tmp_path)
    assert len(real) == 2 * len(list(probe.glob("*/*.hdf5")))
    assert compare(real, fake_batch(tmp_path / "out")) == []
