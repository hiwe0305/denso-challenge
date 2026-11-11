"""The stage 1 VLM packaged for stage 3 (DA-30 task 2, Q-28C), and `persist` keeping it.

Safetensors files here are tiny but real: an 8-byte header length, the JSON header,
then the bytes, as `safetensors.torch.save_file` writes them.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest
import yaml
from flywheel_psi0.stage1 import colab
from flywheel_psi0.stage1.runplan import Stage1Plan
from flywheel_psi0.stage1.vlm_checkpoint import (
    header_problems,
    package,
    safetensors_header,
    sha256,
)
from flywheel_psi0.trainer.psi0_trainer import Runner
from flywheel_psi0.tray.runplan import run_plan_id

REPO = Path(__file__).resolve().parents[4]
EGODEX_SHORT = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"
EMBED = "model.language_model.embed_tokens.weight"


def write_safetensors(path: Path, tensors: dict[str, tuple[str, list[int]]], fill: int) -> None:
    header, offset = {"__metadata__": {"format": "pt"}}, 0
    for name, (dtype, shape) in tensors.items():
        size = 2
        for n in shape:
            size *= n
        header[name] = {"dtype": dtype, "shape": shape, "data_offsets": [offset, offset + size]}
        offset += size
    raw = json.dumps(header).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + bytes([fill]) * offset)


TENSORS = {EMBED: ("BF16", [12, 4]), "model.visual.pos_embed.weight": ("BF16", [3, 4])}


def parent_dir(root: Path) -> Path:
    write_safetensors(root / "model.safetensors", TENSORS, fill=1)
    (root / "config.json").write_text('{"text_config": {"vocab_size": 12}}')
    (root / "tokenizer.json").write_text("{}")
    (root / "preprocessor_config.json").write_text("{}")
    return root


def test_the_header_is_read_without_the_weights(tmp_path: Path) -> None:
    write_safetensors(tmp_path / "m.safetensors", TENSORS, fill=0)
    assert safetensors_header(tmp_path / "m.safetensors") == {
        EMBED: ("BF16", (12, 4)),
        "model.visual.pos_embed.weight": ("BF16", (3, 4)),
    }


def test_a_resized_or_renamed_tensor_is_named() -> None:
    parent = {EMBED: ("BF16", (12, 4)), "a": ("BF16", (1,))}
    trained = {EMBED: ("BF16", (16, 4)), "lm_head.weight": ("BF16", (12, 4))}
    problems = header_problems(trained, parent)
    assert any("missing" in p and "'a'" in p for p in problems)
    assert any("not in the parent" in p for p in problems)
    assert any(EMBED in p and "(16, 4)" in p for p in problems)
    assert header_problems(parent, parent) == []


def test_package_takes_the_weights_and_the_parents_other_files(tmp_path: Path) -> None:
    parent = parent_dir(tmp_path / "parent")
    write_safetensors(tmp_path / "ckpt_300" / "model.safetensors", TENSORS, fill=7)
    out = tmp_path / "drive" / "vlm"
    manifest = package(tmp_path / "ckpt_300", parent, out, {"step": 300})
    assert sorted(p.name for p in out.iterdir()) == [
        "config.json",
        "model.safetensors",
        "preprocessor_config.json",
        "tokenizer.json",
    ]  # nothing but the parent's files: DA-34's B refuses any other

    assert (out / "model.safetensors").read_bytes()[-1] == 7  # trained, not the parent's
    assert manifest["weights_sha256"] == sha256(out / "model.safetensors")
    assert manifest["files"]["config.json"] == sha256(parent / "config.json")
    assert manifest["loadable_as_model_name_or_path"] and manifest["step"] == 300
    assert json.loads((tmp_path / "drive" / "vlm.json").read_text()) == manifest
    lines = "".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
        for p in sorted(out.iterdir(), key=lambda p: p.name)
    )  # DA-34's tray.colab_train.manifest_sha256, written out
    assert manifest["manifest_sha256"] == hashlib.sha256(lines.encode()).hexdigest()
    again = package(tmp_path / "ckpt_300", parent, out, {"step": 300})  # a second persist
    assert again["weights_sha256"] == manifest["weights_sha256"]


def test_package_flags_weights_stage_3_would_not_load(tmp_path: Path) -> None:
    parent = parent_dir(tmp_path / "parent")
    write_safetensors(tmp_path / "ckpt" / "model.safetensors", {EMBED: ("F32", [12, 4])}, 0)
    manifest = package(tmp_path / "ckpt", parent, tmp_path / "out", {})
    assert not manifest["loadable_as_model_name_or_path"]
    assert len(manifest["header_problems"]) == 2


def test_a_stray_file_in_the_folder_is_a_problem(tmp_path: Path) -> None:
    parent = parent_dir(tmp_path / "parent")
    (parent / ".cache").mkdir()
    (parent / ".cache" / "lock").write_text("")  # dot entries are not the VLM's
    write_safetensors(tmp_path / "ckpt" / "model.safetensors", TENSORS, fill=7)
    out = tmp_path / "vlm"
    out.mkdir()
    (out / "optimizer.pt").write_text("state")
    manifest = package(tmp_path / "ckpt", parent, out, {})
    assert manifest["header_problems"] == ["optimizer.pt: in the folder but not in the parent's"]
    assert not (out / ".cache").exists()


def test_package_needs_the_weights(tmp_path: Path) -> None:
    (tmp_path / "ckpt").mkdir()
    with pytest.raises(FileNotFoundError, match="no weights"):
        package(tmp_path / "ckpt", parent_dir(tmp_path / "parent"), tmp_path / "out", {})


@pytest.fixture
def work(fake_psi0: Path, in_process: Runner, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = fake_psi0.parent
    (work / "fw").symlink_to(REPO)
    (work / "data" / "egodex" / "part1").mkdir(parents=True)
    monkeypatch.setattr(colab, "logging_runner", lambda path: in_process)
    return work


def test_persist_keeps_the_vlm_when_the_plan_asks(work: Path, tmp_path: Path) -> None:
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["persist_vlm"] = True
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    plan = Stage1Plan.load(plan_path)
    parent_dir(work / "Psi0" / "cache" / "checkpoints" / plan.parent.vlm.path.rsplit("/", 1)[0])
    colab.train(work, plan_path, repeat=False)
    launched = json.loads((work / "runs" / plan.job.id / "result.json").read_text())
    write_safetensors(Path(launched["checkpoint_dir"]) / "model.safetensors", TENSORS, fill=9)

    drive = tmp_path / "drive"
    colab.persist(work, plan_path, drive)
    vlm = drive / plan.job.id / "vlm"
    manifest = json.loads((drive / plan.job.id / "vlm.json").read_text())
    assert manifest["run_plan_id"] == run_plan_id(plan) and manifest["step"] == 200
    assert manifest["final"] and manifest["loadable_as_model_name_or_path"]
    assert manifest["parent"]["sha256"] == plan.parent.vlm.sha256
    assert (vlm / "config.json").exists() and (drive / plan.job.id / "metrics.jsonl").exists()
    report = json.loads((work / "report.json").read_text())["phases"]["persist"]
    assert report["vlm"]["saved"] and report["vlm"]["header_problems"] == []
    assert report["vlm"]["manifest_sha256"] == manifest["manifest_sha256"]
    assert report["vlm"]["drive_dir"] == str(vlm)  # not under MyDrive in this test


def test_persist_without_a_checkpoint_keeps_the_logs(work: Path, tmp_path: Path) -> None:
    raw = yaml.safe_load(EGODEX_SHORT.read_text())
    raw["persist_vlm"] = True
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(raw))
    (work / "runs" / "da30-egodex-short").mkdir(parents=True)
    (work / "runs" / "da30-egodex-short" / "train.log").write_text("step 1\n")
    colab.persist(work, plan_path, tmp_path / "drive")
    assert (tmp_path / "drive" / "da30-egodex-short" / "train.log").exists()
    report = json.loads((work / "report.json").read_text())["phases"]["persist"]
    assert report["vlm"] == {"saved": False, "reason": "no checkpoint in result.json"}


def test_the_egodex_sample_plan_does_not_keep_weights() -> None:
    assert not Stage1Plan.load(EGODEX_SHORT).persist_vlm


@pytest.mark.parametrize("problems", [[], ["lm_head is not tied to the input embeddings"]])
def test_check_vlm_loads_the_drive_copy_and_stops_on_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problems: list[str]
) -> None:
    seen: list[Path] = []

    def load_check(path: Path) -> dict[str, object]:
        seen.append(path)
        # The keys of the real load_check, `seconds` included (11/11/2026: it clashed
        # with Report.phase's own `seconds` and check-vlm crashed after the check).
        return {
            "seconds": 34.4,
            "vocab": 153792,
            "tokenizer": 151669,
            "parameters": 2131333120,
            "problems": problems,
        }

    monkeypatch.setattr(colab, "load_check", load_check)
    work = tmp_path / "da30"
    work.mkdir()
    if problems:
        with pytest.raises(SystemExit, match="not tied"):
            colab.check_vlm(work, EGODEX_SHORT, tmp_path / "drive")
    else:
        colab.check_vlm(work, EGODEX_SHORT, tmp_path / "drive")
    assert seen == [tmp_path / "drive" / "da30-egodex-short" / "vlm"]
    report = json.loads((work / "report.json").read_text())["phases"]["check_vlm"]
    assert report["problems"] == problems
    assert report["load_seconds"] == 34.4 and report["vocab"] == 153792
