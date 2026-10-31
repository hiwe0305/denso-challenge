# Môi trường SIMPLE chỉ MuJoCo

_Ngày 28/10/2026. Story [S1-02](../product/stories/S1-02-moi-truong-simple.md) nhiệm vụ con 1.2, 1.3 (AC 1) và phần `mujoco` của nhiệm vụ con 2 (AC 2). Dùng chung cho task hai bàn và task bê khay (DA-32). Số đo là thực đo trên một máy, một lần chạy._

**Vì sao uv thay Docker** (nhiệm vụ con 1.2): Docker trên máy dev không có NVIDIA container runtime (`docker info` chỉ có `runc`), và image SIMPLE kèm Isaac Sim 4.5 mà `sim_mode=mujoco` không dùng. Venv uv chạy thẳng trên driver của máy, nhẹ hơn và đủ cho mọi việc chỉ MuJoCo. Image Docker theo digest (nhiệm vụ con 1.1) để dành cho máy chạy `mujoco_isaac`.

## Cài

```bash
bash scripts/g0/setup_simple.sh
```

Script tạo venv Python 3.10 ở `fwdata/simple/.venv` của checkout chính (mọi worktree dùng chung), clone SIMPLE vào `fwdata/simple/SIMPLE` ở commit ghim, clone ba submodule của SIMPLE qua HTTPS ở commit ghim, cài SIMPLE và ba submodule editable không kèm phụ thuộc, rồi cài phụ thuộc theo bảng dưới. Chạy lại được nhiều lần; lần đầu mất khoảng 7 phút cộng thời gian tải torch CUDA và khoảng 420 MB của ba submodule.

| Thành phần | Giá trị |
|---|---|
| SIMPLE | `6d10628794d9c7de4596b4f2afb2c054a637c2bc` (30/8/2026) |
| Python | 3.10.22 (SIMPLE yêu cầu `==3.10.*`) |
| MuJoCo | 3.3.6 |
| torch | 2.7.0+cu128 (bản CPU khi máy không có `nvidia-smi`) |
| `unitree_sdk2_python` | `cf26ccef0e615c9509140322bec154adc391c052`; cầu nối DDS, kèm `cyclonedds==0.10.2` |
| `gear_sonic` | `e61eeb1dec9678dcc02f97c5ac27ca6a4fe82128`; cấu hình và robot SONIC, kèm `tyro`, `pin` |
| `decoupled_wbc` | `5b304e4d643fe89cd000068dcbba7e7519539caa`; GR00T decoupled WBC, policy RL `Balance.onnx`, `Walk.onnx` (1,9 MB mỗi file, file thật), kèm `onnxruntime`; `pin-pink==4.4.0` và `qpsolvers[quadprog]==4.13.0` cho IK cổ tay `TeleopRetargetingIK` (DA-33) |
| Asset | SIMPLE tự tải từ Hugging Face `USC-PSI-Lab/SIMPLE` lần đầu dùng (`robots_g1.zip` 134 MB, `robots_g1_sonic.zip`, cảnh HSSD, `assets_objects.zip` …); 2,1 GB trong `fwdata/simple/SIMPLE/data/` sau khi chạy cả task MP và task hai bàn (`du`, 28/10) |

## Khác với `pyproject.toml` của SIMPLE

| Thay đổi | Lý do |
|---|---|
| Không cài `isaacsim[all,extscache]==4.5.0` | Chỉ dùng `sim_mode=mujoco`; SIMPLE chỉ import Isaac khi `sim_mode` chứa `isaac` (`envs/base_dual_env.py`) |
| torch cài từ index `cu128` hoặc `cpu` của PyTorch | SIMPLE dùng index `cu128`; giữ đúng bản 2.7.0 |
| **Gói `curobo` giả** (`scripts/g0/simple/curobo_stub/`) khi máy không có `nvcc` | SIMPLE import cuRobo khi nạp bất kỳ robot nào (`robots/mixin.py` raise nếu thiếu). cuRobo thật cần biên dịch CUDA. Gói giả chỉ cho import qua; gọi tới bất kỳ lớp nào của nó báo lỗi "cần cuRobo thật". **Không dùng được cho datagen (DA-33)**: máy sinh dữ liệu phải cài cuRobo thật bằng `scripts/install_curobo.sh` của SIMPLE |
| Thêm `opencv-python-headless`, `matplotlib`, `huggingface_hub`, `platformdirs`, `requests`, `scipy`, `pyyaml`, `imageio`, `imageio-ffmpeg`, `pytest` | SIMPLE import khi chạy nhưng không khai trong phụ thuộc chính, hoặc test và tải asset của đội cần |
| Ba submodule `unitree_sdk2_python`, `gear_sonic`, `decoupled_wbc` clone qua HTTPS, không qua `git submodule` | `.gitmodules` của SIMPLE khai `unitree_sdk2_python` và `decoupled_wbc` qua SSH. Script đối chiếu commit với gitlink của SIMPLE và dừng nếu lệch. Các submodule khác (`curobo`, `AMO`, `GR00T-WholeBodyControl`, `XRoboToolkit`, …) không cần cho `sim_mode=mujoco` |
| Ba submodule cài `--no-deps`, chỉ thêm `cyclonedds==0.10.2`, `tyro`, `pin`, `onnxruntime`, `pin-pink==4.4.0`, `qpsolvers[quadprog]==4.13.0` | Danh sách phụ thuộc của chúng kéo theo teleop PICO, ROS, GUI (`decoupled_wbc[full]`); `unitree_sdk2py` đòi `opencv-python` bản có GUI, venv đã có bản headless |
| Ba file Git LFS của policy AMO (`src/simple/robots/policy/amo_jit.pt`, `adapter_jit.pt`, `adapter_norm_stats.pt`) tải qua HTTPS từ `media.githubusercontent.com` theo commit ghim | Máy không có `git-lfs`; clone chỉ có con trỏ LFS. Vì vậy `git status` của clone SIMPLE báo ba file này đã sửa; đó là file thật thay cho con trỏ, không phải sửa mã |

## Bốn điều phải biết khi chạy

1. `export MUJOCO_GL=egl` trước khi chạy để render offscreen.
2. Task G1 wholebody của SIMPLE bắt `render_hz = 0.1 / physics_dt` (50 khi `physics_dt = 0.002`). `scripts/test_env.py` của SIMPLE không truyền `render_hz` nên không chạy được task G1; dùng `scripts/g0/simple/smoke_mp.py`.
3. `g1_wholebody` nạp policy AMO với `device="cuda"` cứng (`robots/g1_wholebody.py`), nên chạy robot này cần GPU NVIDIA.
4. Task `*Teleop-v0` (task hai bàn) chạy `SonicLocoManipEnv` với robot `g1_sonic`: `gym.make` cần `sonic_config` (từ `gear_sonic.utils.mujoco_sim.configs.SimLoopConfig().load_wbc_yaml()`, thêm `ENV_NAME="simple"`), `physics_dt=0.005` và `render_hz=50`, như `src/simple/cli/teleop_decoupled_wbc.py`. `scripts/g0/simple/smoke_two_table.py` và `run_two_table.py` làm đúng như vậy; `smoke_mp.py` chỉ dùng cho task MP.

## Smoke test

```bash
MUJOCO_GL=egl fwdata/simple/.venv/bin/python scripts/g0/simple/smoke_mp.py \
    --env-id simple/G1WholebodyBendPickMP-v0 --steps 100 --out fwdata/simple/smoke_mp
```

Kết quả ngày 28/10/2026 (thực đo, một lần):

| Đo | Giá trị |
|---|---|
| Máy | Laptop, RTX 3050 Laptop 4 GB (driver 595.99.02), 14 GB RAM, 12 luồng CPU, Ubuntu 26.04.1 |
| Kết quả | 100 bước, không lỗi, `isaacsim` không bị import |
| Ảnh | 4 camera (`head_stereo_left/right`, `front_stereo_left/right`), mỗi ảnh 360 × 640 × 3 |
| Reset lần đầu | 307 s (gồm tải và dựng asset lần đầu) |
| Thời gian một bước env (trung vị) | 17 ms, gồm vật lý, AMO và render 4 camera |
| RAM đỉnh | 2,5 GB |

Ở `sim_mode=mujoco`, cảnh HSSD của task không được dựng; camera đầu thấy sàn phẳng, bàn, vật và hai bàn tay Dex3. Task bê khay dùng sàn phẳng nên khớp.

## Task hai bàn và decoupled WBC

Đo ngày 28/10/2026 trên cùng máy, một lần mỗi phép. Script: `scripts/g0/simple/smoke_two_table.py` (smoke) và `scripts/g0/simple/run_two_table.py` (đứng, đi, render); dựng env như `teleop_decoupled_wbc.py`, agent đứng chép `get_stabilize_action` của `agents/pico_decoupled_agent.py`, bỏ phần PICO. Video và ảnh ở `fwdata/simple/two_table/` (không commit).

| Phép | Kết quả |
|---|---|
| Smoke `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`, 100 bước, chỉ lệnh dây treo | Không lỗi, `isaacsim` không bị import; 2 camera đầu 360 × 640; bước env trung vị 7,9 ms; reset đầu 375 s (gồm tải cảnh và asset); RAM đỉnh 2,6 GB |
| Đứng: WBC chạy từ bước đầu, dây treo hạ 0,15 m/s tới `length = −0,25` rồi tắt khi vận tốc đứng của hông dưới 0,05 m/s (cách của `agents/pico_sonic_agent.py`) | Tắt dây ở bước 86; 414 bước sau đó hông 0,742–0,747 m (mục tiêu WBC 0,74 m), trục thân thẳng ≥ 0,997 |
| Đi: `navigate_cmd = [−0,25, 0, 0, 0]` trong 150 bước (3 s) | Đi lùi 0,73 m; hông ≥ 0,728 m, trục thân ≥ 0,997; hết lệnh thì đứng yên |

Ghi chú:

- Action của đường này là `decoupled_wbc` (đặt khớp mục tiêu, PD trong `G1Sonic.apply_action`), không phải `wbc_torque` của bộ điều khiển SONIC ngoài tiến trình.
- Dây treo phải dừng hạ ở `−0,25`. Hạ tiếp thì vận tốc hông không bao giờ dưới 0,05 m/s, dây kéo robot ngồi xổm tới hông 0,20 m.
- Không cần train RL cho đứng và đi: teleop bàn phím (DA-16) chỉ cần map phím sang `navigate_cmd` và mục tiêu tay.
- Ở `sim_mode=mujoco`, vật được dựng từ mesh va chạm tô trắng (`engines/mujoco.py`); muốn vật có màu thì dựng một model chỉ để render (chép qpos từ sim mỗi bước), như `run_two_table.py` làm.

## Còn thiếu của S1-02

- `sim_mode=mujoco_isaac` và Replay & Render bằng Isaac (AC 2, AC 3): cần máy có Isaac Sim 4.5 và NVIDIA container runtime.
- `datagen` trên task MP (AC 3): cần cuRobo thật; máy dev chỉ có gói giả.
- Đo trung bình và p95 trên ít nhất 5 episode, VRAM đỉnh, trên máy RTX 3060 (AC 4).
