"""`Stage1Trainer` and the stage 1 launcher end to end on CPU against a fake Psi0.

The fake `psi.trainers.pretrain.PretrainTrainer` has the pin's `create_dataloaders`
shape - `shuffle` assigned only in the mixture branch, read in the other - so the
test fails the way the real run would if the launcher did not restore it. Its
`log` adds `train/grad_norm_vlm` in place, as Psi0's does.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest
from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
from flywheel.contracts.training import TrainingMetric
from flywheel_psi0.stage1.launch import main as launch_main
from flywheel_psi0.stage1.patches import SHUFFLE_READ, restore_shuffle
from flywheel_psi0.stage1.runplan import Stage1Plan
from flywheel_psi0.stage1.trainer import Stage1Trainer, egodex_layout

REPO = Path(__file__).resolve().parents[4]
PLAN = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"

FAKE_PRETRAIN = """
from __future__ import annotations

import os


class PretrainTrainer:
    def __init__(self, output_dir, mixed):
        self.project_dir = os.path.join(output_dir, "pretrain", "run.job")
        self.global_step = 0
        self.mixed = mixed

    def create_dataloaders(self, train_dataset, val_dataset) -> tuple[dict, None]:
        if self.mixed:
            g = shuffle = batch_size = drop_last = None
        else:
            batch_size = 16
            drop_last = True
        train_dataloader_kwargs = {"drop_last": drop_last}
        if not self.mixed:
            train_dataloader_kwargs["shuffle"] = shuffle
        return train_dataloader_kwargs, None

    def log(self, metrics, start_time=None):
        metrics.update({"train/grad_norm_vlm": 0.7})

    def save_checkpoint(self, global_step):
        path = os.path.join(self.project_dir, "checkpoints", f"ckpt_{global_step}")
        os.makedirs(path, exist_ok=True)
        return path
"""

FAKE_TRAIN_PY = """
import json
import sys
from psi.trainers.pretrain import PretrainTrainer

args = dict(a[2:].split("=", 1) for a in sys.argv[2:] if a.startswith("--") and "=" in a)
assert sys.argv[1] == "pretrain_egodex_qwen3vl_config"
trainer = PretrainTrainer(args["train.output_dir"], mixed=False)
loader, _ = trainer.create_dataloaders(None, None)
assert loader["shuffle"] is True
steps = int(args["train.max_training_steps"])
for step in range(steps):
    trainer.global_step = step
    trainer.log({"train/loss": 3.0 - 0.01 * step, "train/action_accuracy": 0.2,
                 "train/lr": 1e-4, "train/epoch": 0})
    if (step + 1) % int(args["train.checkpointing_steps"]) == 0 or step + 1 == steps:
        trainer.save_checkpoint(step + 1)
"""


@pytest.fixture
def fake_psi0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "Psi0"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "train.py").write_text(FAKE_TRAIN_PY)
    trainers = root / "src" / "psi" / "trainers"
    trainers.mkdir(parents=True)
    (root / "src" / "psi" / "__init__.py").write_text("")
    (trainers / "__init__.py").write_text("")
    (trainers / "pretrain.py").write_text(FAKE_PRETRAIN)
    (root / ".env").write_text("")
    monkeypatch.syspath_prepend(str(root / "src"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RANK", raising=False)
    yield root
    for name in [m for m in sys.modules if m == "psi" or m.startswith("psi.")]:
        del sys.modules[name]


def in_process(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
    """What `torchrun -m flywheel_psi0.stage1.launch <spec>` would do, on one rank."""
    assert command[-3:-1] == ["-m", "flywheel_psi0.stage1.launch"]
    assert env["WANDB_MODE"] == "offline"
    try:
        launch_main([command[-1]])
    except Exception:
        return 1
    return 0


def trainer(fake_root: Path, tmp_path: Path) -> Stage1Trainer:
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
        runner=in_process,
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
    fake_psi0: Path, tmp_path: Path
) -> None:
    job = spec(tmp_path)
    result = trainer(fake_psi0, tmp_path).train(job)

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


def test_a_global_batch_counts_accumulation(fake_psi0: Path, tmp_path: Path) -> None:
    assert trainer(fake_psi0, tmp_path).global_batch_size() == 32


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed = FAKE_PRETRAIN.replace(
        "drop_last = True", "drop_last = True\n            shuffle = True"
    )
    cls = module_with(tmp_path, monkeypatch, fixed)
    original = cls.create_dataloaders  # type: ignore[attr-defined]
    assert restore_shuffle(cls) is False
    assert cls.create_dataloaders is original  # type: ignore[attr-defined]


def test_restore_shuffle_refuses_an_unknown_variant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    twice = FAKE_PRETRAIN.replace(
        "        return train_dataloader_kwargs, None",
        "            " + SHUFFLE_READ + "\n        return train_dataloader_kwargs, None",
    )
    cls = module_with(tmp_path, monkeypatch, twice)
    with pytest.raises(RuntimeError, match="review the shuffle patch"):
        restore_shuffle(cls)


def test_restore_shuffle_keeps_line_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cls = module_with(tmp_path, monkeypatch, FAKE_PRETRAIN)
    line = cls.create_dataloaders.__code__.co_firstlineno  # type: ignore[attr-defined]
    assert restore_shuffle(cls) is True
    patched = cls.create_dataloaders  # type: ignore[attr-defined]
    assert patched.__code__.co_firstlineno == line
    assert patched(cls("/tmp", mixed=False), None, None)[0]["shuffle"] is True
