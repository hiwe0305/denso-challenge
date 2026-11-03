#!/usr/bin/env bash
# S1-04 task 6 (AC 7): time a short Psi0 stage 3 run on one Colab A100 or H100.
#
# Runs on the Colab VM (Colab has no Docker), from a copy of this repo at $FW:
#
#   bash scripts/g0/colab_train_probe.sh setup                 # env + checkpoints + data
#   bash scripts/g0/colab_train_probe.sh probe 16 400 200 250  # batch steps every kill_at
#   bash scripts/g0/colab_train_probe.sh probe 64 150 1000 0   # throughput only, no cut
#   bash scripts/g0/colab_train_probe.sh summary               # -> $WORK/probe-summary.json
#
# The environment is the Psi0 image of S1-03 (docker/psi0/compose.yaml) rebuilt without
# Docker: the exact package list read from that image (docker/psi0/requirements-image.txt,
# passed as $REQS) plus psi editable from the pinned checkout, as `serve_psi0.sh setup` does
# with PSI0_ENV=image. Checkpoints and data are fetched at the revisions the team pins.
#
# `probe` runs the stage 3 recipe (configs/models/psi0-stage3.yaml) through Psi0Trainer
# (DA-19), changing only the batch size, step count, checkpoint and validation interval;
# validation keeps the recipe's 20 batches so its cost is measured. With kill_at > 0 the
# first attempt is killed once a train line past kill_at is written and a second attempt
# resumes from the last ckpt_<step>. nvidia-smi samples device memory every second next to
# the job, because Psi0 reports only torch's allocated peak.
set -euo pipefail

WORK=${WORK:-/content/s104}
FW=${FW:-$WORK/fw}
REQS=${REQS:-$WORK/requirements-image.txt}
PSI0_COMMIT=cda3fdfafe47cb6fa75400d013de1bd36e3cea05
PSI_MODEL_REV=cb1480f50d9764ab2f6261bc2e651a67ad54da17 # docs/g0/psi0-eval.md 1.1 (S1-03)
PSI_DATA_REV=e78fb93cc28912a3031a10b8656d32d7f0a2b867  # docs/g0/psi-data.md (train pin)
TASK=G1WholebodyLocomotionPickBetweenTablesTeleop-v0
DATA_SHA256=6cdf9022c23649f68d2faf418a97c47c01aca9d1fac27e9af366116d69927586
PSI0=$WORK/Psi0
PY=${PY:-$PSI0/.venv-psi/bin/python}

log() { echo "[probe $(date +%H:%M:%S)] $*"; }
phase() { # name seconds: append one timed phase to $WORK/phases.jsonl
  printf '{"phase": "%s", "seconds": %s}\n' "$1" "$2" >>"$WORK/phases.jsonl"
}

cmd_setup() {
  mkdir -p "$WORK"
  [[ -f "$REQS" ]] || { echo "missing $REQS (docker/psi0/requirements-image.txt of S1-03)" >&2; exit 1; }
  local t0=$SECONDS
  [[ -d $PSI0/.git ]] || git clone -q --filter=blob:none https://github.com/physical-superintelligence-lab/Psi0.git "$PSI0"
  git -C "$PSI0" checkout -q "$PSI0_COMMIT"
  command -v uv >/dev/null || pip install -q uv
  # Colab sets UV_SYSTEM_PYTHON, which would send every install to its system python.
  (cd "$PSI0" && env -u UV_SYSTEM_PYTHON uv venv --allow-existing .venv-psi --python 3.11)
  (cd "$PSI0" && GIT_LFS_SKIP_SMUDGE=1 env -u UV_SYSTEM_PYTHON uv pip install --python "$PY" -r "$REQS" \
    && env -u UV_SYSTEM_PYTHON uv pip install --python "$PY" --no-deps -e .)
  # scripts/train.py asserts load_dotenv(); W&B stays offline.
  printf 'HF_HOME=%s/hf\nTOKENIZERS_PARALLELISM=false\nWANDB_MODE=offline\n' "$WORK" >"$PSI0/.env"
  "$PY" -c "import psi, torch, flash_attn; print('torch', torch.__version__, 'flash_attn', flash_attn.__version__, torch.cuda.get_device_name(0))"
  phase env $((SECONDS - t0))

  t0=$SECONDS
  "$PY" - "$PSI0/cache/checkpoints" "$WORK/data" <<EOF
import sys
from huggingface_hub import snapshot_download
ckpts, data = sys.argv[1:]
snapshot_download("USC-PSI-Lab/psi-model", revision="$PSI_MODEL_REV", local_dir=ckpts,
    allow_patterns=["psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k/*",
                    "psi0/postpre.1by1.pad36.2601131206.ckpt.he30k/*"])
snapshot_download("USC-PSI-Lab/psi-data", repo_type="dataset", revision="$PSI_DATA_REV",
    local_dir=data, allow_patterns=["simple/$TASK.zip"])
EOF
  echo "$DATA_SHA256  $WORK/data/simple/$TASK.zip" | sha256sum -c -
  [[ -d $WORK/data/simple/$TASK/meta ]] || unzip -q -o "$WORK/data/simple/$TASK.zip" -d "$WORK/data/simple"
  phase download $((SECONDS - t0))
}

cmd_probe() {
  local batch=$1 steps=$2 every=$3 kill_at=$4
  local job="s104-b$batch"
  mkdir -p "$WORK/runs/$job"
  nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader,nounits -lms 1000 \
    >"$WORK/runs/$job/nvidia-smi.csv" &
  local sampler=$! t0=$SECONDS status=0
  PYTHONPATH="$FW/packages/flywheel-psi0/src:$FW/packages/flywheel-contracts/src" \
    "$PY" - "$WORK" "$FW" "$job" "$batch" "$steps" "$every" "$kill_at" <<'EOF' || status=$?
import json, sys
from pathlib import Path

from flywheel.contracts import CheckpointRef, DatasetRef, TrainSpec
from flywheel.contracts.artifacts import ActionLayout
from flywheel_psi0.trainer import Psi0Recipe, Psi0Trainer
from flywheel_psi0.trainer.colab import PARENT, PSI0_COMMIT, TASK, g1_layout_json, interrupting_runner
from flywheel_psi0.trainer.psi0_trainer import run_subprocess

work, fw, job = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
batch, steps, every, kill_at = map(int, sys.argv[4:8])
spec = TrainSpec(
    job_id=job,
    dataset=DatasetRef(dataset_id=f"psi-data-{TASK}", uri=str(work / "data" / "simple" / TASK)),
    parent=CheckpointRef(checkpoint_id=PARENT),
    seed=292285,
)
# Only what a short probe must change; validation keeps the recipe's 20 batches.
overrides = {
    "train.train_batch_size": batch,
    "train.max_training_steps": steps,
    "train.checkpointing_steps": every,
    "train.validation_steps": every,
}
metrics = work / "runs" / job / "metrics.jsonl"
attempts = []
for attempt in (0, 1) if kill_at else (0,):
    runner = interrupting_runner(metrics, attempt, kill_at) if attempt == 0 and kill_at else run_subprocess
    trainer = Psi0Trainer(
        Psi0Recipe.load(fw / "configs" / "models" / "psi0-stage3.yaml"),
        psi0_root=work / "Psi0",
        runs_root=work / "runs",
        layout=ActionLayout.model_validate({"dimensions": g1_layout_json()}),
        run_plan_id="rp-s104-probe",
        release_id=f"psi-data-{TASK}",
        psi0_commit=PSI0_COMMIT,
        overrides=overrides,
        runner=runner,
    )
    result = trainer.train(spec)
    attempts.append({"attempt": attempt, "infra_status": result.infra_status,
                     **json.loads((work / "runs" / job / "result.json").read_text())})
(work / "runs" / job / "probe.json").write_text(json.dumps(
    {"job": job, "batch": batch, "steps": steps, "every": every, "kill_at": kill_at,
     "overrides": overrides, "attempts": attempts}, indent=2, default=str))
EOF
  kill "$sampler" 2>/dev/null || true
  phase "probe-$job" $((SECONDS - t0))
  return "$status"
}

cmd_summary() {
  "$PY" - "$WORK" <<'EOF'
import json, statistics, sys
from pathlib import Path

work = Path(sys.argv[1])
out = {"phases": [json.loads(l) for l in (work / "phases.jsonl").read_text().splitlines()]}
for probe in sorted(work.glob("runs/*/probe.json")):
    job_dir = probe.parent
    info = json.loads(probe.read_text())
    rows = [json.loads(l) for l in (job_dir / "metrics.jsonl").read_text().splitlines()]
    every = info["every"]
    per_attempt = {}
    for attempt in sorted({r["attempt"] for r in rows}):
        lines = [r for r in rows if r["attempt"] == attempt]
        train = [r for r in lines if r["split"] == "train"]
        clean, val, ckpt = [], [], []
        for prev, cur in zip(lines, lines[1:]):
            gap = cur["wall_time_s"] - prev["wall_time_s"]
            if cur["split"] == "val":
                val.append(gap)  # evaluate() on 20 val batches, plus the extra train-batch sample
            elif prev["split"] == "train" and cur["step"] == prev["step"] + 1:
                # The train line of a checkpoint step also carries save_checkpoint.
                (ckpt if cur["step"] % every == 0 else clean).append(gap)
        step_s = statistics.median(clean) if clean else None
        per_attempt[attempt] = {
            "first_step": train[0]["step"] if train else None,
            "last_step": train[-1]["step"] if train else None,
            "startup_s": train[0]["wall_time_s"] if train else None,
            "step_s_median": step_s,
            "step_s_p90": statistics.quantiles(clean, n=10)[-1] if len(clean) >= 10 else None,
            "n_clean_steps": len(clean),
            "val_s": val,
            "ckpt_extra_s": [g - step_s for g in ckpt] if step_s else ckpt,
            "torch_peak_vram_gb": max((r["vram_gb"] or 0) for r in lines) if lines else None,
            "loss_last": train[-1]["loss"] if train else None,
        }
    smi = [l.split(", ") for l in (job_dir / "nvidia-smi.csv").read_text().splitlines() if l.count(",") == 2]
    out[info["job"]] = {
        "batch": info["batch"],
        "attempts": per_attempt,
        "infra_status": [a["infra_status"] for a in info["attempts"]],
        "errors": [a.get("error") for a in info["attempts"] if a.get("error")],
        "smi_peak_mib": max((int(m) for _, m, _ in smi), default=None),
        "smi_util_median": statistics.median(int(u) for _, _, u in smi) if smi else None,
        "samples_per_s": info["batch"] / per_attempt[0]["step_s_median"] if per_attempt.get(0, {}).get("step_s_median") else None,
    }
(work / "probe-summary.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
EOF
}

cmd=${1:?usage: colab_train_probe.sh setup|probe B STEPS EVERY KILL_AT|summary}
shift
"cmd_$cmd" "$@"
