# Release synthetic S1 đầu tiên của task bê khay (DA-33)

Release `tray_s1_0d84cc87b1e5`: 102 episode G1 bê khay do planner kịch bản sinh trên decoupled WBC, đã qua QA tối thiểu và QA phát lại, ở định dạng Ψ₀ (LeRobot v2.1). Đây là dữ liệu robot của thí nghiệm DA-34 (nhánh A dùng đủ, nhánh C dùng tập con có hash). Story [DA-33](../../product/stories/DA-33-synthetic-s1-khay.md) nhiệm vụ 9, [plan](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md), quyết định D-22 đến D-26 ở [decisions.md](decisions.md).

## Nhận dạng

| Trường | Giá trị |
|---|---|
| `release_hash` | `0d84cc87b1e5e55db91cd13ca40bf07d24a560b83a4c8ebbd2111952dcdc18d6` |
| Vị trí | `rtx3060:~/denso-da33/fwdata/releases/tray_s1_0d84cc87b1e5/` (không commit) |
| Kích thước | 217 file, 901 495 734 byte; danh sách sha256 từng file ở `release_manifest.json` |
| Nội dung | 102 episode, 148 013 frame, 50 Hz, 1 câu lệnh task |
| Nguồn | `source_kind = synthetic`, `source_detail = planner_wbc`, `synthetic_tier = S1`, `action_quality = planned`, `embodiment_id = g1_sonic_dwbc@1`, `renderer = mujoco`, `data_class = public` (Q-33D), `split = train` |
| Planner | `da33-planner-4+cfg.815b822a` (logic 4, hash cấu hình `tray_planner.yaml`) |
| Hiển thị | SimReady `4763fbfaa4f8e97658e68b57d01b4c86659e08b5` |
| Mã | SIMPLE `6d10628`, nhánh `DA-33-tray-release`; lô sinh `fwdata/simple/tray/gen/s1-prod-1103` |

Kiểm lại release: `release.verify_manifest()` hoặc chạy contract test với `FLYWHEEL_TRAY_RELEASE` trỏ vào thư mục release.

## Lô sinh

Máy `rtx3060` (RTX 3060 12 GB, 64 CPU, 94 GB RAM), 22 worker, mỗi worker một env, 1 luồng BLAS (D-23). Mức ngẫu nhiên hóa 1 trên seed train 1000–1129 (Q-33A, Q-33B). Seed 0–143 đã dùng để chỉnh planner và thử lô t7 nên không dùng lại, để tỉ lệ thành công đo trên seed mới.

| Bước | Kết quả |
|---|---|
| Sinh, 3/11/2026 09:37:55–09:58:16 (20,3 phút) | 130 lượt, 102 thành công theo `check_success` (78,5 %), 102 qua QA tối thiểu |
| QA phát lại, 09:58:25–10:10:13 (11,8 phút) | 102/102 phát lại thành công; khay lệch tư thế cuối 0,0 mm (trung vị và tối đa), trùng từng bit như D-24 |
| Xuất và release | 102 episode; 42,5 s gồm script của SIMPLE và hash 0,9 GB |

Lỗi của 28 lượt hỏng, theo nhãn của scorer DA-32 và lý do ABORT của planner:

| Nhãn | Số lượt | Nghĩa |
|---|---|---|
| `L-ONE-HAND` | 10 | Tuột một tay khi mang (D-25: tay đỡ võng khoảng 10 cm) |
| `L-TRAY-TILT` | 7 | Khay nghiêng quá ngưỡng |
| `abort:timeout:RELEASE` | 4 | Hết giờ ở pha nhả |
| `L-PLACE-POSE` | 3 | Đặt ngoài vùng đích hoặc lệch hướng |
| `abort:timeout:REACH` | 2 | Không với tới tay cầm, khay xa |
| `abort:timeout:LIFT` | 1 | Hết giờ khi nhấc |
| `abort:timeout:ARRIVE_B` | 1 | Hết giờ khi đi tới bàn B |

Thời gian mỗi lượt (đồng hồ thực của worker): trung bình 160,5 s, trung vị 128,8 s, p95 411,9 s; tổng 5,80 worker-giờ cho 0,99 giờ mô phỏng. Episode thành công dài 25,8–36,0 s mô phỏng, trung bình 29,0 s. Chậm hơn số đo D-23 (109,5 s mỗi lượt) vì máy sát trần RAM: lúc 09:50:43 kernel giết 2 worker (shard 0 và 1) do hết bộ nhớ. Hai lượt đang chạy dở của chúng không kịp ghi dòng sổ, nên chạy lại cùng seed khi `generate.py` chạy tiếp hai shard đó; mọi seed 1000–1129 có đúng một dòng trong sổ. Máy treo vì hết RAM trong lúc chạy; từ 3/11/2026 mọi job trên `rtx3060` theo quy tắc RAM của Hiếu: tối đa 14 worker mỗi lô, mọi job của đội cộng lại ≤ 60 GB, bọc bằng `systemd-run --user --scope -p MemoryMax=…`.

## Layout action và state

`action` 36 chiều, không đệm; `states` 32 chiều, Ψ₀ đệm lên 36 lúc train (`pad_state_dim`). Tên từng chiều ở `meta/action_layout.json` (hợp đồng `ActionLayout`) và `meta/flywheel_export.json`. Contract test so từng cột với cột cùng tên của dữ liệu gốc.

| Chiều | Action | State |
|---|---|---|
| 0–2 | Ngón cái tay trái (`left_hand_thumb_0..2`) | Như action |
| 3–4 | Ngón giữa tay trái (`left_hand_middle_0..1`) | Như action |
| 5–6 | Ngón trỏ tay trái (`left_hand_index_0..1`) | Như action |
| 7–13 | Tay phải: cái 0–2, trỏ 0–1, giữa 0–1 | Như action |
| 14–20 | Cánh tay trái 7 khớp (vai 3, khuỷu, cổ tay 3) | Như action |
| 21–27 | Cánh tay phải 7 khớp | Như action |
| 28–30 | Hông roll, pitch, yaw | Hông roll, pitch, yaw đo được |
| 31 | `base_height_command` (0,74 m) | Lệnh chiều cao của bước trước |
| 32–33 | `navigate_cmd` vx, vy (m/s, \|·\| ≤ 0,5) | |
| 34 | `navigate_cmd` vyaw (rad/s, \|·\| ≤ 1,0); WBC đọc như cờ quay | |
| 35 | `navigate_cmd` target_yaw (rad, tích phân từ vyaw) | |

Thứ tự ngón tay trái (cái, giữa, trỏ) là thứ tự của script SIMPLE và baseline `psi0_decoupled_wbc` của SIMPLE; comment `ACTION_SLICES_36D` của Ψ₀ ghi 3:5 là ngón trỏ, khác dữ liệu (D-26). Thân trên của action (bàn tay, cánh tay, hông) và lệnh đi là lệnh planner đã gửi cho WBC, không phải đầu ra đã đồng bộ của WBC (D-24); lệch quy ước teleop của psi-data khoảng một bước 20 ms.

Bộ điều khiển: decoupled WBC của SIMPLE, chân chạy `GR00T-WholeBodyControl-Balance.onnx` khi ‖(vx, vy, vyaw)‖ < 0,1 và `GR00T-WholeBodyControl-Walk.onnx` khi đi; tay theo mục tiêu `TeleopRetargetingIK`. Đánh giá policy train trên release này bằng `eval-decoupled-wbc`, cùng đường phát lại của QA.

## Contract test

`packages/flywheel-simple/tests/tray/test_export_contract.py` chạy checklist design 27/10/2026 mục 6.4 trên release:

| Mục | Kiểm |
|---|---|
| 1 | `codebase_version` v2.1, `fps` 50, `robot_type` g1; `dtype` và `shape` mọi feature khớp gói hai bàn của psi-data; 36 và 32 chiều có tên |
| 2 | `episode_index` 0..101; `frame_index` từ 0 mỗi episode; `dataset_from_index`, `dataset_to_index` liên tục. Cột `index` toàn cục có khoảng hở giữa episode như psi-data (D-26) |
| 3 | `timestamp` = `frame_index / 50` trong nửa chu kỳ |
| 4 | Video giải mã được, 360 × 640, số frame bằng số dòng |
| 5 | Mọi episode có câu lệnh và khối `flywheel` |
| 6 | `stats_psi0.json` tính trên đúng release, không NaN; không có chiều action đệm |
| 7 | Đọc lại bằng loader Ψ₀: chờ công thức `eval-decoupled-wbc` của DA-19 |

## Giới hạn của synthetic S1

- Action là quỹ đạo planner (`action_quality = planned`): mượt theo min-jerk (D-20), không có do dự, sửa sai hay nhịp tay của người như teleop PICO. Synthetic S2 của DA-35 bù phần này.
- Chỉ mức ngẫu nhiên hóa 1; mức 2 để làm dịch chuyển khi đánh giá (design 28/10 mục 6.3).
- Cách cầm duy nhất là đỡ ngửa bàn tay (`up90`, D-25); khay rơi khoảng 3,5 cm khi tay rút ra lúc đặt.
- Chọn theo thành công: 28 lượt hỏng không vào release, nên dữ liệu không có cảnh tuột tay hay hồi phục.
- Ảnh render bằng MuJoCo với mesh SimReady, không phải Isaac.
- Seed train liền nhau 1000–1129; nhánh C của DA-34 phải lấy tập con theo hash, không lấy theo thứ tự seed.
