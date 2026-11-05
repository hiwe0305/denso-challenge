"""A fake Psi0 repo for the stage 1 tests: `scripts/train.py` and `PretrainTrainer`.

The fake `psi.trainers.pretrain.PretrainTrainer` has the pin's `create_dataloaders`
shape - `shuffle` assigned only in the mixture branch, read in the other - so a
test fails the way the real run would if the launcher did not restore it. Its
`log` adds `train/grad_norm_vlm` in place, as Psi0's does.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest
from flywheel_psi0.stage1.launch import main as launch_main
from flywheel_psi0.trainer.psi0_trainer import Runner

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


def _in_process(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
    """What `torchrun -m flywheel_psi0.stage1.launch <spec>` would do, on one rank."""
    assert command[-3:-1] == ["-m", "flywheel_psi0.stage1.launch"]
    assert env["WANDB_MODE"] == "offline"
    try:
        launch_main([command[-1]])
    except Exception:
        return 1
    return 0


@pytest.fixture
def in_process() -> Runner:
    return _in_process


@pytest.fixture
def pretrain_source() -> str:
    return FAKE_PRETRAIN
