"""VM side of the tray C fine-tune, on CPU: gates, cut checks, trainer wiring (DA-34 task 2)."""

from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import Any

import pytest
from flywheel_psi0.trainer.recipe import Psi0Recipe
from flywheel_psi0.tray import colab_train
from flywheel_psi0.tray.colab_train import (
    FROZEN,
    cut_problems,
    dataset_dir,
    job_id,
    load_plan,
)
from flywheel_psi0.tray.demo_sets import DemoSets
from flywheel_psi0.tray.runplan import Stage1Parent, TrayRunPlan

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

    def install_env(work: Path) -> float:
        installs.append(work)
        return 0.0

    monkeypatch.setattr(colab_train, "install_env", install_env)
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


# Branch B (task 4): C's job with the VLM from DA-30's stage 1 folder on Drive.
B_PLAN = "configs/runplans/tray/he-tray-b.yaml"
BASE_VLM = "psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k"


# The parent VLM's tensors, in miniature: names, dtypes and shapes are what the pin hashes.
TENSORS: dict[str, tuple[str, tuple[int, ...]]] = {
    "model.language_model.embed_tokens.weight": ("BF16", (6, 2)),
    "model.visual.patch_embed.proj.weight": ("BF16", (2, 3)),
}


def _write_safetensors(path: Path, tensors: dict[str, tuple[str, tuple[int, ...]]]) -> None:
    """A valid safetensors file: little-endian header length, JSON header, zero data."""
    header: dict[str, object] = {"__metadata__": {"format": "pt"}}
    offset = 0
    for name, (dtype, shape) in tensors.items():
        size = 2 * shape[0] * shape[1]
        header[name] = {
            "dtype": dtype,
            "shape": list(shape),
            "data_offsets": [offset, offset + size],
        }
        offset += size
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + bytes(offset))


def _vlm_folders(root: Path) -> tuple[Path, Path]:
    """(stage 1 folder as on Drive, parent VLM folder without weights) with fake files."""
    base, stage1 = root / "base" / Path(BASE_VLM).name, root / "drive" / "da30" / "vlm-ego"
    for folder in (base, stage1):
        (folder / "sub").mkdir(parents=True)
        (folder / "config.json").write_text('{"model_type": "qwen3_vl"}')
        (folder / "sub" / "tokenizer.json").write_text('{"vocab": 1}')
    _write_safetensors(stage1 / colab_train.WEIGHTS, TENSORS)
    return stage1, base


def _pins(stage1: Path) -> dict[str, str]:
    return {
        "job_id": "da30-t2-stage1-ego-s0",
        "drive_dir": "da30/vlm-ego",
        "weights_sha256": colab_train.sha256(stage1 / colab_train.WEIGHTS),
        "manifest_sha256": colab_train.manifest_sha256(stage1),
        "parent_header_sha256": colab_train.header_sha256(TENSORS),
    }


def _frozen_b(tmp_path: Path, plan: TrayRunPlan, pins: dict[str, str]) -> tuple[Path, str]:
    """A repo copy whose B plan is pinned, out of draft and frozen, as task 4.7 leaves it."""
    import yaml
    from flywheel_psi0.tray import runplan

    repo = _repo_copy(tmp_path, plan)
    raw = yaml.safe_load((REPO / B_PLAN).read_text())
    raw["parents"]["psi0-b-ego-stage1"]["vlm_stage1"].update(pins)
    del raw["status"]
    (repo / B_PLAN).write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    lock = json.loads(runplan.freeze(repo / B_PLAN, repo).read_text())
    return repo, lock["run_plan_id"]


def test_b_does_not_run_from_the_draft_plan() -> None:
    with pytest.raises(SystemExit) as stop:
        colab_train.load_job("B")
    message = str(stop.value)
    assert "is a draft" in message and "B_FROZEN is unset" in message
    assert "vlm_stage1.weights_sha256 is not pinned yet (DA-30)" in message


def test_b_runs_only_the_approved_frozen_plan(
    tmp_path: Path, plan: TrayRunPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage1, _ = _vlm_folders(tmp_path / "vlm")
    repo, frozen = _frozen_b(tmp_path / "repo", plan, _pins(stage1))
    with pytest.raises(SystemExit, match="B_FROZEN is unset"):
        colab_train.load_job("B", repo)
    monkeypatch.setattr(colab_train, "B_FROZEN", "rp_000000000000")
    with pytest.raises(SystemExit, match="only rp_000000000000 is approved for B"):
        colab_train.load_job("B", repo)
    monkeypatch.setattr(colab_train, "B_FROZEN", frozen)
    job = colab_train.load_job("B", repo)
    assert (job.job_id, job.run_plan_id, job.parent_name) == (
        "da34-t4-ft-b-s0",
        frozen,
        "psi0-b-ego-stage1",
    )
    assert (job.demo_set, job.set_hash) == ("C", plan.demo_sets.hashes["C"])
    # B uploads C's cut as is: same marker, same checks
    _write_cut(job.data(tmp_path / "work"), plan)
    assert job.data(tmp_path / "work").parent.name == "B"
    assert job.cut_problems(job.data(tmp_path / "work"), repo) == []


def test_the_stage1_folder_must_be_the_pinned_one_with_only_the_weights_changed(
    tmp_path: Path,
) -> None:
    from flywheel_psi0.tray.runplan import Stage1Vlm

    stage1, base = _vlm_folders(tmp_path)
    pins = Stage1Vlm(story="DA-30", ledger="x", from_parent="p", **_pins(stage1))
    assert colab_train.stage1_vlm_problems(stage1, base, pins) == []
    (stage1 / ".cache").mkdir()  # dot entries are left out of the manifest
    (stage1 / ".cache" / "lock").write_text("x")
    assert colab_train.stage1_vlm_problems(stage1, base, pins) == []
    (stage1 / "sub" / "tokenizer.json").write_text('{"vocab": 2}')
    problems = colab_train.stage1_vlm_problems(stage1, base, pins)
    assert "sub/tokenizer.json: differs from the parent VLM folder's" in problems
    assert any("manifest sha256" in p for p in problems)
    (stage1 / "sub" / "tokenizer.json").write_text('{"vocab": 1}')
    (stage1 / "optimizer.bin").write_text("x")
    (base / "preprocessor_config.json").write_text("{}")
    problems = colab_train.stage1_vlm_problems(stage1, base, pins)
    assert "optimizer.bin: not in the parent VLM folder" in problems
    assert "preprocessor_config.json: missing from the stage 1 VLM folder" in problems
    _write_safetensors(stage1 / colab_train.WEIGHTS, {"a.weight": ("BF16", (1, 1))})
    assert any(
        p.endswith(f"plan pins {pins.weights_sha256}")
        for p in colab_train.stage1_vlm_problems(stage1, base, pins)
    )
    assert colab_train.stage1_vlm_problems(tmp_path / "nowhere", base, pins)[0].endswith(
        "the stage 1 VLM is not there"
    )


def test_manifest_prints_what_the_plan_pins(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stage1, _ = _vlm_folders(tmp_path)
    with pytest.raises(SystemExit) as stop:
        colab_train.main(["manifest", "--folder", str(stage1)])
    assert stop.value.code == 0
    pins = _pins(stage1)
    out = capsys.readouterr().out
    assert f"weights_sha256: {pins['weights_sha256']}" in out
    assert f"header_sha256: {pins['parent_header_sha256']} (2 tensors, dtypes ['BF16']" in out
    assert f"manifest_sha256: {pins['manifest_sha256']}" in out and "files: 3" in out
    lines = colab_train.folder_manifest(stage1).splitlines()
    assert [line.split("  ")[1] for line in lines] == [
        "config.json",
        "model.safetensors",
        "sub/tokenizer.json",
    ]


def test_setup_of_b_refuses_without_the_drive_folder_before_any_install(
    tmp_path: Path, plan: TrayRunPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage1, _ = _vlm_folders(tmp_path / "vlm")
    repo, frozen = _frozen_b(tmp_path / "repo", plan, _pins(stage1))
    monkeypatch.setattr(colab_train, "B_FROZEN", frozen)
    monkeypatch.setattr(colab_train, "DRIVE", tmp_path / "unmounted")
    installs: list[Path] = []

    def install_env(work: Path) -> float:
        installs.append(work)
        return 0.0

    monkeypatch.setattr(colab_train, "install_env", install_env)
    work = tmp_path / "work"
    _write_cut(colab_train.load_job("B", repo).data(work), plan)
    with pytest.raises(SystemExit, match="mount Drive first"):
        colab_train.setup(work, "B", repo)
    assert installs == []


def test_train_runs_b_on_the_stage1_vlm_and_cs_action_header(
    tmp_path: Path, plan: TrayRunPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    import flywheel_psi0.trainer as trainer_package

    stage1, base = _vlm_folders(tmp_path / "vlm")
    repo, frozen = _frozen_b(tmp_path / "repo", plan, _pins(stage1))
    monkeypatch.setattr(colab_train, "B_FROZEN", frozen)
    monkeypatch.setattr(trainer_package, "Psi0Trainer", _FakeTrainer)
    work = tmp_path / "work"
    job = colab_train.load_job("B", repo)
    _write_cut(job.data(work), plan)
    # where setup leaves the two folders
    psi0 = work / "Psi0"
    with pytest.raises(SystemExit, match="the stage 1 VLM is not there"):
        colab_train.train(work, "B", repo)
    shutil.copytree(stage1, psi0 / colab_train.STAGE1_DIR / "vlm-ego")
    shutil.copytree(base, psi0 / "cache/checkpoints" / BASE_VLM)
    colab_train.train(work, "B", repo)
    seen = _FakeTrainer.seen
    spec = seen["spec"]
    assert (spec.job_id, spec.seed, spec.parent.checkpoint_id) == (
        "da34-t4-ft-b-s0",
        0,
        "psi0-b-ego-stage1",
    )
    added = seen["recipe"].parents["psi0-b-ego-stage1"]
    c_parent = seen["recipe"].parents["psi0-baseline-egodex-he"]
    assert added.model_name_or_path == "cache/checkpoints/stage1/vlm-ego"
    assert added.pretrained_action_header_path == c_parent.pretrained_action_header_path
    # everything else as C: recipe args, override, release id of set C
    assert seen["recipe"].args == Psi0Recipe.load(REPO / plan.recipe.file).args
    assert seen["overrides"] == {"train.validation_steps": 2000}
    assert seen["release_id"] == "tray_s1_f9433b028c52#C:a202cc028a2e"
    assert seen["run_plan_id"] == frozen


@pytest.mark.parametrize(
    ("tensors", "seen"),
    [
        # what save_model writes from a wrapped model: same tensors under another prefix
        ({f"vlm_model.{k}": v for k, v in TENSORS.items()}, "top-level ['vlm_model']"),
        ({**TENSORS, "lm_head.weight": ("BF16", (6, 2))}, "lm_head True"),
        ({k: ("F32", s) for k, (_, s) in TENSORS.items()}, "dtypes ['F32']"),
        (
            {**TENSORS, "model.language_model.embed_tokens.weight": ("BF16", (4, 2))},
            "embed_tokens [(4, 2)]",
        ),
    ],
)
def test_stage1_weights_must_have_the_parent_vlms_tensors(
    tmp_path: Path, tensors: dict[str, tuple[str, tuple[int, ...]]], seen: str
) -> None:
    # Qwen3VL from_pretrained only warns on such keys: stage 3 would train from random weights
    from flywheel_psi0.tray.runplan import Stage1Vlm

    stage1, base = _vlm_folders(tmp_path)
    _write_safetensors(stage1 / colab_train.WEIGHTS, tensors)
    pins = Stage1Vlm(story="DA-30", ledger="x", from_parent="p", **_pins(stage1))
    pins = pins.model_copy(update={"parent_header_sha256": colab_train.header_sha256(TENSORS)})
    problems = colab_train.stage1_vlm_problems(stage1, base, pins)
    assert [p for p in problems if "tensors are not the parent VLM's" in p and seen in p], problems
    assert len(problems) == 1  # sha256 and manifest are the folder's own: only the header fails
    (stage1 / colab_train.WEIGHTS).write_bytes(b"not a safetensors file")
    assert any(
        "no readable safetensors header" in p
        for p in colab_train.stage1_vlm_problems(stage1, base, pins)
    )


def test_the_plan_pins_the_header_of_cs_vlm() -> None:
    # 625 BF16 tensors, no lm_head, embed_tokens 153792 x 2048, read by range request from
    # psi-model cb1480f on 9/11/2026; DA-30's package (PR #171) found the same
    plan = TrayRunPlan.load(REPO / B_PLAN)
    stage1 = plan.parents["psi0-b-ego-stage1"]
    assert isinstance(stage1, Stage1Parent)
    assert stage1.vlm_stage1.parent_header_sha256 == (
        "53d000d9626a13faf4bcb5268517b8441c34b187c88c9dee0b4c250dc19d6d59"
    )
