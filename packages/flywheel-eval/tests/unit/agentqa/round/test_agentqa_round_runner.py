"""The round runner: one pack per run directory, failures recorded, the plan in use (PR #204)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.eval.agentqa.cli import app
from flywheel.eval.agentqa.round import pipeline
from flywheel.eval.agentqa.round.pack import sha256_of
from flywheel.eval.agentqa.round.pipeline import RunRefused, run_round
from flywheel.eval.agentqa.round.records import Admission, RunRecord
from flywheel.eval.agentqa.round.version import CONFIG_ROOT, agent_hash
from helpers_round import (  # noqa: F401  (isolated_store is an autouse fixture)
    NOW,
    PLAN,
    PackMaker,
    edited_plan,
    isolated_store,
    pack_maker,
)
from typer.testing import CliRunner


@pytest.fixture
def make_pack(tmp_path: Path) -> PackMaker:
    return pack_maker(tmp_path)


def stored(out: Path) -> RunRecord:
    return RunRecord.model_validate_json((out / "run.json").read_text())


def scores_only(plan: dict[str, list[dict[str, object]]]) -> None:
    """A plan whose tools need only scores (no trace_stats, train_window ...)."""
    keep = {"task_lookup", "step_pass_table", "failure_clusters", "latch_consistency"}
    plan["calls"] = [c for c in plan["calls"] if c["tool"] in keep]


# point 1 -------------------------------------------------------------------------------

def test_from_pack_with_another_pack_is_refused(make_pack: PackMaker, tmp_path: Path) -> None:
    first, other, out = make_pack("a"), make_pack("b", rename={"C_70": "C_70x"}), tmp_path / "out"
    run_round(first, out, now=NOW)
    for step in ("pack", "admit", "measure"):
        with pytest.raises(RunRefused, match="new --out"):
            run_round(other, out, from_step=step)
    assert stored(out).pack_sha256 == sha256_of(first)


# point 2 -------------------------------------------------------------------------------

def test_any_step_failure_is_recorded_as_broken(make_pack: PackMaker, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise KeyError("no such column\nsecond line")

    monkeypatch.setattr(pipeline, "measure", boom)
    out = tmp_path / "out"
    with pytest.raises(KeyError):
        run_round(make_pack(), out, now=NOW)
    record = stored(out)
    assert record.status == "broken"
    assert [(s.name, s.status) for s in record.steps][-1] == ("measure", "broken")
    assert record.problems[-1] == "measure: KeyError: no such column"


def test_cli_prints_one_line_for_a_recorded_failure(make_pack: PackMaker, tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("tables/x.json")

    monkeypatch.setattr(pipeline, "measure", boom)
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["round", "--pack", str(make_pack()), "--out", str(out),
                                      "--no-model"])
    assert result.exit_code == 2 and isinstance(result.exception, SystemExit)
    assert "FileNotFoundError" in result.output and "Traceback" not in result.output
    assert len(result.output.strip().splitlines()) == 1


# point 4 -------------------------------------------------------------------------------

def test_the_agent_hash_covers_the_plan_used(make_pack: PackMaker, tmp_path: Path) -> None:
    pack = make_pack()
    a = run_round(pack, tmp_path / "a", now=NOW)
    plan = edited_plan(tmp_path, scores_only)
    b = run_round(pack, tmp_path / "b", plan_path=plan, now=NOW)
    assert a.agent_hash != b.agent_hash
    assert (a.plan_path, a.plan_sha256) == (PLAN.as_posix(), sha256_of(PLAN))
    assert (b.plan_path, b.plan_sha256) == (plan.as_posix(), sha256_of(plan))


@pytest.mark.parametrize("name", ["routing.yaml", "hosted.yaml"])
def test_the_agent_hash_covers_the_gateway_config(tmp_path: Path, name: str) -> None:
    import shutil

    root = tmp_path / "cfg"
    shutil.copytree(CONFIG_ROOT, root)
    plan = root / "plans" / "tray.yaml"
    first = agent_hash("tray", plan, root)
    (root / name).write_text((root / name).read_text() + "\n# touched\n")
    assert agent_hash("tray", plan, root) != first


@pytest.mark.parametrize("name", ["agentqa/agent.yaml", "diagnosis/system.yaml"])
def test_the_agent_hash_covers_the_agent_and_system_configs(tmp_path: Path, name: str) -> None:
    import shutil

    configs = tmp_path / "configs" / "eval"
    shutil.copytree(CONFIG_ROOT, configs / "agentqa")
    shutil.copytree(CONFIG_ROOT.parent / "diagnosis", configs / "diagnosis")
    root = configs / "agentqa"
    first = agent_hash("tray", root=root)
    (configs / name).write_text((configs / name).read_text() + "\n# touched\n")
    assert agent_hash("tray", root=root) != first


# point 5 -------------------------------------------------------------------------------

def test_a_wrong_pack_or_plan_path_leaves_nothing(make_pack: PackMaker, tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(RunRefused, match="no pack"):
        run_round(tmp_path / "nope.json", out)
    with pytest.raises(RunRefused, match="no plan"):
        run_round(make_pack(), out, plan_path=tmp_path / "nope.yaml")
    assert not out.exists()
    result = CliRunner().invoke(app, ["round", "--pack", str(tmp_path / "nope.json"),
                                      "--out", str(out), "--no-model"])
    assert result.exit_code == 2 and "Traceback" not in result.output and not out.exists()


# point 10 ------------------------------------------------------------------------------

def test_from_measure_with_a_plan_needing_other_kinds(make_pack: PackMaker,
                                                      tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    first = run_round(pack, out, now=NOW)
    old = Admission.model_validate_json((out / "admission.json").read_text())
    assert old.missing_kinds  # the full plan wants trace, metrics ...
    plan = edited_plan(tmp_path, scores_only)
    again = run_round(pack, out, plan_path=plan, from_step="measure")
    new = Admission.model_validate_json((out / "admission.json").read_text())
    assert new.missing_kinds == [] and new.accepted == old.accepted
    assert again.run_id == first.run_id and again.plan_sha256 == sha256_of(plan)
    assert again.steps[1].outputs["admission.json"] == sha256_of(out / "admission.json")
    assert not any(p.startswith("admit: no accepted entry") for p in again.problems)
    assert stored(out) == again


def test_from_hypothesize_with_another_plan_is_refused(make_pack: PackMaker,
                                                       tmp_path: Path) -> None:
    pack, out = make_pack(), tmp_path / "out"
    run_round(pack, out, now=NOW)
    with pytest.raises(RunRefused, match="plan"):
        run_round(pack, out, plan_path=edited_plan(tmp_path, scores_only),
                  from_step="hypothesize")
    json.loads((out / "run.json").read_text())  # untouched and readable
