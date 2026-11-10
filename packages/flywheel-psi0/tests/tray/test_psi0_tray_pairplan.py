"""The paired 60k plan of DA-34 task 6: one cut, two VLMs, pins pending (tray.md 19)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.tray import pairplan, runplan
from flywheel_psi0.tray.pairplan import TrayPairPlan, check, epochs, pending
from flywheel_psi0.tray.runplan import run_plan_id

REPO = Path(__file__).resolve().parents[4]
PLANS = REPO / "configs/runplans/tray"
PAIR = PLANS / "he-tray-pair60k.yaml"


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = yaml.safe_load(PAIR.read_text(encoding="utf-8"))
    return raw


def _problems(raw: dict[str, Any]) -> list[str]:
    return check(TrayPairPlan.model_validate(raw), REPO)


def _pinned(raw: dict[str, Any]) -> dict[str, Any]:
    """Every null pin filled with real files of today's pools, as W1 and W2 would fill them.

    The parts name made-up pools: the files are the old releases' (CMAX of v2's release,
    T160 of the targeted one), which a real part may not pin as its regeneration.
    """
    raw = copy.deepcopy(raw)
    cmax = yaml.safe_load((PLANS / "he-tray-cmax.yaml").read_text(encoding="utf-8"))
    cplus = yaml.safe_load((PLANS / "round-tray-cplus.yaml").read_text(encoding="utf-8"))
    raw["cut"]["parts"] = [
        {"regenerates": "pool-a", "release": cmax["release"], "demo_sets": cmax["demo_sets"],
         "set_name": "CMAX"},
        {"regenerates": "pool-b", "release": cplus["targets"]["release"],
         "demo_sets": cplus["targets"]["demo_sets"], "set_name": "T160"},
    ]  # fmt: skip
    raw["cut"].update(visuals_revision="0" * 40, episodes=589, frames=837194, stats_sha256="a" * 64)
    raw["parents"]["psi0-ego-stage1-egx"]["vlm_stage1"].update(
        job_id="da30-t2-stage1-egx-s0", drive_dir="da30/vlm-egx",
        weights_sha256="b" * 64, manifest_sha256="c" * 64,
    )  # fmt: skip
    raw["pinned_files"] = {}
    return raw


def test_the_draft_holds_and_lists_what_w1_and_w2_owe() -> None:
    plan = TrayPairPlan.load(PAIR)
    assert check(plan, REPO) == []
    assert plan.status == "draft" and plan.steps() == 60000
    todo = pending(plan)
    assert len(todo) == 13
    assert sum("(W1)" in p for p in todo) == 9 and sum("(DA-30)" in p for p in todo) == 4
    assert plan.interpretation.rules_marker == "pair60k-rules"
    text = (REPO / plan.interpretation.doc).read_text(encoding="utf-8")
    assert runplan.rules_sha256(text, "pair60k-rules") == plan.interpretation.rules_sha256
    # the other two blocks are not touched by section 19
    b = runplan.TrayRunPlan.load(PLANS / "he-tray-b.yaml")
    assert runplan.rules_sha256(text, "branch-b-rules") == b.interpretation.rules_sha256


def test_only_the_vlm_differs_by_construction() -> None:
    plan = TrayPairPlan.load(PAIR)
    b_all, c_all = (
        plan.parents[plan.branches["B_ALL"].parent],
        plan.parents["psi0-baseline-egodex-he"],
    )
    assert isinstance(b_all, runplan.Stage1Parent) and isinstance(c_all, runplan.Parent)
    assert b_all.vlm_stage1.from_parent == plan.branches["C_ALL"].parent
    assert b_all.action_header == c_all.action_header
    v2 = runplan.TrayRunPlan.load(PLANS / "he-tray-v2.yaml")
    assert (plan.eval, plan.stats, plan.train_seeds) == (v2.eval, v2.stats, v2.train_seeds)
    assert c_all == v2.parents["psi0-baseline-egodex-he"]
    # the +zone1 scene (DA-33 #182): v2's file list, re-hashed; the cut records the revision
    assert plan.pinned_files is not None and v2.pinned_files is not None
    assert list(plan.pinned_files) == list(v2.pinned_files)
    assert plan.cut.visuals_revision == "4763fbfaa4f8e97658e68b57d01b4c86659e08b5+zone1"
    assert dict(plan.recipe.overrides) == {
        "train.validation_steps": 2000,
        "train.max_training_steps": 60000,
    }


@pytest.mark.parametrize(
    ("path", "value", "seen"),
    [
        (("recipe", "overrides", "train.learning_rate"), 5e-5, "a pair may set only"),
        (("eval", "episode_limit_s"), 60.0, "eval_of: eval differs"),
        (("train_seeds",), [1], "eval_of: train seeds"),
        (
            ("eval_of", "run_plan_id"),
            "rp_000000000000",
            "eval_of: configs/runplans/tray/he-tray-v2",
        ),
        (("eval_of", "eval_set"), "rp_366283071c4a-x", "is not an eval set of"),
        (("budget", "runs"), ["B_ALL"], "runs are exactly the branches"),
        (("budget", "ceiling_cu"), 40, "over the ceiling"),
        (("interpretation", "rules_sha256"), "0" * 64, "reading rules"),
        (
            ("parents", "psi0-ego-stage1-egx", "vlm_stage1", "from_parent"),
            "psi0-abl-he-only",
            "from_parent psi0-abl-he-only is no release parent",
        ),
        (
            ("parents", "psi0-ego-stage1-egx", "action_header", "path"),
            "psi0/postpre.abl.only.he.2602050012/action_header.safetensors",
            "action header is not",
        ),
    ],
)
def test_any_second_difference_is_refused(path: tuple[str, ...], value: object, seen: str) -> None:
    raw = _raw()
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    problems = _problems(raw)
    assert any(seen in p for p in problems), problems


def test_the_step_count_is_stated_and_a_pair_is_two_branches_two_parents() -> None:
    raw = _raw()
    del raw["recipe"]["overrides"]["train.max_training_steps"]
    assert any("states its step count" in p for p in _problems(raw))
    raw = _raw()
    raw["branches"]["C_ALL"]["parent"] = "psi0-ego-stage1-egx"
    with pytest.raises(ValueError, match="two parents"):
        TrayPairPlan.model_validate(raw)
    raw = _raw()
    raw["branches"]["C2"] = {"parent": "psi0-baseline-egodex-he", "role": "x"}
    with pytest.raises(ValueError, match="two branches"):
        TrayPairPlan.model_validate(raw)


def test_cut_parts_pin_whole_and_new() -> None:
    raw = _pinned(_raw())
    assert _problems(raw) == []
    half = copy.deepcopy(raw)
    half["cut"]["parts"][1]["set_name"] = None
    assert any("together" in p for p in _problems(half))
    old = copy.deepcopy(raw)
    old["cut"]["parts"][0]["regenerates"] = old["cut"]["parts"][0]["release"]["id"]
    assert any("pins the old release" in p for p in _problems(old))
    wrong = copy.deepcopy(raw)
    wrong["cut"]["parts"][1]["demo_sets"]["hashes"]["T160"] = "d" * 64
    assert any(p.startswith("part pool-b: demo set T160") for p in _problems(wrong))


def test_no_launch_and_no_freeze_until_pinned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert pairplan.main(["check", str(PAIR)]) == 0
    assert "draft, 13 pins pending" in capsys.readouterr().out
    assert pairplan.main(["check", str(PAIR), "--launch"]) == 1
    err = capsys.readouterr().err
    assert "DRAFT" in err and err.count("PENDING:") == 13 and "not frozen" in err
    with pytest.raises(ValueError, match="status draft"):
        pairplan.freeze(PAIR, REPO)
    # runplan hands a paired plan over, and refuses a --release it would not read
    assert runplan.main(["check", str(PAIR)]) == 0
    assert "13 pins pending" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        runplan.main(["check", str(PAIR), "--release", str(tmp_path)])


def test_freezes_once_pinned_and_released_from_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = _pinned(_raw())
    plan_path = tmp_path / "he-tray-pair60k.yaml"
    plan_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="status draft"):
        pairplan.freeze(plan_path, REPO)
    del raw["status"]
    plan_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    lock = runplan.freeze(plan_path, REPO)
    frozen = json.loads(lock.read_text())["run_plan_id"]
    assert frozen == run_plan_id(TrayPairPlan.model_validate(raw))
    assert pairplan.main(["check", str(plan_path), "--launch"]) == 0
    out = capsys.readouterr().out
    assert "launch OK" in out and "1.15 epochs of ALL" in out  # 60000 x 16 / 837194


def test_epochs_of_c_cplus_and_all() -> None:
    # tray.md 19.4: frames from meta/info.json of the cuts on rtx3060; ALL estimated
    assert epochs(40000, 16, 228247) == pytest.approx(2.804, abs=1e-3)
    assert epochs(40000, 16, 455372) == pytest.approx(1.405, abs=1e-3)
    assert epochs(60000, 16, 861624) == pytest.approx(1.114, abs=1e-3)


FALLBACK = PLANS / "he-tray-pair40k-seq.yaml"


def test_the_60k_plan_reads_60k_and_40k_early_and_needs_both_caps_at_once() -> None:
    plan = TrayPairPlan.load(PAIR)
    assert (plan.checkpoints.primary, plan.checkpoints.early) == (60000, 40000)
    assert plan.schedule.mode == "parallel" and pairplan.balance_needed(plan) == 14 + 2 * 70
    # Hiếu 11/11/2026 "Chốt A100": both runs on A100, cap 70 each, recipe unchanged
    assert "--gpu A100" in plan.budget.watcher and plan.budget.ceiling_cu == 140
    assert "early 40000" in pairplan.summary(plan, REPO)


@pytest.mark.parametrize(
    ("change", "seen"),
    [
        ({"primary": 50000}, "is not the step count 60000"),
        ({"early": 60000}, "is not before 60000"),
        ({"early": 45000}, "saves every 10000 steps only"),
    ],
)
def test_the_checkpoints_read_are_ones_psi0_saves(change: dict[str, int], seen: str) -> None:
    raw = _raw()
    raw["checkpoints"].update(change)
    assert any(seen in p for p in _problems(raw))


def test_the_watcher_line_states_the_cap_and_floor() -> None:
    raw = _raw()
    raw["schedule"]["floor_cu"] = 20
    assert "budget.watcher does not say --floor 20" in _problems(raw)


def test_the_fallback_is_the_60k_plan_with_40k_steps_run_one_after_the_other() -> None:
    main, fallback = _raw(), yaml.safe_load(FALLBACK.read_text(encoding="utf-8"))
    differs = {k for k in main.keys() | fallback.keys() if main.get(k) != fallback.get(k)}
    assert differs == {"name", "recipe", "budget", "checkpoints", "schedule"}
    assert {k for k in main["recipe"] if main["recipe"][k] != fallback["recipe"][k]} == {
        "overrides"
    }
    assert fallback["recipe"]["overrides"] == {
        **main["recipe"]["overrides"], "train.max_training_steps": 40000
    }  # fmt: skip
    plan = TrayPairPlan.model_validate(fallback)
    assert check(plan, REPO) == [] and len(pending(plan)) == 13
    assert (plan.checkpoints.primary, plan.checkpoints.early) == (40000, None)
    assert plan.schedule.mode == "sequential" and pairplan.balance_needed(plan) == 14 + 18
    assert plan.interpretation == TrayPairPlan.load(PAIR).interpretation  # one rules block
    assert run_plan_id(plan) != run_plan_id(TrayPairPlan.load(PAIR))
