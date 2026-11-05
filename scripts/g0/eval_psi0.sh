#!/usr/bin/env bash
# Client side of the G0 reproduction (S1-03). Talks to a server started by serve_psi0.sh serve.
#
#   bash scripts/g0/eval_psi0.sh smoke [--host H] [--calls N]   /health, /info and N dummy /act calls
#   bash scripts/g0/eval_psi0.sh run --level L --sim-mode M [--episodes N] [--episode-start S] [--pass K]
#       SIMPLE eval-decoupled-wbc of TASK (default the two-table task) on the published conditions
#       of level L, in SIMPLE's image; results and pins in fwdata/simple/s103/runs/<M>/level-L/...
#       Serve the matching checkpoint first, e.g. RUN=<two-table run> serve_psi0.sh serve.
#   bash scripts/g0/eval_psi0.sh openloop --data DIR --images real|gray|blur|shift   benchmark B4
#   bash scripts/g0/eval_psi0.sh delay-proxy --listen P --delay S --log FILE        benchmark B3
#   bash scripts/g0/eval_psi0.sh replay-server --train DIR [--first N] [--listen P]  benchmark B6
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
# Published eval conditions: psi-data simple-eval/<TASK>.zip, one LeRobot dir per level. Pinned by
# revision (PO 3/11/2026, PR #68); the zip is checked against the LFS sha256 Hugging Face reports.
PSI_DATA_REV="${PSI_DATA_REV:-de140d67ba77a541f2a58354f7edf4e2480b7c56}"
# The image's two-table task file is SIMPLE 6d10628's, which spawns the arms raised (the fingers hit
# table 1 and push the robot back 0.1-0.28 m). Mount the file from SIMPLE b75c678 (upstream 77872fe:
# zero arm init_qpos, as in the data), the SIMPLE pin since PR #68. SIMPLE_TASK_FIX=off reproduces
# the image as is. The image's robot, agent and policy files already equal b75c678.
SIMPLE_TASK_FIX="${SIMPLE_TASK_FIX:-on}"
SIMPLE_FIX_COMMIT="${SIMPLE_FIX_COMMIT:-b75c6786f87b4a7f43b52b0ac5b83a1d9ea62e11}"
SIMPLE_FIX_FILE=src/simple/tasks/g1_wholebody_locomotion_pick_between_tables_teleop.py
SIMPLE_FIX_SHA256="${SIMPLE_FIX_SHA256:-51bce5d6c0311219d9a827b589910d915521dccc89b69a1ab20ff35081b6dc8f}"
# DDS domain of the client. Every SIMPLE env calls ChannelFactoryInitialize(DOMAIN_ID); DOMAIN_ID
# comes only from gear_sonic's wbc_configs/g1_29dof_sonic_model12.yaml (0; override_wbc_config does
# not touch it, and eval passes no CLI args to SimLoopConfig), so every SIMPLE run on a box shares
# domain 0. A non-zero value mounts a copy of that yaml with this DOMAIN_ID; 0 keeps the image's.
SIMPLE_DDS_DOMAIN="${SIMPLE_DDS_DOMAIN:-103}"
# Clock of the eval loop. Unset: the image's eval-decoupled-wbc as SIMPLE ships (wall clock).
# sim | wall: run it through docker/psi0/simtime_eval.py, mounted into the image; sim makes
# time.monotonic() the MuJoCo time of the evaluated env and sleep() return at once in the eval loop,
# psi0_decoupled_wbc and the sonic WBC agent; wall changes nothing on the same code path. DA-34
# found the wall clock changes outcomes on a loaded box (docs/he/tray.md 8.1). flywheel_simple's
# tray wrapper (#90) is not used: its sim clock reads the tray env and is wall time for this task.
SIMPLE_EVAL_CLOCK="${SIMPLE_EVAL_CLOCK:-}"
WBC_YAML=/workspace/simple/third_party/gear_sonic/utils/mujoco_sim/wbc_configs/g1_29dof_sonic_model12.yaml
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
  # One cache dir per revision, so another PSI_DATA_REV never reuses these conditions.
  local evals="evals/simple-eval-${PSI_DATA_REV:0:7}"
  local conds="$SIMPLE_DATA/$evals/$TASK/dr-level-$level" zip="$SIMPLE_DATA/$evals/$TASK.zip"
  if [[ ! -d "$conds" ]]; then
    mkdir -p "$SIMPLE_DATA/$evals"
    curl -sfL -o "$zip" "https://huggingface.co/datasets/USC-PSI-Lab/psi-data/resolve/$PSI_DATA_REV/simple-eval/$TASK.zip"
    local want got
    want=$(curl -sf "https://huggingface.co/api/datasets/USC-PSI-Lab/psi-data/paths-info/$PSI_DATA_REV" \
      -d "paths=simple-eval/$TASK.zip&expand=true" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['lfs']['oid'])")
    got=$(sha256sum "$zip" | cut -d' ' -f1)
    [[ -n "$want" && "$want" == "$got" ]] || die "eval zip sha256 $got != LFS oid ${want:-?} at $PSI_DATA_REV"
    unzip -q -o "$zip" -d "$SIMPLE_DATA/$evals"
  fi
  [[ -d "$conds" ]] || die "no eval conditions at $conds"
  local entry=(--entrypoint /workspace/simple/.venv/bin/eval-decoupled-wbc) clock_args=() clock="image"
  if [[ -n "$SIMPLE_EVAL_CLOCK" ]]; then
    [[ "$SIMPLE_EVAL_CLOCK" == sim || "$SIMPLE_EVAL_CLOCK" == wall ]] || die "SIMPLE_EVAL_CLOCK must be sim or wall"
    entry=(--entrypoint /workspace/simple/.venv/bin/python)
    clock_args=(-v "$REPO/docker/psi0/simtime_eval.py:/opt/s103/simtime_eval.py:ro")
    clock="$SIMPLE_EVAL_CLOCK (docker/psi0/simtime_eval.py)"
  fi
  local fix_mount=() task_file="image (SIMPLE 6d10628)"
  if [[ "$SIMPLE_TASK_FIX" == on ]]; then
    local fix="$SIMPLE_DATA/patches/${SIMPLE_FIX_COMMIT:0:7}/$(basename "$SIMPLE_FIX_FILE")"
    if [[ ! -f "$fix" ]]; then
      mkdir -p "$(dirname "$fix")"
      curl -sfL -o "$fix" "https://raw.githubusercontent.com/physical-superintelligence-lab/SIMPLE/$SIMPLE_FIX_COMMIT/$SIMPLE_FIX_FILE"
    fi
    [[ "$(sha256sum "$fix" | cut -d' ' -f1)" == "$SIMPLE_FIX_SHA256" ]] || die "task file $fix does not match SIMPLE_FIX_SHA256"
    fix_mount=(-v "$fix:/workspace/simple/$SIMPLE_FIX_FILE:ro")
    task_file="SIMPLE ${SIMPLE_FIX_COMMIT:0:7} (sha256 ${SIMPLE_FIX_SHA256:0:12})"
  fi
  local dds_mount=()
  if [[ "$SIMPLE_DDS_DOMAIN" != 0 ]]; then
    local yaml="$SIMPLE_DATA/patches/dds-$SIMPLE_DDS_DOMAIN/$(basename "$WBC_YAML")"
    mkdir -p "$(dirname "$yaml")"
    docker run --rm --entrypoint cat "$SIMPLE_IMAGE" "$WBC_YAML" \
      | sed -E "s/^DOMAIN_ID: 0( |$)/DOMAIN_ID: $SIMPLE_DDS_DOMAIN\1/" > "$yaml"
    grep -q "^DOMAIN_ID: $SIMPLE_DDS_DOMAIN\b" "$yaml" || die "could not set DOMAIN_ID in $yaml"
    dds_mount=(-v "$yaml:$WBC_YAML:ro")
  elif [[ "${SIMPLE_ALLOW_SHARED:-0}" != 1 ]]; then
    # On domain 0, run alone. This eval path opens no DDS publisher or subscriber (SIMPLE b75c678),
    # but teleop/replay/WBC runs of other stories do.
    local others
    others=$(ps -eo pid=,args= | grep -E "eval-decoupled-wbc|teleop-decoupled-wbc|replay-decoupled-wbc|flywheel_simple|gear_sonic|simple/\.venv/bin/python|pytest .*-m sim" \
      | grep -v -E "grep|eval_psi0.sh" || true)
    [[ -z "$others" ]] || die "other SIMPLE processes share DDS domain 0; wait, set SIMPLE_DDS_DOMAIN, or SIMPLE_ALLOW_SHARED=1:
$others"
  fi
  # The client trusts the server for run, checkpoint and RTC; check it serves this task.
  local info
  info=$(curl -sf "http://$host:$PORT/info") || die "no Psi0 server on $host:$PORT; run: serve_psi0.sh serve"
  local task_lc="${TASK,,}"
  [[ "$info" == *"${task_lc%-v0}"* ]] || die "server on $host:$PORT does not serve $TASK: $(head -c 200 <<<"$info")"
  local simple_tag="simple-${SIMPLE_FIX_COMMIT:0:7}${SIMPLE_EVAL_CLOCK:+-clock-$SIMPLE_EVAL_CLOCK}"
  [[ "$SIMPLE_TASK_FIX" == on ]] || simple_tag="simple-6d10628"
  # Runs before 4/11/2026 00:35 (all on de140d6) have no eval-<rev> component in their path.
  local tag="$simple_tag/eval-${PSI_DATA_REV:0:7}/$sim_mode/level-$level/pass-$pass/ep$start-$((start + episodes - 1))"
  local out="$SIMPLE_DATA/runs/$tag"
  [[ -e "$out/eval_stats.txt" ]] && die "$out already has results; use another --pass"
  # Pre-create the read-only mount points, or dockerd creates them root-owned.
  mkdir -p "$out" "$SIMPLE_DATA"/{assets,robots,scenes}
  printf '%s\n' "$info" > "$out/server_info.json"

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
    "${fix_mount[@]}" "${dds_mount[@]}" \
    "${clock_args[@]}" -w /workspace/simple "${entry[@]}" "$SIMPLE_IMAGE" \
    ${SIMPLE_EVAL_CLOCK:+/opt/s103/simtime_eval.py --clock "$SIMPLE_EVAL_CLOCK"} \
    "simple/$TASK" psi0_decoupled_wbc "dr-level-$level" \
    --host "$host" --port "$PORT" --sim-mode "$sim_mode" --headless \
    --data-format lerobot --data-dir "data/$evals/$TASK/dr-level-$level" \
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
    "$ACTION_EXEC_HORIZON" "$RTC_FLAG" "$host:$PORT" "$TASK" "$task_file" "$SIMPLE_DDS_DOMAIN" "$clock" <<'PY'
import json, re, sys
from pathlib import Path

out = Path(sys.argv[1])
(status, seconds, sim_mode, level, pass_, start, episodes, run, ckpt_step, model_rev, psi0_commit,
 data_rev, image, exec_h, rtc, server, task, task_file, dds_domain, clock) = sys.argv[2:22]
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
    "psi_data_revision": data_rev, "simple_image": image, "simple_task_file": task_file, "dds_domain": int(dds_domain), "eval_clock": clock,
    # What the server itself reports; the run/ckpt/horizon/rtc fields above are the client's env.
    "server_info": json.loads((out / "server_info.json").read_text()),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("sim_mode", "level", "pass", "n", "successes", "client_exit", "wall_seconds")}))
PY
  log "run report: $out/summary.json"
  return "$status"
}

# Open-loop replay of train episodes (Psi0's mock_psi0_client_openloop) with the images swapped,
# to measure how much the policy relies on them (benchmark B4 in docs/g0/psi0-eval.md):
# real | gray (constant 128) | blur (Gaussian, radius 8) | shift (real frames of the same
# episode, half an episode away in time).
cmd_openloop() {
  local images=real data="" host=127.0.0.1 eps="0 1 2" stride=5
  while (( $# )); do
    case "$1" in
      --images) images="$2"; shift 2 ;;
      --data) data="$2"; shift 2 ;;
      --host) host="$2"; shift 2 ;;
      --eps) eps="$2"; shift 2 ;;
      --stride) stride="$2"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  [[ -d "$data" ]] || die "--data must be the dir holding the LeRobot train repo of the run"
  local out="$PSI0_ROOT/openloop-images/$images"
  mkdir -p "$out"
  # shellcheck disable=SC2086
  psi_exec env IMAGES="$images" MPLBACKEND=Agg python - --run-dir "$RUN_DIR" --host "$host" --port "$PORT" \
    --eps-idx $eps --sequential --split train --stride "$stride" --root-dir "$data" \
    --repo-id "$(basename "$(ls -d "$data"/*/ | head -1)")" --output-dir "$out" --tag "$images" <<'PY'
import os, sys
from PIL import ImageFilter

import psi.deploy.mock_psi0_client_openloop as ol

mode = os.environ["IMAGES"]
replay = ol.replay_episode

def swap(frames):
    if mode == "real":
        return frames
    n = len(frames)
    out = []
    for k, f in enumerate(frames):
        f = dict(f)
        if mode == "gray":
            f["observations"] = [img.point(lambda _: 128) for img in f["observations"]]
        elif mode == "blur":
            f["observations"] = [img.filter(ImageFilter.GaussianBlur(8)) for img in f["observations"]]
        elif mode == "shift":
            f["observations"] = frames[(k + n // 2) % n]["observations"]
        else:
            raise SystemExit(f"unknown --images {mode}")
        out.append(f)
    return out

def patched(url, frames, *args, **kwargs):
    return replay(url, swap(frames), *args, **kwargs)

ol.replay_episode = patched
sys.argv = ["mock_psi0_client_openloop", *sys.argv[1:]]
ol.main()
PY
  log "open-loop reports: $out"
}

# Benchmark B3 (docs/g0/psi0-eval.md): relay 127.0.0.1:LISTEN -> 127.0.0.1:PORT, holding each reply
# DELAY seconds, and log per call the robot state sent, an image hash and the action chunk returned.
# Two runs of one episode against a freshly started server (same seed) then show whether the
# delay changes the closed loop.
cmd_delay_proxy() {
  local listen=22087 delay=0 logf=""
  while (( $# )); do
    case "$1" in
      --listen) listen="$2"; shift 2 ;;
      --delay) delay="$2"; shift 2 ;;
      --log) logf="$2"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  [[ -n "$logf" ]] || die "--log FILE is required"
  log "127.0.0.1:$listen -> 127.0.0.1:$PORT, +${delay}s per call, log $logf"
  exec python3 - "$listen" "$PORT" "$delay" "$logf" <<'PY'
import base64, hashlib, http.client, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

listen, port, delay, logf = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
log = open(logf, "a", buffering=1)

def arrays(o, path=""):
    """Yield (path, raw bytes, dtype, shape) of every Psi0-serialised numpy blob in a message."""
    if isinstance(o, dict):
        if "__numpy__" in o:
            yield path, base64.b64decode(o["__numpy__"]), o["dtype"], o["shape"]
        else:
            for k, v in o.items():
                yield from arrays(v, f"{path}/{k}")

def floats(raw, dtype):
    import array
    a = array.array("f" if dtype == "<f4" else "d")
    a.frombytes(raw)
    return [round(x, 6) for x in a]

class Relay(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def relay(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=600)
        c.request(self.command, self.path, body=body or None,
                  headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
        r = c.getresponse()
        data = r.read()
        if self.path == "/act":
            time.sleep(delay)
            req, rep = json.loads(body), json.loads(data)
            rec = {"t": time.time(), "delay": delay}
            for p, raw, dt, shape in arrays(req):
                if p.startswith("/image"):
                    rec["image_sha"] = hashlib.sha256(raw).hexdigest()[:16]
                elif p == "/state/states":
                    rec["state"] = floats(raw, dt)
            for p, raw, dt, shape in arrays(rep):
                if p == "/action":
                    rec["action"] = floats(raw, dt)
                    rec["action_shape"] = shape
            rec["history"] = req.get("history")
            log.write(json.dumps(rec) + "\n")
        self.send_response(r.status)
        self.send_header("Content-Type", r.getheader("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = relay

    def log_message(self, *args):
        pass

ThreadingHTTPServer(("127.0.0.1", listen), Relay).serve_forever()
PY
}

# Benchmark B6 (docs/g0/psi0-eval.md): a stand-in for the Psi0 server that answers /act with the
# recorded 36-D actions of train episodes, 24 per call (the served exec horizon), starting a new
# episode at every reset (eval episode k replays train episode FIRST+k). The SIMPLE client then
# drives the robot with ground-truth actions through the same mapping and WBC as with Psi0.
# Needs pandas and pyarrow (PYTHON, e.g. the SIMPLE venv). Holds the last action after the end.
cmd_replay_server() {
  local train="" first=0 listen="$PORT"
  while (( $# )); do
    case "$1" in
      --train) train="$2"; shift 2 ;;
      --first) first="$2"; shift 2 ;;
      --listen) listen="$2"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  [[ -d "$train/data" ]] || die "--train must be a LeRobot dataset dir (with data/)"
  log "replaying $train from episode $first on 127.0.0.1:$listen"
  exec "${PYTHON:-python3}" - "$train" "$first" "$listen" "$TASK" <<'PY'
import base64, json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pandas as pd

train, first, listen, task = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
EXEC = 24
state = {"episode": first - 1, "cursor": 0, "actions": None}

def blob(a):
    a = np.ascontiguousarray(a)
    return {"__numpy__": base64.b64encode(a.tobytes()).decode(), "dtype": a.dtype.str, "shape": list(a.shape)}

def load(ep):
    df = pd.read_parquet(next(train.glob(f"data/chunk-*/episode_{ep:06d}.parquet")))
    return np.stack(df["action"].to_numpy()).astype(np.float32)

class Replay(BaseHTTPRequestHandler):
    def reply(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self.reply({"status": "ok"})
        # The client checks that the server serves its task, and names its video dir after this.
        self.reply({"policy": "replay", "timestamp": f"train-ep{state['episode']}",
                    "run_dir": f"replay-of-{task.lower()}-{train.name}"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if (req.get("history") or {}).get("reset"):
            state["episode"] += 1
            state["cursor"] = 0
            state["actions"] = load(state["episode"])
            print(f"episode {state['episode']}: {len(state['actions'])} recorded actions", flush=True)
        acts = state["actions"]
        idx = np.minimum(np.arange(state["cursor"], state["cursor"] + EXEC), len(acts) - 1)
        state["cursor"] += EXEC
        self.reply({"action": blob(acts[idx]), "err": 0.0, "traj_image": blob(np.zeros((1, 1, 3), np.uint8))})

    def log_message(self, *args):
        pass

ThreadingHTTPServer(("127.0.0.1", listen), Replay).serve_forever()
PY
}

case "${1:-}" in
  smoke) shift; cmd_smoke "$@" ;;
  replay-server) shift; cmd_replay_server "$@" ;;
  run) shift; cmd_run "$@" ;;
  openloop) shift; cmd_openloop "$@" ;;
  delay-proxy) shift; cmd_delay_proxy "$@" ;;
  *) sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
