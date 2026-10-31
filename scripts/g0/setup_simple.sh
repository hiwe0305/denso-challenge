#!/usr/bin/env bash
# Set up a MuJoCo-only SIMPLE environment (no Isaac Sim) for G1 tasks (S1-02; used by the tray task DA-32).
#
# Creates a Python 3.10 venv at $FWDATA/simple/.venv with SIMPLE installed
# editable at the pinned commit, and SIMPLE's dependencies minus isaacsim,
# torch and torchvision. Also installs the three SIMPLE submodules the
# *Teleop-v0 tasks (two-table task) need: unitree_sdk2_python, gear_sonic and
# decoupled_wbc. Robot assets are fetched by SIMPLE itself on first use.
#
# Usage: bash scripts/g0/setup_simple.sh
# Env:   FWDATA (default: fwdata/ of the main checkout, shared by all worktrees)
set -euo pipefail

SIMPLE_REPO="https://github.com/physical-superintelligence-lab/SIMPLE.git"
SIMPLE_COMMIT="6d10628794d9c7de4596b4f2afb2c054a637c2bc"
# Submodules for the *Teleop-v0 tasks: "path|HTTPS url|commit". Commits are the
# gitlinks of SIMPLE_COMMIT; the URLs are HTTPS because SIMPLE's .gitmodules
# lists two of them over SSH.
SUBMODULES=(
  "third_party/unitree_sdk2_python|https://github.com/songlin/unitree_sdk2_python.git|cf26ccef0e615c9509140322bec154adc391c052"
  "third_party/gear_sonic|https://github.com/songlin/gear_sonic.git|e61eeb1dec9678dcc02f97c5ac27ca6a4fe82128"
  "third_party/decoupled_wbc|https://github.com/songlin/decoupled_wbc.git|5b304e4d643fe89cd000068dcbba7e7519539caa"
)

common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
FWDATA="${FWDATA:-$(dirname "$common_dir")/fwdata}"
SIMPLE_DIR="$FWDATA/simple/SIMPLE"
VENV="$FWDATA/simple/.venv"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

mkdir -p "$FWDATA/simple"
if [ ! -d "$SIMPLE_DIR/.git" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone -q "$SIMPLE_REPO" "$SIMPLE_DIR"
fi
git -C "$SIMPLE_DIR" fetch -q --depth 200 origin
git -C "$SIMPLE_DIR" -c advice.detachedHead=false checkout -q "$SIMPLE_COMMIT"

# The AMO lower-body policy files are Git LFS objects. Fetch them over HTTPS so
# git-lfs is not needed; leave a file alone once it is no longer a pointer.
for f in amo_jit.pt adapter_jit.pt adapter_norm_stats.pt; do
  dest="$SIMPLE_DIR/src/simple/robots/policy/$f"
  if head -c 40 "$dest" | grep -q 'git-lfs'; then
    curl -fsSL -o "$dest.tmp" \
      "https://media.githubusercontent.com/media/physical-superintelligence-lab/SIMPLE/$SIMPLE_COMMIT/src/simple/robots/policy/$f"
    mv "$dest.tmp" "$dest"
  fi
done

for entry in "${SUBMODULES[@]}"; do
  IFS='|' read -r path url commit <<<"$entry"
  dir="$SIMPLE_DIR/$path"
  pinned="$(git -C "$SIMPLE_DIR" ls-tree HEAD "$path" | awk '{print $3}')"
  [ "$pinned" = "$commit" ] || { echo "$path: SIMPLE pins $pinned, script pins $commit" >&2; exit 1; }
  if [ ! -e "$dir/.git" ]; then
    rmdir "$dir" 2>/dev/null || true  # SIMPLE's clone leaves an empty folder
    GIT_LFS_SKIP_SMUDGE=1 git clone -q "$url" "$dir"
  fi
  git -C "$dir" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dir" fetch -q origin
  git -C "$dir" -c advice.detachedHead=false checkout -q "$commit"
done
# The GR00T lower-body RL policies (Balance, Walk) must be real files, not LFS pointers.
for f in "$SIMPLE_DIR"/third_party/decoupled_wbc/sim2mujoco/resources/robots/g1/policy/*.onnx; do
  if head -c 40 "$f" | grep -q 'git-lfs'; then echo "LFS pointer, not a model: $f" >&2; exit 1; fi
done

[ -x "$VENV/bin/python" ] || "$UV" venv -q --python 3.10 "$VENV"
export VIRTUAL_ENV="$VENV"

# SIMPLE's runtime dependencies (pyproject.toml at the pinned commit) without
# isaacsim, torch and torchvision; plus what its asset download and our tests use.
"$UV" pip install -q \
  "dm-control==1.0.21" "mujoco==3.3.6" "numpy==1.26.4" \
  "gymnasium>0.29.1" "python-fcl>=0.7.0.8" "rich>=13.9.4" "transforms3d>=0.4.2" \
  "trimesh>=4.7.1" "typer-slim>=0.17.3" "python-dotenv>=0.9.9" openpi-client \
  "huggingface_hub>=0.18.3" platformdirs requests scipy pyyaml \
  opencv-python-headless matplotlib imageio imageio-ffmpeg pytest
# SIMPLE loads the AMO lower-body policy with device="cuda" (g1_wholebody.py),
# so use the CUDA build whenever an NVIDIA GPU is present.
if command -v nvidia-smi >/dev/null; then torch_index=cu128; else torch_index=cpu; fi
"$UV" pip install -q "torch==2.7.0" "torchvision==0.22.0" --index-url "https://download.pytorch.org/whl/$torch_index"
"$UV" pip install -q --no-deps -e "$SIMPLE_DIR"
# *Teleop-v0 tasks: the DDS bridge (unitree_sdk2py needs cyclonedds 0.10.2), the
# SONIC robot config (gear_sonic: tyro, pin) and the decoupled WBC (onnxruntime
# runs its RL policies). Installed without their own dependency lists, which pull
# in PICO teleop, ROS and GUI packages this environment does not use.
"$UV" pip install -q "cyclonedds==0.10.2" tyro pin onnxruntime
# decoupled_wbc's TeleopRetargetingIK (DA-33 wrist IK, flywheel_simple.wbc.upper_body)
# solves with pink on the quadprog backend of qpsolvers.
"$UV" pip install -q "pin-pink==4.4.0" "qpsolvers[quadprog]==4.13.0"
"$UV" pip install -q --no-deps \
  -e "$SIMPLE_DIR/third_party/unitree_sdk2_python" \
  -e "$SIMPLE_DIR/third_party/gear_sonic" \
  -e "$SIMPLE_DIR/third_party/decoupled_wbc"

# SIMPLE imports cuRobo when it loads any robot. Without nvcc the real cuRobo
# cannot be built, so install the dev-only stub (raises on use) instead.
site_packages="$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
if ! "$VENV/bin/python" -c 'import curobo, sys; sys.exit(getattr(curobo, "IS_STUB", False))' 2>/dev/null; then
  if command -v nvcc >/dev/null; then
    echo "nvcc found: install the real cuRobo with $SIMPLE_DIR/scripts/install_curobo.sh" >&2
  else
    rm -rf "$site_packages/curobo"
    cp -r "$(dirname "${BASH_SOURCE[0]}")/simple/curobo_stub/curobo" "$site_packages/curobo"
    echo "Installed the cuRobo stub (no planning on this machine)"
  fi
fi

MUJOCO_GL=egl "$VENV/bin/python" - <<'EOF'
import mujoco, simple, sys
import simple.envs.sonic_loco_manip, simple.robots.g1_sonic  # two-table env and robot
from decoupled_wbc.control.policy.wbc_policy_factory import get_wbc_policy  # noqa: F401
# TeleopRetargetingIK itself imports a visualizer left out here, so check its solver.
import pink, qpsolvers  # noqa: F401
assert "quadprog" in qpsolvers.available_solvers
assert "isaacsim" not in sys.modules
print(f"simple {simple.__version__}, mujoco {mujoco.__version__}, python {sys.version.split()[0]}")
EOF
echo "SIMPLE env ready: $VENV (export MUJOCO_GL=egl before running)"
