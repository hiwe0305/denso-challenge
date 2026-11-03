"""`Psi0Trainer` and the launcher, end to end on CPU against a fake Psi0 (DA-19 AC 2).

`fake_psi0` writes a Psi0 repo whose `scripts/train.py` calls the hooked methods in
the order the real loop does (`clip_grad_norms`, `log`, `save_checkpoint`, then
`inference` and `log` at validation), on a fake `psi.trainers.finetune` with no
torch. The runner calls the real launcher in-process instead of `torchrun`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest
from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
from flywheel.contracts.artifacts import ActionDimension, ActionLayout
from flywheel.contracts.protocols import TrainerAdapter
from flywheel.contracts.training import TrainingMetric
from flywheel_psi0.trainer import Psi0Recipe, Psi0Trainer
from flywheel_psi0.trainer.launch import LossTap
from flywheel_psi0.trainer.launch import main as launch_main

REPO = Path(__file__).resolve().parents[5]
RECIPES = REPO / "configs" / "models"
PARENT = "psi0-baseline-egodex-he"
DIMS = 36

FAKE_TRAINER = """
import os
import numpy as np


class FakeTensor:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=np.float64)
        self.shape = self.array.shape

    def __getitem__(self, index):
        return FakeTensor(self.array[index])

    def detach(self):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.array


class Param:
    def __init__(self, grad):
        self.grad = grad


class Model:
    def named_parameters(self):
        # A frozen VLM: its parameters never receive a gradient.
        yield "module.vlm_model.visual.weight", Param(None)
        yield "module.action_header.proj.weight", Param(FakeTensor([3.0, 4.0]))


class Functional:
    # `torch.nn.functional` reduced to what `forward_and_loss` uses.

    @staticmethod
    def mse_loss(input, target, reduction="mean"):
        squared = (input.array - target.array) ** 2
        return FakeTensor(squared if reduction == "none" else squared.mean())


F = Functional()


class Cfg:
    def __init__(self, validation_steps):
        train = {"validation_steps": validation_steps, "data_parallel": "ddp"}
        self.train = type("Train", (), train)


class FinetuneTrainer:
    def __init__(self, output_dir, validation_steps):
        self.project_dir = os.path.join(output_dir, "finetune", "run.job")
        self.cfg = Cfg(validation_steps)
        self.model = Model()
        self.global_step = 0
        self.dtype = "bf16"
        self.calls = []

    def set_train(self):
        self.calls.append("train")

    def set_eval(self):
        self.calls.append("eval")

    def unwrap_model(self):
        return self.model

    def forward_and_loss(self, model, batch):
        actions = batch["actions"]
        # The velocity error grows along the chunk, as an untrained header's would.
        noise = np.linspace(0.1, 0.5, actions.shape[1])[None, :, None]
        loss = F.mse_loss(FakeTensor(actions.array + noise), actions, reduction="none")
        # Like Psi0 with --model.rtc, positions below max-delay (8) stay out of the loss.
        return {"loss": float(loss.array[:, 8:].mean())}

    def training_step(self, batch):
        losses = self.forward_and_loss(self.model, batch)
        return True, {"loss": losses["loss"]}

    def log(self, metrics, start_time=None):
        pass

    def clip_grad_norms(self):
        return {"action_header": 0.5}

    def inference(self, eval_model, batch):
        rng = np.random.default_rng(self.global_step)
        actions = batch["actions"].array
        return FakeTensor(actions[:, :30] + rng.normal(0, 0.1, actions[:, :30].shape))

    def evaluate(self, batches):
        # Psi0 computes the val loss with the same F.mse_loss, outside training_step.
        losses = [self.forward_and_loss(self.model, batch)["loss"] for batch in batches]
        for batch in batches:
            self.inference(self.model, batch)
        return {"loss": sum(losses) / len(losses)}

    def save_checkpoint(self, global_step):
        path = os.path.join(self.project_dir, "checkpoints", f"ckpt_{global_step}")
        os.makedirs(path, exist_ok=True)
        return path
"""

FAKE_TRAIN_PY = """
import sys
import numpy as np
from psi.trainers.finetune import FakeTensor, FinetuneTrainer

args = dict(a[2:].split("=", 1) for a in sys.argv[2:] if a.startswith("--") and "=" in a)
if args.get("seed") == "13":
    OutOfMemoryError = type("OutOfMemoryError", (RuntimeError,), {})
    raise OutOfMemoryError("CUDA out of memory")
trainer = FinetuneTrainer(args["train.output_dir"], int(args["train.validation_steps"]))
rng = np.random.default_rng(0)
for step in range(int(args["train.max_training_steps"])):
    trainer.global_step = step
    batch = {"actions": FakeTensor(rng.uniform(-1, 1, (2, 30, 36)))}
    _, losses = trainer.training_step(batch)
    trainer.clip_grad_norms()
    trainer.log({"train/lr_act": 1e-4, "train/grad_norm_act": 0.5, "train/loss": losses["loss"],
                 "train/epoch": 0})
    if (step + 1) % int(args["train.checkpointing_steps"]) == 0:
        trainer.save_checkpoint(step + 1)
    if step % int(args["train.validation_steps"]) == 0:
        val = [{"actions": FakeTensor(rng.uniform(-1, 1, (2, 30, 36)))} for _ in range(2)]
        trainer.log({"eval/" + k: v for k, v in trainer.evaluate(val).items()})
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
    (trainers / "finetune.py").write_text(FAKE_TRAINER)
    (root / ".env").write_text("")
    monkeypatch.syspath_prepend(str(root / "src"))
    monkeypatch.chdir(tmp_path)  # the launcher chdirs into the repo; restore afterwards
    monkeypatch.delenv("RANK", raising=False)
    yield root
    for name in [m for m in sys.modules if m == "psi" or m.startswith("psi.")]:
        del sys.modules[name]


def in_process(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
    """What `torchrun -m flywheel_psi0.trainer.launch <spec>` would do, on one rank."""
    assert env["WANDB_MODE"] == "offline"
    assert command[-3:-1] == ["-m", "flywheel_psi0.trainer.launch"]
    try:
        launch_main([command[-1]])
    except Exception:
        return 1
    return 0


GROUPS = {"hand": 14, "arm": 14, "torso_rpy": 3, "height": 1}
GROUPS |= {"base_velocity": 2, "turn": 1, "target_yaw": 1}


def g1_layout() -> ActionLayout:
    return ActionLayout(
        dimensions=[
            ActionDimension(name=f"{group}_{i}", group=group, masked=False)
            for group, size in GROUPS.items()
            for i in range(size)
        ]
    )


def dataset(tmp_path: Path) -> DatasetRef:
    uri = tmp_path / "psi-data" / "simple" / "G1WholebodyLocomotionPickBetweenTablesTeleop-v0"
    (uri / "meta").mkdir(parents=True, exist_ok=True)
    low = [0.0] * 3 + [-1.5] * 4 + [-0.5] * 3 + [0.0] * 4 + [-1.0] * 22
    high = [0.5] * 3 + [0.0] * 4 + [0.0] * 3 + [1.5] * 4 + [1.0] * 22
    (uri / "meta" / "stats_psi0.json").write_text(json.dumps({"action": {"min": low, "max": high}}))
    return DatasetRef(dataset_id="psi-data-two-table", uri=str(uri))


def trainer(fake_root: Path, tmp_path: Path, **overrides: object) -> Psi0Trainer:
    return Psi0Trainer(
        Psi0Recipe.load(RECIPES / "psi0-stage3.yaml"),
        psi0_root=fake_root,
        runs_root=tmp_path / "runs",
        layout=g1_layout(),
        run_plan_id="rp_smoke",
        release_id="rel_psi_data_two_table",
        psi0_commit="cda3fdf",
        overrides={
            "train.max_training_steps": 6,
            "train.checkpointing_steps": 3,
            "train.validation_steps": 5,
            **overrides,  # type: ignore[dict-item]
        },
        python_bin=Path("/psi/venv/bin"),
        runner=in_process,
    )


def spec(tmp_path: Path, seed: int = 292285) -> TrainSpec:
    return TrainSpec(
        job_id="job.smoke-1",
        dataset=dataset(tmp_path),
        parent=CheckpointRef(checkpoint_id=PARENT),
        seed=seed,
    )


def read(path: Path) -> list[TrainingMetric]:
    return [TrainingMetric.model_validate_json(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_every_stage_recipe_renders_unique_flags(stage: int) -> None:
    recipe = Psi0Recipe.load(RECIPES / f"psi0-stage{stage}.yaml")
    fill = dict.fromkeys(
        ["exp", "seed", "timestamp", "output_dir", "dataset_root", "dataset_name", "vlm"], "x"
    )
    argv = recipe.argv({**fill, "action_header": "x"})
    flags = [arg.split("=", 1)[0] for arg in argv if arg.startswith("--")]
    assert argv[0] == recipe.config_module
    assert len(flags) == len(set(flags))
    assert f"--train.name={recipe.trainer_module}" in argv


def test_stage3_keeps_the_author_settings_that_matter_for_the_he_experiment() -> None:
    recipe = Psi0Recipe.load(RECIPES / "psi0-stage3.yaml")
    assert recipe.vlm_frozen
    assert recipe.args["model.rtc"] is True and recipe.args["model.action-dim"] == 36
    assert set(recipe.parents) >= {PARENT, "psi0-abl-he-only", "psi0-abl-egodex-10pct"}


def test_override_replaces_and_cannot_touch_per_job_args() -> None:
    recipe = Psi0Recipe.load(RECIPES / "psi0-stage3.yaml")
    assert recipe.with_overrides({"train.train_batch_size": 2}).args["train.train_batch_size"] == 2
    with pytest.raises(ValueError, match="seed"):
        recipe.with_overrides({"seed": 1})


def test_psi0_trainer_satisfies_the_trainer_protocol(fake_psi0: Path, tmp_path: Path) -> None:
    assert isinstance(trainer(fake_psi0, tmp_path), TrainerAdapter)


def test_command_runs_the_launcher_with_the_job_args(fake_psi0: Path, tmp_path: Path) -> None:
    psi0 = trainer(fake_psi0, tmp_path, **{"train.train_batch_size": 4})
    launch = psi0.launch_spec(spec(tmp_path))

    assert psi0.command()[:2] == ["/psi/venv/bin/torchrun", "--nproc_per_node=1"]
    assert "--timestamp=job-smoke-1" in launch.argv  # no dot, or Psi0 cannot resume it
    assert "--seed=292285" in launch.argv
    assert any(a.endswith("postpre.1by1.pad36.2601131206.ckpt.he30k") for a in launch.argv)
    assert "--data.train-repo-ids=G1WholebodyLocomotionPickBetweenTablesTeleop-v0" in launch.argv
    assert launch.global_batch_size == 4
    assert launch.hand_open_pose is not None and len(launch.hand_open_pose) == 14
    assert launch.identity["vlm_frozen"] is True and launch.identity["attempt"] == 0
    assert launch.rtc_prefix == 8  # --model.rtc with --model.max-delay=8


def test_unknown_parent_is_refused(fake_psi0: Path, tmp_path: Path) -> None:
    other = spec(tmp_path).model_copy(update={"parent": CheckpointRef(checkpoint_id="nope")})
    with pytest.raises(KeyError, match="nope"):
        trainer(fake_psi0, tmp_path).launch_spec(other)


def test_train_writes_metrics_and_reports_the_checkpoint(fake_psi0: Path, tmp_path: Path) -> None:
    psi0 = trainer(fake_psi0, tmp_path)
    result = psi0.train(spec(tmp_path))

    assert result.infra_status == "ok"
    assert result.checkpoint == CheckpointRef(checkpoint_id="psi0-s3-job.smoke-1-s292285")
    records = read(tmp_path / "runs" / "job.smoke-1" / "metrics.jsonl")
    train = [r for r in records if r.split == "train"]
    val = [r for r in records if r.split == "val"]
    assert [r.step for r in train] == list(range(6)) and [r.step for r in val] == [0, 5]
    # The fake VLM is frozen: measured in clip_grad_norms, before zero_grad.
    assert {r.grad_norm_vlm for r in train} == {0.0}
    assert len(val[0].hand_open_hist) == 10 and len(val[0].pred_std) == DIMS
    # Every train line splits its own loss; the fake's error grows along the chunk.
    assert all(set(r.loss_by_group) == set(GROUPS) for r in train)
    assert len(train[0].loss_by_chunk_pos) == 30 - 8  # RTC prefix dropped
    assert train[0].loss_by_chunk_pos[-1] > train[0].loss_by_chunk_pos[0]
    assert train[0].loss == pytest.approx(
        sum(train[0].loss_by_chunk_pos) / len(train[0].loss_by_chunk_pos)
    )
    # Validation steps (0 and 5) also sample actions on the train batch.
    assert [r.step for r in train if r.pred_std] == [0, 5]
    assert len(train[0].hand_open_hist) == 10 and len(train[0].pred_var_by_dim) == DIMS
    reported = json.loads((tmp_path / "runs" / "job.smoke-1" / "result.json").read_text())
    assert reported["checkpoint_step"] == 6 and reported["checkpoint_dir"].endswith("ckpt_6")


def test_rerun_appends_the_next_attempt(fake_psi0: Path, tmp_path: Path) -> None:
    psi0 = trainer(fake_psi0, tmp_path)
    psi0.train(spec(tmp_path))
    psi0.train(spec(tmp_path))

    records = read(tmp_path / "runs" / "job.smoke-1" / "metrics.jsonl")
    assert sorted({r.attempt for r in records}) == [0, 1]


def test_out_of_memory_is_reported_without_a_checkpoint(fake_psi0: Path, tmp_path: Path) -> None:
    result = trainer(fake_psi0, tmp_path).train(spec(tmp_path, seed=13))

    assert result.infra_status == "out_of_memory" and result.checkpoint is None


def test_missing_dotenv_is_a_clear_error(fake_psi0: Path, tmp_path: Path) -> None:
    (fake_psi0 / ".env").unlink()
    with pytest.raises(FileNotFoundError, match="cp .env.sample .env"):
        trainer(fake_psi0, tmp_path).train(spec(tmp_path))


def test_loss_tap_records_only_unreduced_loss_inside_training_step() -> None:
    class Functional:
        @staticmethod
        def mse_loss(input: float, target: float, reduction: str = "mean") -> tuple[str, float]:
            return reduction, input - target

        relu = "passed through"

    seen: list[object] = []
    tap = LossTap(Functional(), seen.append)
    tap.mse_loss(3.0, 1.0, reduction="none")  # evaluate(): not active
    tap.active = True
    tap.mse_loss(3.0, 1.0)  # a reduced loss is not the per-element one
    assert tap.mse_loss(5.0, 1.0, reduction="none") == ("none", 4.0)

    assert seen == [("none", 4.0)]
    assert tap.relu == "passed through"
