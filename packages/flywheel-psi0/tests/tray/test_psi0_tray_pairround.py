"""The round plan on a branch of the paired plan: C70_R1 on C_70's failures (DA-34 7.4)."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel_psi0.tray import pairround, runplan
from flywheel_psi0.tray.pairround import TrayPairRoundPlan, check, freeze, pending
from flywheel_psi0.tray.runplan import lock_path, rules_sha256, run_plan_id

LIVE = Path(__file__).resolve().parents[4]
PAIR = "configs/runplans/tray/he-tray-pair60k.yaml"
ROUND = "configs/runplans/tray/round-tray-c70.yaml"
ROWS = "configs/runplans/tray/round-c70-rollouts.jsonl"
DOC = "docs/he/tray.md"
RULES = "<!-- round-c70-rules -->\n\n(r1) C70_R1 against C_ALL.\n\n<!-- /round-c70-rules -->\n"


def _rows() -> list[dict[str, Any]]:
    """60 rollouts, 10 of them successes, as the C_70 stage 1 rows file holds them."""
    return [
        {"level": 1 + i // 30, "seed": 1000100 + i % 30, "success": i % 6 == 0} for i in range(60)
    ]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw(repo: Path) -> dict[str, Any]:
    """The draft round plan of tray.md 20, against the fake repo's files."""
    return {
        "name": "round-tray-c70-psi0",
        "purpose": "round",
        "story": "DA-34",
        "status": "draft",
        "inherits": PAIR,
        "base_branch": "C_70",
        "branch": "C70_R1",
        "uniform_branch": "C_ALL",
        "max_rounds": 1,
        "failures": {
            "eval_dir": "rtx3060:~/eval/pair60k-C_70-60000-rp_a04c14e79dfd",
            "runs_sha256": "9" * 64,
            "eval_set": "rp_a04c14e79dfd-2e57f60",
            "conditions_sha256": (
                "b9c38b37afa6fbdd4027be287df85fe7b016130bd32227f97c876f6bae7d3dfb"
            ),
            "checkpoint": 60000,
            "rows": {"file": ROWS, "sha256": _sha(repo / ROWS)},
            "counts": {"rollouts": 60, "success": 10, "failures": 50},
            "cluster_key": ["first_fail_step", "failure", "level"],
        },
        "diagnosis": {
            "representatives_per_cluster": 5,
            "representative_seed": 20261112,
            "reset_runs": 10,
            "tau_k": 0.8,
            "knn_k": 5,
            "tau_cov": "p95 leave-one-out kNN distance over S70's conditions",
            "step6": "unavailable",
            "step7_rollouts_per_representative": 3,
        },
        "budget": {
            "b_add_episodes": 181,
            "per_failure_rollouts": 20,
            "per_cluster_cap": 200,
            "failures_per_cluster_max": 10,
            "order": "g/c, Beta(1,1)",
            "train_cap_cu": 80,
            "eval_cap_cu": 14,
            "diagnosis_cap_cu": 8,
        },
        "targets": {
            "n_add_max": 181,
            "from_failures_of": "C_70",
            "generator": "flywheel_simple.tray.targets",
            "seed_window": [100000, 199999],
            "quality_filter": {"max_tilt_carry_deg": 10.0, "max_part_shift_end_mm": 20.0},
            "seeds": [],
        },
        "train": {
            "parent": "psi0-baseline-egodex-he",
            "data": "S70 (index 0-424) + targeted set (index 425-)",
            "stats_sha256": ("1c745091bc7dcfc9912d3c3ee0d4d8b1e1ee16ed6e9c7f7d6b5fd9c16b600243"),
            "recipe": "as the paired plan",
            "steps": 60000,
            "train_seed": 0,
            "gpu": "A100",
        },
        "eval": {
            "eval_set": "rp_a04c14e79dfd-2e57f60",
            "checkpoint": 60000,
            "stages": "as 19.2",
            "server": "Colab L4",
        },
        "comparisons": [
            {"rule": "r1", "variant": "C70_R1", "baseline": "C_ALL", "kind": "primary"},
            {"rule": "r2", "variant": "C70_R1", "baseline": "C_70", "kind": "secondary"},
        ],
        "interpretation": {"doc": DOC, "rules_marker": "round-c70-rules"},
    }


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with the frozen paired plan, the rows file and the rules block."""
    root = tmp_path / "repo"
    for rel in (PAIR, str(lock_path(Path(PAIR)))):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LIVE / rel, root / rel)
    (root / ROWS).write_text("".join(json.dumps(r) + "\n" for r in _rows()))
    (root / DOC).parent.mkdir(parents=True)
    (root / DOC).write_text("# tray\n\n" + RULES)
    return root


def _plan(raw: dict[str, Any]) -> TrayPairRoundPlan:
    return TrayPairRoundPlan.model_validate(raw)


def test_the_live_round_plan_is_frozen_with_its_targets_and_rules() -> None:
    """The committed round-tray-c70.yaml (task 7.5, 12/11/2026) checks against the live repo:
    the frozen paired plan, the targeted set's pinned files and tray.md's rules block."""
    plan = TrayPairRoundPlan.load(LIVE / ROUND)
    assert (plan.status, plan.base_branch, plan.branch) == ("frozen", "C_70", "C70_R1")
    assert check(plan, LIVE) == []
    assert pending(plan) == []
    assert (plan.targets.set_name, len(plan.targets.seeds)) == ("R181", 181)
    lock = json.loads(lock_path(LIVE / ROUND).read_text())
    assert lock["run_plan_id"] == "rp_aae292bc79da"


def test_the_draft_round_holds_and_says_what_is_pending(repo: Path) -> None:
    plan = _plan(_raw(repo))
    assert check(plan, repo) == []
    todo = pending(plan)
    assert any("targets.seeds" in p for p in todo)
    assert any("rules_sha256" in p for p in todo)


def test_the_round_differs_from_its_base_branch_in_the_data_only(repo: Path) -> None:
    raw = _raw(repo)
    raw["train"].update(parent="psi0-ego-stage1-egx", steps=40000, train_seed=1)
    raw["train"]["stats_sha256"] = "0" * 64
    problems = check(_plan(raw), repo)
    assert any("train.parent" in p for p in problems)
    assert any("train.steps" in p for p in problems)
    assert any("train.train_seed" in p for p in problems)
    assert any("train.stats_sha256" in p for p in problems)


def test_the_budget_is_what_the_uniform_branch_adds(repo: Path) -> None:
    raw = _raw(repo)
    raw["budget"]["b_add_episodes"] = raw["targets"]["n_add_max"] = 200
    assert any("606 - 425 = 181" in p for p in check(_plan(raw), repo))
    raw = _raw(repo)
    raw["uniform_branch"] = "B_ALL"  # the stage 1 VLM: not the same parent as C_70
    assert any("uniform_branch B_ALL" in p for p in check(_plan(raw), repo))
    raw = _raw(repo)
    raw["uniform_branch"] = "C_70"
    assert any("uniform_branch C_70" in p for p in check(_plan(raw), repo))


def test_branches_comparisons_and_failures_tie_to_the_paired_plan(repo: Path) -> None:
    raw = _raw(repo)
    raw["branch"] = "C_ALL"
    raw["targets"]["from_failures_of"] = "B_70"
    raw["comparisons"][0]["baseline"] = "C_70"
    raw["failures"]["checkpoint"] = 40000
    raw["eval"]["eval_set"] = "rp_other-0000000"
    problems = check(_plan(raw), repo)
    assert any("branch C_ALL already exists" in p for p in problems)
    assert any("from the failures of the base branch" in p for p in problems)
    assert any("the primary comparison" in p for p in problems)
    assert any("failures.checkpoint" in p for p in problems)
    assert any("eval.eval_set" in p for p in problems)


def test_the_rows_file_is_pinned_and_counted(repo: Path) -> None:
    raw = _raw(repo)
    raw["failures"]["counts"]["success"] = 11
    assert any("counts" in p for p in check(_plan(raw), repo))
    (repo / ROWS).write_text((repo / ROWS).read_text() + "\n")
    assert any(f"{ROWS} changed" in p for p in check(_plan(_raw_with_old_sha(repo)), repo))


def _raw_with_old_sha(repo: Path) -> dict[str, Any]:
    raw = _raw(repo)
    raw["failures"]["rows"]["sha256"] = "1" * 64
    return raw


def test_the_parent_plan_must_be_frozen_and_unchanged(repo: Path) -> None:
    lock = repo / lock_path(Path(PAIR))
    data = json.loads(lock.read_text())
    data["run_plan_id"] = "rp_000000000000"
    lock.write_text(json.dumps(data))
    assert any("changed since it was frozen" in p for p in check(_plan(_raw(repo)), repo))
    lock.unlink()
    assert any("is not frozen" in p for p in check(_plan(_raw(repo)), repo))


def test_rules_once_pinned_must_match_the_block(repo: Path) -> None:
    raw = _raw(repo)
    raw["interpretation"]["rules_sha256"] = rules_sha256(RULES, "round-c70-rules")
    assert check(_plan(raw), repo) == []
    (repo / DOC).write_text("# tray\n\n" + RULES.replace("C_ALL", "C_70"))
    assert any("changed since the plan pinned them" in p for p in check(_plan(raw), repo))


def test_freeze_refuses_a_draft_and_null_pins(repo: Path) -> None:
    path = repo / ROUND
    path.write_text(yaml.safe_dump(_raw(repo), sort_keys=False))
    with pytest.raises(ValueError) as error:
        freeze(path, repo)
    assert "status draft" in str(error.value)
    assert "targets.seeds" in str(error.value)
    assert not lock_path(path).exists()


def test_targets_stay_in_the_train_seed_window_and_the_budget(repo: Path) -> None:
    raw = _raw(repo)
    raw["targets"]["seeds"] = [99999, 100001, 100000]
    problems = check(_plan(raw), repo)
    assert any("seed_window" in p for p in problems)
    assert any("unique and ascending" in p for p in problems)
    raw["targets"]["seeds"] = list(range(100000, 100182))
    assert any("more than n_add_max 181" in p for p in check(_plan(raw), repo))


def test_runplan_hands_a_round_on_a_paired_plan_to_pairround(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = repo / ROUND
    path.write_text(yaml.safe_dump(_raw(repo), sort_keys=False))
    monkeypatch.setattr(runplan, "REPO", repo)
    monkeypatch.setattr(pairround, "REPO", repo)
    assert runplan.main(["check", str(path)]) == 0
    out = capsys.readouterr().out
    assert "round draft, branch C70_R1 on C_70" in out
    assert runplan.main(["check", str(path), "--launch"]) == 1
    assert "DRAFT" in capsys.readouterr().err
    with pytest.raises(ValueError, match="status draft"):
        runplan.freeze(path, repo)


def test_a_frozen_round_locks_its_id(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With targets and rules pinned (check_targets mocked: no release here), freeze writes
    the lock, and `--launch` passes until the plan changes."""
    raw = _raw(repo)
    raw["status"] = "frozen"
    raw["targets"].update(seeds=[100001, 100002], set_hash="s" * 64)
    raw["interpretation"]["rules_sha256"] = rules_sha256(RULES, "round-c70-rules")
    path = repo / ROUND
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    monkeypatch.setattr(pairround, "check_targets", lambda targets, repo: [])
    monkeypatch.setattr(pairround, "pending_targets", lambda targets: [])
    out = freeze(path, repo)
    plan = TrayPairRoundPlan.load(path)
    assert json.loads(out.read_text())["run_plan_id"] == run_plan_id(plan)
    monkeypatch.setattr(pairround, "REPO", repo)
    assert pairround.main(["check", str(path), "--launch"]) == 0
    changed = copy.deepcopy(raw)
    changed["targets"]["seeds"] = [100001, 100003]
    path.write_text(yaml.safe_dump(changed, sort_keys=False))
    assert pairround.main(["check", str(path), "--launch"]) == 1
