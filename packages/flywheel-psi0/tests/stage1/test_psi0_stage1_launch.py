"""`Stage1Trainer` and the stage 1 launcher end to end on CPU against a fake Psi0.

The fake repo (`fake_psi0`, `in_process`) is in this directory's conftest.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
from flywheel.contracts.training import TrainingMetric
from flywheel_psi0.stage1.patches import SHUFFLE_READ, restore_shuffle
from flywheel_psi0.stage1.runplan import Stage1Plan
from flywheel_psi0.stage1.trainer import Stage1Trainer, egodex_layout
from flywheel_psi0.trainer.psi0_trainer import Runner

REPO = Path(__file__).resolve().parents[4]
PLAN = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"


def trainer(fake_root: Path, tmp_path: Path, runner: Runner) -> Stage1Trainer:
    plan = Stage1Plan.load(PLAN)
    return Stage1Trainer(
        plan.load_recipe(REPO).with_overrides(
            {"train.max_training_steps": 5, "train.checkpointing_steps": 5}
        ),
        psi0_root=fake_root,
        runs_root=tmp_path / "runs",
        layout=egodex_layout(),
        run_plan_id="rp_stage1",
        release_id=plan.dataset.id,
        psi0_commit=plan.code.psi0.commit,
        python_bin=Path("/psi/venv/bin"),
        runner=runner,
    )


def spec(tmp_path: Path) -> TrainSpec:
    root = tmp_path / "data" / "egodex"
    (root / "part1").mkdir(parents=True)
    return TrainSpec(
        job_id="da30-egodex-short",
        dataset=DatasetRef(dataset_id="egodex-test-first2", uri=str(root)),
        parent=CheckpointRef(checkpoint_id="psi0-pre-egodex-390k"),
        seed=7,
    )


def test_run_writes_metrics_and_checkpoint_with_shuffle_restored(
    fake_psi0: Path, tmp_path: Path, in_process: Runner
) -> None:
    job = spec(tmp_path)
    result = trainer(fake_psi0, tmp_path, in_process).train(job)

    assert result.infra_status == "ok"
    assert result.checkpoint is not None
    assert result.checkpoint.checkpoint_id == "psi0-s1-da30-egodex-short-s7"
    job_dir = tmp_path / "runs" / "da30-egodex-short"
    records = [
        TrainingMetric.model_validate_json(line)
        for line in (job_dir / "metrics.jsonl").read_text().splitlines()
    ]
    assert [r.step for r in records] == [0, 1, 2, 3, 4]
    assert records[0].loss == pytest.approx(3.0) and records[-1].loss == pytest.approx(2.96)
    assert {r.split for r in records} == {"train"}
    assert all(
        r.grad_norm_vlm == pytest.approx(0.7) and r.lr == pytest.approx(1e-4) for r in records
    )
    assert not records[0].vlm_frozen
    launched = json.loads((job_dir / "result.json").read_text())
    assert launched["checkpoint_step"] == 5 and launched["status"] == "ok"
    argv = json.loads((job_dir / "launch.json").read_text())["argv"]
    assert f"--data.root-dir={Path(job.dataset.uri).resolve()}" in argv


def test_a_global_batch_counts_accumulation(
    fake_psi0: Path, tmp_path: Path, in_process: Runner
) -> None:
    assert trainer(fake_psi0, tmp_path, in_process).global_batch_size() == 32


def test_egodex_layout_is_48_dims_with_masked_padding() -> None:
    layout = egodex_layout()
    assert len(layout.dimensions) == 48
    padded = [i for i, d in enumerate(layout.dimensions) if d.masked]
    assert padded == [6, 7, 8, 30, 31, 32]  # zeros_like(delta_rpy) in convert_to_delta_actions


def module_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> type:
    (tmp_path / "patched_mod.py").write_text(body)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("patched_mod", None)
    import patched_mod

    return patched_mod.PretrainTrainer  # type: ignore[no-any-return]


def test_restore_shuffle_leaves_a_fixed_version_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pretrain_source: str
) -> None:
    fixed = pretrain_source.replace(
        "drop_last = True", "drop_last = True\n            shuffle = True"
    )
    cls = module_with(tmp_path, monkeypatch, fixed)
    original = cls.create_dataloaders  # type: ignore[attr-defined]
    assert restore_shuffle(cls) is False
    assert cls.create_dataloaders is original  # type: ignore[attr-defined]


def test_restore_shuffle_refuses_an_unknown_variant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pretrain_source: str
) -> None:
    twice = pretrain_source.replace(
        "        return train_dataloader_kwargs, None",
        "            " + SHUFFLE_READ + "\n        return train_dataloader_kwargs, None",
    )
    cls = module_with(tmp_path, monkeypatch, twice)
    with pytest.raises(RuntimeError, match="review the shuffle patch"):
        restore_shuffle(cls)


def test_restore_shuffle_keeps_line_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pretrain_source: str
) -> None:
    cls = module_with(tmp_path, monkeypatch, pretrain_source)
    line = cls.create_dataloaders.__code__.co_firstlineno  # type: ignore[attr-defined]
    assert restore_shuffle(cls) is True
    patched = cls.create_dataloaders  # type: ignore[attr-defined]
    assert patched.__code__.co_firstlineno == line
    assert patched(cls("/tmp", mixed=False), None, None)[0]["shuffle"] is True
