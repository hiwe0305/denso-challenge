#!/usr/bin/env bash
# Client side of the G0 reproduction (S1-03). Talks to a server started by serve_psi0.sh serve.
#
#   bash scripts/g0/eval_psi0.sh smoke [--host H] [--calls N]   /health, /info and N dummy /act calls
#   bash scripts/g0/eval_psi0.sh run                            SIMPLE evaluation, 3 levels x 30 (subtask 3)
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

case "${1:-}" in
  smoke) shift; cmd_smoke "$@" ;;
  run) die "SIMPLE evaluation is subtask 3 of S1-03 and is not written yet" ;;
  *) sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
