# DA-33 · Synthetic S1 cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp (PO duyệt hướng 28/10/2026); nhiệm vụ con chi tiết viết khi DA-32 xong nhiệm vụ con 4 |
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

- [ ] 1. Planner kịch bản hai cổ tay qua `TeleopRetargetingIK` (AC 1)
- [ ] 2. Chuỗi 7 pha và một episode thành công (AC 2, 3)
- [ ] 3. Sinh hàng loạt, QA, release (AC 4)
- [ ] 4. Đo, sổ chi phí, ghi `action_layout` (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/`, `packages/flywheel-simple/tests/tray/`
- `packages/flywheel-simple/src/flywheel_simple/wbc/`, `packages/flywheel-simple/tests/wbc/`
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

## Ghi chép khi làm
