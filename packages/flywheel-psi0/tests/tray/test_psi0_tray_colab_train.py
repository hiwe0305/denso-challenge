"""VM side of the tray C fine-tune, on CPU: gates, cut checks, trainer wiring (DA-34 task 2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.tray import colab_train
from flywheel_psi0.tray.colab_train import (
    FROZEN,
    cut_problems,
    dataset_dir,
    job_id,
    load_plan,
)
from flywheel_psi0.tray.demo_sets import DemoSets
from flywheel_psi0.tray.runplan import TrayRunPlan

REPO = Path(__file__).resolve().parents[4]
PLAN = "configs/runplans/tray/he-tray-v2.yaml"


@pytest.fixture
def plan() -> TrayRunPlan:
    return TrayRunPlan.load(REPO / PLAN)


def _repo_copy(tmp_path: Path, plan: TrayRunPlan) -> Path:
    """Every file load_plan reads, so a test can change one."""
    files = [
        "configs/models/psi0-stage3.yaml",
        "configs/splits/default.yaml",
        "configs/runplans/tray/demo_sets-v2.json",
        "configs/runplans/tray/quality-s1-pool-1104.jsonl",
        PLAN,
        "configs/runplans/tray/he-tray-v2.lock.json",
        "docs/he/tray.md",
        *(plan.pinned_files or {}),
    ]
    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, tmp_path / rel)
    return tmp_path


def _write_cut(data: Path, plan: TrayRunPlan, **override: Any) -> None:
    """A cut as scripts/he/demo_subset.py writes it: only the meta files the VM checks."""
    sets = DemoSets.model_validate_json((REPO / plan.demo_sets.file).read_text())
    demo = sets.sets["C"]
    marker = {
        "demo_set": "C",
        "set_hash": demo.set_hash,
        "release_id": sets.release_id,
        "release_hash": sets.release_hash,
        "n": demo.n,
        "episodes": [
            {"episode_index": n, "source_episode_index": o}
            for n, o in enumerate(demo.episode_indices)
        ],
        **override,
    }
    (data / "meta").mkdir(parents=True)
    (data / "meta" / colab_train.MARKER).write_text(json.dumps(marker))
    (data / "meta" / "stats_psi0.json").write_text("{}")
    (data / "meta" / "info.json").write_text(json.dumps({"total_episodes": demo.n}))
    rows = "".join(json.dumps({"episode_index": i, "length": 9}) + "\n" for i in range(demo.n))
    (data / "meta" / "episodes.jsonl").write_text(rows)


def test_the_frozen_v2_plan_loads(plan: TrayRunPlan) -> None:
    loaded, run_plan = load_plan(REPO)
    assert (
        run_plan
        == FROZEN
        == json.loads((REPO / PLAN).with_suffix(".lock.json").read_text())["run_plan_id"]
    )
    assert loaded == plan
    assert job_id(plan) == "da34-t2-ft-c-s0"


def test_a_drifted_pinned_file_stops_the_vm(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _repo_copy(tmp_path, plan)
    assert load_plan(repo)[1] == FROZEN
    run_py = repo / "packages/flywheel-simple/src/flywheel_simple/tray/run.py"
    run_py.write_text(run_py.read_text() + "# edited after the freeze\n")
    with pytest.raises(SystemExit, match="tray/run.py changed.*re-freeze or record a Decision"):
        load_plan(repo)


def test_an_edited_tier_2_rule_stops_the_vm(tmp_path: Path, plan: TrayRunPlan) -> None:
    # only runplan check sees it: the rules block is not a pinned file and the plan is unchanged
    repo = _repo_copy(tmp_path, plan)
    doc = repo / "docs/he/tray.md"
    doc.write_text(doc.read_text().replace("p_C < 10%", "p_C < 20%", 1))
    with pytest.raises(SystemExit, match=r"(?s)plan does not hold.*reading rules in docs/he/tray"):
        load_plan(repo)


def test_only_the_tier_2_id_runs(
    tmp_path: Path, plan: TrayRunPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo_copy(tmp_path, plan)
    monkeypatch.setattr(colab_train, "FROZEN", "rp_000000000000")
    with pytest.raises(SystemExit, match="tier 2 approved rp_000000000000 only"):
        load_plan(repo)


def test_an_unfrozen_plan_does_not_run(tmp_path: Path, plan: TrayRunPlan) -> None:
    repo = _repo_copy(tmp_path, plan)
    (repo / "configs/runplans/tray/he-tray-v2.lock.json").unlink()
    with pytest.raises(SystemExit, match="not frozen"):
        load_plan(repo)


def test_dataset_dir_is_named_after_the_env(plan: TrayRunPlan, tmp_path: Path) -> None:
    assert dataset_dir(tmp_path, plan) == tmp_path / "sets/C/G1WholebodyTrayTransferTeleop-v0"


def test_the_cut_of_set_c_holds(plan: TrayRunPlan, tmp_path: Path) -> None:
    _write_cut(tmp_path, plan)
    assert cut_problems(tmp_path, plan) == []


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"demo_set": "A"}, "cut demo_set is 'A'"),
        ({"set_hash": "0" * 64}, "cut set_hash"),
        ({"release_hash": "f" * 64}, "cut release_hash"),
        ({"n": 159}, "cut n is 159"),
    ],
)
def test_a_cut_of_something_else_is_refused(
    plan: TrayRunPlan, tmp_path: Path, override: dict[str, Any], expected: str
) -> None:
    _write_cut(tmp_path, plan, **override)
    assert any(p.startswith(expected) for p in cut_problems(tmp_path, plan))


def test_a_cut_of_other_episodes_is_refused(plan: TrayRunPlan, tmp_path: Path) -> None:
    sets = DemoSets.model_validate_json((REPO / plan.demo_sets.file).read_text())
    other = sorted(set(sets.sets["A"].episode_indices) - set(sets.sets["C"].episode_indices))
    episodes = [{"episode_index": n, "source_episode_index": o} for n, o in enumerate(other[:160])]
    _write_cut(tmp_path, plan, episodes=episodes)
    assert "cut episodes are not set C's episode indices in the release" in cut_problems(
        tmp_path, plan
    )


def test_a_cut_without_its_own_stats_is_refused(plan: TrayRunPlan, tmp_path: Path) -> None:
    _write_cut(tmp_path, plan)
    (tmp_path / "meta/stats_psi0.json").unlink()
    assert any("stats_psi0.json" in p for p in cut_problems(tmp_path, plan))
    assert cut_problems(tmp_path / "nowhere", plan)[0].endswith("not a demo-set cut")


def test_the_cut_psi0_reads_must_be_set_c_too(plan: TrayRunPlan, tmp_path: Path) -> None:
    _write_cut(tmp_path, plan)
    (tmp_path / "meta/info.json").write_text(json.dumps({"total_episodes": 161}))
    with (tmp_path / "meta/episodes.jsonl").open("a") as rows:
        rows.write(json.dumps({"episode_index": 160}) + "\n")  # a stale file mixed in
    problems = cut_problems(tmp_path, plan)
    assert "cut meta/info.json total_episodes is 161, set C has 160" in problems
    assert "cut meta/episodes.jsonl rows are not episodes 0 .. 159" in problems
    (tmp_path / "meta/info.json").unlink()
    assert "cut meta/info.json total_episodes is None, set C has 160" in cut_problems(
        tmp_path, plan
    )


def test_setup_refuses_a_wrong_cut_before_any_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installs: list[Path] = []
    monkeypatch.setattr(colab_train, "install_env", lambda work: installs.append(work) or 0.0)
    with pytest.raises(SystemExit, match="cut does not hold"):
        colab_train.setup(tmp_path)  # nothing uploaded
    assert installs == []


class _FakeTrainer:
    seen: dict[str, Any] = {}

    def __init__(self, recipe: Any, **kwargs: Any) -> None:
        _FakeTrainer.seen = {"recipe": recipe, **kwargs}

    def train(self, spec: Any) -> Any:
        _FakeTrainer.seen["spec"] = spec
        job = Path(_FakeTrainer.seen["runs_root"]) / spec.job_id
        job.mkdir(parents=True)
        (job / "result.json").write_text(json.dumps({"checkpoint_step": 40000}))
        return type("Result", (), {"infra_status": "ok"})()


def test_train_runs_branch_c_as_the_plan_says(
    plan: TrayRunPlan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import flywheel_psi0.trainer as trainer_package

    monkeypatch.setattr(trainer_package, "Psi0Trainer", _FakeTrainer)
    _write_cut(dataset_dir(tmp_path, plan), plan)
    colab_train.train(tmp_path)
    seen = _FakeTrainer.seen
    spec = seen["spec"]
    assert (spec.job_id, spec.seed) == ("da34-t2-ft-c-s0", 0)
    assert spec.parent.checkpoint_id == "psi0-baseline-egodex-he"
    assert Path(spec.dataset.uri) == dataset_dir(tmp_path, plan)
    assert seen["run_plan_id"] == FROZEN
    assert seen["overrides"] == {"train.validation_steps": 2000}
    assert seen["release_id"] == "tray_s1_f9433b028c52#C:a202cc028a2e"
    phase = json.loads((tmp_path / "report.json").read_text())["phases"]["train"]
    # what scripts/he/he1_colab.py train_state reads to call the job done
    assert (phase["job_id"], phase["infra_status"], phase["checkpoint_step"]) == (
        "da34-t2-ft-c-s0",
        "ok",
        40000,
    )


def test_check_phase_needs_no_env(
    plan: TrayRunPlan, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_cut(dataset_dir(tmp_path, plan), plan)
    with pytest.raises(SystemExit) as stop:
        colab_train.main(["check", "--work", str(tmp_path)])
    assert stop.value.code == 0
    assert "rp_a04c14e79dfd da34-t2-ft-c-s0: cut and plan hold" in capsys.readouterr().out
