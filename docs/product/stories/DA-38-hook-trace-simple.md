# DA-38 · Hook ghi `TraceStep` và `CameraParams` từ MuJoCo trong rollout SIMPLE

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 3/11/2026) |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Phần hook của story 3.1a (04 mục S2: "`SimpleSimulator`, hook ghi tín hiệu, `t_state`, `t_image`, tham số camera"); issue #31; 07 mục 2.4 (bản 1.1) |
| Nhãn | [Adapter] · `epic:3` · `gate:G1` · `area:sim` |
| Sprint | S2 · hạn merge **8/11/2026** (07 mục 2.4) |
| Ước lượng | 14 giờ (khoảng 10–18, ước lượng) |
| Phụ thuộc | Hợp đồng `TraceStep`, `CameraParams` và file mẫu (DA-25, PR #48, Long, 6/11). Môi trường SIMPLE của S1-02; task khay của DA-32; server Ψ₀ của S1-03. Không chặn ai ngoài DA-13 (R3–R5 trên trace thật) và DA-37 (cờ `check_success` thật) |

## Story

Là người làm làn Đánh giá, tôi muốn mỗi rollout SIMPLE của đội ghi một trace theo chu kỳ điều khiển (lệnh gửi, trạng thái đo, mốc thời gian) và tham số camera của lượt chạy, đọc thẳng từ MuJoCo, để DA-13 chạy được R3, R4, R5 và DA-37 hiệu chỉnh scorer trên dữ liệu thật thay vì file mẫu.

## Tiêu chí chấp nhận

1. Mỗi chu kỳ điều khiển của `eval-decoupled-wbc` (agent `psi0_decoupled_wbc`) ghi một `TraceStep` hợp lệ theo hợp đồng của DA-25, cho cả task hai bàn `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` và task khay `simple/G1WholebodyTrayTransferTeleop-v0`. Không fork SIMPLE.
2. Trường theo quyết định ở issue #31:
   - `t_state` là `data.time` của MuJoCo lúc đọc trạng thái.
   - `t_image` là thời gian mô phỏng của khung được đưa vào policy ở chu kỳ đó; chu kỳ không có khung mới thì `null`.
   - `cmd_upper = action[0:28]`; `meas_upper` là góc khớp đo, cùng thứ tự.
   - `cmd_lower = action[28:34] + action[35]`; `meas_lower` cùng thứ tự: góc hông đo, chiều cao gốc, vận tốc gốc trong hệ thân, yaw của gốc.
3. Mỗi camera mà policy dùng có một `CameraParams`, lấy từ `CameraCfg` của SIMPLE và model MuJoCo đang chạy: `fx`, `fy`, `cx`, `cy` ở đúng độ phân giải render, `pose` so với body gắn camera, quaternion (w, x, y, z). `reference_sha256` trỏ tới bản tham chiếu của commit SIMPLE đã ghim.
4. Mỗi episode ghi cờ `check_success` của SIMPLE (`sim_success`) cạnh trace.
5. Phần tính toán (dựng `TraceStep`, `CameraParams` từ mảng số) không import `simple` hay `mujoco`, và có test CPU với bộ giả chạy trong CI. Phần cài hook import `simple` có test gắn marker `sim`.
6. Trên `rtx3060`, mỗi task có một lượt chạy thật sinh ra tệp trace. Giá trị trong tệp đến từ sim, không hard-code (kiểm bằng phương sai khác 0 và khớp với `env._success`). Mỗi lượt chạy có dòng `LedgerEntry` trong `docs/g0/ledger/DA-38.csv`.

## Nhiệm vụ

- [x] 1. File story và phạm vi file
- [ ] 2. Dựng `TraceStep` và `CameraParams` từ mảng số, test CPU với bộ giả (AC 2, 3, 5)
- [ ] 3. Bộ ghi trace theo quy ước tệp của hợp đồng, kèm cờ `sim_success` (AC 1, 4)
- [ ] 4. Cài hook vào `eval-decoupled-wbc` (bọc env và agent), test `sim` (AC 1, 5)
- [ ] 5. Lượt chạy thật task hai bàn trên `rtx3060`, ghi ledger (AC 6)
- [ ] 6. Lượt chạy thật task khay trên `rtx3060`, ghi ledger (AC 6)
- [ ] 7. Tài liệu `docs/g0/trace.md`: cách chạy, ý nghĩa trường, giới hạn ở sim (AC 1–6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/trace/`, `packages/flywheel-simple/tests/trace/`
- `packages/flywheel-simple/pyproject.toml` (thêm phụ thuộc `flywheel-contracts`, `numpy`, `pydantic`), `uv.lock` (PO cho phép 3/11/2026)
- `scripts/g0/trace/`
- `docs/g0/trace.md`, `docs/g0/ledger/DA-38.csv`

Ngoài phạm vi, làm PR docs riêng: dòng DA-38 trong 07 mục 2.2 và 2.4; ánh xạ story 3.1a sang DA-38 trong 04.

## Ghi chú cho người làm

- Trên master không có lớp `SimpleSim`. Vòng episode thật là `simple.cli.eval_decoupled_wbc._run_eval_worker` (SIMPLE @ `6d10628`):
  - `gym.make(env_id)` cho ra `SonicLocoManipEnv`, hoặc `TrayTransferEnv` của DA-32 (lớp con của nó).
  - Agent là `simple.baselines.psi0_decoupled_wbc`.
  - Mỗi lần `env.step` là một chu kỳ 50 Hz, và `_get_obs` render camera ngay sau phần vật lý.
- Hook được cài như `flywheel_simple.tray.run` đã thay module `time`: vá `gym.make` và class agent trong module eval, không fork SIMPLE.
- Client RTC của DA-19 không nằm trên đường này. Agent của SIMPLE chỉ gửi ảnh tới server khi hàng đợi action rỗng (mỗi chunk một lần).
- Lệnh `cmd_*` lấy từ dòng action 36 chiều của Ψ₀ mà agent dùng ở chu kỳ đó, không lấy từ `target_q` sau WBC.
- Đo hông: `joint_qpos[[13, 14, 12]]` (roll, pitch, yaw), như agent dựng state.
- Đo vận tốc: `qvel[0:3]` của freejoint là vận tốc trong hệ thế giới, cần xoay sang hệ yaw của thân.
- Ở sim, ảnh và trạng thái chung một đồng hồ, nên `t_image` bằng `t_state` ở các chu kỳ có khung và `dropped_frames` bằng 0. R4 trên sim dùng để nghiệm thu bộ phát hiện bằng ca cấy trễ (issue #31).
- Góp ý hợp đồng (quy ước tệp, `run_plan_id`, mật độ `t_image`, `dropped_frames`, `check_success`) đã đăng ở review của PR #48. Code theo bản hợp đồng được merge.
- Chạy trên `rtx3060` theo rule RAM của đội: tối đa 60 GB và 14 worker cho cả đội; mỗi job bọc trong `systemd-run --user --scope -p MemoryMax=…`. Dùng thư mục `~/denso-da38`.

## Kiểm thử

- `uv run pytest packages/flywheel-simple/tests/trace -m "not sim"` trong workspace.
- `pytest packages/flywheel-simple/tests/trace -m sim` trong môi trường SIMPLE của S1-02 (`fwdata/simple/.venv`).

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Tạo story cho phần hook của story 3.1a theo issue #31 và 07 mục 2.4 (bản 1.1) | PO (Hiếu) |

## Ghi chép khi làm
