"""The Colab smoke job's interrupt and resume bookkeeping, on CPU (DA-19 task 5)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import ActionLayout
from flywheel_psi0.trainer.colab import (
    JOB_ID,
    completed_checkpoints,
    continuity,
    g1_layout_json,
    interrupting_runner,
    lock_constraints,
    persist,
    repair_lock,
    restore,
)

WRITER = """
import json, sys, time
path = sys.argv[1]
for step in range(1000):
    record = {"split": "train", "attempt": 0, "step": step, "loss": 1.0}
    with open(path, "a") as stream:
        stream.write(json.dumps(record) + "\\n")
    time.sleep(0.02)
"""


def line(attempt: int, step: int, loss: float, split: str = "train") -> str:
    return json.dumps({"split": split, "attempt": attempt, "step": step, "loss": loss})


def test_runner_kills_the_job_once_the_step_is_logged(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    script = tmp_path / "writer.py"
    script.write_text(WRITER)
    run = interrupting_runner(metrics, attempt=0, kill_at=10, poll_seconds=0.05)

    start = time.monotonic()
    returncode = run([sys.executable, str(script), str(metrics)], tmp_path, {})

    steps = [json.loads(x)["step"] for x in metrics.read_text().splitlines()]
    assert returncode != 0  # killed, not finished
    assert 10 <= max(steps) < 999 and time.monotonic() - start < 30


def test_continuity_reads_where_the_second_attempt_resumed(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    rows = [line(0, s, 1.0 / (s + 1)) for s in range(31)] + [line(0, 20, 0.9, "val")]
    rows += [line(1, s, 1.0 / (s + 1)) for s in range(20, 60)]
    metrics.write_text("\n".join(rows) + "\n")

    report = continuity(metrics, checkpoint_step=20)
    assert report["attempt0_steps"] == [0, 30] and report["attempt1_steps"] == [20, 59]
    assert report["resumed_at_checkpoint"] is True
    assert report["loss_after_cut"][0] == 1.0 / 21


def test_resume_from_the_wrong_step_is_reported(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    metrics.write_text("\n".join([line(0, 0, 1.0), line(0, 25, 0.5), line(1, 0, 1.0)]) + "\n")

    assert continuity(metrics, checkpoint_step=20)["resumed_at_checkpoint"] is False


def test_provisional_g1_layout_is_a_valid_36_dim_layout() -> None:
    layout = ActionLayout.model_validate({"dimensions": g1_layout_json()})
    assert len(layout.dimensions) == 36
    assert [d.group for d in layout.dimensions[:14]] == ["hand"] * 14


TUNA = "https://pypi.tuna.tsinghua.edu.cn"
FILES = "https://files.pythonhosted.org/packages/18/c7"
BROKEN_LOCK = f"""version = 1
requires-python = "==3.11.*"

[[package]]
name = "jsonpointer"
version = "3.1.1"
source = {{ registry = "{TUNA}/simple" }}
sdist = {{ url = "{TUNA}/packages/18/c7/jsonpointer-3.1.1.tar.gz", hash = "sha256:aa" }}

[[package]]
name = "jsonpointer"
version = "3.1.1"
source = {{ registry = "https://pypi.org/simple" }}
sdist = {{ url = "{FILES}/jsonpointer-3.1.1.tar.gz", hash = "sha256:aa", size = 9068 }}

[[package]]
name = "jsonschema"
version = "4.25.1"
source = {{ registry = "{TUNA}/simple" }}

[package.optional-dependencies]
format-nongpl = [
    {{ name = "jsonpointer" }},
]

[package.optional-dependencies]
format-nongpl = [
    {{ name = "jsonpointer" }},
]

[[package]]
name = "black"
version = "26.3.1"
source = {{ registry = "{TUNA}/simple" }}

[[package]]
name = "black"
version = "26.5.1"
source = {{ registry = "https://pypi.org/simple" }}

[[package]]
name = "lerobot"
version = "0.3.3"
source = {{ git = "https://github.com/songlin/lerobot.git?rev=09929d8" }}
"""


def test_repair_lock_folds_the_mirror_and_drops_the_merge_duplicates() -> None:
    tomllib = pytest.importorskip("tomllib")  # 3.11+, like the VM; CI also runs 3.10

    fixed = repair_lock(BROKEN_LOCK)
    packages = tomllib.loads(fixed)["package"]  # the original does not even parse

    assert "tuna" not in fixed and "sha256:aa" in fixed
    assert [(p["name"], p["version"]) for p in packages] == [
        ("jsonpointer", "3.1.1"),
        ("jsonschema", "4.25.1"),
        ("black", "26.5.1"),  # the newer of the two sides
        ("lerobot", "0.3.3"),
    ]
    assert packages[1]["optional-dependencies"]["format-nongpl"] == [{"name": "jsonpointer"}]


def test_lock_constraints_pin_registry_packages_only() -> None:
    constraints = lock_constraints(repair_lock(BROKEN_LOCK)).splitlines()
    assert constraints == ["jsonpointer==3.1.1", "jsonschema==4.25.1", "black==26.5.1"]


COLAB_SMOKE = Path(__file__).parent / "fixtures" / "metrics_colab_smoke.jsonl"


def test_the_first_real_colab_log_is_valid_and_resumes_bit_for_bit() -> None:
    """The A100 run of 3/11/2026: killed after step 31, resumed from ckpt_20."""
    from flywheel.contracts.training import TrainingMetric

    records = [TrainingMetric.model_validate_json(x) for x in COLAB_SMOKE.read_text().splitlines()]
    train = {(r.attempt, r.step): r for r in records if r.split == "train"}
    report = continuity(COLAB_SMOKE, checkpoint_step=20)

    assert report["attempt0_steps"] == [0, 31] and report["attempt1_steps"] == [20, 59]
    assert report["resumed_at_checkpoint"]
    for step in range(20, 32):  # the overlap: same batches, same RNG state, same loss
        assert train[(0, step)].loss == train[(1, step)].loss
        assert train[(0, step)].lr == train[(1, step)].lr
    assert {r.grad_norm_vlm for r in train.values()} == {0.0}  # frozen VLM, measured
    assert all(len(r.loss_by_chunk_pos) == 30 - 8 for r in train.values())


def fake_job(work: Path, saved_step: int, steps: tuple[int, ...]) -> Path:
    """A job directory as Psi0Trainer leaves it, with `ckpt_<step>` for each of `steps`."""
    job = work / "runs" / JOB_ID
    run = job / "psi0" / "finetune" / "fw-run.da19" / "checkpoints"
    for step in steps:
        (run / f"ckpt_{step}").mkdir(parents=True)
        (run / f"ckpt_{step}" / "model.safetensors").write_bytes(b"w" * step)
    (job / "metrics.jsonl").write_text(line(0, saved_step, 1.0) + "\n")
    (job / "result.json").write_text(json.dumps({"checkpoint_step": saved_step}))
    return job


def test_only_fully_saved_checkpoints_count_as_complete(tmp_path: Path) -> None:
    job = fake_job(tmp_path, saved_step=40, steps=(20, 40, 60))  # ckpt_60 still writing

    assert [p.name for p in completed_checkpoints(job)] == ["ckpt_20", "ckpt_40"]


def test_persist_then_restore_brings_the_job_back_on_a_fresh_vm(tmp_path: Path) -> None:
    fake_job(tmp_path / "vm1", saved_step=40, steps=(20, 40, 60))
    drive = tmp_path / "drive"

    persist(tmp_path / "vm1", drive)
    restore(tmp_path / "vm2", drive)

    restored = tmp_path / "vm2" / "runs" / JOB_ID
    names = sorted(p.name for p in restored.glob("psi0/*/*/checkpoints/ckpt_*"))
    assert names == ["ckpt_20", "ckpt_40"]  # the half-written ckpt_60 never left vm1
    assert (restored / "metrics.jsonl").read_text() == line(0, 40, 1.0) + "\n"
    report = json.loads((tmp_path / "vm2" / "report.json").read_text())
    assert report["phases"]["restore"]["source"] == str(drive / JOB_ID)
