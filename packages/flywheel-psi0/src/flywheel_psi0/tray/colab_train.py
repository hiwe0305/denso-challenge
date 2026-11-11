"""Fine-tune branch C of tray RunPlan v2 on a Colab L4 (DA-34 task 2, AC 2).

VM side, one session for the one run tier 2 pays for here (C+ is the round's).
The repo goes to `<work>/fw` (`git archive` of master) and C's cut, built on
rtx3060 from the release, to `<work>/sets/C/<env name>`; then, from `<work>`:

    export PYTHONPATH=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
    python3 -m flywheel_psi0.tray.colab_train setup
    Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train

Both phases load `configs/runplans/tray/he-tray-v2.yaml` and refuse to go on unless
it is the frozen plan of tier 2 (`FROZEN`), `runplan.check` holds and no pinned
eval file has drifted: the `--launch` rule of docs/he/tray.md section 11, applied
again on the VM because the VM runs the uploaded copy, not the one checked on
rtx3060. `setup` builds Psi0's environment with the same commands as DA-26's
`scripts/he/he1_colab.py install_env`, downloads the baseline parent pair at the
plan's psi-model revision and checks each file against the plan's sha256, then
checks the uploaded cut (`cut_problems`). `train` runs Psi0Trainer with the plan's
recipe and override, the parent of branch C and the plan's train seed, and writes
the `train` phase of `<work>/report.json` the way he1_colab does.

Branch C+ (task 5, `--branch C_PLUS`) runs the same way on the round plan
`configs/runplans/tray/round-tray-cplus.yaml`: everything the v2 checks above ask,
plus the round frozen as `CPLUS_FROZEN` with its targets pinned (`runplan.check_round`),
and a joined cut (`flywheel_psi0.tray.cplus_cut`) whose first part is exactly C's cut
and whose second is the round's targeted set. Recipe, parent and train seed are
branch C's, as the round plan inherits them.

Branch B (task 4, `--branch B`) runs the plan `configs/runplans/tray/he-tray-b.yaml`
once it is frozen as `B_FROZEN` with DA-30's stage 1 checkpoint pinned; until then it
refuses. B is C's job with one change, the VLM: C's cut (set C) goes to
`<work>/sets/B/<env name>`; `setup` copies the stage 1 VLM folder from Google Drive
(`/content/drive/MyDrive/<drive_dir>`, mounted before) to `Psi0/<STAGE1_DIR>`, and
refuses unless its `model.safetensors` and its whole-folder manifest match the plan's
sha256 and every other file is byte for byte the file of C's VLM folder at the plan's
psi-model revision (config, tokenizer, processor: only the weights may differ).
The weights' safetensors header (tensor names, dtypes, shapes) must hash to the plan's
`parent_header_sha256`, the header of C's VLM weights: Qwen3VL `from_pretrained` only
warns on unmatched keys (a `vlm_model.` prefix, a sharded file) and stage 3 would train
from freshly initialised weights. `train` checks the folder again and gives Psi0Trainer
the recipe with the stage 1 parent added in memory (the recipe file is not edited).
The action header is C's.
`manifest --folder <dir>` prints what the plan pins, for whoever fills them (task 4.7).

The four runs of task 6 (`--branch B_ALL|C_ALL|B_70|C_70`) run the paired plan
`configs/runplans/tray/he-tray-pair60k.yaml` (`pairplan`), frozen as `PAIR_FROZEN`
(task 6.2, `rp_e2fb9f62c223`); any other plan id is refused. A branch names its parent
(C's VLM, or DA-30's stage 1 VLM, handled as B's) and its data: the cut ALL or the subset
S70 (`pair_cut`). The data comes from Drive (Drive is mounted before `setup`):
`MyDrive/denso/da34/cuts/<ALL|S70>.tar` with its `.json`, checked for size before and
sha256 after the copy, extracted to `<work>/sets/<name>/<env name>`, then checked
against the plan's pins (`pair_cut.cut_problems`: parts, each episode's own seed, the
subset's list, totals, and ALL's `stats_psi0.json` for both data sizes), all before any
install. Recipe, override (60 000 steps), train seed and action header are the plan's,
the same for all four.

Branch C70_R1 (task 7, `--branch C70_R1`) is the Failure -> Data round on C_70
(`pairround`, `configs/runplans/tray/round-tray-c70.yaml`, docs/he/tray.md 20). It runs
only once that round is frozen with its targets and rules pinned and its id is set as
`ROUND_C70_FROZEN` (the approval, as PAIR_FROZEN was for the four runs); until then it
refuses, whatever the plan file says. Everything but the data is C_70's job: the pair
plan's recipe, overrides and train seed, C_70's parent. The data is
`MyDrive/denso/da34/cuts/C70_R1.tar` (`round_cut pack`), S70 then the targeted set with
ALL's stats, checked by `round_cut.round_problems` before any install.

CUDA toolkit (11/11/2026): the Colab image of that day ships only CUDA 13.0 and no
`nvcc` on PATH, while Psi0's torch is 2.7.0+cu126. A job that builds a C++/CUDA op at
run time (DeepSpeed's ZeRO-3 of stage 1) then fails its pre-flight: DeepSpeed's
CUDAMismatchException, then "Ninja is required". Stage 3 builds none: Psi0 at
PSI0_COMMIT trains it under torchrun with `train.data_parallel ddp` and
`torch.optim.AdamW`, creates the DeepSpeed plugin only for `deepspeed`, imports no
DeepSpeed, triton or `cpp_extension` under `src/psi`, and flash-attn comes as a
prebuilt cu12 wheel. `setup` checks this on the recipe before anything is installed
(`extension_builds`), and records it; a recipe that would build ops is refused unless
`CUDA_HOME` is a CUDA TORCH_CUDA toolkit with `nvcc` and `ninja` is on PATH
(`toolchain_problems`, with the commands that fixed stage 1 in the message).

What happens after is DA-26's code: `scripts/he/he1_colab.py stage` and
`persist` read only `<work>/runs`, `report.json` and `train.log`, and
`scripts/he/he1_fetch.py --remote-work /content/da34` pulls the checkpoints to the
laptop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flywheel_psi0.trainer.colab import (
    FLASH_ATTN_WHEEL,
    PSI0_COMMIT,
    PSI0_REPO,
    Report,
    lock_constraints,
    repair_lock,
    sh,
)
from flywheel_psi0.trainer.recipe import ParentCheckpoint, Psi0Recipe
from flywheel_psi0.tray import pair_cut, pairround, round_cut
from flywheel_psi0.tray.demo_sets import DemoSets, canonical_sha256
from flywheel_psi0.tray.pairplan import TrayPairPlan
from flywheel_psi0.tray.pairplan import check as pair_check
from flywheel_psi0.tray.pairplan import pending as pair_pending
from flywheel_psi0.tray.runplan import (
    REPO,
    Parent,
    Stage1Parent,
    Stage1Vlm,
    TrayRoundPlan,
    TrayRunPlan,
    check,
    check_round,
    file_pin_drift,
    lock_path,
    pinned_file_drift,
    run_plan_id,
    stage1_pending,
)

PLAN = "configs/runplans/tray/he-tray-v2.yaml"
FROZEN = "rp_a04c14e79dfd"  # he-tray-v2.lock.json, merged in #116 (5/11/2026)
BRANCH = "C"  # tier 2: the only branch of the plan (C+ is round-tray-cplus.yaml)
CPLUS_PLAN = "configs/runplans/tray/round-tray-cplus.yaml"
CPLUS_FROZEN = "rp_71fee3fcff69"  # round-tray-cplus.lock.json, frozen 8/11/2026 (task 5.3)
CPLUS = "C_PLUS"
B_PLAN = "configs/runplans/tray/he-tray-b.yaml"
# Set when he-tray-b.yaml is frozen with DA-30's checkpoint pinned (task 4.7); until
# then no B job runs, whatever the plan file says.
B_FROZEN: str | None = None
B = "B"
PAIR_PLAN = "configs/runplans/tray/he-tray-pair60k.yaml"
# he-tray-pair60k.yaml frozen on Hiếu's Decision (task 6.2, 11/11/2026); no job of the
# four runs runs any other plan id, whatever the plan file says.
PAIR_FROZEN: str | None = "rp_e2fb9f62c223"
PAIR = ("B_ALL", "C_ALL", "B_70", "C_70")  # the branches of PAIR_PLAN, checked on load
ROUND_C70_PLAN = "configs/runplans/tray/round-tray-c70.yaml"
# Set to the round's id once Hiếu approves the round (R1-R7 of tray.md 20.9) and it is
# frozen with its targets (task 7.5); until then no C70_R1 job runs.
ROUND_C70_FROZEN: str | None = None
ROUND_C70 = "C70_R1"
DRIVE = Path("/content/drive/MyDrive")  # `colab drivemount -s <session> /content/drive`
STAGE1_DIR = "cache/checkpoints/stage1"  # under Psi0, beside the psi-model snapshot
WEIGHTS = "model.safetensors"  # the one file a stage 1 VLM folder changes
WORK = Path("/content/da34")
MARKER = "flywheel_subset.json"  # written by scripts/he/demo_subset.py and cplus_cut
TORCH_CUDA = "12.6"  # torch 2.7.0+cu126 of Psi0's lock at PSI0_COMMIT (trainer/colab.py)
# Data-parallel modes under which Psi0 builds ops at run time (DeepSpeed's op builder)
BUILDS_OPS = frozenset({"deepspeed"})
TOOLCHAIN_FIX = (
    "apt-get install -y cuda-nvcc-12-6 cuda-cudart-dev-12-6 libcurand-dev-12-6 "
    "libcublas-dev-12-6 && pip install ninja, then run with "
    "CUDA_HOME=/usr/local/cuda-12.6 PATH=/usr/local/cuda-12.6/bin:$PATH "
    "(the fix of DA-30's stage 1 on 11/11/2026)"
)


def extension_builds(recipe: Psi0Recipe, overrides: dict[str, Any]) -> bool:
    """Whether the job builds C++/CUDA ops at run time: only under DeepSpeed in Psi0."""
    mode = overrides.get("train.data_parallel", recipe.args.get("train.data_parallel"))
    return mode in BUILDS_OPS


def cuda_toolkit_version(home: Path) -> str | None:
    """major.minor of the toolkit at `home`, from its version.json (None if unreadable)."""
    try:
        version = json.loads((home / "version.json").read_text())["cuda"]["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return ".".join(str(version).split(".")[:2])


def toolchain_problems(env: dict[str, str] | None = None) -> list[str]:
    """For a job that builds ops: CUDA_HOME a TORCH_CUDA toolkit with nvcc, ninja on PATH."""
    env = dict(os.environ) if env is None else env
    home = env.get("CUDA_HOME")
    problems = []
    if not home:
        problems.append("CUDA_HOME is not set")
    else:
        found = cuda_toolkit_version(Path(home))
        if found != TORCH_CUDA:
            problems.append(f"CUDA_HOME {home} is CUDA {found}, torch is cu{TORCH_CUDA}")
        if not (Path(home) / "bin" / "nvcc").is_file():
            problems.append(f"no nvcc in {home}/bin")
    if shutil.which("ninja", path=env.get("PATH")) is None:
        problems.append("ninja is not on PATH")
    return problems


def load_plan(repo: Path = REPO, plan_file: str = PLAN) -> tuple[TrayRunPlan, str]:
    """The frozen v2 plan and its run_plan_id, or SystemExit with every reason not to run."""
    plan = TrayRunPlan.load(repo / plan_file)
    problems = check(plan, repo)
    problems += [f"{d}: re-freeze or record a Decision" for d in pinned_file_drift(plan, repo)]
    if plan.superseded_by is not None:
        problems.append(f"superseded by {plan.superseded_by}")
    lock = lock_path(repo / plan_file)
    if not lock.is_file():
        problems.append(f"{lock} missing: the plan is not frozen")
    else:
        frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
        if frozen != run_plan_id(plan):
            problems.append(f"{plan_file} changed since it was frozen as {frozen}")
        elif frozen != FROZEN:
            problems.append(f"{lock.name} holds {frozen}; tier 2 approved {FROZEN} only")
    if BRANCH not in plan.branches or plan.budget is None or BRANCH not in plan.budget.runs:
        problems.append(f"branch {BRANCH} has no run in the plan's budget")
    if problems:
        raise SystemExit("plan does not hold, no training:\n  " + "\n  ".join(problems))
    return plan, FROZEN


def load_round(repo: Path = REPO) -> tuple[TrayRunPlan, TrayRoundPlan, str]:
    """The v2 plan (all of load_plan's checks), the frozen C+ round and its id."""
    plan, _ = load_plan(repo)
    round_plan = TrayRoundPlan.load(repo / CPLUS_PLAN)
    problems = check_round(round_plan, repo)
    if round_plan.inherits != PLAN or round_plan.base_branch != BRANCH:
        problems.append(f"{CPLUS_PLAN} does not build on branch {BRANCH} of {PLAN}")
    if round_plan.branch != CPLUS:
        problems.append(f"{CPLUS_PLAN} is branch {round_plan.branch}, not {CPLUS}")
    lock = lock_path(repo / CPLUS_PLAN)
    if round_plan.status != "frozen" or not lock.is_file():
        problems.append(f"{CPLUS_PLAN} is not frozen")
    else:
        frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"]
        if frozen != run_plan_id(round_plan):
            problems.append(f"{CPLUS_PLAN} changed since it was frozen as {frozen}")
        elif frozen != CPLUS_FROZEN:
            problems.append(f"{lock.name} holds {frozen}; the C+ Decision approved {CPLUS_FROZEN}")
    if problems:
        raise SystemExit("round does not hold, no training:\n  " + "\n  ".join(problems))
    return plan, round_plan, CPLUS_FROZEN


def load_b(repo: Path = REPO) -> tuple[TrayRunPlan, str]:
    """The frozen B plan and its run_plan_id, or SystemExit with every reason not to run."""
    plan = TrayRunPlan.load(repo / B_PLAN)
    problems = check(plan, repo)
    problems += [f"{d}: re-freeze or record a Decision" for d in pinned_file_drift(plan, repo)]
    if plan.superseded_by is not None:
        problems.append(f"superseded by {plan.superseded_by}")
    if plan.status == "draft":
        problems.append(f"{B_PLAN} is a draft: no B job runs before task 4.7")
    problems += stage1_pending(plan)
    if plan.variant_of is None or plan.variant_of.run_plan_id != FROZEN:
        problems.append(f"{B_PLAN} is not a variant of {FROZEN}")
    lock = lock_path(repo / B_PLAN)
    frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] if lock.is_file() else None
    if frozen is None:
        problems.append(f"{lock.name} missing: the B plan is not frozen")
    elif frozen != run_plan_id(plan):
        problems.append(f"{B_PLAN} changed since it was frozen as {frozen}")
    if B_FROZEN is None:
        problems.append("no B plan is approved yet: B_FROZEN is unset (task 4.7)")
    elif frozen is not None and frozen != B_FROZEN:
        problems.append(f"{lock.name} holds {frozen}; only {B_FROZEN} is approved for B")
    if B not in plan.branches or plan.budget is None or B not in plan.budget.runs:
        problems.append(f"branch {B} has no run in the plan's budget")
    if problems:
        raise SystemExit("B plan does not hold, no training:\n  " + "\n  ".join(problems))
    assert B_FROZEN is not None
    return plan, B_FROZEN


def load_pair(repo: Path = REPO) -> tuple[TrayPairPlan, str]:
    """The frozen four-run plan and its id, or SystemExit with every reason not to run."""
    plan = TrayPairPlan.load(repo / PAIR_PLAN)
    problems = pair_check(plan, repo) + [f"PENDING: {p}" for p in pair_pending(plan)]
    problems += [
        f"{d}: re-freeze or record a Decision" for d in file_pin_drift(plan.pinned_files, repo)
    ]
    if plan.status == "draft":
        problems.append(f"{PAIR_PLAN} is a draft: no pair job runs before task 6.2")
    lock = lock_path(repo / PAIR_PLAN)
    frozen = json.loads(lock.read_text(encoding="utf-8"))["run_plan_id"] if lock.is_file() else None
    if frozen is None:
        problems.append(f"{lock.name} missing: the pair plan is not frozen")
    elif frozen != run_plan_id(plan):
        problems.append(f"{PAIR_PLAN} changed since it was frozen as {frozen}")
    if PAIR_FROZEN is None:
        problems.append("no pair plan is approved yet: PAIR_FROZEN is unset (task 6.2)")
    elif frozen is not None and frozen != PAIR_FROZEN:
        problems.append(f"{lock.name} holds {frozen}; only {PAIR_FROZEN} is approved")
    if sorted(plan.branches) != sorted(PAIR):
        problems.append(f"the pair plan's branches are {sorted(plan.branches)}, not {PAIR}")
    if problems:
        raise SystemExit("pair plan does not hold, no training:\n  " + "\n  ".join(problems))
    assert PAIR_FROZEN is not None
    return plan, PAIR_FROZEN


def load_pair_round(repo: Path = REPO) -> tuple[TrayPairPlan, pairround.TrayPairRoundPlan, str]:
    """The frozen pair plan (all of load_pair's checks), the frozen round on C_70, its id."""
    path = repo / ROUND_C70_PLAN
    if not path.is_file():
        raise SystemExit(f"{ROUND_C70_PLAN} is missing: no C70_R1 job without the round plan")
    pair, _ = load_pair(repo)
    plan = pairround.TrayPairRoundPlan.load(path)
    problems = pairround.check(plan, repo) + pairround.launch_problems(plan, path)
    if plan.inherits != PAIR_PLAN or plan.branch != ROUND_C70:
        problems.append(f"{ROUND_C70_PLAN} is not branch {ROUND_C70} of {PAIR_PLAN}")
    if ROUND_C70_FROZEN is None:
        problems.append("no round is approved yet: ROUND_C70_FROZEN is unset (tray.md 20.9)")
    elif run_plan_id(plan) != ROUND_C70_FROZEN:
        problems.append(
            f"{ROUND_C70_PLAN} is {run_plan_id(plan)}; only {ROUND_C70_FROZEN} is approved"
        )
    if problems:
        raise SystemExit("round does not hold, no training:\n  " + "\n  ".join(problems))
    assert ROUND_C70_FROZEN is not None
    return pair, plan, ROUND_C70_FROZEN


def pair_job_id(branch: str, seed: int = 0) -> str:
    """`da34-t6-ft-b-all-s0`: Colab session and run folder; ledger job_da34_ft_B_ALL."""
    return f"da34-t6-ft-{branch.lower().replace('_', '-')}-s{seed}"


@dataclass(frozen=True)
class Job:
    """One fine-tune of the tray experiment: C of v2, C+ of its round, B, or a pair run."""

    plan: TrayRunPlan | TrayPairPlan  # the frozen plan: recipe, parent, train seed, task
    run_plan_id: str
    branch: str
    demo_set: str  # what the release id of the run names
    set_hash: str
    release_id: str
    round_plan: TrayRoundPlan | None = None
    plan_branch: str = BRANCH  # the plan's branch whose parent and demo set the job uses
    data_name: str | None = None  # pair runs: the cut (ALL) or the subset (S70) it trains on
    pair_round: pairround.TrayPairRoundPlan | None = None  # C70_R1: the round on C_70

    @property
    def job_id(self) -> str:
        if self.pair_round is not None:
            branch = self.branch.lower().replace("_", "-")
            return f"da34-t7-ft-{branch}-s{self.plan.train_seeds[0]}"
        if self.data_name is not None:
            return pair_job_id(self.branch, self.plan.train_seeds[0])
        if self.branch == BRANCH:
            assert isinstance(self.plan, TrayRunPlan)
            return job_id(self.plan)
        if self.branch == B:
            return f"da34-t4-ft-b-s{self.plan.train_seeds[0]}"
        return f"da34-t5-ft-cplus-s{self.plan.train_seeds[0]}"

    @property
    def parent_name(self) -> str:
        return self.plan.branches[self.plan_branch].parent

    def data(self, work: Path) -> Path:
        folder = self.data_name or self.branch
        return work / "sets" / folder / self.plan.task["env_id"].rsplit("/", 1)[-1]

    def cut_problems(self, data: Path, repo: Path = REPO) -> list[str]:
        if self.pair_round is not None:
            assert isinstance(self.plan, TrayPairPlan)
            return round_cut.round_problems(data, self.pair_round, self.plan, repo)
        if isinstance(self.plan, TrayPairPlan):
            assert self.data_name is not None
            return pair_cut.cut_problems(data, self.plan, self.data_name, repo)
        if self.round_plan is None:
            return cut_problems(data, self.plan, repo, self.plan_branch)
        return cplus_cut_problems(data, self.plan, self.round_plan, repo)


def load_job(branch: str = BRANCH, repo: Path = REPO) -> Job:
    if branch == BRANCH:
        plan, run_plan = load_plan(repo)
        demo_set = plan.branches[BRANCH].demo_set
        return Job(
            plan, run_plan, BRANCH, demo_set, plan.demo_sets.hashes[demo_set], plan.release.id
        )
    if branch == CPLUS:
        plan, round_plan, run_plan = load_round(repo)
        assert round_plan.targets.set_hash is not None and round_plan.targets.release is not None
        return Job(
            plan,
            run_plan,
            CPLUS,
            CPLUS,
            round_plan.targets.set_hash,
            f"{plan.release.id}+{round_plan.targets.release.id}",
            round_plan,
        )
    if branch == B:
        plan, run_plan = load_b(repo)
        demo_set = plan.branches[B].demo_set
        return Job(
            plan,
            run_plan,
            B,
            demo_set,
            plan.demo_sets.hashes[demo_set],
            plan.release.id,
            plan_branch=B,
        )
    if branch in PAIR:
        pair, run_plan = load_pair(repo)
        data_name = pair.data_of(pair.branches[branch])
        subset = pair.subset(data_name)
        hashes = (
            [p.demo_sets.hashes[p.set_name] for p in pair.cut.parts if p.demo_sets and p.set_name]
            if subset is None
            else [sp.seeds_sha256 for sp in subset.parts]
        )
        return Job(
            pair,
            run_plan,
            branch,
            data_name,
            canonical_sha256(hashes),
            "+".join(p.release.id for p in pair.cut.parts if p.release),
            plan_branch=branch,
            data_name=data_name,
        )
    if branch == ROUND_C70:
        pair, pair_round, run_plan = load_pair_round(repo)
        targets = pair_round.targets
        assert targets.set_hash is not None and targets.release is not None
        releases = [p.release.id for p in pair.cut.parts if p.release]
        return Job(
            pair,
            run_plan,
            ROUND_C70,
            ROUND_C70,
            targets.set_hash,
            "+".join([*releases, targets.release.id]),
            plan_branch=pair_round.base_branch,
            data_name=ROUND_C70,
            pair_round=pair_round,
        )
    raise SystemExit(f"no fine-tune for branch {branch}")


def job_id(plan: TrayRunPlan) -> str:
    """`da34-t2-ft-c-s0`: Colab session and run folder; ledger job_da34_ft_C."""
    return f"da34-t2-ft-{BRANCH.lower()}-s{plan.train_seeds[0]}"


def dataset_dir(work: Path, plan: TrayRunPlan) -> Path:
    """Psi0 takes the folder name as the dataset name, like SIMPLE's env id."""
    return work / "sets" / BRANCH / plan.task["env_id"].rsplit("/", 1)[-1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            digest.update(block)
    return digest.hexdigest()


def cut_problems(
    data: Path, plan: TrayRunPlan, repo: Path = REPO, branch: str = BRANCH
) -> list[str]:
    """Everything wrong between a branch's uploaded cut (C's, also B's) and the plan's pins."""
    marker_path = data / "meta" / MARKER
    if not marker_path.is_file():
        return [f"{marker_path} missing: not a demo-set cut"]
    marker: dict[str, Any] = json.loads(marker_path.read_text(encoding="utf-8"))
    sets = DemoSets.model_validate_json((repo / plan.demo_sets.file).read_text(encoding="utf-8"))
    name = plan.branches[branch].demo_set
    demo = sets.sets[name]
    problems = []
    expected = {
        "demo_set": name,
        "set_hash": plan.demo_sets.hashes[name],
        "release_id": plan.release.id,
        "release_hash": plan.release.release_hash,
        "n": demo.n,
    }
    for key, value in expected.items():
        if marker.get(key) != value:
            problems.append(f"cut {key} is {marker.get(key)!r}, the plan's is {value!r}")
    sources = [e["source_episode_index"] for e in marker.get("episodes", [])]
    if sources != demo.episode_indices:
        problems.append(f"cut episodes are not set {name}'s episode indices in the release")
    if [e["episode_index"] for e in marker.get("episodes", [])] != list(range(len(sources))):
        problems.append("cut episodes are not renumbered 0 .. n-1")
    # the dataset Psi0 reads, not only the marker that describes it
    info = data / "meta" / "info.json"
    total = (
        json.loads(info.read_text(encoding="utf-8")).get("total_episodes")
        if info.is_file()
        else None
    )
    if total != demo.n:
        problems.append(f"cut meta/info.json total_episodes is {total!r}, set {name} has {demo.n}")
    rows = data / "meta" / "episodes.jsonl"
    lines = rows.read_text(encoding="utf-8").splitlines() if rows.is_file() else []
    if [json.loads(line)["episode_index"] for line in lines if line.strip()] != list(range(demo.n)):
        problems.append(f"cut meta/episodes.jsonl rows are not episodes 0 .. {demo.n - 1}")
    if not (data / "meta" / "stats_psi0.json").is_file():
        problems.append("cut has no meta/stats_psi0.json (own_train_set stats)")
    return problems


def _dataset_problems(data: Path, n: int) -> list[str]:
    """The dataset Psi0 reads, not only the marker that describes it: n episodes, own stats."""
    problems = []
    info = data / "meta" / "info.json"
    total = (
        json.loads(info.read_text(encoding="utf-8")).get("total_episodes")
        if info.is_file()
        else None
    )
    if total != n:
        problems.append(f"cut meta/info.json total_episodes is {total!r}, the set has {n}")
    rows = data / "meta" / "episodes.jsonl"
    lines = rows.read_text(encoding="utf-8").splitlines() if rows.is_file() else []
    if [json.loads(line)["episode_index"] for line in lines if line.strip()] != list(range(n)):
        problems.append(f"cut meta/episodes.jsonl rows are not episodes 0 .. {n - 1}")
    if not (data / "meta" / "stats_psi0.json").is_file():
        problems.append("cut has no meta/stats_psi0.json (own_train_set stats)")
    return problems


def _part_problems(
    part: dict[str, Any], expected: dict[str, Any], sources: list[int], start: int
) -> list[str]:
    name = expected["demo_set"]
    problems = [
        f"part {name}: {key} is {part.get(key)!r}, the plan's is {value!r}"
        for key, value in expected.items()
        if part.get(key) != value
    ]
    episodes = part.get("episodes", [])
    if [e["source_episode_index"] for e in episodes] != sources:
        problems.append(f"part {name}: episodes are not the set's episode indices in its release")
    if [e["episode_index"] for e in episodes] != list(range(start, start + len(sources))):
        problems.append(f"part {name}: episodes are not renumbered from {start}")
    return problems


def cplus_cut_problems(
    data: Path, plan: TrayRunPlan, round_plan: TrayRoundPlan, repo: Path = REPO
) -> list[str]:
    """Everything wrong between C+'s uploaded joined cut and the two sets it must hold."""
    marker_path = data / "meta" / MARKER
    if not marker_path.is_file():
        return [f"{marker_path} missing: not a demo-set cut"]
    marker: dict[str, Any] = json.loads(marker_path.read_text(encoding="utf-8"))
    targets = round_plan.targets
    if targets.demo_sets is None or targets.release is None or targets.set_name is None:
        return ["the round pins no targeted set"]
    c_sets = DemoSets.model_validate_json((repo / plan.demo_sets.file).read_text("utf-8"))
    t_sets = DemoSets.model_validate_json((repo / targets.demo_sets.file).read_text("utf-8"))
    c_name = plan.branches[BRANCH].demo_set
    c_demo, t_demo = c_sets.sets[c_name], t_sets.sets[targets.set_name]
    n = c_demo.n + t_demo.n
    problems = []
    if (marker.get("demo_set"), marker.get("n")) != (CPLUS, n):
        problems.append(
            f"cut is {marker.get('demo_set')!r} of n={marker.get('n')!r}, not {CPLUS} of {n}"
        )
    parts = marker.get("parts", [])
    if len(parts) != 2:
        return [*problems, f"cut has {len(parts)} parts, C+ has 2 (C, then {targets.set_name})"]
    problems += _part_problems(
        parts[0],
        {
            "demo_set": c_name,
            "set_hash": plan.demo_sets.hashes[c_name],
            "release_id": plan.release.id,
            "release_hash": plan.release.release_hash,
            "n": c_demo.n,
        },
        c_demo.episode_indices,
        0,
    )
    problems += _part_problems(
        parts[1],
        {
            "demo_set": targets.set_name,
            "set_hash": targets.set_hash,
            "release_id": targets.release.id,
            "release_hash": targets.release.release_hash,
            "n": targets.n_add,
        },
        t_demo.episode_indices,
        c_demo.n,
    )
    return problems + _dataset_problems(data, n)


def _files(folder: Path) -> list[Path]:
    """Regular files under folder, by path; dot entries (OS and cache cruft) left out."""
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(folder).parts)
    )


def folder_manifest(folder: Path) -> str:
    """`<sha256>  <path>` per file, sorted by path: what `manifest_sha256` hashes."""
    return "".join(f"{sha256(p)}  {p.relative_to(folder).as_posix()}\n" for p in _files(folder))


def manifest_sha256(folder: Path) -> str:
    return hashlib.sha256(folder_manifest(folder).encode("utf-8")).hexdigest()


def safetensors_header(path: Path) -> dict[str, tuple[str, tuple[int, ...]]]:
    """`{tensor name: (dtype, shape)}` from a safetensors file's JSON header, not its data."""
    with path.open("rb") as f:
        (length,) = struct.unpack("<Q", f.read(8))
        if length > path.stat().st_size - 8:  # not a header length: never read that much
            raise ValueError(f"header length {length} exceeds the file")
        header: dict[str, Any] = json.loads(f.read(length))
    return {
        name: (str(entry["dtype"]), tuple(int(n) for n in entry["shape"]))
        for name, entry in header.items()
        if name != "__metadata__"
    }


def header_sha256(header: dict[str, tuple[str, tuple[int, ...]]]) -> str:
    """Canonical sha256 of `{name: [dtype, shape]}`: what `parent_header_sha256` pins."""
    return canonical_sha256({name: [dtype, list(shape)] for name, (dtype, shape) in header.items()})


def header_summary(header: dict[str, tuple[str, tuple[int, ...]]]) -> str:
    """Tensors, dtypes, lm_head and embedding shape: what to read when the hash differs."""
    dtypes = sorted({dtype for dtype, _ in header.values()})
    embed = [shape for name, (_, shape) in header.items() if name.endswith("embed_tokens.weight")]
    lm_head = any("lm_head" in name for name in header)
    prefixes = sorted({name.split(".", 1)[0] for name in header})
    return (
        f"{len(header)} tensors, dtypes {dtypes}, top-level {prefixes}, lm_head {lm_head},"
        f" embed_tokens {embed}"
    )


def stage1_vlm_problems(folder: Path, base: Path, vlm: Stage1Vlm) -> list[str]:
    """A stage 1 VLM folder against its pins and against the parent VLM folder it came from.

    `base` holds the parent's VLM folder without its weights (config, tokenizer,
    processor). The stage 1 folder must hold exactly those files, byte for byte, plus
    WEIGHTS: stage 1 changes the weights and nothing Qwen3VL or its processor reads
    besides them.
    """
    if not folder.is_dir():
        return [f"{folder} missing: the stage 1 VLM is not there"]
    problems = []
    weights = folder / WEIGHTS
    found = sha256(weights) if weights.is_file() else "missing"
    if found != vlm.weights_sha256:
        problems.append(f"{weights}: sha256 {found}, plan pins {vlm.weights_sha256}")
    if weights.is_file():
        try:
            header = safetensors_header(weights)
        except (OSError, ValueError, KeyError, struct.error) as error:
            problems.append(f"{weights}: no readable safetensors header ({error})")
        else:
            if header_sha256(header) != vlm.parent_header_sha256:
                problems.append(
                    f"{weights}: tensors are not the parent VLM's (header sha256"
                    f" {header_sha256(header)}, plan pins {vlm.parent_header_sha256});"
                    f" {header_summary(header)}"
                )
    found = manifest_sha256(folder)
    if found != vlm.manifest_sha256:
        problems.append(f"{folder}: manifest sha256 {found}, plan pins {vlm.manifest_sha256}")
    mine = {p.relative_to(folder).as_posix(): p for p in _files(folder)}
    theirs = {p.relative_to(base).as_posix(): p for p in _files(base)}
    if WEIGHTS in theirs:
        problems.append(f"{base} holds {WEIGHTS}: download the parent folder without weights")
    for rel in sorted(set(mine) - set(theirs) - {WEIGHTS}):
        problems.append(f"{rel}: not in the parent VLM folder")
    for rel in sorted(set(theirs) - set(mine)):
        problems.append(f"{rel}: missing from the stage 1 VLM folder")
    for rel in sorted(set(mine) & set(theirs)):
        if sha256(mine[rel]) != sha256(theirs[rel]):
            problems.append(f"{rel}: differs from the parent VLM folder's")
    if not theirs:
        problems.append(f"{base}: no parent VLM files to compare with")
    return problems


def stage1_paths(
    plan: TrayRunPlan | TrayPairPlan, parent_name: str, psi0: Path
) -> tuple[Path, Path, Stage1Vlm]:
    """(stage 1 folder on the VM, parent VLM folder of the snapshot, pins) of a B parent."""
    parent = plan.parents[parent_name]
    if not isinstance(parent, Stage1Parent) or parent.vlm_stage1.drive_dir is None:
        raise SystemExit(f"parent {parent_name} is not a pinned stage 1 parent")
    base = plan.parents[parent.vlm_stage1.from_parent]
    assert isinstance(base, Parent)  # runplan.check holds
    folder = psi0 / STAGE1_DIR / Path(parent.vlm_stage1.drive_dir).name
    snapshot = psi0 / "cache/checkpoints" / Path(base.vlm.path).parent
    return folder, snapshot, parent.vlm_stage1


def recipe_for(job: Job, recipe: Psi0Recipe, psi0: Path) -> Psi0Recipe:
    """The recipe a job trains with: B's stage 1 parent added in memory, the file unchanged."""
    parent = job.plan.parents[job.parent_name]
    if not isinstance(parent, Stage1Parent):
        return recipe
    folder, _, vlm = stage1_paths(job.plan, job.parent_name, psi0)
    base = recipe.parents[vlm.from_parent]
    added = ParentCheckpoint(
        model_name_or_path=folder.relative_to(psi0).as_posix(),
        pretrained_action_header_path=base.pretrained_action_header_path,
    )
    return recipe.model_copy(update={"parents": {**recipe.parents, job.parent_name: added}})


def install_env(work: Path) -> float:
    """The commands of scripts/he/he1_colab.py install_env (DA-19 setup, no downloads)."""
    start = time.monotonic()
    psi0 = work / "Psi0"
    if not (psi0 / ".git").exists():
        sh(f"git clone --filter=blob:none {PSI0_REPO} {psi0}")
    sh(f"git checkout -q {PSI0_COMMIT}", cwd=psi0)
    sh("pip install -q uv")
    if not (psi0 / ".venv-psi").exists():
        sh("env -u UV_SYSTEM_PYTHON uv venv .venv-psi --python 3.11", cwd=psi0)
    constraints = work / "psi0-constraints.txt"
    constraints.write_text(lock_constraints(repair_lock((psi0 / "uv.lock").read_text())))
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --python .venv-psi/bin/python "
        f"-e . --group psi -c {constraints}",
        cwd=psi0,
        env={"GIT_LFS_SKIP_SMUDGE": "1"},
    )
    sh(
        f"env -u UV_SYSTEM_PYTHON uv pip install --no-config "
        f"--python {psi0}/.venv-psi/bin/python --no-deps '{FLASH_ATTN_WHEEL}'",
        cwd=work,
    )
    (psi0 / ".env").write_text(
        f"HF_HOME={work}/hf\nTOKENIZERS_PARALLELISM=false\nWANDB_MODE=offline\n"
    )
    return time.monotonic() - start


def setup(work: Path, branch: str = BRANCH, repo: Path = REPO) -> None:
    job = load_job(branch, repo)
    plan = job.plan
    if plan.code["psi0"].commit != PSI0_COMMIT:
        raise SystemExit(f"plan pins Psi0 {plan.code['psi0'].commit}, DA-19 setup {PSI0_COMMIT}")
    recipe = Psi0Recipe.load(repo / plan.recipe.file)
    builds = extension_builds(recipe, dict(plan.recipe.overrides))
    if builds and (problems := toolchain_problems()):  # before any install or download
        raise SystemExit(
            f"{plan.recipe.file} builds CUDA ops at run time and the toolchain does not hold:"
            f"\n  " + "\n  ".join(problems) + f"\nfix: {TOOLCHAIN_FIX}"
        )
    data = job.data(work)
    fetched: dict[str, Any] = {}
    if job.data_name is not None and not (data / "meta").is_dir():  # a pair run: from Drive
        start = time.monotonic()
        fetched = pair_cut.fetch(
            DRIVE / pair_cut.DRIVE_CUTS / f"{job.data_name}.tar", work / "sets"
        )
        if fetched["root"] != f"{job.data_name}/{data.name}":
            raise SystemExit(
                f"the tar holds {fetched['root']}, the job reads {job.data_name}/{data.name}"
            )
        fetched["seconds"] = round(time.monotonic() - start, 1)
    problems = job.cut_problems(data, repo)  # before the env: a wrong upload costs no install
    if problems:
        raise SystemExit(
            f"{job.branch}'s cut does not hold, no training:\n  " + "\n  ".join(problems)
        )
    if isinstance(
        plan.parents[job.parent_name], Stage1Parent
    ):  # before the env too: a missing Drive folder costs no install
        _, _, vlm = stage1_paths(plan, job.parent_name, work / "Psi0")
        assert vlm.drive_dir is not None
        if not (DRIVE / vlm.drive_dir / WEIGHTS).is_file():
            raise SystemExit(f"{DRIVE / vlm.drive_dir / WEIGHTS} missing: mount Drive first")
    env_seconds = install_env(work)
    psi0, python = work / "Psi0", work / "Psi0" / ".venv-psi" / "bin" / "python"
    start = time.monotonic()
    pinned, extra = fetch_parent(job, psi0, python)
    problems = []
    for path, expected in pinned.items():
        found = sha256(path) if path.is_file() else "missing"
        if found != expected:
            problems.append(f"{path}: sha256 {found}, plan pins {expected}")
    if problems:
        raise SystemExit("pinned weights differ, no training:\n  " + "\n  ".join(problems))
    Report(work).phase(
        f"setup_tray_{job.branch.lower()}",
        env_seconds + time.monotonic() - start,
        job_id=job.job_id,
        run_plan_id=job.run_plan_id,
        env_seconds=round(env_seconds, 1),
        download_seconds=round(time.monotonic() - start, 1),
        sha256_checked={str(p.relative_to(work)): h for p, h in pinned.items()},
        demo_set_hash=job.set_hash,
        dataset=str(data),
        cuda_ops_built=builds,  # False: no nvcc or ninja needed (ddp, torch AdamW)
        **({"data_fetched": fetched} if fetched else {}),
        **extra,
    )


def fetch_parent(job: Job, psi0: Path, python: Path) -> tuple[dict[Path, str], dict[str, Any]]:
    """Put the job's parent where its recipe points; return the files to check and report.

    C and C+: the release pair, whole folders, at the plan's psi-model revision. B: the
    action header the same way, the parent VLM folder without its weights (to compare
    with), and the stage 1 VLM folder copied from Drive and checked by stage1_vlm_problems.
    """
    plan = job.plan
    parent = plan.parents[job.parent_name]
    snapshot = psi0 / "cache/checkpoints"
    ignore: list[str] = []
    if isinstance(parent, Parent):
        # whole folders: Psi0 loads each as a directory (config, tokenizer, weights)
        dirs = [w.path.rsplit("/", 1)[0] for w in (parent.vlm, parent.action_header)]
    else:
        base = plan.parents[parent.vlm_stage1.from_parent]
        assert isinstance(base, Parent)
        base_dir = base.vlm.path.rsplit("/", 1)[0]
        dirs = [base_dir, parent.action_header.path.rsplit("/", 1)[0]]
        ignore = [f"{base_dir}/*.safetensors"]  # B never loads the parent's VLM weights
    sh(
        f'{python} -c "from huggingface_hub import snapshot_download; '
        f"snapshot_download('{plan.psi_model.repo}', repo_type='model', "
        f"revision='{plan.psi_model.revision}', allow_patterns={[f'{d}/*' for d in dirs]!r}, "
        f"ignore_patterns={ignore!r}, local_dir='{snapshot}')\""
    )
    if isinstance(parent, Parent):
        return {
            snapshot / parent.vlm.path: parent.vlm.sha256,
            snapshot / parent.action_header.path: parent.action_header.sha256,
        }, {}
    folder, base_folder, vlm = stage1_paths(plan, job.parent_name, psi0)
    assert vlm.drive_dir is not None and vlm.weights_sha256 is not None
    start = time.monotonic()
    if folder.exists():
        shutil.rmtree(folder)  # a rerun copies again rather than trust a partial copy
    shutil.copytree(DRIVE / vlm.drive_dir, folder)
    copy_seconds = time.monotonic() - start
    problems = stage1_vlm_problems(folder, base_folder, vlm)
    if problems:
        raise SystemExit("stage 1 VLM does not hold, no training:\n  " + "\n  ".join(problems))
    return {snapshot / parent.action_header.path: parent.action_header.sha256}, {
        "stage1_vlm": {
            "drive_dir": vlm.drive_dir,
            "folder": str(folder.relative_to(psi0.parent)),
            "weights_sha256": vlm.weights_sha256,
            "manifest_sha256": vlm.manifest_sha256,
            "job_id": vlm.job_id,
            "copy_seconds": round(copy_seconds, 1),
        }
    }


def train(work: Path, branch: str = BRANCH, repo: Path = REPO) -> None:
    from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
    from flywheel.contracts.artifacts import ActionLayout

    from flywheel_psi0.trainer import Psi0Trainer
    from flywheel_psi0.trainer.colab import g1_layout_json

    job = load_job(branch, repo)
    plan = job.plan
    data = job.data(work)
    problems = job.cut_problems(data, repo)
    psi0 = work / "Psi0"
    if isinstance(plan.parents[job.parent_name], Stage1Parent):
        folder, base_folder, vlm = stage1_paths(plan, job.parent_name, psi0)
        problems += stage1_vlm_problems(folder, base_folder, vlm)  # as setup left it
    if problems:
        raise SystemExit(
            f"{job.branch}'s cut or parent does not hold, no training:\n  " + "\n  ".join(problems)
        )
    spec = TrainSpec(
        job_id=job.job_id,
        dataset=DatasetRef(dataset_id=f"{job.release_id}#{job.demo_set}", uri=str(data)),
        # C+ starts where C started: same parent, recipe and seed (round-tray-cplus.yaml);
        # B from its stage 1 parent, added to the recipe by recipe_for
        parent=CheckpointRef(checkpoint_id=job.parent_name),
        seed=plan.train_seeds[0],
    )
    trainer = Psi0Trainer(
        recipe_for(job, Psi0Recipe.load(repo / plan.recipe.file), psi0),
        psi0_root=psi0,
        runs_root=work / "runs",
        layout=ActionLayout.model_validate({"dimensions": g1_layout_json()}),
        run_plan_id=job.run_plan_id,
        release_id=f"{job.release_id}#{job.demo_set}:{job.set_hash[:12]}",
        psi0_commit=PSI0_COMMIT,
        nproc_per_node=plan.recipe.nproc_per_node,
        overrides=dict(plan.recipe.overrides),
    )
    start = time.monotonic()
    result = trainer.train(spec)
    launched = json.loads((work / "runs" / spec.job_id / "result.json").read_text())
    Report(work).phase(  # the phase he1_colab.py stage reads to call a job done
        "train",
        time.monotonic() - start,
        branch=job.branch,
        job_id=spec.job_id,
        run_plan_id=job.run_plan_id,
        infra_status=result.infra_status,
        checkpoint_step=launched.get("checkpoint_step"),
        checkpoint_dir=launched.get("checkpoint_dir"),
        error=launched.get("error"),
        overrides=dict(plan.recipe.overrides),
    )
    if result.infra_status != "ok":
        raise SystemExit(f"train ended {result.infra_status}: {launched.get('error')}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=["setup", "train", "check", "manifest"])
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument(
        "--branch", choices=[BRANCH, CPLUS, B, *PAIR, ROUND_C70], default=BRANCH
    )
    parser.add_argument("--folder", type=Path, help="manifest: a stage 1 VLM folder")
    args = parser.parse_args(argv)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    if args.phase == "manifest":  # what he-tray-b.yaml pins for DA-30's folder (task 4.7)
        if args.folder is None or not (args.folder / WEIGHTS).is_file():
            raise SystemExit(f"manifest needs --folder <a folder with {WEIGHTS}>")
        header = safetensors_header(args.folder / WEIGHTS)
        print(f"header_sha256: {header_sha256(header)} ({header_summary(header)})")
        print(f"weights_sha256: {sha256(args.folder / WEIGHTS)}")
        print(f"manifest_sha256: {manifest_sha256(args.folder)}")
        print(f"files: {len(_files(args.folder))}")
        raise SystemExit(0)
    if args.phase == "check":  # on rtx3060 before the upload, and in tests: no env, no GPU
        job = load_job(args.branch)
        problems = job.cut_problems(job.data(args.work))
        print("\n".join(problems) or f"{job.run_plan_id} {job.job_id}: cut and plan hold")
        raise SystemExit(1 if problems else 0)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == "setup":
        setup(args.work, args.branch)
    else:
        train(args.work, args.branch)


if __name__ == "__main__":
    main()
