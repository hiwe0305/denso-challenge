# DA-33 · Synthetic S1 cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm. Nhiệm vụ 1–4 đã merge (PR #28, 2/11/2026); nhiệm vụ 5, 6, 7 đã merge (PR #39, 3/11/2026); nhiệm vụ 8, 9 xong trên nhánh `DA-33-tray-release`. PO duyệt kế hoạch nhiệm vụ 5–9 và mặc định Q-33A, Q-33B, Q-33D (3/11/2026) |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 4, 5, 7 (M2) |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S2 tuần 1; M2 8/11/2026 |
| Ước lượng | 20 giờ (khoảng 15–30, ước lượng) |
| Phụ thuộc | DA-32 (task, vị từ, bộ điều khiển đứng và đi). Không cần cuRobo; chạy hàng loạt trên máy 3060 hoặc server thuê cho nhanh |

## Story

Là trưởng nhóm, tôi muốn sinh tự động episode G1 bê khay bằng hai tay bằng planner kịch bản trên decoupled WBC, để có ít nhất 80 demo robot đạt QA cho thí nghiệm DA-34.

## Tiêu chí chấp nhận

1. Planner kịch bản sinh quỹ đạo tư thế hai cổ tay theo hình học tay cầm (tiếp cận, cầm, nhấc, mang, hạ, nhả) và đưa vào `TeleopRetargetingIK` của decoupled_wbc thay cho luồng PICO; đóng mở bàn tay Dex3; lệnh đi qua `navigate_cmd`. Chạy từ package của đội, không fork SIMPLE.
2. Chuỗi pha của planner theo 7 bước scorer của DA-32; mỗi pha có điều kiện chuyển đo được.
3. Một episode sinh tự động mang khay thành công theo `check_success()` của DA-32 (mục tiêu 6/11).
4. Sinh ≥ 100 episode bằng bộ ghi LeRobot của SIMPLE, ≥ 80 đạt QA; release có hash; mỗi episode ghi `source_kind = synthetic`, `synthetic_tier = S1`, `action_quality = planned`, phiên bản planner.
5. Đo thời gian sinh mỗi episode, tỉ lệ đạt, GPU-giờ; ghi sổ chi phí.
6. Ghi `action_layout` (cổ tay, bàn tay, `navigate_cmd`) và bộ điều khiển (decoupled WBC) của dữ liệu, khớp với `eval-decoupled-wbc` mà DA-34 dùng.

## Nhiệm vụ

Kế hoạch chi tiết: [docs/superpowers/plans/2026-10-31-da33-tray-synthetic.md](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md).

- [x] 1. Đo đi và quay của G1 trong cảnh khay; bộ tích phân `navigate_cmd`; dọn file cảnh MJCF khi đóng env (AC 1)
- [x] 2. Mục tiêu hai cổ tay qua `TeleopRetargetingIK`, đóng mở bàn tay Dex3 (AC 1)
- [x] 3. Máy pha của planner theo 7 bước scorer, có điều kiện chuyển và timeout (AC 2)
- [x] 4. Một episode planner mang khay thành công theo `check_success()` (AC 3, mục tiêu 6/11)
- [x] 5. Bộ ghi LeRobot cùng định dạng teleop của SIMPLE, kèm khối `flywheel` trong `environment_config` (AC 4)
- [x] 6. Sinh hàng loạt, sổ lượt sinh chỉ ghi thêm, QA tối thiểu (AC 4, 5)
- [x] 7. QA bằng phát lại `replay-decoupled-wbc` ở `mujoco` (AC 4)
- [x] 8. Xuất sang định dạng Ψ₀ (action 36, state 32, LeRobot v2.1), contract test (AC 4, 6)
- [x] 9. Chạy lô sản xuất, release có hash, `action_layout`, sổ chi phí (AC 4, 5, 6; M2 8/11/2026)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/`, `packages/flywheel-simple/tests/tray/`
- `packages/flywheel-simple/src/flywheel_simple/wbc/`, `packages/flywheel-simple/tests/wbc/`
- `configs/sim/tray_planner.yaml`
- `configs/sim/tray.yaml` (từ 31/10/2026, chỉ chiều cao khay và khoảng cách tới mép bàn, theo D-16, Hiếu duyệt)
- `scripts/g0/tray/`
- `docs/g0/tray/`, `docs/g0/ledger/DA-33.csv`

## Ghi chú cho người làm

- Luồng PICO của SIMPLE (`agents/pico_decoupled_agent.py`) là mẫu: PicoStreamer → `TeleopPolicy` (`TeleopRetargetingIK`, IK bàn tay `instantiate_g1_hand_ik_solver`) → `G1DecoupledWholeBodyPolicy`. Planner thay PicoStreamer bằng quỹ đạo cổ tay tự sinh. Tay cầm khay có tư thế cầm cố định theo hình học nên tính trực tiếp, không cần tìm grasp.
- Khi mang, giữ cố định tư thế tương đối hai cổ tay trong khung thân để khay không nghiêng; policy Balance và Walk train không có tải ở tay (rủi ro ở design mục 9).
- Không cần cuRobo. Laptop RTX 3050 4 GB chạy được để thử; sinh hàng loạt trên máy 3060 hoặc server thuê.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Tạo story nháp theo design 28/10/2026 | PO (Hiếu) |
| 28/10/2026 | Đổi sang planner kịch bản trên decoupled WBC, bỏ MP agent, `datagen` và cuRobo | PO (Hiếu) |
| 31/10/2026 | Thêm `configs/sim/tray.yaml` vào Phạm vi file: khay cao 0,09 m, cách mép 0,20 m (D-16) | PO (Hiếu) |
| 31/10/2026 | Viết 9 nhiệm vụ con theo plan 31/10/2026; thêm `configs/sim/tray_planner.yaml` vào Phạm vi file; đường dữ liệu ghi bằng bộ ghi teleop của SIMPLE, QA bằng `replay-decoupled-wbc`, xuất bằng `postprocess_psi0_sonic.py` | Claude, chờ PO (Hiếu) duyệt |
| 3/11/2026 | PO duyệt kế hoạch nhiệm vụ 5–9: Q-33A mức 1 trên seed train, Q-33B 130 lượt, Q-33D `public`; bộ ghi dùng chung tên trường với DA-35 | PO (Hiếu) |
| 3/11/2026 | PO duyệt D-24: dữ liệu ghi lệnh đã gửi cho WBC, episode bắt đầu như eval của SIMPLE, QA bằng `replay-decoupled-wbc` ([decisions.md](../../g0/tray/decisions.md)) | PO (Hiếu) |

## Ghi chép khi làm

- 3/11/2026, nhiệm vụ 8: `tray/export.py` chọn episode qua cả QA tối thiểu và QA phát lại, dựng lại thành dataset bằng symlink rồi chạy nguyên `postprocess_psi0_sonic.py` của SIMPLE; thêm `meta/action_layout.json` và `meta/flywheel_export.json` (D-26). Cột 3:5 là khớp middle tay trái, 5:7 là index, ngược comment `ACTION_SLICES_36D` của Ψ₀; `index` toàn cục có khoảng hở như psi-data. Contract test 10/10 trên `rtx3060` (lô t7), features khớp psi-data, từng cột khớp cột cùng tên của dữ liệu gốc.
- 3/11/2026, nhiệm vụ 9: lô `s1-prod-1103` trên `rtx3060` (mức 1, seed train 1000–1129, 22 worker, chạy trước quy tắc RAM 14 worker của Hiếu; 2 worker bị OOM kill lúc 09:50 rồi chạy tiếp, không mất episode): 130 lượt, 102 thành công, 102 qua QA tối thiểu, 102/102 qua QA phát lại. Release `tray_s1_0d84cc87b1e5` (102 episode, 148 013 frame, 0,90 GB), contract test 11/11 trên release ([synthetic-s1.md](../../g0/tray/synthetic-s1.md)). Release dựng đầu tiên ghi sai tên chiều trong `action_layout` nên đã bị thay (D-26).
