#!/usr/bin/env bash
# Client side of the G0 reproduction (S1-03). Talks to a server started by serve_psi0.sh serve.
#
#   bash scripts/g0/eval_psi0.sh smoke [--host H] [--calls N]   /health, /info and N dummy /act calls
#   bash scripts/g0/eval_psi0.sh run --level L --sim-mode M [--episodes N] [--episode-start S] [--pass K]
#       SIMPLE eval-decoupled-wbc of TASK (default the two-table task) on the published conditions
#       of level L, in SIMPLE's image; results and pins in fwdata/simple/s103/runs/<M>/level-L/...
#       Serve the matching checkpoint first, e.g. RUN=<two-table run> serve_psi0.sh serve.
#
# smoke does not need SIMPLE: it sends zero images and zero state, so the actions are meaningless,
# but it proves the checkpoint loads and that /act answers with an (exec horizon, action dim) chunk.
set -euo pipefail
# shellcheck source=serve_psi0.sh
source "$(dirname "${BASH_SOURCE[0]}")/serve_psi0.sh"

cmd_smoke() {
  local host=127.0.0.1 calls=3
  while (( $# )); do
    case "$1" in
      --host) host="$2"; shift 2 ;;
      --calls) calls="$2"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  mkdir -p "$SMOKE_DIR"
  local out status=0
  out="$SMOKE_DIR/smoke-$(date +%Y%m%dT%H%M%S).json"
  psi_exec python - "http://$host:$PORT" "$calls" "$RUN" "$CKPT_STEP" "$PSI_MODEL_REV" > "$out" <<'PY' || status=$?
import json, re, shutil, subprocess, sys, time

import numpy as np
import requests

from psi.deploy.helpers import RequestMessage, ResponseMessage

base, calls, run, ckpt_step, model_rev = sys.argv[1], int(sys.argv[2]), *sys.argv[3:6]
problems = []

health = requests.get(f"{base}/health", timeout=10)
if health.status_code != 200 or health.json().get("status") != "ok":
    problems.append(f"/health returned {health.status_code} {health.text[:200]}")
info = requests.get(f"{base}/info", timeout=10).json()
act_spec = info["action"]
exec_h, action_dim = act_spec["action_exec_horizon"], act_spec["action_dim"]
height, width = info["transforms"][0]["size"]
image_keys = list(info["expected_keys"]["image"]) or ["observation.images.head"]
state_dim = int(re.search(r"padded to (\d+)", info["expected_keys"]["state"]["states"]).group(1))

latencies, shapes = [], []
for i in range(calls):
    request = RequestMessage(
        image={key: np.zeros((height, width, 3), dtype=np.uint8) for key in image_keys},
        instruction="smoke test",
        # The first call resets RTC state; later calls exercise the RTC path.
        history={"reset": True} if i == 0 else {},
        state={"states": np.zeros((1, state_dim), dtype=np.float32)},
        condition={},
        gt_action=np.zeros((1, action_dim), dtype=np.float32),
        dataset_name="simple",
        timestamp=str(time.time()),
    )
    start = time.perf_counter()
    reply = requests.post(f"{base}/act", json=request.serialize(), timeout=600)
    latencies.append(time.perf_counter() - start)
    body = reply.json()
    # On an exception the server still answers 200, with {"status": "<error>"} instead of an action.
    if not isinstance(body, dict) or "action" not in body:
        problems.append(f"/act call {i}: no action in reply: {str(body)[:300]}")
        break
    action = np.asarray(ResponseMessage.deserialize(body).action)
    shapes.append(list(action.shape))
    if action.shape != (exec_h, action_dim):
        problems.append(f"/act call {i}: action shape {action.shape}, expected {(exec_h, action_dim)}")
    if not np.isfinite(action).all():
        problems.append(f"/act call {i}: non-finite action values")

vram = None
if shutil.which("nvidia-smi"):
    vram = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.strip()

report = {
    "server": base,
    "run": run,
    "ckpt_step": ckpt_step,
    "psi_model_revision": model_rev,
    "info": info,
    "calls": calls,
    "action_shapes": shapes,
    # The first call includes warm-up; it is not a cycle latency.
    "latency_s": [round(x, 3) for x in latencies],
    "gpu_memory_after": vram,
    "problems": problems,
    "ok": not problems,
}
print(json.dumps(report, indent=2))
sys.exit(0 if report["ok"] else 1)
PY
  cat "$out"
  log "smoke report: $out"
  return "$status"
}

# SIMPLE client in the authors' published image, pinned by digest, so `mujoco` and `mujoco_isaac`
# runs use the same SIMPLE build (Isaac Sim 4.5 is only in the image). Tag latest on 3/11/2026,
# built 30/08/2026; its eval_decoupled_wbc.py and psi0_decoupled_wbc.py equal SIMPLE 6d10628.
SIMPLE_IMAGE="${SIMPLE_IMAGE:-ghcr.io/physical-superintelligence-lab/simple@sha256:38a674039f413ca171d5f8f841c2b9a9d67771fdaf7bcc73c4777fdfcb7a561f}"
TASK="${TASK:-G1WholebodyLocomotionPickBetweenTablesTeleop-v0}"
# Published eval conditions: psi-data simple-eval/<TASK>.zip, one LeRobot dir per level.
PSI_DATA_REV="${PSI_DATA_REV:-de140d67ba77a541f2a58354f7edf4e2480b7c56}"
SIMPLE_DATA="${SIMPLE_DATA:-$MAIN_REPO/fwdata/simple/s103}"
# A SIMPLE data/ tree with assets, robots and scenes already downloaded; mounted read-only.
SIMPLE_ASSETS="${SIMPLE_ASSETS:-$MAIN_REPO/fwdata/simple/SIMPLE/data}"

cmd_run() {
  local level=0 sim_mode=mujoco_isaac episodes=10 start=0 pass=1 host=127.0.0.1
  while (( $# )); do
    case "$1" in
      --level) level="$2"; shift 2 ;;
      --sim-mode) sim_mode="$2"; shift 2 ;;
      --episodes) episodes="$2"; shift 2 ;;
      --episode-start) start="$2"; shift 2 ;;
      --pass) pass="$2"; shift 2 ;;
      --host) host="$2"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  local conds="$SIMPLE_DATA/evals/simple-eval/$TASK/dr-level-$level"
  if [[ ! -d "$conds" ]]; then
    mkdir -p "$SIMPLE_DATA/evals/simple-eval"
    curl -sfL -o "$SIMPLE_DATA/evals/simple-eval/$TASK.zip" \
      "https://huggingface.co/datasets/USC-PSI-Lab/psi-data/resolve/$PSI_DATA_REV/simple-eval/$TASK.zip"
    unzip -q -o "$SIMPLE_DATA/evals/simple-eval/$TASK.zip" -d "$SIMPLE_DATA/evals/simple-eval"
  fi
  [[ -d "$conds" ]] || die "no eval conditions at $conds"
  local tag="$sim_mode/level-$level/pass-$pass/ep$start-$((start + episodes - 1))"
  local out="$SIMPLE_DATA/runs/$tag"
  [[ -e "$out/eval_stats.txt" ]] && die "$out already has results; use another --pass"
  # Pre-create the read-only mount points, or dockerd creates them root-owned.
  mkdir -p "$out" "$SIMPLE_DATA"/{assets,robots,scenes}
  curl -sf "http://$host:$PORT/health" >/dev/null || die "no Psi0 server on $host:$PORT; run: serve_psi0.sh serve"

  # Isaac Sim (Kit) writes its shader, material and log caches under the image venv's omni/ dir,
  # which a non-root user cannot create; without them startup stalls after "app ready". Host dirs
  # also keep the shader cache warm across runs. HOME holds Documents/Kit and ~/.cache/ov.
  local omni=/workspace/simple/.venv/lib/python3.10/site-packages/omni kit="$SIMPLE_DATA/kit"
  mkdir -p "$kit"/{cache,data,logs,home}
  local begin end status=0
  begin=$(date +%s)
  # Each mount of SIMPLE_ASSETS is read-only; outputs go to SIMPLE_DATA only.
  docker run --rm --name "s103-eval-$sim_mode-l$level-p$pass-$start" --runtime nvidia --network host \
    --user "${FW_UID:-$(id -u)}:${FW_GID:-$(id -g)}" --shm-size 16g \
    --memory "${SIMPLE_MEM_LIMIT:-20g}" --memory-swap "${SIMPLE_MEM_LIMIT:-20g}" \
    -e NVIDIA_VISIBLE_DEVICES="${GPUS:-0}" -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    -e OMNI_KIT_ACCEPT_EULA=Y -e MUJOCO_GL=egl -e HOME=/kit-home -e DEBUG=1 \
    -v "$kit/cache:$omni/cache" -v "$kit/data:$omni/data" -v "$kit/logs:$omni/logs" \
    -v "$kit/home:/kit-home" \
    -v "$SIMPLE_DATA:/workspace/simple/data" \
    -v "$SIMPLE_ASSETS/assets:/workspace/simple/data/assets:ro" \
    -v "$SIMPLE_ASSETS/robots:/workspace/simple/data/robots:ro" \
    -v "$SIMPLE_ASSETS/scenes:/workspace/simple/data/scenes:ro" \
    -w /workspace/simple --entrypoint /workspace/simple/.venv/bin/eval-decoupled-wbc "$SIMPLE_IMAGE" \
    "simple/$TASK" psi0_decoupled_wbc "dr-level-$level" \
    --host "$host" --port "$PORT" --sim-mode "$sim_mode" --headless \
    --data-format lerobot --data-dir "data/evals/simple-eval/$TASK/dr-level-$level" \
    --episode-start "$start" --num-episodes "$episodes" --eval-dir "data/runs/$tag" \
    > "$out/client.log" 2>&1 || status=$?
  end=$(date +%s)
  # SIMPLE writes videos to data/evals/<policy>/<server tag>.<task>/dr-level-L/episode_N, shared by
  # every pass and sim mode; move them next to this run's results before the next run overwrites them.
  local ep
  for ep in "$SIMPLE_DATA"/evals/psi0_decoupled_wbc/*."$TASK/dr-level-$level"/episode_*; do
    [[ -d "$ep" ]] && mkdir -p "$out/videos" && mv "$ep" "$out/videos/"
  done

  # Revisions and outcome in one file per invocation (story test: same config, recorded pins).
  python3 - "$out" "$status" "$((end - begin))" "$sim_mode" "$level" "$pass" "$start" "$episodes" \
    "$RUN" "$CKPT_STEP" "$PSI_MODEL_REV" "$PSI0_COMMIT" "$PSI_DATA_REV" "$SIMPLE_IMAGE" \
    "$ACTION_EXEC_HORIZON" "$RTC_FLAG" "$host:$PORT" "$TASK" <<'PY'
import json, re, sys
from pathlib import Path

out = Path(sys.argv[1])
(status, seconds, sim_mode, level, pass_, start, episodes, run, ckpt_step, model_rev, psi0_commit,
 data_rev, image, exec_h, rtc, server, task) = sys.argv[2:19]
lines = (out / "eval_stats.txt").read_text().splitlines() if (out / "eval_stats.txt").exists() else []
results = {m[1]: m[2] == "True" for l in lines if (m := re.match(r"(episode_\d+): (True|False)", l.strip()))}
summary = {
    "task": task,
    "sim_mode": sim_mode, "level": int(level), "pass": int(pass_),
    "episode_start": int(start), "episodes_requested": int(episodes),
    "results": results, "n": len(results), "successes": sum(results.values()),
    "client_exit": int(status), "wall_seconds": int(seconds),
    "server": server, "run": run, "ckpt_step": int(ckpt_step), "psi_model_revision": model_rev,
    "psi0_commit": psi0_commit, "action_exec_horizon": int(exec_h), "rtc": rtc == "--rtc",
    "psi_data_revision": data_rev, "simple_image": image,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("sim_mode", "level", "pass", "n", "successes", "client_exit", "wall_seconds")}))
PY
  log "run report: $out/summary.json"
  return "$status"
}

case "${1:-}" in
  smoke) shift; cmd_smoke "$@" ;;
  run) shift; cmd_run "$@" ;;
  *) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
