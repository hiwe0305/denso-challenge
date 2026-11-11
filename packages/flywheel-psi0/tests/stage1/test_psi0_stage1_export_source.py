"""A DA-18 export as a stage 1 dataset (DA-30 task 2): pin, pack, fetch, refuse; on CPU.

The fixture export has the layout and `meta.json` of `export_stage1` with dummy
sample bytes: nothing here opens the HDF5 or the mp4, only names and hashes.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.base import canonical_json, content_id
from flywheel_psi0.stage1 import colab, export_source
from flywheel_psi0.stage1.export_source import ExportRefused, fetch, pack, verify_export
from flywheel_psi0.stage1.runplan import ExportDataset, Stage1Plan
from flywheel_psi0.tray.runplan import run_plan_id
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[4]
EGODEX_SHORT = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"
RECIPE = {"chunk_size": 1, "upsample_rate": 3}


def make_export(root: Path, samples: int = 3, data_class: str = "public") -> str:
    """Write a fixture export under `root`; returns its export_id."""
    files: dict[str, str] = {}
    for i in range(samples):
        for ext in ("hdf5", "mp4"):
            name = f"part1/carry_red_box/{i}.{ext}"
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(f"{ext} {i}".encode())
            files[name] = hashlib.sha256(f"{ext} {i}".encode()).hexdigest()
    stats = json.dumps({"egodex": {"q01": [-1.0, 0.0, -3.0], "q99": [1.0, 0.0, 3.0]}}).encode()
    (root / "egodex_stat.json").write_bytes(stats)
    files["egodex_stat.json"] = hashlib.sha256(stats).hexdigest()
    fmt = export_source.FORMAT
    export_id = content_id("egx", {"format": fmt, "recipe": RECIPE, "files": files})
    meta = {
        "export_id": export_id,
        "format": fmt,
        "recipe": RECIPE,
        "source": {"data_class": data_class, "deid_waiver": None},
        "counts": {"samples": samples, "frames": 90 * samples, "by_part": {"part1": samples}},
        "files": files,
    }
    (root / "meta.json").write_text(canonical_json(meta) + "\n")
    return export_id


@pytest.fixture
def export(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "export"
    return root, make_export(root)


def test_a_fixture_export_verifies(export: tuple[Path, str]) -> None:
    root, export_id = export
    assert verify_export(root, export_id, "part1", "public") == []


def test_pack_is_reproducible(export: tuple[Path, str], tmp_path: Path) -> None:
    root, export_id = export
    first = pack(root, tmp_path / "a.tar")
    os.utime(root / "part1" / "carry_red_box" / "0.mp4", (1, 1))  # mtime is not in the tar
    second = pack(root, tmp_path / "b.tar")
    assert first == second
    assert first["export_id"] == export_id and first["samples"] == 3


@pytest.mark.parametrize(
    ("tamper", "problem"),
    [
        (lambda r: (r / "part1/carry_red_box/1.mp4").write_bytes(b"other"), "sha256 differs"),
        (lambda r: (r / "part1/carry_red_box/9.hdf5").write_bytes(b"x"), "not in meta.json"),
        (lambda r: (r / "part1/carry_red_box/2.hdf5").unlink(), "missing"),
    ],
)
def test_a_changed_export_is_refused(export: tuple[Path, str], tamper: Any, problem: str) -> None:
    root, export_id = export
    tamper(root)
    assert any(problem in p for p in verify_export(root, export_id, "part1"))


def test_another_export_id_or_data_class_is_refused(export: tuple[Path, str]) -> None:
    root, export_id = export
    assert any("the plan pins" in p for p in verify_export(root, "egx_" + "0" * 16, "part1"))
    assert any("data_class" in p for p in verify_export(root, export_id, "part1", "internal"))


def test_meta_edited_to_match_a_changed_file_is_refused(export: tuple[Path, str]) -> None:
    root, export_id = export
    (root / "part1/carry_red_box/1.mp4").write_bytes(b"other")
    meta = json.loads((root / "meta.json").read_text())
    meta["files"]["part1/carry_red_box/1.mp4"] = hashlib.sha256(b"other").hexdigest()
    (root / "meta.json").write_text(canonical_json(meta))
    assert any("hash to" in p for p in verify_export(root, export_id, "part1"))


def test_fetch_unpacks_a_pinned_tarball(export: tuple[Path, str], tmp_path: Path) -> None:
    root, export_id = export
    pin = pack(root, tmp_path / "drive" / f"{export_id}.tar")
    target = tmp_path / "vm" / "data" / "egodex"
    got = fetch(tmp_path / "drive" / f"{export_id}.tar", pin["sha256"], target, export_id, "part1")
    assert got["samples"] == 3 and got["tarball_sha256"] == pin["sha256"]
    assert (target / "part1" / "carry_red_box" / "2.mp4").read_bytes() == b"mp4 2"
    assert not (target.parent / f"{export_id}.tar").exists()  # the local copy is removed


def test_fetch_refuses_another_tarball(export: tuple[Path, str], tmp_path: Path) -> None:
    root, export_id = export
    tarball = tmp_path / "drive" / "e.tar"
    pack(root, tarball)
    target = tmp_path / "vm" / "egodex"
    with pytest.raises(ExportRefused, match="the plan pins"):
        fetch(tarball, "0" * 64, target, export_id, "part1")
    assert not target.exists()


def test_fetch_refuses_a_path_outside_the_root(tmp_path: Path) -> None:
    tarball = tmp_path / "evil.tar"
    with tarfile.open(tarball, "w") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    digest = export_source.sha256(tarball)
    with pytest.raises(ExportRefused, match="plain relative path"):
        fetch(tarball, digest, tmp_path / "vm" / "egodex", "egx_" + "0" * 16, "part1")
    assert not (tmp_path / "vm" / "escape.txt").exists()


def test_fetch_never_unpacks_over_another_export(export: tuple[Path, str], tmp_path: Path) -> None:
    root, export_id = export
    with pytest.raises(ExportRefused, match="not empty"):
        fetch(tmp_path / "missing.tar", "0" * 64, root, export_id, "part1")


def export_block(
    export_id: str, digest: str, masked: bool = True, size: int = 1000
) -> dict[str, Any]:
    return {
        "kind": "export",
        "id": f"team-ego-{export_id}",
        "source": {
            "name": "team-ego",
            "export_id": export_id,
            "tarball": f"denso/da30/exports/{export_id}.tar",
            "sha256": digest,
            "bytes": size,
            "samples": 3,
        },
        "split_dir": "part1",
        "data_class": "public",
        "identity_masked": masked,
    }


def test_an_export_must_be_identity_masked() -> None:
    block = export_block("egx_" + "1" * 16, "2" * 64, masked=False)
    with pytest.raises(ValidationError, match="identity masking"):
        ExportDataset.model_validate(block)
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["dataset"] = {**block, "source": {**block["source"], "name": "egodex"}}
    with pytest.raises(ValidationError):  # the EgoDex waiver does not reach exports
        Stage1Plan.model_validate(raw)


def test_the_egodex_sample_plan_keeps_its_id() -> None:
    # docs/he/stage1.md 1.6 names this id for run 2; the export kind must not move it.
    assert run_plan_id(Stage1Plan.load(EGODEX_SHORT)) == "rp_6c8cf029703b"


def test_setup_gets_the_export_from_drive(
    export: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, export_id = export
    drive = tmp_path / "MyDrive"
    pin = pack(root, drive / "denso" / "da30" / "exports" / f"{export_id}.tar")
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["dataset"] = export_block(export_id, pin["sha256"], size=pin["bytes"])
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    work = tmp_path / "da30"
    (work / "Psi0" / "assets" / "stats").mkdir(parents=True)
    shipped = {"egodex": {"q01": [-2.0, 0.0, -1.0], "q99": [2.0, 0.0, 1.0]}}
    (work / "Psi0" / "assets" / "stats" / "egodex_stat_all.json").write_text(json.dumps(shipped))
    (work / "fw").symlink_to(REPO)
    commands: list[str] = []
    monkeypatch.setattr(colab, "setup_psi0_env", lambda work: None)
    monkeypatch.setattr(colab, "match_cuda_toolchain", lambda venv_bin, sh: {"env": {}})
    monkeypatch.setattr(colab, "check_parent", lambda psi0, plan: None)
    monkeypatch.setattr(colab, "sh", lambda command, cwd=None, env=None: commands.append(command))
    colab.setup(work, plan_path, drive)
    report = json.loads((work / "report.json").read_text())["phases"]["setup_stage1"]
    assert report["export_id"] == export_id and report["episodes"] == 3
    assert report["layout_problems"] == []
    assert report["stats_coverage"]["dims_outside_shipped_q01_q99"] == [2]
    assert (work / "plan.path").read_text() == str(plan_path.resolve())  # for persist_cell
    assert not any("precompute" in c for c in commands)  # the export has actions_48d
    assert (work / "data" / "egodex" / "part1" / "carry_red_box" / "0.hdf5").exists()


def test_setup_stops_on_a_parent_that_is_not_the_pin(tmp_path: Path) -> None:
    plan = Stage1Plan.load(EGODEX_SHORT)
    weights = tmp_path / "cache" / "checkpoints" / plan.parent.vlm.path
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"not the parent")
    with pytest.raises(SystemExit, match="the plan pins"):
        colab.check_parent(tmp_path, plan)


def test_stats_coverage_names_the_dims_the_clip_would_cut() -> None:
    shipped = {"egodex": {"q01": [-1.0, 0.0, -1.0, -2.0], "q99": [1.0, 0.0, 1.0, 2.0]}}
    export = {"egodex": {"q01": [-0.5, 0.0, -1.5, -1.0], "q99": [0.5, 0.0, 0.5, 1.0]}}
    coverage = export_source.stats_coverage(export, shipped)
    assert coverage["dims"] == 3  # the zero-range pad dim is left out
    assert coverage["dims_outside_shipped_q01_q99"] == [2]
    assert coverage["span_ratio_median"] == 0.5 and coverage["span_ratio_max"] == 1.0
    assert coverage["span_ratio_max_dim"] == 2


def test_fetch_refuses_another_sample_count_before_moving_anything(
    export: tuple[Path, str], tmp_path: Path
) -> None:
    root, export_id = export
    pin = pack(root, tmp_path / "drive" / f"{export_id}.tar")
    target = tmp_path / "vm" / "data" / "egodex"
    with pytest.raises(ExportRefused, match="counts 3 samples, the plan pins 4"):
        fetch(
            tmp_path / "drive" / f"{export_id}.tar",
            pin["sha256"],
            target,
            export_id,
            "part1",
            samples=4,
        )
    assert list(target.parent.iterdir()) == []  # no export, no staging dir, no local tar
    got = fetch(
        tmp_path / "drive" / f"{export_id}.tar",
        pin["sha256"],
        target,
        export_id,
        "part1",
        samples=3,
    )
    assert got["samples"] == 3  # and the next setup is not refused as "not empty"


def test_setup_refuses_a_plan_that_pins_another_sample_count(
    export: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, export_id = export
    drive = tmp_path / "MyDrive"
    pin = pack(root, drive / "denso" / "da30" / "exports" / f"{export_id}.tar")
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["dataset"] = export_block(export_id, pin["sha256"], size=pin["bytes"])
    raw["dataset"]["source"]["samples"] = 4
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    work = tmp_path / "da30"
    work.mkdir()
    (work / "fw").symlink_to(REPO)
    monkeypatch.setattr(colab, "setup_psi0_env", lambda work: None)
    monkeypatch.setattr(colab, "match_cuda_toolchain", lambda venv_bin, sh: {"env": {}})
    monkeypatch.setattr(colab, "check_parent", lambda psi0, plan: None)
    monkeypatch.setattr(colab, "sh", lambda command, cwd=None, env=None: None)
    with pytest.raises(ExportRefused, match="the plan pins 4"):
        colab.setup(work, plan_path, drive)
    assert not (work / "data" / "egodex").exists()
    assert not (work / "data" / "egodex.unverified").exists()


def test_a_refused_export_is_not_left_where_the_loader_reads(
    export: tuple[Path, str], tmp_path: Path
) -> None:
    root, export_id = export
    (root / "part1" / "carry_red_box" / "1.mp4").write_bytes(b"tampered")
    tarball = tmp_path / "t.tar"
    with tarfile.open(tarball, "w") as tar:  # a tar of the tampered export (pack refuses)
        tar.add(root, arcname=".")
    target = tmp_path / "vm" / "data" / "egodex"
    with pytest.raises(ExportRefused, match="sha256 differs"):
        fetch(tarball, export_source.sha256(tarball), target, export_id, "part1")
    assert not target.exists() and not (target.parent / "egodex.unverified").exists()
    assert list(target.parent.iterdir()) == []  # the local tar copy is gone too


def _setup_refuses(plan_path: Path, drive: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    ran: list[str] = []
    monkeypatch.setattr(colab, "setup_psi0_env", lambda work: ran.append("env"))
    monkeypatch.setattr(colab, "sh", lambda command, cwd=None, env=None: ran.append(command))
    with pytest.raises(SystemExit) as refused:
        colab.setup(drive.parent / "da30", plan_path, drive)
    assert ran == []  # nothing installed, nothing downloaded
    return str(refused.value)


@pytest.mark.parametrize("data_class", ["internal", "restricted"])
def test_setup_sends_only_public_data_to_colab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data_class: str
) -> None:
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["dataset"] = export_block("egx_" + "1" * 16, "2" * 64) | {"data_class": data_class}
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    assert "only public data goes to Colab" in _setup_refuses(
        plan_path, tmp_path / "MyDrive", monkeypatch
    )


def test_setup_checks_the_tarball_on_drive_before_any_install(
    export: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, export_id = export
    drive = tmp_path / "MyDrive"
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["dataset"] = export_block(export_id, "2" * 64)
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    assert "mount Drive before setup" in _setup_refuses(plan_path, drive, monkeypatch)
    pack(root, drive / raw["dataset"]["source"]["tarball"])  # there, but not 1000 bytes
    assert "the plan pins 1000" in _setup_refuses(plan_path, drive, monkeypatch)
