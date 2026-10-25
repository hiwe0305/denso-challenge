# Design: chia việc theo làn, cấu trúc code, model phụ trợ và robot DENSO

_Ngày 25/10/2026. Trạng thái: **đã duyệt** (trưởng nhóm, 25/10/2026), chưa có code. Bổ sung [design ngày 25/10/2026 về MuJoCo](2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 10, 11 và thay một phần 03 mục 7.1 (source tree), 07 mục 2.1–2.3 (sở hữu, story, tải). Mục 10 chọn model phụ trợ quanh Ψ₀; mục 11 ghi chi tiết robot DENSO đọc từ hình vẽ. Đã đưa vào 03 bản 0.6, 07 bản 0.4, RULE, CLAUDE.md và file story ngày 25/10/2026._

Quy ước: **[Đã chốt]** là yêu cầu của trưởng nhóm (Hiếu) ngày 25/10/2026. **[Đề xuất]** là lựa chọn của người viết, cần duyệt.

## 0. Đọc nhanh

1. **Hiếu nhận SIMPLE và mọi việc cần GPU của Châu**, vì chỉ Hiếu có phần cứng [Đã chốt].
2. **Hưng làm simulation theo chuẩn một dự án robotics**: thư viện MuJoCo thuần Python, adapter cho flywheel, workspace ROS 2 (description, control, teleop, bringup), môi trường Docker [Đã chốt].
3. **Phần data flywheel còn lại chia cho 3 người theo 3 làn**: Thông làm Dữ liệu, Châu làm Đánh giá, Long làm Vòng quyết định. Ba làn không gọi code của nhau; mọi chỗ nối đi qua hợp đồng do Hiếu giữ [Đã chốt hướng; cách chia là Đề xuất].
4. **Cấu trúc code**: mỗi làn là một package riêng với một chủ; phần dùng chung (hợp đồng, kho, bộ giả, CLI) là "nhân" do Hiếu giữ; import-linter chặn làn import lẫn nhau [Đề xuất].
5. **Cấu hình**: mỗi file cấu hình có một chủ, một schema và một test kiểm; cấu hình sắp theo làn [Đề xuất].
6. **Model phụ trợ**: stage 1 của Ψ₀ giữ Qwen3-VL-2B; Nemotron chỉ đọc log; Molmo2-4B và RoboBrain 2.5-4B làm công cụ gán nhãn video egocentric; Qwen3.5-4B là tùy chọn khi Agent QA/QC cần nhìn hình (mục 10) [Đề xuất].
7. **Robot DENSO theo hình vẽ**: hai khay gắn trên đế, một bàn trượt nâng chung hai tay, có thể có camera cổ tay; ba điểm này có thể đổi định nghĩa task khay → máy và cấu hình camera, cần BTC xác nhận (mục 11).
8. Lúc này repo mới có khung rỗng (S1-01) và S1-08 chưa merge, nên đổi cấu trúc bây giờ là rẻ nhất: một PR chỉ di chuyển file, không đổi logic, trước khi các làn bắt đầu viết code.

## 1. Bối cảnh

Yêu cầu của trưởng nhóm ngày 25/10/2026:

- Phần SIMPLE và phần của Châu chuyển cho Hiếu vì chỉ Hiếu có phần cứng chạy.
- Phần của Hưng thêm cấu hình môi trường MuJoCo và ROS 2, theo chuẩn của một dự án simulation robotics.
- Phần data flywheel còn lại chia rõ cho 3 người, để họ không phải thông qua nhau mà chỉ thông qua Hiếu.
- Cấu trúc code phải được định nghĩa rõ; cấu hình của từng phần phải sạch và rõ.

**Cách hiểu "phần của Châu"** (người viết, cần Hiếu xác nhận): là các việc cần GPU hoặc máy của Hiếu: S1-04 (chi phí fine-tune), `Psi0Policy`, train ACT và Diffusion Policy, chạy F-ACT, C cuối, B-fail của ACT, phần client RTC của DA-23. Việc không cần GPU của Châu (scorer, task, phân tích) chuyển vào các làn ở mục 3; Châu là một trong 3 người làm data flywheel.

**Cấu trúc hiện tại có 5 chỗ chưa sạch** (kiểm trên `master` và nhánh S1-08 ngày 25/10/2026):

| # | Hiện trạng | Hệ quả |
|---|---|---|
| 1 | Một package `flywheel` chứa 16 module của 5 người, chung một `pyproject.toml` và một thư mục `tests/` | Ai thêm phụ thuộc cũng sửa cùng file; không biết module nào của ai từ cấu trúc |
| 2 | import-linter chỉ cấm lõi import runtime ngoài; không có luật giữa các module trong lõi | `decide` gọi thẳng `qa`, `diagnosis` gọi thẳng `runner` mà không ai chặn; người này phụ thuộc code người kia |
| 3 | `ruff` chỉ quét `packages/flywheel`, `mypy` chỉ kiểm `packages/flywheel/src`, `pytest` chỉ chạy `packages/flywheel/tests` | Test của `flywheel-fakes` không chạy trong CI; mypy báo 3 lỗi khi chạy trên `flywheel-fakes` |
| 4 | Test e2e của lõi (`packages/flywheel/tests/e2e/`) import `flywheel_fakes` | Lõi phụ thuộc ngược vào package khác khi test |
| 5 | `CODEOWNERS` chỉ có dòng `*`, các dòng còn lại để trống tên | Không tự động biết ai cần xem PR |

## 2. Năm vai và ranh giới

| Người | Vai | Giữ | Không làm |
|---|---|---|---|
| **Hiếu** | Nhân, mô hình và phần cứng | Hợp đồng, kho, bộ giả, CLI; SIMPLE; Ψ₀ (policy, trainer, probe, RTC client); ACT, DP; NIM; mọi job GPU (máy 3060, Colab); duyệt và merge | Code bên trong các làn |
| **Hưng** | Simulation | `denso-sim`, `flywheel-mujoco`, workspace ROS 2, Docker sim, Isaac sau | Logic flywheel |
| **Thông** | Làn Dữ liệu | `flywheel-data`: ingest, normalize, annotate, QA, phát lại để kiểm, release, export | Chấm, chẩn đoán, quyết định |
| **Châu** | Làn Đánh giá | `flywheel-eval`: tập điều kiện, task và scorer, chẩn đoán, evidence card, Agent QA/QC | Chạy job GPU, quyết định |
| **Long** | Làn Vòng quyết định | `flywheel-loop`: RunPlan, runner, decide, acquisition, gate, holdout, sổ chi phí, báo cáo, HD | Ingest, chấm |

**Quy tắc "chỉ thông qua Hiếu"** [Đề xuất]:

1. Ba làn và Hưng chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`). Không import package của làn khác. import-linter chặn (mục 5.3).
2. Mọi dữ liệu đi giữa hai làn là một **artifact có schema trong `flywheel.contracts`** (mục 3.2). Muốn thêm hay đổi schema thì mở PR hợp đồng; chỉ Hiếu duyệt.
3. Mỗi artifact có **file mẫu trong `flywheel.testkit`** ngay khi schema được merge. Làn nhận code và test trên file mẫu, không chờ làn gửi.
4. Code chạy thật nối các làn lại chỉ ở một chỗ: `flywheel-cli` (composition root, mục 4.1), do Hiếu giữ. Mỗi làn đăng ký lệnh và hiện thực của mình qua entry point, nên thêm lệnh không phải sửa file chung.
5. Việc cần GPU: làn viết code chạy được trên CPU với bộ giả; Hiếu chạy job thật từ RunPlan.

## 3. Ba làn data flywheel

### 3.1 Việc của từng làn

| Làn | Chủ | Vào | Ra | Story |
|---|---|---|---|---|
| **Dữ liệu** | Thông | Bản ghi teleop (MCAP từ ROS 2), dataset BTC, video egocentric thô, mẫu synthetic | Episode bundle, `ReleaseManifest`, bản export LeRobot v2.1 và v3, dataset EgoDex cho stage 1, `ReplayReport` | S1-10 (phần kho, làm cho nhân), DA-01 (làm cho nhân), DA-02, DA-03, DA-04, DA-17, DA-18, DA-21, DA-22; S2 nạp, QA, release; S6 SOP |
| **Đánh giá** | Châu | `Trace`, `metrics.jsonl`, kết quả probe, log RTC | `Score`, `Cluster`, `EvidenceCard`, `QAReport`, tập điều kiện và chia tập | DA-08, DA-12, DA-13, DA-20; S2 khung và hiệu chỉnh scorer; S3 vector điều kiện, kNN, chẩn đoán, kiểm hệ thống; S4 phép kiểm cần rollout (code); evidence card |
| **Vòng quyết định** | Long | `EvidenceCard`, `LedgerEntry`, `FixRateEvent`, bảng giá | `RunPlan`, `Decision` (duyệt kế hoạch, cổng dev), kế hoạch thu, báo cáo | S2 runner, sổ chi phí; S3 RunPlan, cổng dev, bảng quyết định, backup; S4 decide, `fw review`, N_B; S5 vòng C, công cụ HD; S6 báo cáo, thống kê; phần runner bất đồng bộ của DA-23 |

Việc đổi chủ so với 07 bản 0.3 [Đề xuất]:

| Việc | Chủ cũ | Chủ mới | Lý do |
|---|---|---|---|
| S1-02, S1-03, S1-04, `Psi0Policy`, ACT, DP, F-ACT chạy, C cuối, B-fail của ACT, client RTC | Hưng, Hiếu, Châu | Hiếu | Cần phần cứng [Đã chốt] |
| S1-06, S1-09 | Châu | Hưng | Là khả năng của env MuJoCo (khôi phục trạng thái, tách hình ảnh, tín hiệu, `materialize_conditions`) |
| DA-17 phát lại để kiểm dữ liệu | Châu | Thông | Là một bước QA của làn Dữ liệu; gọi `SimulatorAdapter.replay()` |
| DA-04, DA-18 egocentric | Long | Thông | Là ingest của làn Dữ liệu |
| DA-01 định dạng episode | Long | Thông làm, Hiếu giữ | Là hợp đồng; làn Dữ liệu cần đầu tiên |
| DA-13 quy lỗi về stage, kiểm hệ thống, chẩn đoán | Long | Châu | Là phân tích của làn Đánh giá |
| DA-08 lỗi train, DA-20 Agent QA/QC, evidence card | Thông | Châu | Là phân tích của làn Đánh giá |
| Sổ chi phí, cổng dev, A/A, N_B, công cụ HD, thống kê, backup | Thông | Long | Là vận hành vòng |
| Khóa holdout | Châu | Long | `gate` là module duy nhất đọc `vault/` |
| `contracts/`, `store/`, `testing/`, `flywheel-fakes`, CLI | Long | Hiếu giữ | Là nhân dùng chung; Long hoặc Thông vẫn viết được khi Hiếu giao, nhưng chỉ Hiếu quyết schema |

### 3.2 Artifact giữa các làn

Mọi artifact là Pydantic model trong `flywheel.contracts`, lưu trong kho có sha256 (03 mục 4). Người tạo là người ghi; người đọc chỉ đọc.

| Artifact | Ghi | Đọc | Có trong 03 |
|---|---|---|---|
| Bản ghi teleop MCAP, đặc tả topic | Hưng | Thông | Mới (mục 6.4) |
| `Episode`, `Segment`, `ReleaseManifest`, `DatasetRef` | Thông | Hiếu, Châu, Long | Có |
| `ReplayReport` | Thông | Châu (Agent QA/QC) | Mới |
| `RunPlan`, `TrainSpec`, `RolloutRequest` | Long | Hiếu, Hưng | Có; `RolloutRequest.timing` mới (03 bản 0.5) |
| `Trace`, `RolloutResult` | Hưng (adapter), Hiếu (chạy) | Châu | Có |
| `Checkpoint`, `metrics.jsonl`, kết quả probe, log RTC | Hiếu | Châu | `metrics.jsonl` có; log RTC và schema probe mới |
| `Score`, `Cluster`, `EvidenceCard`, `QAReport` | Châu | Long | `QAReport` mới |
| `Decision`, `LedgerEntry`, `FixRateEvent` | Long | Mọi người | Có |

Danh sách này là hợp đồng giữa các làn. **Việc đầu tiên của Sprint 1 ở nhân**: Hiếu merge schema và file mẫu cho mọi artifact mới (MCAP topic spec, `ReplayReport`, log RTC, schema probe, `QAReport`) trước ngày 29/10/2026, cùng mốc với `base.py` của S1-10.

## 4. Cấu trúc repo

### 4.1 Cây thư mục

```text
denso-challenge/
├── packages/                          # uv workspace
│   ├── flywheel-contracts/            # NHÂN · Hiếu · Pydantic model, 6 Protocol, schema artifact; chỉ phụ thuộc pydantic, pyarrow
│   ├── flywheel-store/                # NHÂN · Hiếu · kho sha256, view DuckDB, refs, khóa vault
│   ├── flywheel-testkit/              # NHÂN · Hiếu · bộ giả (từ flywheel-fakes), contract suite, file mẫu mọi artifact
│   ├── flywheel-cli/                  # NHÂN · Hiếu · lệnh `fw`, đăng ký làn và adapter qua entry point, `fw --version`
│   ├── flywheel-data/                 # LÀN · Thông
│   ├── flywheel-eval/                 # LÀN · Châu
│   ├── flywheel-loop/                 # LÀN · Long
│   ├── flywheel-mujoco/               # ADAPTER · Hưng · DensoMujocoSim (SimulatorAdapter) trên denso-sim
│   ├── flywheel-psi0/                 # ADAPTER · Hiếu · policy, trainer, probe, client RTC
│   ├── flywheel-lerobot/              # ADAPTER · Hiếu · ACT, Diffusion Policy
│   ├── flywheel-simple/               # ADAPTER · Hiếu · chỉ cho G0
│   ├── flywheel-nim/                  # ADAPTER · Hiếu · NimClient, định tuyến theo data_class; generators/ của Hưng
│   └── denso-sim/                     # THƯ VIỆN SIM · Hưng · MuJoCo thuần Python: robot, cảnh, task env; không import ROS, không import flywheel
├── ros2_ws/                           # colcon workspace · Hưng (mục 6)
│   └── src/denso_*/
├── configs/                           # mục 7
├── docker/                            # mỗi image một thư mục: ros2-sim/ (Hưng), simple/, psi0/ (Hiếu)
├── compose.yaml                       # service: sim, simple-worker, psi0-serve, psi0-train, llm-serve
├── tests/e2e/                         # test nối các làn bằng bộ giả · Hiếu
├── scripts/
│   ├── repo/                          # pr_guard, daily_report, progress, storylib, check_links, setup_labels · Long
│   └── g0/                            # spike G0 · chủ theo từng story
├── docs/  website/  deliverables/
├── pyproject.toml                     # workspace, cấu hình ruff, mypy, pytest, import-linter cho MỌI package
└── uv.lock
```

Tên import dùng namespace `flywheel.*` (PEP 420) [Đề xuất]: `flywheel.contracts`, `flywheel.store`, `flywheel.testkit`, `flywheel.cli`, `flywheel.data`, `flywheel.eval`, `flywheel.loop`. Mã của S1-08 (`from flywheel.contracts import …`) giữ nguyên. Adapter giữ tên `flywheel_<tên>` như 03. `fw --version` chuyển sang `flywheel.cli`.

### 4.2 Bên trong một package làn

Mọi package làn có cùng khuôn [Đề xuất]:

```text
packages/flywheel-data/
├── pyproject.toml                 # phụ thuộc của riêng làn; entry point "flywheel.cli" và "flywheel.lanes"
├── README.md                      # làn làm gì, artifact vào và ra, lệnh chạy, ai giữ thư mục nào
├── src/flywheel/data/             # không có flywheel/__init__.py (namespace)
│   ├── __init__.py                # chỉ export API công khai của làn
│   ├── api.py                     # hàm công khai: nhận artifact vào, trả artifact ra
│   ├── cli.py                     # Typer app con, đăng ký vào `fw` qua entry point
│   ├── config.py                  # Pydantic model cho configs/data/*.yaml
│   ├── ingest/                    # keyboard_mcap.py, btc.py, egocentric/, synthetic.py
│   ├── normalize/   annotate/   qa/   release/
│   ├── replay_check/              # gọi SimulatorAdapter.replay(), so ngưỡng
│   ├── export/                    # lerobot_v21.py, lerobot_v3.py, egodex.py
│   └── py.typed
└── tests/
    ├── unit/                      # một file test cho một module
    ├── contract/                  # đọc file mẫu của testkit, ghi artifact đúng schema
    └── conftest.py
```

`flywheel-eval` có `scenarios/`, `tasks/tray_to_machine/`, `scorer/`, `diagnosis/`, `cards/`, `agentqa/` (gồm `viz/`). `flywheel-loop` có `runplan/`, `runner/`, `decide/`, `acquisition/`, `gate/` (gồm `holdout.py`, chỗ duy nhất đọc `vault/`), `ledger/`, `reports/`, `hd/`.

**Quy tắc viết code** [Đề xuất]:

- Hàm trong `api.py` nhận và trả artifact của `flywheel.contracts`, không trả dict tự do.
- Không đọc biến môi trường hay đường dẫn cứng trong module; mọi giá trị đi qua `config.py`.
- Không có `utils.py` chung chung; hàm phụ đặt cạnh nơi dùng.
- Một module làm một việc, dưới khoảng 300 dòng; tên theo việc (`near_duplicate_guard.py`, không `helpers.py`).
- Mọi số chưa đo trong mã hoặc cấu hình ghi `# giả định` kèm nguồn.

### 4.3 Bên trong adapter và denso-sim

Adapter có khuôn như làn, thêm `registry.py` khai entry point `flywheel.adapters` (ví dụ `simulator.denso_mujoco = flywheel_mujoco:DensoMujocoSim`). Adapter chạy ngoài tiến trình (03 mục 2.1) có thêm `worker/` chỉ dùng stdlib và runtime của nó.

`denso-sim` là thư viện thuần, dùng chung cho adapter flywheel và node ROS 2:

```text
packages/denso-sim/
├── src/denso_sim/
│   ├── robot/          # sinh MJCF từ tham số, actuator, sensor
│   ├── scene/          # trạm, khay, linh kiện, máy, đồ gá
│   ├── task/           # env khay → máy: reset(seed), step, vị từ thành công
│   ├── control/        # bộ điều khiển trong sim (khớp, đế, cột nâng, gripper), IK
│   ├── planner/        # synthetic S1
│   ├── teleop/         # ánh xạ phím → lệnh đầu tay, không phụ thuộc ROS
│   ├── assets/         # mesh, texture
│   └── timing.py       # bước theo đồng hồ sim hoặc đồng hồ thật, chèn độ trễ (eval bất đồng bộ)
└── tests/
```

## 5. Cấu hình công cụ

### 5.1 Gốc `pyproject.toml`

Một chỗ cho cấu hình công cụ, áp cho mọi package [Đề xuất]:

| Công cụ | Cấu hình |
|---|---|
| ruff | `include = ["packages/*/src/**/*.py", "packages/*/tests/**/*.py", "tests/**/*.py"]`; giữ `E, F, I, UP`, thêm `B`, `SIM`, `RET` |
| mypy | `strict = true`, `namespace_packages = true`, `explicit_package_bases = true`, `mypy_path` liệt kê `packages/*/src`; mỗi package có `py.typed` |
| pytest | `testpaths = ["packages", "tests/e2e"]`; marker `e2e_fake`, `gpu`, `ros` (job GPU và ROS không chạy trong CI mặc định) |
| import-linter | Mục 5.3 |
| Python | `>=3.10` cho mọi package chạy trên host; adapter chạy trong container ghi phiên bản riêng trong Dockerfile |

### 5.2 CI

| Job | Chạy |
|---|---|
| `core` | `uv sync --locked`, ruff, mypy, pytest (trừ `gpu`, `ros`), lint-imports cho mọi package |
| `ros` | Trong image `docker/ros2-sim`: `colcon build`, `colcon test` cho `ros2_ws/` khi PR chạm `ros2_ws/` hoặc `packages/denso-sim/` |
| `guard` | pr-guard như hiện tại, đọc phạm vi file của story |

### 5.3 Luật import

```toml
[[tool.importlinter.contracts]]
name = "Nhân không phụ thuộc làn, adapter hay runtime"
type = "forbidden"
source_modules = ["flywheel.contracts", "flywheel.store", "flywheel.testkit"]
forbidden_modules = ["flywheel.data", "flywheel.eval", "flywheel.loop", "flywheel.cli",
                     "flywheel_mujoco", "flywheel_psi0", "flywheel_lerobot", "flywheel_simple", "flywheel_nim",
                     "denso_sim", "mujoco", "torch", "lerobot", "simple", "psi0", "isaacsim", "rclpy"]

[[tool.importlinter.contracts]]
name = "Ba làn không import lẫn nhau"
type = "independence"
modules = ["flywheel.data", "flywheel.eval", "flywheel.loop"]

[[tool.importlinter.contracts]]
name = "Làn chỉ đi qua Protocol, không import adapter hay runtime"
type = "forbidden"
source_modules = ["flywheel.data", "flywheel.eval", "flywheel.loop"]
forbidden_modules = ["flywheel_mujoco", "flywheel_psi0", "flywheel_lerobot", "flywheel_simple", "flywheel_nim",
                     "denso_sim", "mujoco", "torch", "lerobot", "simple", "psi0", "isaacsim", "rclpy"]

[[tool.importlinter.contracts]]
name = "denso-sim không biết flywheel hay ROS"
type = "forbidden"
source_modules = ["denso_sim"]
forbidden_modules = ["flywheel", "rclpy"]
```

`flywheel.cli` là composition root duy nhất được import cả làn và adapter.

### 5.4 Sở hữu tự động

`CODEOWNERS` điền đủ tên GitHub theo cột chủ ở mục 4.1, 6 và 7. Vì Hiếu duyệt duy nhất, `CODEOWNERS` dùng để báo người chủ biết PR chạm vào phần của họ (bình luận, không chặn).

## 6. Simulation và ROS 2 (Hưng)

### 6.1 Vai trò hai lớp

| Lớp | Dùng cho | Vì sao |
|---|---|---|
| `denso-sim` gọi thẳng MuJoCo | Rollout hàng loạt của flywheel, phát lại, eval, synthetic S1–S2 | Tất định, nhanh, không có độ trễ của middleware |
| ROS 2 bọc `denso-sim` | Teleop, hiển thị (RViz), ghi rosbag2, giao diện giống robot thật | Bản ghi teleop trong sim và trên robot DENSO đi cùng một đường MCAP; DENSO có thể chạy ROS (design 23/10 mục 9) |

### 6.2 Workspace ROS 2

```text
ros2_ws/
├── src/
│   ├── denso_description/     # ament_cmake · urdf/*.urdf.xacro, meshes/, config/robot_params.yaml (nguồn duy nhất của kích thước), rviz/
│   ├── denso_interfaces/      # ament_cmake · msg/srv riêng: TaskState, EpisodeEvent, ResetTask
│   ├── denso_mujoco/          # ament_python · node sim: chạy denso-sim, xuất /clock, /joint_states, ảnh camera, TF; nhận lệnh
│   ├── denso_control/         # ament_cmake · config/controllers.yaml cho ros2_control (đế, cột nâng, hai tay, gripper)
│   ├── denso_teleop/          # ament_python · node bàn phím → lệnh đầu tay (dùng denso_sim.teleop)
│   └── denso_bringup/         # ament_cmake · launch/sim.launch.py, teleop.launch.py, record.launch.py; config/ cho từng launch
└── README.md                  # build, chạy, bảng topic
```

**Quy ước theo chuẩn ROS** [Đề xuất]: đơn vị và hệ tọa độ theo REP-103; khung `map`, `odom`, `base_link` theo REP-105; tên package `denso_<việc>`; launch viết bằng Python `*.launch.py`; mọi tham số trong YAML của package, không đặt cứng trong code; topic theo namespace `/denso/…`; sim xuất `/clock` và mọi node chạy `use_sim_time`; phụ thuộc khai trong `package.xml` để `rosdep` cài; test bằng `launch_testing` và `colcon test`.

**Nguồn duy nhất của robot** [Đề xuất]: `denso_description/config/robot_params.yaml` sinh ra URDF (qua xacro, cho ROS và RViz) và MJCF (qua `denso_sim.robot`, thêm actuator, sensor, tham số tiếp xúc). Khi DENSO gửi URDF/USD, thay xacro bằng file của DENSO và giữ phần MJCF thêm vào. `configs/embodiments/denso.yaml` của flywheel chỉ trỏ tới file này và khai `action_layout`.

**Chọn bridge MuJoCo–ROS 2**: plugin `ros2_control` có sẵn cho MuJoCo hay node tự viết, Hưng kiểm ở nhiệm vụ con đầu của story ROS 2 và ghi `Decision`.

### 6.3 Môi trường

| Thành phần | Cấu hình [Đề xuất] |
|---|---|
| ROS 2 | Jazzy (bản LTS) trong Docker `docker/ros2-sim/Dockerfile`, không cài lên máy host |
| MuJoCo | Ghim phiên bản trong `packages/denso-sim/pyproject.toml`; image ROS cài `denso-sim` từ workspace bằng `pip install -e` |
| Dev | `.devcontainer/` trỏ tới image `ros2-sim`; ai cũng mở được trên laptop không GPU |
| Hiển thị | RViz và viewer MuJoCo qua X11 hoặc chế độ headless ghi video |

### 6.4 Bảng topic (hợp đồng với làn Dữ liệu)

| Topic | Kiểu | Tần số |
|---|---|---|
| `/denso/joint_states` | `sensor_msgs/JointState` | Tần số điều khiển |
| `/denso/camera/head/image_raw`, `camera_info` | `sensor_msgs/Image`, `CameraInfo` | fps camera |
| `/denso/cmd/base` | `geometry_msgs/Twist` | Tần số điều khiển |
| `/denso/cmd/arm_l`, `/denso/cmd/arm_r`, `/denso/cmd/lift`, `/denso/cmd/gripper_*` | Lệnh của controller tương ứng | Tần số điều khiển |
| `/denso/task/state`, `/denso/task/event` | `denso_interfaces` | Khi đổi |
| `/tf`, `/tf_static`, `/clock` | Chuẩn | Chuẩn |

Bảng chốt trong `flywheel.contracts` (tên topic, kiểu, tần số), vì làn Dữ liệu đọc MCAP theo bảng này mà không cần ROS.

## 7. Cấu hình theo làn

```text
configs/
├── kernel/          # Hiếu · data_class, đường dẫn kho, phiên bản schema
├── models/          # Hiếu · recipe Ψ₀ stage 1–3, ACT, DP; điểm cuối LLM cho Agent QA/QC (model, revision)
├── runplans/        # Hiếu duyệt, Long viết công cụ · RunPlan của từng nhánh
├── embodiments/     # Hưng · denso.yaml: action_layout, trỏ tới denso_description
├── sim/             # Hưng · tham số env, mức Level 0–2, tham số tiếp xúc
├── data/            # Thông · ngưỡng QA, ngưỡng phát lại, cấu hình export
├── eval/            # Châu · task khay → máy (tham số vị từ), ngưỡng chẩn đoán, prompt Agent QA/QC
└── loop/            # Long · bảng giá, ngưỡng cổng, ngân sách vòng
```

Quy tắc [Đề xuất]: mỗi thư mục có một chủ; mỗi file YAML có Pydantic model ở `config.py` của package chủ; test `tests/contract/test_configs.py` của package đó nạp mọi file của thư mục mình. Giá trị giả định ghi chú thích `# giả định: <nguồn>`. Không có cấu hình nằm rải trong code.

## 8. Chuyển từ cấu trúc hiện tại

1. Merge S1-08 như hiện tại (Long đã xong).
2. Một PR `chore-restructure` chỉ di chuyển file và sửa cấu hình công cụ, không đổi logic: tách `packages/flywheel` thành bốn package nhân; đổi `flywheel-fakes` thành `flywheel-testkit`; tạo khung rỗng ba package làn, `flywheel-mujoco`, `denso-sim`; chuyển test e2e ra `tests/e2e/`; sửa ruff, mypy, pytest, import-linter, CI như mục 5; dời `scripts/*.py` vào `scripts/repo/`, sửa đường dẫn trong workflow, `CLAUDE.md`, `RULE.md`. Người làm: Long (biết mã S1-01, S1-08), Hiếu duyệt.
3. Sau PR này, các làn bắt đầu viết code. Khung package của DA-19 và DA-22 (mục mới hôm nay) chuyển vào PR này.
4. Sửa 03 bản 0.6 (mục 7.1 thay bằng mục 4 ở đây), 07 bản 0.4 (sở hữu, story, tải), RULE, CLAUDE.md, file story theo mục 3.1. Thêm vào file story: DA-15 dựng khay theo câu trả lời Q-K và camera theo Q-L (mục 11); DA-18 dùng model gán nhãn và vòng thử ở mục 10.2, 10.3; DA-20 thêm Qwen3.5-4B nếu Q-M là có.

## 9. Rủi ro

| Rủi ro | Dấu hiệu | Giảm thiểu |
|---|---|---|
| **Hiếu quá tải**: nhân, Ψ₀, ACT, DP, SIMPLE, mọi job GPU, duyệt mọi PR | PR chờ quá 1 ngày; job GPU trễ | Job GPU chạy từ RunPlan bằng một lệnh nên tốn giờ máy hơn giờ người; nhân viết một lần ở Sprint 1 rồi gần như đóng băng; Long hoặc Thông viết PR nhân khi Hiếu giao; cân nhắc cho người khác dùng Colab của đội (câu hỏi Q-H) |
| Đổi cấu trúc làm nhánh đang mở phải rebase | S1-03, S1-04, S1-08 | Merge S1-08 trước; S1-03, S1-04 chỉ chạm `docker/`, `scripts/g0/`, `docs/g0/` nên ít bị ảnh hưởng |
| Hợp đồng chưa đủ nên làn phải hỏi nhau | Làn cần trường chưa có trong schema | Mở PR hợp đồng cho Hiếu; không thêm trường "tạm" trong code làn |
| ROS 2 làm chậm phần sim | Hưng mất thời gian vào ROS trước khi env chạy | `denso-sim` không phụ thuộc ROS; MJCF tối thiểu và env làm trước, ROS 2 bọc sau |

## 10. Model phụ trợ quanh Ψ₀

Ngày 25/10/2026 trưởng nhóm hỏi so sánh Nemotron 3.5 Bolt E4B với Qwen3.5-2B/4B, RoboBrain 2.5-4B, Molmo2-4B, SmolVLM2-2.2B, HY-Embodied-0.5, và có nên dùng Nemotron cho EgoDex không. Thông tin dưới đây tra ngày 25/10/2026; mọi điểm benchmark là số **tự công bố** của từng nhóm, chưa đo trên task của đội.

### 10.1 Bảng so sánh

| Model | Nhận gì | Kích thước | Mạnh ở (theo tác giả) | Giấy phép | Trên RTX 3060 12 GB |
|---|---|---|---|---|---|
| Nemotron 3.5 Bolt E4B 4GB | Chữ (theo NVIDIA; trang Ollama ghi có ảnh, mâu thuẫn) | 8B tổng, 4B hiệu dụng | Hội thoại, gọi tool, ngữ cảnh 64K | OpenMDW-1.1 | Có, bản Q4 khoảng 3–4 GB |
| Qwen3.5-2B, 4B | Chữ, ảnh | 2B, 4B | VLM tổng quát; Qwen báo hơn Qwen3-VL về hiểu ảnh; ngữ cảnh 262K | Apache 2.0 | Có, bản lượng tử khoảng 2–3 GB |
| RoboBrain 2.5-4B | Ảnh, video | 4B, kiến trúc Qwen3-VL | Không gian 3D có độ sâu, quỹ đạo thao tác 3D, ước tiến độ task theo từng khung | Xem model card | Có |
| Molmo2-4B | Ảnh, video | 4B, LLM Qwen3, SigLIP 2 | Chỉ điểm và theo dõi vật trong video, đếm | Apache 2.0 (dữ liệu xem riêng) | Có |
| SmolVLM2-2.2B | Ảnh, video | 2,2B | Nhẹ (5,2 GB khi xử lý video); Video-MME 52,1 | Apache 2.0 | Có |
| HY-Embodied-0.5 (bản 2B) | Ảnh, video | 4B tổng, 2,2B hoạt động (Mixture-of-Transformers) | Suy luận không gian và hành động; đứng đầu 16/22 benchmark cùng cỡ | Xem model card | Có, trọng số khoảng 8 GB |

### 10.2 Chọn theo vai [Đề xuất]

| Vai | Chọn | Lý do |
|---|---|---|
| VLM stage 1 của Ψ₀ (fine-tune trên egocentric, DA-18) | Giữ **Qwen3-VL-2B** của Ψ₀ | Action expert của stage 2 học trên đặc trưng của backbone này; đổi backbone là train lại stage 1 (khoảng 829 giờ video theo tác giả) và stage 2, ngoài phạm vi 12 tuần. RoboBrain 2.5 cùng họ Qwen3-VL nhưng bản 4B khác kích thước ẩn, nên cũng không lắp thẳng được; để L1 |
| EgoDex với Nemotron | **Không dùng** | Nemotron chỉ đọc chữ |
| Gán nhãn video egocentric (DA-04, DA-18): ranh giới bước, theo dõi tay và linh kiện, câu hỏi đáp cho P1 | **RoboBrain 2.5-4B** cho ranh giới bước (ước tiến độ), **Molmo2-4B** cho theo dõi và chỉ điểm | Chạy cục bộ trên 3060 nên dữ liệu DENSO không rời máy; thay vai gợi ý ranh giới của Cosmos Reason (cần GPU lớn) trong design 23/10 mục 5.1, 5.3; người vẫn duyệt mẫu |
| Agent QA/QC đọc log (DA-20) | Giữ **Nemotron 3.5 Bolt E4B** [Đã chốt] | Việc là đọc số và chữ |
| Agent QA/QC nhìn hình (bảng ảnh stage 1, video phát lại MuJoCo) | **Qwen3.5-4B**, tùy chọn | Nemotron không nhìn được; chỉ thêm khi trưởng nhóm muốn agent tự xem hình (câu Q-M) |
| Đối chứng cho probe P1 | RoboBrain 2.5-4B hoặc HY-Embodied-0.5 | Cho thấy Qwen3-VL-2B của Ψ₀ yếu hơn mức có thể ở loại câu hỏi nào |
| Lọc thô, tóm tắt video nhanh | SmolVLM2-2.2B | Rẻ nhất, yếu nhất về không gian |

Mọi model ở trên là trọng số mở, chạy cục bộ, nên giữ được quy tắc `data_class` (design 23/10 mục 5.4). Model và revision ghim trong `configs/models/` (mục 7); endpoint chạy trên máy của Hiếu, dev dùng model giả trong `flywheel.testkit`.

### 10.3 Chọn bằng vòng thử trên dữ liệu của đội

Trước khi chốt model gán nhãn và model nhìn hình: một vòng thử 4–6 giờ (ước lượng) trong DA-18 và DA-20, trên 30 khung EgoDex mẫu, 30 ảnh render MuJoCo của robot tương đương và bộ câu hỏi P1. Đo: độ đúng câu hỏi đáp, sai số ranh giới bước (số khung), tỉ lệ chỉ đúng điểm gắp, VRAM và độ trễ trên 3060. Kết quả ghi `Decision`.

## 11. Robot DENSO đọc từ hình vẽ

Trưởng nhóm gửi hình vẽ robot DENSO ngày 25/10/2026 (bản vẽ đường nét, nhìn chéo từ trước). Hình **chưa đưa vào repo**, vì repo đang công khai trên GitHub và chưa rõ DENSO cho phép công bố hình này (câu Q-N). Bảng dưới là những gì đọc được; mọi kích thước vẫn chờ URDF/USD và thông số từ BTC.

| Bộ phận | Thấy trong hình | Khác giả định hiện tại | Hệ quả |
|---|---|---|---|
| Khay | **Hai khay hở gắn trên mặt trước của đế**, hai bên chân cột | Design 23/10 mục 7.1 coi khay thuộc trạm | Nếu linh kiện lấy từ khay trên robot, DA-15 dựng khay theo đế; bước 1 "vào vị trí" là đỗ trước máy; vector điều kiện bỏ "vị trí khay", giữ tư thế linh kiện trong khay (câu Q-K) |
| Cột nâng | Ray thẳng đứng, **một bàn trượt mang cả hai vai** | Khớp | Nhóm `lift` một chiều, chung cho hai tay |
| Hai tay | Khớp vai tròn lớn, nhiều khớp hình trụ, trông như 6–7 khớp mỗi tay | Khớp với phán đoán "kiểu Kinova Gen3", chưa xác nhận | Số khớp quyết định kích thước `arm_l`, `arm_r` |
| Gripper | Hai ngón song song; **một khối nhỏ ở cổ tay**, có thể là camera cổ tay | Mục 3 của design 25/10 (MuJoCo) chọn một camera đỉnh cột, camera cổ tay tắt | Nếu là camera: bật trong MJCF, Ψ₀ nhận nhiều ảnh (câu Q-L) |
| Đỉnh cột | Tấm và khung vươn cao hơn cột, có thiết bị nhìn xuống phía trước | Khớp với "camera đỉnh cột" | Camera đầu nhìn từ trên xuống khay và vùng làm việc; góc nhìn gần với video đội đầu của công nhân, có lợi cho fine-tune stage 1 |
| Đế | Bánh lớn ở hông, nút dừng khẩn giữa mặt trước, thanh cản dưới | Chưa biết vi sai hay đa hướng | Quyết định `base` 2 hay 3 chiều |
| Phía sau | Khối vỏ cao, có thể chứa điện tử và pin | Chưa có | Thêm vào MJCF cho va chạm và vùng với tới |

Robot cầm bằng gripper hai ngón còn EgoDex là bàn tay người: video egocentric có giá trị ở hình ảnh và cấu trúc task, không ở nhãn action (design 23/10 mục 5.3). Đây cũng là lý do model gán nhãn ở mục 10.2 chọn theo khả năng xử lý vật, điểm gắp, quỹ đạo và tiến độ, là những thứ chung giữa người và robot.

## 12. Câu hỏi cho trưởng nhóm

| Mã | Câu hỏi |
|---|---|
| Q-H | Người khác có được dùng Colab của đội để chạy job GPU nhẹ không, hay mọi job GPU qua tay Hiếu? |
| Q-I | Cách hiểu "phần của Châu" ở mục 1 có đúng không? |
| Q-J | ROS 2 Jazzy trong Docker có hợp với máy của đội và với ROS mà DENSO dùng (nếu biết) không? |
| Q-K | Linh kiện lấy từ hai khay gắn trên đế robot hay từ khay của trạm? (hỏi BTC) |
| Q-L | Khối nhỏ ở cổ tay có phải camera không; camera đỉnh cột có độ sâu (RGB-D) không? (hỏi BTC) |
| Q-M | Agent QA/QC có cần tự nhìn hình không; nếu có thì thêm Qwen3.5-4B bên cạnh Nemotron |
| Q-N | Hình vẽ robot DENSO có được đưa vào repo công khai không? |

**Lựa chọn của người viết** (cần Hiếu xem khi duyệt): ba làn và người làm (mục 3); việc đổi chủ (mục 3.1); namespace `flywheel.*` (mục 4.1); khuôn package và quy tắc viết code (mục 4.2); cấu hình công cụ và luật import (mục 5); hai lớp sim, cấu trúc ROS 2, Jazzy (mục 6); thư mục cấu hình theo làn (mục 7); thứ tự chuyển (mục 8); model theo vai và vòng thử (mục 10); hệ quả của hình vẽ robot cho DA-15 và camera (mục 11).
