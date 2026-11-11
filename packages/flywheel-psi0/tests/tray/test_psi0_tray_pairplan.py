"""The paired 60k plan of DA-34 task 6: one cut, two VLMs x two data sizes (tray.md 19)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.tray import pairplan, runplan
from flywheel_psi0.tray.pairplan import (
    TrayPairPlan,
    check,
    epochs,
    pending,
    seeds_sha256,
    subset_lists,
    subset_seeds,
    subset_size,
)
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
    raw["pinned_files"] = {}
    for subset in raw["subsets"]:
        subset["parts"][0]["regenerates"], subset["parts"][1]["regenerates"] = "pool-a", "pool-b"
    plan = TrayPairPlan.model_validate(raw)
    lists = subset_lists(plan, REPO)
    for subset in raw["subsets"]:
        for sp in subset["parts"]:
            seeds = lists[subset["name"]][sp["regenerates"]]
            sp.update(episodes=len(seeds), seeds_sha256=seeds_sha256(seeds))
        subset.update(episodes=sum(sp["episodes"] for sp in subset["parts"]), frames=580000)
    return raw


def test_the_frozen_plan_holds_with_every_pin_set() -> None:
    plan = TrayPairPlan.load(PAIR)
    assert check(plan, REPO) == []
    assert plan.status is None and plan.steps() == 60000  # task 6.2, Hiếu 11/11/2026
    lock = json.loads(PAIR.with_name("he-tray-pair60k.lock.json").read_text(encoding="utf-8"))
    assert lock["run_plan_id"] == run_plan_id(plan) == "rp_e2fb9f62c223"
    assert pending(plan) == []  # W1 and S70 pinned 11/11/2026, then DA-30's stage 1 VLM
    assert plan.interpretation.rules_marker == "pair60k-rules"
    text = (REPO / plan.interpretation.doc).read_text(encoding="utf-8")
    assert runplan.rules_sha256(text, "pair60k-rules") == plan.interpretation.rules_sha256
    # the other two blocks are not touched by section 19
    b = runplan.TrayRunPlan.load(PLANS / "he-tray-b.yaml")
    assert runplan.rules_sha256(text, "branch-b-rules") == b.interpretation.rules_sha256


def test_only_the_vlm_and_the_subset_differ_by_construction() -> None:
    plan = TrayPairPlan.load(PAIR)
    cells = {n: (b.parent, plan.data_of(b)) for n, b in plan.branches.items()}
    assert cells == {
        "B_ALL": ("psi0-ego-stage1-egx", "ALL"),
        "C_ALL": ("psi0-baseline-egodex-he", "ALL"),
        "B_70": ("psi0-ego-stage1-egx", "S70"),
        "C_70": ("psi0-baseline-egodex-he", "S70"),
    }
    s70 = plan.subset("S70")
    assert s70 is not None and (s70.fraction, s70.order, s70.stats) == (0.7, "sha256_seed", "cut")
    assert [p.regenerates for p in s70.parts] == [p.regenerates for p in plan.cut.parts]
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
        (("budget", "ceiling_cu"), 140, "over the ceiling"),
        (("schedule", "waves"), [["B_ALL", "C_ALL"], ["B_70"]], "every branch in exactly one wave"),
        (("comparisons", 0, "kind"), "secondary", "exactly one primary"),
        (("comparisons", 0, "baseline"), "C_ALL", "the primary compares one data size"),
        (("comparisons", 1, "margin"), None, "a margin goes with noninferiority only"),
        (("subsets", 0, "parts", 1, "regenerates"), "pool-x", "parts are not the cut's"),
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


def test_the_step_count_is_stated_and_the_branches_are_two_vlms_on_every_data() -> None:
    raw = _raw()
    del raw["recipe"]["overrides"]["train.max_training_steps"]
    assert any("states its step count" in p for p in _problems(raw))
    for name, parent in (("C_ALL", "psi0-ego-stage1-egx"), ("C_70", "psi0-other")):
        raw = _raw()
        raw["branches"][name]["parent"] = parent
        with pytest.raises(ValueError, match="parent|two parents"):
            TrayPairPlan.model_validate(raw)
    raw = _raw()
    raw["branches"]["C2"] = {"parent": "psi0-baseline-egodex-he", "role": "x"}
    with pytest.raises(ValueError, match="every \\(parent, data\\) pair once"):
        TrayPairPlan.model_validate(raw)
    raw = _raw()
    del raw["branches"]["C_70"]  # B_70 alone has no paired baseline on S70
    with pytest.raises(ValueError, match="every \\(parent, data\\) pair once"):
        TrayPairPlan.model_validate(raw)
    raw = _raw()
    raw["branches"]["B_70"]["data"] = "S60"
    with pytest.raises(ValueError, match="is no subset"):
        TrayPairPlan.model_validate(raw)
    # the plain pair still holds: two branches on the cut, no subsets, no comparisons
    raw = _raw()
    for key in ("B_70", "C_70"):
        del raw["branches"][key]
    for key in ("subsets", "comparisons"):
        del raw[key]
    with pytest.raises(ValueError, match="pinned but unused"):
        TrayPairPlan.model_validate({**_raw(), "branches": raw["branches"]})
    raw["schedule"].pop("waves")
    raw["budget"].update(runs=["B_ALL", "C_ALL"], ceiling_cu=140)
    assert _problems(raw) == []


def test_subset_size_rounds_up_exactly() -> None:
    assert [subset_size(n, 0.7) for n in (10, 20, 429, 177, 1)] == [7, 14, 301, 124, 1]
    assert subset_size(3, 0.7) == 3  # 2.1 rounds up to 3


def test_the_subset_is_the_seeds_by_sha256_alone() -> None:
    seeds = list(range(1000, 1610))
    chosen = subset_seeds(seeds, 0.7)
    assert len(chosen) == 427 and chosen == sorted(chosen) and set(chosen) <= set(seeds)
    # the order of the input and any other seed in the pool change nothing for a seed
    assert subset_seeds(list(reversed(seeds)), 0.7) == chosen
    assert subset_seeds(seeds[:10], 0.7) == subset_seeds(list(reversed(seeds[:10])), 0.7)
    # pinned by its list; one seed more or less is another list
    assert seeds_sha256(chosen) == seeds_sha256(list(reversed(chosen)))
    assert seeds_sha256(chosen) != seeds_sha256(chosen[1:])
    with pytest.raises(ValueError, match="twice"):
        subset_seeds([1, 1, 2], 0.7)


def test_w1_pins_cut_all_and_s70_as_delivered(capsys: pytest.CaptureFixture[str]) -> None:
    # DA-33's cut of 11/11/2026 05:11 (rtx3060 cut-all-zone1): 429 + 177 episodes
    plan = TrayPairPlan.load(PAIR)
    assert (plan.cut.episodes, plan.cut.frames) == (606, 861624)
    assert [p.release.id for p in plan.cut.parts if p.release] == [
        "tray_s1_41899efb4b27",
        "tray_s1_4a8f4a8c6a8d",
    ]
    assert [len(pairplan.part_seeds(p, REPO) or []) for p in plan.cut.parts] == [429, 177]
    s70 = plan.subset("S70")
    assert s70 is not None and (s70.episodes, s70.frames) == (425, 603915)
    assert [p.episodes for p in s70.parts] == [301, 124]
    assert pairplan.main(["subset", str(PAIR)]) == 0
    listed = json.loads(capsys.readouterr().out)["S70"]
    assert [v["seeds_sha256"] for v in listed.values()] == [p.seeds_sha256 for p in s70.parts]


def test_subset_pins_are_checked_against_the_pinned_parts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = _pinned(_raw())
    assert _problems(raw) == []
    s70 = raw["subsets"][0]
    assert [sp["episodes"] for sp in s70["parts"]] == [subset_size(n, 0.7) for n in (
        len(pairplan.part_seeds(TrayPairPlan.model_validate(raw).cut.parts[0], REPO) or []),
        len(pairplan.part_seeds(TrayPairPlan.model_validate(raw).cut.parts[1], REPO) or []),
    )]  # fmt: skip
    wrong = copy.deepcopy(raw)
    wrong["subsets"][0]["parts"][0]["seeds_sha256"] = "e" * 64
    assert any("seeds_sha256 is not the list" in p for p in _problems(wrong))
    wrong = copy.deepcopy(raw)
    wrong["subsets"][0]["parts"][1]["episodes"] += 1
    assert any("episodes pinned" in p for p in _problems(wrong))
    wrong = copy.deepcopy(raw)
    wrong["subsets"][0]["episodes"] += 1
    assert any("is not the parts' sum" in p for p in _problems(wrong))
    early = _raw()
    early["cut"]["parts"][0].update(release=None, demo_sets=None, set_name=None)
    assert any("pinned before the part" in p for p in _problems(early))


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


def test_w2_pins_the_stage1_vlm_as_delivered() -> None:
    # DA-30's stage 1 on A100 (rp_1d7627234111, job da30-tray-ego-b, step 300), vlm.json
    parent = TrayPairPlan.load(PAIR).parents["psi0-ego-stage1-egx"]
    assert isinstance(parent, runplan.Stage1Parent)
    vlm = parent.vlm_stage1
    assert (vlm.job_id, vlm.drive_dir) == ("da30-tray-ego-b", "denso/da30/da30-tray-ego-b/vlm")
    assert vlm.weights_sha256 is not None and vlm.weights_sha256.startswith("c48ec2df761d")
    assert vlm.manifest_sha256 is not None and vlm.manifest_sha256.startswith("019daa801041")


def test_the_decision_draft_reads_the_frozen_plan_by_its_rules() -> None:
    from flywheel.contracts.entities import Decision

    plan = TrayPairPlan.load(PAIR)
    decision = Decision.model_validate_json(
        PAIR.with_name("he-tray-pair60k.decision.json").read_text(encoding="utf-8")
    )
    assert (decision.subject_id, decision.verdict) == (run_plan_id(plan), "open")
    assert decision.criteria["rules_sha256"] == plan.interpretation.rules_sha256
    assert set(decision.metrics["comparisons"]) == {c.rule for c in plan.comparisons}
    assert set(decision.metrics["runs"]) == set(plan.branches)


def test_no_launch_and_no_freeze_until_pinned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # the live plan is frozen (task 6.2): it launches
    assert pairplan.main(["check", str(PAIR), "--launch"]) == 0
    assert "launch OK" in capsys.readouterr().out
    # the same plan as a draft: no launch, no freeze
    draft = tmp_path / "draft" / "he-tray-pair60k.yaml"
    draft.parent.mkdir()
    draft.write_text(yaml.safe_dump({**_raw(), "status": "draft"}, allow_unicode=True))
    assert pairplan.main(["check", str(draft)]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith(", draft") and "pending" not in out
    assert pairplan.main(["check", str(draft), "--launch"]) == 1
    err = capsys.readouterr().err
    assert "DRAFT" in err and "PENDING:" not in err and "not frozen" in err
    with pytest.raises(ValueError, match="status draft"):
        pairplan.freeze(draft, REPO)
    # a plan with W2's pins null lists them, and only them
    raw = {**_raw(), "status": "draft"}
    raw["parents"]["psi0-ego-stage1-egx"]["vlm_stage1"].update(
        job_id=None, drive_dir=None, weights_sha256=None, manifest_sha256=None
    )
    unpinned = tmp_path / "he-tray-pair60k.yaml"
    unpinned.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    assert pairplan.main(["check", str(unpinned)]) == 0
    assert "draft, 4 pins pending" in capsys.readouterr().out
    assert pairplan.main(["check", str(unpinned), "--launch"]) == 1
    err = capsys.readouterr().err
    assert err.count("PENDING:") == 4 and err.count("(DA-30)") == 4
    # runplan hands a paired plan over, and refuses a --release it would not read
    assert runplan.main(["check", str(PAIR)]) == 0
    assert "pending" not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        runplan.main(["check", str(PAIR), "--release", str(tmp_path)])


def test_freezes_once_pinned_and_released_from_draft(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = _pinned({**_raw(), "status": "draft"})
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
    assert "1.66 epochs of S70" in out  # 60000 x 16 / 580000
    assert pairplan.main(["subset", str(plan_path)]) == 0
    listed = json.loads(capsys.readouterr().out)["S70"]
    for sp in raw["subsets"][0]["parts"]:
        part = listed[sp["regenerates"]]
        assert (part["episodes"], part["seeds_sha256"]) == (sp["episodes"], sp["seeds_sha256"])


def test_epochs_of_c_cplus_and_all() -> None:
    # tray.md 19.4: frames from meta/info.json of the cuts on rtx3060; ALL estimated
    assert epochs(40000, 16, 228247) == pytest.approx(2.804, abs=1e-3)
    assert epochs(40000, 16, 455372) == pytest.approx(1.405, abs=1e-3)
    assert epochs(60000, 16, 861624) == pytest.approx(1.114, abs=1e-3)


def test_the_60k_plan_reads_60k_and_40k_early_and_needs_every_cap_at_once() -> None:
    plan = TrayPairPlan.load(PAIR)
    assert (plan.checkpoints.primary, plan.checkpoints.early) == (60000, 40000)
    assert plan.schedule.mode == "parallel" and pairplan.balance_needed(plan) == 14 + 4 * 70
    assert plan.schedule.waves == [["B_ALL", "C_ALL"], ["B_70", "C_70"]]
    # Hiếu 11/11/2026 "Chốt A100": every run on A100, recipe unchanged; cap 70 each as a
    # safety net (the fetch loop stops a session once ckpt_60000 is verified)
    assert "--gpu A100 --cap 70" in plan.budget.watcher and plan.budget.ceiling_cu == 280
    assert "early 40000" in pairplan.summary(plan, REPO)
    assert plan.comparisons is not None
    assert [(c.rule, c.variant, c.baseline, c.kind, c.margin) for c in plan.comparisons] == [
        ("a′", "B_70", "C_70", "primary", None),
        ("f", "B_70", "C_ALL", "noninferiority", 0.10),
        ("g", "C_70", "C_ALL", "noninferiority", 0.10),
        ("h", "B_ALL", "C_ALL", "secondary", None),
    ]


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
