"""The stage 1 RunPlan of DA-34 branch B (DA-30 task 2): C's parent, the cleaned export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.stage1 import colab
from flywheel_psi0.stage1.runplan import (
    PLACEHOLDER_EXPORT_ID,
    PLACEHOLDER_SHA256,
    ExportDataset,
    Stage1Plan,
    check,
    draft_reasons,
    main,
    placeholder_pins,
)
from flywheel_psi0.tray.runplan import run_plan_id

REPO = Path(__file__).resolve().parents[4]
PLAN = REPO / "configs" / "runplans" / "stage1" / "tray-ego-b.yaml"
TRAY = REPO / "configs" / "runplans" / "tray" / "he-tray-v2.yaml"
EXPORT_ID = "egx_7b43c30dc5d88cd7"  # DA-04's cleaned export, docs/he/stage1.md 2.9


def plan() -> Stage1Plan:
    return Stage1Plan.load(PLAN)


def frozen(tmp_path: Path) -> Path:
    """The plan as it will be once PRs #173 and #174 are merged: `status` dropped."""
    raw = yaml.safe_load(PLAN.read_text())
    raw.pop("status")
    path = tmp_path / "tray-ego-b.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def with_placeholders(raw: dict[str, Any]) -> dict[str, Any]:
    raw["dataset"]["source"] |= {"export_id": PLACEHOLDER_EXPORT_ID, "sha256": PLACEHOLDER_SHA256}
    return raw


def test_the_pinned_draft_checks_out_and_says_why_it_is_a_draft(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check(plan(), REPO) == []
    assert placeholder_pins(plan()) == []
    assert main(["check", str(PLAN)]) == 0
    assert "draft: marked `status: draft` with every pin set" in capsys.readouterr().out


def test_the_pin_is_the_cleaned_export() -> None:
    dataset = plan().dataset
    assert isinstance(dataset, ExportDataset)
    assert dataset.source.export_id == EXPORT_ID and dataset.source.samples == 132
    assert dataset.source.tarball == f"denso/da30/exports/{EXPORT_ID}.tar"
    assert dataset.data_class == "public" and dataset.identity_masked


def test_the_parent_is_branch_cs_vlm() -> None:
    tray = yaml.safe_load(TRAY.read_text())
    c_parent = tray["parents"][tray["branches"]["C"]["parent"]]["vlm"]
    assert plan().parent.vlm.model_dump() == c_parent
    assert plan().psi_model.revision == tray["psi_model"]["revision"]
    assert plan().code.psi0.commit == tray["code"]["psi0"]["commit"]


def test_the_run_is_the_egodex_script_on_the_export() -> None:
    recipe = plan().load_recipe(REPO)
    fill = {"exp": "e", "seed": "7", "timestamp": "t", "output_dir": "/r", "action_header": ""}
    fill |= {"dataset_root": "/content/da30/data", "dataset_name": "egodex"}
    argv = recipe.argv({**fill, "vlm": recipe.parents[plan().parent.id].model_name_or_path})
    assert (
        "--model.model_name_or_path="
        "cache/checkpoints/psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k"
    ) in argv
    assert "--data.transform.field.stat-path=assets/stats/egodex_stat_all.json" in argv
    assert "--train.max_training_steps=300" in argv and "--train.validation_steps=0" in argv
    assert isinstance(plan().dataset, ExportDataset) and plan().persist_vlm


def test_dropping_the_draft_keeps_the_checks_and_the_id(tmp_path: Path) -> None:
    pinned = Stage1Plan.load(frozen(tmp_path))
    assert draft_reasons(pinned) == [] and check(pinned, REPO) == []
    assert run_plan_id(pinned) == run_plan_id(plan())


def test_a_placeholder_pin_must_be_marked_draft(tmp_path: Path) -> None:
    raw = with_placeholders(yaml.safe_load(frozen(tmp_path).read_text()))
    assert any("not marked `status: draft`" in p for p in check(Stage1Plan.model_validate(raw)))
    draft = Stage1Plan.model_validate(raw | {"status": "draft"})
    assert check(draft, REPO) == []
    assert draft_reasons(draft) == [
        "export_id is the placeholder",
        "tarball sha256 is the placeholder",
    ]


def test_the_status_is_not_part_of_the_id(tmp_path: Path) -> None:
    pinned = yaml.safe_load(frozen(tmp_path).read_text())
    with_status = Stage1Plan.model_validate(pinned | {"status": "draft"})
    assert run_plan_id(with_status) == run_plan_id(Stage1Plan.model_validate(pinned))


def test_setup_refuses_the_draft_before_anything_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[str] = []
    monkeypatch.setattr(colab, "setup_psi0_env", lambda work: ran.append("env"))
    monkeypatch.setattr(colab, "sh", lambda command, cwd=None, env=None: ran.append(command))
    with pytest.raises(SystemExit, match="draft: marked `status: draft` with every pin set"):
        colab.setup(tmp_path, PLAN)
    assert ran == []
