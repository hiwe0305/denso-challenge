"""The stage 1 RunPlan, its recipe and its pass criteria (DA-30 AC 1), on CPU."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from flywheel_psi0.stage1.runplan import (
    Stage1Plan,
    check,
    first_loss_matches,
    loss_decreased,
    main,
    train_losses,
)
from flywheel_psi0.tray.runplan import run_plan_id

REPO = Path(__file__).resolve().parents[4]
PLAN = REPO / "configs" / "runplans" / "stage1" / "egodex-short.yaml"

# pretrain-egodex-psi0-fast.sh at cda3fdf, the args the recipe must keep as they are.
SCRIPT_ARGS = [
    "--train.name=pretrain",
    "--train.data_parallel=deepspeed",
    "--train.mixed_precision=bf16",
    "--train.train_batch_size=16",
    "--train.gradient_accumulation_steps=2",
    "--train.learning_rate=1e-4",
    "--train.lr_scheduler_type=constant",
    "--data.chunk_size=1",
    "--data.upsample_rate=3",
    "--data.transform.field.stat-path=assets/stats/egodex_stat_all.json",
    "--data.use-delta-actions",
    "--model.action_tokenizer.pretrained_checkpoint=src/fast/egodex-rel-50w-1x48-v2048-s100",
    "--model.tune-mm-vision",
]


def plan() -> Stage1Plan:
    return Stage1Plan.load(PLAN)


def argv() -> list[str]:
    fill = {"exp": "e", "seed": "7", "timestamp": "t", "output_dir": "/runs/j/psi0"}
    fill |= {"dataset_root": "/data", "dataset_name": "egodex", "action_header": ""}
    recipe = plan().load_recipe(REPO)
    return recipe.argv({**fill, "vlm": recipe.parents[plan().parent.id].model_name_or_path})


def test_the_committed_plan_checks_out() -> None:
    assert check(plan(), REPO) == []
    assert main(["check", str(PLAN)]) == 0


def test_the_plan_id_is_stable_and_content_addressed() -> None:
    first = run_plan_id(plan())
    assert first.startswith("rp_") and first == run_plan_id(plan())
    changed = plan().model_copy(update={"job": plan().job.model_copy(update={"seed": 8})})
    assert run_plan_id(changed) != first


def test_argv_is_the_authors_script_from_pre_on_the_export() -> None:
    rendered = argv()
    assert rendered[:2] == ["pretrain_egodex_qwen3vl_config", "model.action-tokenizer:fast"]
    for arg in SCRIPT_ARGS:
        assert arg in rendered
    assert "--data.transform.model.resize.size" in rendered
    assert "--data.root-dir=/data/egodex" in rendered
    vlm = "--model.model_name_or_path=cache/checkpoints/psi0/pre.fast.2605160748.ckpt.ego390k"
    assert vlm in rendered
    flags = [arg.split("=", 1)[0] for arg in rendered if arg.startswith("--")]
    assert len(flags) == len(set(flags))


def test_the_plan_overrides_only_length_val_and_deepspeed() -> None:
    rendered = argv()
    assert "--train.max_training_steps=200" in rendered
    assert "--train.validation_steps=0" in rendered
    assert "--train.deepspeed_config=scripts/deepspeed/zero3_offload.json" in rendered
    assert set(plan().overrides) == {
        "train.max_training_steps",
        "train.checkpointing_steps",
        "train.validation_steps",
        "train.deepspeed_config",
    }


def test_check_rejects_a_bad_plan(tmp_path: Path) -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["overrides"]["train.not_an_arg"] = 1
    raw["overrides"]["train.validation_steps"] = 100
    raw["parent"]["id"] = "psi0-pre-unknown"
    raw["criteria"]["repeat_steps"] = 500
    bad = Stage1Plan.model_validate(raw)
    problems = check(bad, REPO)
    assert any("train.not_an_arg" in p for p in problems)
    assert any("val is on" in p for p in problems)
    assert any("psi0-pre-unknown" in p for p in problems)
    assert any("shorter" in p for p in problems)


def test_check_catches_a_parent_path_from_another_folder() -> None:
    raw = yaml.safe_load(PLAN.read_text())
    raw["parent"]["vlm"]["path"] = "psi0/pre.fast.egodex.2512241941.ckpt200k/model.safetensors"
    assert any("not under" in p for p in check(Stage1Plan.model_validate(raw), REPO))


def write_metrics(path: Path, rows: list[tuple[int, int, object]]) -> Path:
    lines = [
        json.dumps({"split": "train", "attempt": attempt, "step": step, "loss": loss})
        for attempt, step, loss in rows
    ]
    lines.append(json.dumps({"split": "val", "attempt": 0, "step": 1, "loss": 0.1}))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_train_losses_keep_the_latest_attempt_per_step(tmp_path: Path) -> None:
    rows: list[tuple[int, int, object]] = [(0, 0, 3.0), (0, 1, 2.9), (0, 2, "NaN")]
    rows += [(1, 1, 2.8), (1, 2, 2.7)]
    metrics = write_metrics(tmp_path / "metrics.jsonl", rows)
    assert train_losses(metrics) == [3.0, 2.8, 2.7]
    assert train_losses(metrics, attempt=0) == [3.0, 2.9]


def test_loss_decreased_compares_window_medians() -> None:
    falling = [3.0 - 0.01 * i for i in range(50)]
    assert loss_decreased(falling, 20)["passed"]
    spike = [2.0] * 20 + [9.0] * 10 + [2.1] * 20  # flat with a spike: not a decrease
    assert not loss_decreased(spike, 20)["passed"]
    short = loss_decreased([1.0] * 10, 20)
    assert not short["passed"] and "need 40" in short["reason"]


@pytest.mark.parametrize(("rerun", "passed"), [(2.03, True), (2.1, False)])
def test_first_loss_matches_within_tolerance(rerun: float, passed: bool) -> None:
    result = first_loss_matches([2.0, 1.9], [rerun, 1.9], rtol=0.02)
    assert result["passed"] is passed
    assert not first_loss_matches([], [2.0], rtol=0.02)["passed"]


def with_dataset(**changes: object) -> dict[str, object]:
    raw = yaml.safe_load(PLAN.read_text())
    source = changes.pop("source", None)
    raw["dataset"].update(changes)
    if source is not None:
        raw["dataset"]["source"]["name"] = source
    return raw  # type: ignore[no-any-return]


def test_the_egodex_waiver_covers_only_public_egodex() -> None:
    assert not Stage1Plan.load(PLAN).dataset.identity_masked  # the plan relies on it
    for source, data_class in [
        ("team_ego", "internal"),
        ("team_ego", "public"),
        ("egodex", "internal"),
        ("egodex", "restricted"),
    ]:
        raw = with_dataset(source=source, data_class=data_class)
        with pytest.raises(ValueError, match="must pass identity masking"):
            Stage1Plan.model_validate(raw)


def test_any_source_passes_once_masked() -> None:
    raw = with_dataset(source="team_ego", data_class="internal", identity_masked=True)
    assert Stage1Plan.model_validate(raw).dataset.source.name == "team_ego"


def test_the_sample_fetch_refuses_an_unwaived_source(tmp_path: Path) -> None:
    from flywheel_psi0.stage1.egodex_sample import main as sample_main

    plan = tmp_path / "plan.yaml"
    plan.write_text(yaml.safe_dump(with_dataset(source="team_ego", data_class="internal")))
    assert sample_main(["fetch", "--plan", str(plan), "--out", str(tmp_path / "data")]) == 2
    assert not (tmp_path / "data").exists()
