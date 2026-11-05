#!/usr/bin/env bash
# Isaac client of the HE-1 tier 2 eval on rtx3060 (DA-26 task 3), started by he1_eval.py run:
#
#   cd ~/denso-da26 && bash fw/scripts/he/he1_client.sh --set sets/interleaved --tag T \
#       --episodes 20 --port 22095
#
# One run of SIMPLE's eval-decoupled-wbc over the interleaved dev set (he1_eval.py interleave),
# in SIMPLE's published image, as scripts/g0/eval_psi0.sh `run` does it for S1-03: the same
# image digest, the b75c678 task file mounted over the image's, a DDS domain of its own, the
# sim clock (docker/psi0/simtime_eval.py), mujoco_isaac. It talks to he1_eval.py's router on
# 127.0.0.1:PORT (ssh -R from the laptop), which picks the server of each episode. Layout of
# ~/denso-da26: fw/ (git archive of master), sets/interleaved/, simple/ (SIMPLE's data/: kit
# caches, patches, eval outputs), runs/da26-t2-eval-n20/ (what the laptop pulls; one set of
# files per run tag: client-<tag>.log, eval/<tag>/eval_stats.txt, videos/<tag>/,
# summary-<tag>.json, server_info-<tag>.json; and `exit`, written last on every way out).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
ROOT="$PWD"
OUT="$ROOT/runs/da26-t2-eval-n20"
mkdir -p "$OUT"
status=1
trap 'echo "$status" > "$OUT/exit"' EXIT
log() { printf '[he1_client] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# Pins of scripts/g0/eval_psi0.sh (S1-03), checked equal by test_he1_eval.py.
SIMPLE_IMAGE="ghcr.io/physical-superintelligence-lab/simple@sha256:38a674039f413ca171d5f8f841c2b9a9d67771fdaf7bcc73c4777fdfcb7a561f"
SIMPLE_FIX_COMMIT="b75c6786f87b4a7f43b52b0ac5b83a1d9ea62e11"
SIMPLE_FIX_FILE=src/simple/tasks/g1_wholebody_locomotion_pick_between_tables_teleop.py
SIMPLE_FIX_SHA256="51bce5d6c0311219d9a827b589910d915521dccc89b69a1ab20ff35081b6dc8f"
WBC_YAML=/workspace/simple/third_party/gear_sonic/utils/mujoco_sim/wbc_configs/g1_29dof_sonic_model12.yaml
TASK=G1WholebodyLocomotionPickBetweenTablesTeleop-v0
SIM_MODE=mujoco_isaac  # RunPlan eval.sim_mode
CLOCK=sim  # RunPlan eval.clock
DDS_DOMAIN="${DDS_DOMAIN:-126}"  # own domain: S1-03 uses 103, other stories 0
MEM_LIMIT="${MEM_LIMIT:-20g}"  # S1-03: peak 15.75 GiB (docker stats, with page cache)
NEED_GB=36  # MemAvailable before start: client 20 + 16 GB (Hiếu 3/11/2026)
# SIMPLE assets, robots and scenes, mounted read-only (the copy S1-03's runs used).
SIMPLE_ASSETS="${SIMPLE_ASSETS:-$HOME/denso-da33/fwdata/simple/SIMPLE/data}"
# Isaac's shader cache, copied once from S1-03's so the first start is not a cold compile.
KIT_SEED="${KIT_SEED:-$HOME/denso-s103/fwdata/simple/s103/kit}"

set_dir="" tag="" episodes="" port=""
while (( $# )); do
  case "$1" in
    --set) set_dir="$2"; shift 2 ;;
    --tag) tag="$2"; shift 2 ;;
    --episodes) episodes="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    *) die "unknown option $1" ;;
  esac
done
[[ -n "$set_dir" && -n "$tag" && -n "$episodes" && -n "$port" ]] || die "--set, --tag, --episodes, --port"
[[ -f "$set_dir/order.json" && -d "$set_dir/simple/$TASK/dr-level-0" ]] || die "no interleaved set at $set_dir"

free_gb=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
(( free_gb >= NEED_GB )) || { status=4; die "MemAvailable ${free_gb} GB < ${NEED_GB} GB"; }
info=$(curl -sf "http://127.0.0.1:$port/info") || die "no router on 127.0.0.1:$port"
[[ "$info" == *g1wholebodylocomotionpickbetweentablesteleop* ]] || die "router does not serve $TASK"
printf '%s\n' "$info" > "$OUT/server_info-$tag.json"

DATA="$ROOT/simple"
for d in assets robots scenes; do [[ -d "$SIMPLE_ASSETS/$d" ]] || die "no $SIMPLE_ASSETS/$d"; done
fix="$DATA/patches/${SIMPLE_FIX_COMMIT:0:7}/$(basename "$SIMPLE_FIX_FILE")"
if [[ ! -f "$fix" ]]; then
  mkdir -p "$(dirname "$fix")"
  curl -sfL -o "$fix" "https://raw.githubusercontent.com/physical-superintelligence-lab/SIMPLE/$SIMPLE_FIX_COMMIT/$SIMPLE_FIX_FILE"
fi
[[ "$(sha256sum "$fix" | cut -d' ' -f1)" == "$SIMPLE_FIX_SHA256" ]] || die "task file $fix is not $SIMPLE_FIX_SHA256"
yaml="$DATA/patches/dds-$DDS_DOMAIN/$(basename "$WBC_YAML")"
mkdir -p "$(dirname "$yaml")"
docker run --rm --entrypoint cat "$SIMPLE_IMAGE" "$WBC_YAML" \
  | sed -E "s/^DOMAIN_ID: 0( |$)/DOMAIN_ID: $DDS_DOMAIN\1/" > "$yaml"
grep -q "^DOMAIN_ID: $DDS_DOMAIN\b" "$yaml" || die "could not set DOMAIN_ID in $yaml"
kit="$DATA/kit"
if [[ ! -d "$kit/cache" && -d "$KIT_SEED/cache" ]]; then
  mkdir -p "$kit" && cp -a "$KIT_SEED/cache" "$kit/cache"
fi
mkdir -p "$kit"/{cache,data,logs,home} "$DATA"/{assets,robots,scenes} "$DATA/evals/he1-dev/$TASK" "$DATA/runs"

omni=/workspace/simple/.venv/lib/python3.10/site-packages/omni
evals="evals/he1-dev/$TASK/dr-level-0"
begin=$(date +%s)
code=0
# Mounts as eval_psi0.sh `run`; outputs go to $DATA only, the set and assets are read-only.
docker run --rm --name da26-eval-client --runtime nvidia --network host \
  --user "$(id -u):$(id -g)" --shm-size 16g --memory "$MEM_LIMIT" --memory-swap "$MEM_LIMIT" \
  -e NVIDIA_VISIBLE_DEVICES=0 -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -e OMNI_KIT_ACCEPT_EULA=Y -e MUJOCO_GL=egl -e HOME=/kit-home -e DEBUG=1 \
  -v "$kit/cache:$omni/cache" -v "$kit/data:$omni/data" -v "$kit/logs:$omni/logs" \
  -v "$kit/home:/kit-home" \
  -v "$DATA:/workspace/simple/data" \
  -v "$ROOT/$set_dir/simple/$TASK:/workspace/simple/data/evals/he1-dev/$TASK:ro" \
  -v "$SIMPLE_ASSETS/assets:/workspace/simple/data/assets:ro" \
  -v "$SIMPLE_ASSETS/robots:/workspace/simple/data/robots:ro" \
  -v "$SIMPLE_ASSETS/scenes:/workspace/simple/data/scenes:ro" \
  -v "$fix:/workspace/simple/$SIMPLE_FIX_FILE:ro" -v "$yaml:$WBC_YAML:ro" \
  -v "$ROOT/fw/docker/psi0/simtime_eval.py:/opt/he1/simtime_eval.py:ro" \
  -w /workspace/simple --entrypoint /workspace/simple/.venv/bin/python "$SIMPLE_IMAGE" \
  /opt/he1/simtime_eval.py --clock "$CLOCK" \
  "simple/$TASK" psi0_decoupled_wbc dr-level-0 \
  --host 127.0.0.1 --port "$port" --sim-mode "$SIM_MODE" --headless \
  --data-format lerobot --data-dir "data/$evals" \
  --episode-start 0 --num-episodes "$episodes" --eval-dir "data/runs/$tag" \
  > "$OUT/client-$tag.log" 2>&1 || code=$?
end=$(date +%s)

mkdir -p "$OUT/eval" "$OUT/videos/$tag"
[[ -d "$DATA/runs/$tag" ]] && mv "$DATA/runs/$tag" "$OUT/eval/$tag"
for ep in "$DATA"/evals/psi0_decoupled_wbc/*."$TASK"/dr-level-0/episode_*; do
  [[ -d "$ep" ]] && mv "$ep" "$OUT/videos/$tag/"
done
python3 - "$OUT" "$code" "$((end - begin))" "$tag" "$SIMPLE_IMAGE" "$SIMPLE_FIX_SHA256" \
  "$DDS_DOMAIN" "$SIM_MODE" "$CLOCK" "$episodes" "$(sha256sum "$set_dir/order.json" | cut -d' ' -f1)" <<'PY'
import json, sys
from pathlib import Path

out = Path(sys.argv[1])
keys = ["client_exit", "wall_seconds", "tag", "simple_image", "simple_task_file_sha256",
        "dds_domain", "sim_mode", "clock", "episodes_requested", "order_json_sha256"]
summary = dict(zip(keys, sys.argv[2:]))
for k in ("client_exit", "wall_seconds", "dds_domain", "episodes_requested"):
    summary[k] = int(summary[k])
(out / f"summary-{summary['tag']}.json").write_text(json.dumps(summary, indent=2) + "\n")
PY
status=$code
log "client exit $code after $((end - begin)) s; results in $OUT"
