#!/usr/bin/env bash
# Serve the published Psi0 checkpoint for the G0 reproduction (S1-03, RunPlan purpose g0_repro).
#
#   bash scripts/g0/serve_psi0.sh setup [--flash-attn]   clone Psi0 at the pinned commit, build its env
#   bash scripts/g0/serve_psi0.sh fetch [--weights]      download the run dir (configs; weights with --weights)
#   bash scripts/g0/serve_psi0.sh check                  smoke check without loading the model
#   bash scripts/g0/serve_psi0.sh serve                  start serve_psi0_simple (needs weights and a GPU)
#
# PSI0_RUNTIME=venv (default) runs in a uv env inside the Psi0 checkout; PSI0_RUNTIME=docker runs in
# the pinned upstream image through docker/psi0/compose.yaml. Every pin below can be overridden from
# the environment. Data stays outside git, under the main checkout's fwdata/ (shared by worktrees).
set -euo pipefail

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
MAIN_REPO="$(cd "$(git -C "$REPO" rev-parse --git-common-dir)/.." && pwd)"

PSI0_COMMIT="${PSI0_COMMIT:-cda3fdfafe47cb6fa75400d013de1bd36e3cea05}"
PSI0_GIT="${PSI0_GIT:-https://github.com/physical-superintelligence-lab/Psi0.git}"
PSI_MODEL_REPO="${PSI_MODEL_REPO:-USC-PSI-Lab/psi-model}"
PSI_MODEL_REV="${PSI_MODEL_REV:-cb1480f50d9764ab2f6261bc2e651a67ad54da17}"
RUN="${RUN:-g1wholebodyxmovebendpickteleop-v0.simple.flow1000.cosine.lr1.0e-04.b112.gpus7.2604100422}"
CKPT_STEP="${CKPT_STEP:-40000}"
PORT="${PORT:-22085}"
DEVICE="${DEVICE:-cuda:0}"
ACTION_EXEC_HORIZON="${ACTION_EXEC_HORIZON:-24}"
RTC_FLAG="${RTC_FLAG:---rtc}"
PSI0_RUNTIME="${PSI0_RUNTIME:-venv}"

PSI0_ROOT="${PSI0_ROOT:-$MAIN_REPO/fwdata/psi0}"
PSI0_SRC="$PSI0_ROOT/Psi0"
PSI0_VENV="$PSI0_SRC/.venv-psi"
RUN_DIR="$PSI0_ROOT/hf/psi0/simple-checkpoints/$RUN"
SMOKE_DIR="$PSI0_ROOT/smoke"
WEIGHTS="$RUN_DIR/checkpoints/ckpt_$CKPT_STEP/model.safetensors"
export PSI0_ROOT PSI0_SRC RUN_DIR

log() { printf '[serve_psi0] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# Run a command inside the Psi0 environment, whichever runtime is selected.
psi_exec() {
  case "$PSI0_RUNTIME" in
    venv)
      [[ -x "$PSI0_VENV/bin/python" ]] || die "no Psi0 env at $PSI0_VENV; run: $0 setup"
      (cd "$PSI0_SRC" && VIRTUAL_ENV="$PSI0_VENV" PATH="$PSI0_VENV/bin:$PATH" "$@") ;;
    docker)
      docker compose -f "$REPO/docker/psi0/compose.yaml" run --rm --no-deps -T psi0 "$@" ;;
    *) die "PSI0_RUNTIME must be venv or docker, got $PSI0_RUNTIME" ;;
  esac
}

cmd_setup() {
  local flash_attn=0
  [[ "${1:-}" == "--flash-attn" ]] && flash_attn=1
  mkdir -p "$PSI0_ROOT"
  if [[ ! -d "$PSI0_SRC/.git" ]]; then
    log "cloning Psi0 into $PSI0_SRC"
    GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none --no-checkout "$PSI0_GIT" "$PSI0_SRC"
  fi
  GIT_LFS_SKIP_SMUDGE=1 git -C "$PSI0_SRC" -c advice.detachedHead=false checkout --quiet "$PSI0_COMMIT"
  # serve_psi0_simple asserts load_dotenv(), which is False for a missing or empty .env.
  [[ -s "$PSI0_SRC/.env" ]] || printf 'PSI_HOME=%s\n' "$PSI0_ROOT" > "$PSI0_SRC/.env"

  if [[ "$PSI0_RUNTIME" == docker ]]; then
    docker compose -f "$REPO/docker/psi0/compose.yaml" pull psi0
    return
  fi
  command -v uv >/dev/null || die "uv not found; install it from https://docs.astral.sh/uv/"
  # Mirrors the README of Psi0 at PSI0_COMMIT; the viz group is not needed to serve. evdev (teleop
  # input devices, needs a C compiler) is not imported anywhere under src/, so it is skipped.
  local sync=(uv sync --frozen --group serve --group psi --index-strategy unsafe-best-match --active
              --no-install-package evdev)
  (cd "$PSI0_SRC" && uv venv --allow-existing .venv-psi --python 3.11)
  if ! (cd "$PSI0_SRC" && GIT_LFS_SKIP_SMUDGE=1 VIRTUAL_ENV="$PSI0_VENV" "${sync[@]}"); then
    # uv.lock at cda3fdf is a broken merge of two locks (pypi.org and a PyPI mirror: repeated
    # tables, packages listed twice), so uv cannot read it. Re-resolve from pyproject.toml, which
    # pins torch, transformers and tyro, and keep the new lock for the record. The authors' exact
    # environment is the pinned image (PSI0_RUNTIME=docker).
    log "upstream uv.lock unusable; re-resolving from pyproject.toml"
    mv "$PSI0_SRC/uv.lock" "$PSI0_SRC/uv.lock.upstream"
    (cd "$PSI0_SRC" && uv lock --index-strategy unsafe-best-match \
      && GIT_LFS_SKIP_SMUDGE=1 VIRTUAL_ENV="$PSI0_VENV" "${sync[@]}")
  fi
  if [[ -f "$PSI0_SRC/uv.lock.upstream" ]]; then
    cp "$PSI0_SRC/uv.lock" "$PSI0_ROOT/uv.lock.relocked"
    log "re-resolved lock: $PSI0_ROOT/uv.lock.relocked ($(sha256sum "$PSI0_ROOT/uv.lock.relocked" | cut -c1-12))"
  fi
  if (( flash_attn )); then
    # Optional: without it Psi0 falls back to PyTorch SDPA. Record a failure on the 5090 (story 2.1).
    psi_exec uv pip install flash_attn==2.7.4.post1 --no-build-isolation
  fi
  psi_exec python -c "import psi, torch; print('psi', psi.__version__, 'torch', torch.__version__)"
}

cmd_fetch() {
  # One --include with several patterns: repeating the flag keeps only the last one.
  local patterns=("psi0/simple-checkpoints/$RUN/*.txt" "psi0/simple-checkpoints/$RUN/*.json")
  [[ "${1:-}" == "--weights" ]] && patterns+=("psi0/simple-checkpoints/$RUN/checkpoints/ckpt_$CKPT_STEP/*")
  psi_exec hf download "$PSI_MODEL_REPO" --revision "$PSI_MODEL_REV" --local-dir "$PSI0_ROOT/hf" \
    --include "${patterns[@]}"
  ls -la "$RUN_DIR" >&2
}

# Everything Server.__init__ of serve_psi0_simple does before it loads the weights, plus the
# hardware facts that decide whether `serve` can work on this machine.
cmd_check() {
  [[ -f "$RUN_DIR/argv.txt" && -f "$RUN_DIR/run_config.json" ]] || die "no run configs in $RUN_DIR; run: $0 fetch"
  mkdir -p "$SMOKE_DIR"
  local out
  out="$SMOKE_DIR/check-$(date +%Y%m%dT%H%M%S).json"
  psi_exec serve_psi0_simple --help >/dev/null || die "serve_psi0_simple --help failed"
  local status=0
  psi_exec python - "$RUN_DIR" "$CKPT_STEP" "$ACTION_EXEC_HORIZON" "$RTC_FLAG" "$PSI0_COMMIT" "$PSI_MODEL_REV" \
    > "$out" <<'PY' || status=$?
import json, os, subprocess, sys
from pathlib import Path

import torch
from transformers import AutoConfig, AutoProcessor

import psi
from psi.models.psi0 import QWEN3VL_VARIANT
from psi.utils import apply_legacy_model_config_defaults, parse_args_to_tyro_config

run_dir, ckpt_step, exec_horizon, rtc_flag, psi0_commit, model_rev = sys.argv[1:7]
run_dir = Path(run_dir)
config = parse_args_to_tyro_config(run_dir / "argv.txt")
launch = config.model_validate(apply_legacy_model_config_defaults(json.loads((run_dir / "run_config.json").read_text())))
model, repack, field = launch.model, launch.data.transform.repack, launch.data.transform.field

chunk, exec_h = model.action_chunk_size, int(exec_horizon)
rtc = rtc_flag == "--rtc"
problems = []
if exec_h > chunk:
    problems.append(f"action_exec_horizon {exec_h} > action_chunk_size {chunk}")
if rtc and exec_h >= chunk:
    problems.append(f"RTC needs action_exec_horizon < action_chunk_size, got {exec_h} >= {chunk}")

# The server builds the VLM from this config and processor before loading weights.
AutoConfig.from_pretrained(QWEN3VL_VARIANT)
AutoProcessor.from_pretrained(QWEN3VL_VARIANT)

weights = run_dir / "checkpoints" / f"ckpt_{ckpt_step}" / "model.safetensors"
cuda = torch.cuda.is_available()
vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9 if cuda else 0.0
weights_gb = weights.stat().st_size / 1e9 if weights.exists() else 6.25
try:
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
except FileNotFoundError:  # images without git; setup already checked the commit out on the host
    git_sha = None
if git_sha is not None and git_sha != psi0_commit:
    problems.append(f"Psi0 checkout at {git_sha}, expected {psi0_commit}")

report = {
    "psi_version": psi.__version__,
    "psi0_commit": git_sha,
    "psi_model_revision": model_rev,
    "torch": torch.__version__,
    "run_dir": str(run_dir),
    "train_repo_ids": list(launch.data.train_repo_ids),
    "protocol": {
        "endpoints": ["GET /health", "GET /info", "POST /act"],
        "transport": "HTTP JSON (FastAPI, uvicorn)",
        "action_dim": model.action_dim,
        "action_chunk_size": chunk,
        "action_exec_horizon_served": exec_h,
        "observation_horizon": model.observation_horizon,
        "pad_state_dim": getattr(repack, "pad_state_dim", None) or getattr(field, "pad_state_dim", None),
        "image_keys": list(getattr(repack, "image_keys", []) or []),
        "image_size": list(launch.data.transform.model.resize.size),
        "rtc_trained": bool(getattr(model, "rtc", False)),
        "rtc_served": rtc,
        "max_delay": getattr(model, "max_delay", None),
    },
    "weights_present": weights.exists(),
    "cuda_available": cuda,
    "gpu": torch.cuda.get_device_name(0) if cuda else None,
    "vram_gb": round(vram_gb, 2),
    "flash_attn": __import__("importlib").util.find_spec("flash_attn") is not None,
    "fits_gpu_bf16": cuda and vram_gb > weights_gb * 1.2,
    "problems": problems,
    "ok": not problems,
}
print(json.dumps(report, indent=2))
sys.exit(0 if report["ok"] else 1)
PY
  cat "$out"
  log "check report: $out"
  return "$status"
}

cmd_serve() {
  [[ -f "$WEIGHTS" ]] || die "no weights at $WEIGHTS; run: $0 fetch --weights"
  log "serving $RUN step $CKPT_STEP on :$PORT ($DEVICE, exec horizon $ACTION_EXEC_HORIZON, $RTC_FLAG)"
  psi_exec serve_psi0_simple --policy psi0 --host 0.0.0.0 --port "$PORT" --device "$DEVICE" \
    --run-dir "$RUN_DIR" --ckpt-step "$CKPT_STEP" \
    --action-exec-horizon "$ACTION_EXEC_HORIZON" "$RTC_FLAG"
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    setup) cmd_setup "$@" ;;
    fetch) cmd_fetch "$@" ;;
    check) cmd_check "$@" ;;
    serve) cmd_serve "$@" ;;
    *) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
  esac
}

# eval_psi0.sh sources this file for the pins and psi_exec.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
