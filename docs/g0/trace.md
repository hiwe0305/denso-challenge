# Trace điều khiển từ rollout SIMPLE

_Ngày 5/11/2026. Story [DA-38](../product/stories/DA-38-hook-trace-simple.md) nhiệm vụ 7 (AC 1–6). Áp cho task hai bàn `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` và task khay `simple/G1WholebodyTrayTransferTeleop-v0`, agent `psi0_decoupled_wbc`, SIMPLE `b75c678`, `--sim-mode mujoco`. Số đo ở mục 5 là thực đo trên `rtx3060`, một lần chạy._

Hook ghi lại từng chu kỳ điều khiển của `eval-decoupled-wbc`: lệnh agent gửi, trạng thái đo trong MuJoCo, mốc thời gian, cùng tham số camera của episode. Từ các tệp này, `fw eval diag-system` (DA-13) chạy R3, R4, R5, R6. Hook không fork SIMPLE. Nó vá ba chỗ trong module eval lúc import: `gym.make`, lớp agent, và dòng thống kê cuối episode (mã ở `packages/flywheel-simple/src/flywheel_simple/trace/`).

## 1. Chạy

Cần có venv SIMPLE ([env-simple.md](env-simple.md)) và một server Ψ₀ đang chạy ([psi0-eval.md](psi0-eval.md)).

```bash
MUJOCO_GL=egl DEBUG=1 \
PYTHONPATH=fwdata/simple/SIMPLE/src:packages/flywheel-simple/src \
FW_TRACE_JOB_DIR=fwdata/traces/<job_id> FW_JOB_ID=<job_id> \
FW_RUN_PLAN_ID=g0-DA-38-20261105 \
FW_CAMERA_REFERENCE_SHA256=fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2 \
  fwdata/simple/.venv/bin/python -m flywheel_simple.trace.run \
  simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0 psi0_decoupled_wbc dr-level-0 \
  --host 127.0.0.1 --port <cổng server> --sim-mode mujoco --headless \
  --data-format lerobot --data-dir <thư mục điều kiện dr-level-0> \
  --num-episodes 2 --eval-dir fwdata/traces/<job_id>/simple-eval --no-save-video
```

- Tham số sau tên module là tham số của `eval-decoupled-wbc` của SIMPLE, giữ nguyên.
- `DEBUG=1` tắt thanh tiến trình của SIMPLE. Không đặt thì SIMPLE `b75c678`, khi chạy 1 worker, thoát mã 1 sau episode cuối vì in vào luồng đã đóng. Trace lúc đó đã ghi xong, nhưng job trông như hỏng.
- Server Ψ₀ chỉ nghe ở loopback. Chọn cổng trống bằng `ss -ltn`: trên `rtx3060`, cổng 22095 là tunnel tới server Colab của DA-26.
- Job spec lấy từ biến môi trường, không lấy từ tham số. Lý do: với `--num-workers N > 1`, SIMPLE tạo worker bằng `spawn`. Worker kế thừa biến môi trường và import lại module dưới tên `__mp_main__`, nhưng không chạy `main()`. Vì vậy hook được cài ở cấp module.
- Thiếu `FW_TRACE_JOB_DIR`, `FW_JOB_ID` hay `FW_RUN_PLAN_ID` thì lệnh dừng và báo tên biến thiếu.
- Mã kế hoạch `g0-…` phải có dạng `g0-<story>-<yyyymmdd>`, ví dụ `g0-DA-38-20261105`.
- `FW_CAMERA_REFERENCE_SHA256` là hash của bản tham chiếu camera đã ghim cho task ([camera-reference-two-table.yaml](camera-reference-two-table.yaml)). Không đặt thì hook không ghi `camera_params.jsonl`, và R5 ra CHƯA RÕ. Task khay chưa có bản tham chiếu ghim, nên chạy không có biến này.
- Task khay dùng cùng lệnh, chỉ đổi env id và thư mục điều kiện. Entry module tự đăng ký env khay và trình đọc điều kiện khay, như `flywheel_simple.tray.run`.
- Trên `rtx3060` có rule RAM của đội. Bọc client trong `systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=0`. Server Ψ₀ chạy trong docker, nên giới hạn RAM bằng `mem_limit` của compose, không bằng `systemd-run`. Chạy server bằng `docker compose run -d`; khi chạy gắn với phiên ssh, container bị dừng lúc phiên đóng. Trước khi chạy, xem ledger và lịch của đội: máy có thể đang được giữ cho một eval khác.

## 2. Tệp ra

Mỗi episode có một thư mục `<trace_id>/` trong thư mục job. `trace_id = <job_id>-<12 ký tự hex ngẫu nhiên>`, tạo lúc env reset. Agent giữ id này ở thuộc tính `fw_trace_id`, để client RTC ghi cùng id.

| Tệp | Nội dung | Ai đọc |
|---|---|---|
| `<job_dir>/<trace_id>/steps.jsonl` | Một `TraceStep` (`flywheel.contracts.trace`) mỗi dòng, mỗi dòng một chu kỳ | DA-13 (R3, R4), scorer |
| `<job_dir>/<trace_id>/camera_params.jsonl` | Một `CameraParams` mỗi camera mà policy dùng; chỉ có khi đặt hash tham chiếu | DA-13 (R5) |
| `<job_dir>/<trace_id>/rollout_result.json` | Một `RolloutResult` (`flywheel.contracts.v0`) | DA-13 (R6), scorer |
| `<job_dir>/rtc.jsonl` | Bản ghi `RTCInferenceRecord` của cả job, nối với trace qua `trace_id`. Hook không ghi tệp này; client RTC ghi | DA-13 (R1, R2) |

`rollout_result.json` gồm:
- `trace_ref.uri`: thư mục `<trace_id>/`;
- `trace_ref.sha256`: sha256 của `steps.jsonl`;
- `sim_success`: cờ `check_success` của SIMPLE;
- `infra_status`;
- `camera_params_hash`: hash tham chiếu đã ghim;
- `adapter_info.version`: `simple@<commit>` của bản SIMPLE đã import.

## 3. Ý nghĩa trường

| Trường | Lấy từ đâu |
|---|---|
| `step` | Số thứ tự chu kỳ trong episode, từ 0 |
| `t_state` | `data.time` của MuJoCo lúc đọc trạng thái, s. Chu kỳ 50 Hz nên hai dòng liền nhau cách 0,02 s |
| `t_image` | Thời gian mô phỏng của khung ảnh đưa vào policy ở chu kỳ đó. Chu kỳ không gửi ảnh thì `null` |
| `cmd_upper` | `action[0:28]` của dòng action 36 chiều mà agent dùng ở chu kỳ đó (trước WBC) |
| `meas_upper` | Góc 28 khớp thân trên đo trong MuJoCo, cùng thứ tự với `UPPER_BODY` của hợp đồng |
| `cmd_lower` | `action[28:34] + action[35]` |
| `meas_lower` | Góc hông đo (`joint_qpos[[13, 14, 12]]`: roll, pitch, yaw), chiều cao gốc, vận tốc gốc trong hệ yaw của thân, yaw của gốc. Thứ tự theo `LOWER_BODY` |
| `dropped_frames` | Luôn 0 ở sim (mục 4) |
| `CameraParams` | `fx`, `fy`, `cx`, `cy` ở độ phân giải render, lấy từ `CameraCfg` của SIMPLE. `pose` so với body gắn camera, quaternion (w, x, y, z), đọc từ model MuJoCo đang chạy. `reference_sha256` là hash đã ghim, không phải hash của camera trong episode |
| `infra_status` | `ok` khi SIMPLE báo kết quả episode. Episode bị ngắt trước đó ghi `simulator_error` **[Đề xuất]** |

Giá trị không hữu hạn (NaN, ±inf) ghi theo tên của hợp đồng (`"NaN"`, `"Infinity"`), không ghi số trần.

## 4. Giới hạn ở sim

- Ảnh và trạng thái dùng chung một đồng hồ mô phỏng. Vì vậy, ở chu kỳ có khung, `t_image` bằng `t_state`, và `dropped_frames` luôn bằng 0. Trên sim, R4 không thấy độ trễ thật; nó dùng để nghiệm thu bộ phát hiện bằng ca cấy trễ (issue #31).
- Agent của SIMPLE chỉ gửi ảnh tới server khi hàng đợi action rỗng, tức mỗi chunk một lần. Phần lớn dòng vì vậy có `t_image = null`.
- `cmd_*` là action của Ψ₀, không phải `target_q` sau WBC. Khoảng cách giữa `cmd_upper` và `meas_upper` gồm cả sai số bám của bộ điều khiển.
- Client RTC của DA-19 không nằm trên đường eval này, nên job thường không có `rtc.jsonl`, và R1, R2 bị bỏ qua.
- Trace chỉ có tín hiệu điều khiển. Tín hiệu task mà scorer hai bàn cần (khoảng cách tay–vật, tiếp xúc, chiều cao vật, vùng đích, va chạm, thăng bằng thân; xem `configs/eval/scorer/two-table.yaml`) không có trong `TraceStep`. Hook không ghi các tín hiệu này. `fw eval score` đọc một artifact khác (trace tín hiệu task, dòng V7 của 03 mục 4.2), nên không nhận `steps.jsonl` làm đầu vào. `TaskDefinition` hai bàn và tín hiệu của nó thuộc story 3.4 **[Đã chốt 5/11/2026, Hiếu]**; bảng tín hiệu thiếu ở story DA-38, ghi chép nhiệm vụ 5.
- Chạy nhiều job SIMPLE cùng lúc trên một máy có thể dùng chung domain 0 của CycloneDDS (story DA-38, ghi chép 3.1/3.2).
- Thời gian một episode khay chưa ổn định. Test `sim` ngày 3/11 đo 605 s, phần lớn do SIMPLE giải mã mọi khung video của episode điều kiện. Lượt chạy thật ngày 6/11 (mục 5) chỉ mất 181 s mỗi episode. Chưa đo nguyên nhân của chênh lệch.
- Hook ghi tệp lúc episode kết thúc. Job bị giết giữa episode thì episode đó không để lại thư mục nào.
- Isaac (`mujoco_isaac`) và server Ψ₀ không vừa chung GPU 12 GB của `rtx3060`. Trước khi chạy server Ψ₀ ở đó, kiểm `nvidia-smi` và `docker ps` xem có eval Isaac nào đang chạy không.

## 5. Lượt chạy thật trên `rtx3060` (5/11/2026)

Số đo của một lần chạy; chi tiết ở story DA-38, ghi chép nhiệm vụ 5 và 6.

| | Task hai bàn | Task khay |
|---|---|---|
| Job | `job_da38_two_table_l0_20261105` (5/11) | `job_da38_tray_20261106` (6/11) |
| Điều kiện | `e78fb93` mức 0, episode 0–1 | Release `tray_s1_0d84cc87b1e5` của DA-33, episode 0–1 |
| Server | Ψ₀ checkpoint hai bàn `ckpt_40000`, image ghim, 7,25 GB VRAM | Cùng server; chưa có checkpoint khay, nên policy không làm task khay |
| Chu kỳ mỗi episode | 1200 (24 s mô phỏng), `t_state` cách nhau 0,02 s | 4500 (90 s mô phỏng), cách nhau 0,02 s |
| Khung ảnh đưa vào policy | 50 mỗi episode (24 chu kỳ một khung) | 188 mỗi episode |
| Kênh có phương sai khác 0 | 28/28 thân trên, 7/7 thân dưới | 28/28, 7/7 |
| `sim_success` | False, False; khớp `eval_stats.txt` của SIMPLE | False, False; khớp |
| `camera_params.jsonl` | Có, 2 camera, hash đã ghim | Không (chưa ghim bản tham chiếu khay) |
| Thời gian client | 147 s cho 2 episode, 1 worker | 208 s cho 2 episode, 2 worker `spawn` |
| `fw eval score` | `steps.jsonl`: không đọc được (khác artifact). Tệp V7 tạm chỉ có `t`: đọc được, cả 6 bước "chưa rõ" | Không chạy (chưa có config scorer khay) |
| `fw eval diag-system` | Đọc được, mã 0. Nhãn LỖI CONTROLLER ở ngưỡng giả định: R3 thân trên 2,57 và 2,65, thân dưới 1,75 và 0,82. R1, R2 bỏ qua | Đọc được, mã 0. Nhãn LỖI CONTROLLER ở ngưỡng giả định: R3 thân trên 2,53 và 2,60, thân dưới 2,93 và 3,06. R1, R2, R5 bỏ qua |

Cả 4/4 episode bị gắn LỖI CONTROLLER do R3, ở ngưỡng còn là giả định. Chưa kiểm nguyên nhân: có thể là lỗi bám thật; có thể là policy sai task (lượt khay dùng checkpoint hai bàn); có thể là `target_yaw` và yaw đo khác hệ quy chiếu. Ngón tay lệch lệnh khi đang cầm vật cũng là chuyện bình thường. Vì vậy kết quả `diag-system` trên sim ở đây **chưa được hiệu chỉnh và chưa dùng để kết luận được**. Các trace này là đầu vào để DA-13 và DA-37 hiệu chỉnh ngưỡng.
